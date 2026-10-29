"""Rule-based adaptive learning routes with prerequisite checks and SQLite history."""
import json,tempfile
from pathlib import Path
from common import ROOT,connect,read_json,now,require_text,save_json

class Study:
 def __init__(self,db_path=None):
    self.db_path=db_path;self.catalog=read_json(ROOT/'data/catalog.json');self.skills={s['id']:s for s in self.catalog};self.questions=read_json(ROOT/'data/questions.json');self.goals=read_json(ROOT/'data/goals.json')
    self.order=self.topological(list(self.skills))
    with connect(db_path) as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS learners(id INTEGER PRIMARY KEY,name TEXT NOT NULL,goal TEXT NOT NULL,created_at TEXT NOT NULL,diagnosed INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS mastery(learner_id INTEGER NOT NULL REFERENCES learners(id),skill TEXT NOT NULL,mastered INTEGER NOT NULL,correct INTEGER NOT NULL,total INTEGER NOT NULL,source TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(learner_id,skill));
          CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,learner_id INTEGER NOT NULL REFERENCES learners(id),phase TEXT NOT NULL,skill TEXT,answers TEXT NOT NULL,result TEXT NOT NULL,created_at TEXT NOT NULL);
        """)
 def topological(self,targets):
    order=[];visiting=set();visited=set()
    def visit(skill):
        if skill in visiting:raise ValueError('Цикл в prerequisites')
        if skill not in self.skills:raise ValueError('Неизвестный prerequisite')
        if skill in visited:return
        visiting.add(skill)
        for parent in self.skills[skill]['prerequisites']:visit(parent)
        visiting.remove(skill);visited.add(skill);order.append(skill)
    for skill in targets:visit(skill)
    return order
 def create(self,name,goal):
    name=require_text(name,'name',80)
    if goal not in self.goals:raise ValueError('Неизвестная цель')
    with connect(self.db_path) as db:lid=db.execute('INSERT INTO learners(name,goal,created_at) VALUES (?,?,?)',(name,goal,now())).lastrowid
    return self.profile(lid)
 def learners(self):
    with connect(self.db_path) as db:return [dict(r) for r in db.execute('SELECT * FROM learners ORDER BY id DESC')]
 def profile(self,lid):
    with connect(self.db_path) as db:
        learner=db.execute('SELECT * FROM learners WHERE id=?',(lid,)).fetchone()
        if not learner:raise LookupError()
        state={r['skill']:dict(r) for r in db.execute('SELECT * FROM mastery WHERE learner_id=?',(lid,))}
        attempts=[dict(r) for r in db.execute('SELECT id,phase,skill,result,created_at FROM attempts WHERE learner_id=? ORDER BY id',(lid,))]
    learner=dict(learner);required=self.topological(self.goals[learner['goal']]['skills']);route=[]
    for skill in required:
        s=self.skills[skill];mastered=state.get(skill,{}).get('mastered',0)==1
        missing=[p for p in s['prerequisites'] if not state.get(p,{}).get('mastered')]
        status='completed' if mastered else ('locked' if missing else 'available')
        reason='Подтверждено тестом' if mastered else ('Сначала: '+', '.join(self.skills[p]['title'] for p in missing) if missing else ('Требуется повторное подтверждение после проверки основ' if state.get(skill,{}).get('correct',0)>=2 else 'Тема нужна для цели; результат теста ниже порога 2/3') if learner['diagnosed'] else 'Сначала пройдите диагностику')
        if not learner['diagnosed']:status='diagnostic_required'
        route.append(dict(s,status=status,reason=reason,score=state.get(skill)))
    completed=sum(s['status']=='completed' for s in route)
    return dict(learner=learner,route=route,completed=completed,total=len(route),
      remaining_minutes=sum(s['minutes'] for s in route if s['status']!='completed'),attempts=[dict(a,result=json.loads(a['result'])) for a in attempts])
 def quiz(self,lid,phase='diagnostic',skill=None):
    p=self.profile(lid)
    if phase not in ('diagnostic','control'):raise ValueError('Неизвестный phase')
    if phase=='diagnostic' and p['learner']['diagnosed']:raise ValueError('Диагностика уже пройдена; используйте контрольные тесты')
    if phase=='control':
        item=next((r for r in p['route'] if r['id']==skill),None)
        if not p['learner']['diagnosed'] or not item or item['status']=='locked':raise ValueError('Тема недоступна: пройдите диагностику и prerequisites')
    qs=[q for q in self.questions if q['phase']==phase and (phase=='diagnostic' or q['skill']==skill)]
    return [{k:v for k,v in q.items() if k not in ('answer','explanation')} for q in qs]
 def submit(self,lid,phase,skill,answers):
    public=self.quiz(lid,phase,skill);ids={q['id'] for q in public}
    if not isinstance(answers,dict) or set(answers)!=ids:raise ValueError('Нужен один ответ на каждый вопрос, без лишних ID')
    if any(value not in ('a','b','c') for value in answers.values()):raise ValueError('Ответы: a, b или c')
    keys=[q for q in self.questions if q['id'] in ids];by_skill={}
    details=[]
    for q in keys:
        ok=answers[q['id']]==q['answer'];by_skill.setdefault(q['skill'],[]).append(ok)
        details.append({'id':q['id'],'correct':ok,'answer':q['answer'],'explanation':q['explanation']})
    with connect(self.db_path) as db:
        state={r['skill']:bool(r['mastered']) for r in db.execute('SELECT * FROM mastery WHERE learner_id=?',(lid,))}
        summary=[]
        for sid in self.order:
            if sid not in by_skill:continue
            n=sum(by_skill[sid]);total=len(by_skill[sid]);raw_pass=n/total>=2/3
            prereqs_ok=all(state.get(p,False) for p in self.skills[sid]['prerequisites'])
            mastered=raw_pass and prereqs_ok;state[sid]=mastered
            db.execute('INSERT OR REPLACE INTO mastery VALUES (?,?,?,?,?,?,?)',(lid,sid,int(mastered),n,total,phase,now()))
            summary.append({'skill':sid,'correct':n,'total':total,'raw_pass':raw_pass,'mastered':mastered,'prerequisites_ok':prereqs_ok})
        invalidated=[]
        for sid in self.order:
            if state.get(sid) and not all(state.get(p,False) for p in self.skills[sid]['prerequisites']):
                state[sid]=False;invalidated.append(sid)
                db.execute('UPDATE mastery SET mastered=0,source=?,updated_at=? WHERE learner_id=? AND skill=?',('prerequisite_revoked',now(),lid,sid))
        if phase=='diagnostic':db.execute('UPDATE learners SET diagnosed=1 WHERE id=?',(lid,))
        result={'summary':summary,'details':details,'invalidated':invalidated}
        db.execute('INSERT INTO attempts(learner_id,phase,skill,answers,result,created_at) VALUES (?,?,?,?,?,?)',(lid,phase,skill,json.dumps(answers),json.dumps(result,ensure_ascii=False),now()))
    return dict(result=result,profile=self.profile(lid))

def demo(out):
    with tempfile.TemporaryDirectory() as tmp:
        study=Study(Path(tmp)/'demo.db');lid=study.create('Демо-слушатель','ml_engineer')['learner']['id']
        # Scripted persona: Python and SQL known, other skills initially weak.
        diag={q['id']:q['answer'] if q['skill'] in ('python','sql') else next(a for a in 'abc' if a!=q['answer']) for q in study.questions if q['phase']=='diagnostic'}
        before=study.submit(lid,'diagnostic',None,diag)['profile']
        control={q['id']:q['answer'] for q in study.questions if q['phase']=='control' and q['skill']=='pandas'}
        after=study.submit(lid,'control','pandas',control)['profile']
        report={'source':'Автоматический сценарий с синтетическим слушателем; добровольцы не участвовали.',
          'before':before,'after':after,'rule':'Порог 2 из 3; prerequisites обязательны; маршрут обновляется после каждого теста.'}
        save_json(out/'route_demo.json',report)
        lines=['# StudyRoute — сценарий проверки','',report['source'],'',report['rule'],'',f"До контрольной: {before['completed']}/{before['total']} тем. После: {after['completed']}/{after['total']}.",
          '', '| Тема | До | После |','|---|---|---|']
        lines += [f"| {a['title']} | {a['status']} | {b['status']} |" for a,b in zip(before['route'],after['route'])]
        (out/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
        return report
