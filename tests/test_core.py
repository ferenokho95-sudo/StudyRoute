import unittest,tempfile
from pathlib import Path
from core import Study,demo
class Tests(unittest.TestCase):
 def setUp(self):
    self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.s=Study(Path(self.tmp.name)/'db');self.id=self.s.create('Тест','ml_engineer')['learner']['id']
 def answers(self,phase,correct_skills=(),skill=None):return {q['id']:q['answer'] if q['skill'] in correct_skills else next(c for c in 'abc' if c!=q['answer']) for q in self.s.questions if q['phase']==phase and (skill is None or q['skill']==skill)}
 def test_quiz_hides_answer(self):
    q=self.s.quiz(self.id);self.assertEqual(len(q),18);self.assertTrue(all('answer' not in x and 'explanation' not in x for x in q))
 def test_missing_answers_no_partial_write(self):
    with self.assertRaises(ValueError):self.s.submit(self.id,'diagnostic',None,{})
    self.assertFalse(self.s.profile(self.id)['learner']['diagnosed'])
 def test_prerequisite_blocks_control(self):
    self.s.submit(self.id,'diagnostic',None,self.answers('diagnostic'))
    with self.assertRaises(ValueError):self.s.quiz(self.id,'control','ml')
 def test_raw_pass_does_not_skip_prerequisite(self):
    r=self.s.submit(self.id,'diagnostic',None,self.answers('diagnostic',('ml',)))
    ml=next(s for s in r['result']['summary'] if s['skill']=='ml');self.assertTrue(ml['raw_pass']);self.assertFalse(ml['mastered'])
 def test_control_unlocks_next(self):
    self.s.submit(self.id,'diagnostic',None,self.answers('diagnostic',('python','stats')))
    r=self.s.submit(self.id,'control','pandas',self.answers('control',('pandas',),'pandas'))
    self.assertEqual(next(s for s in r['profile']['route'] if s['id']=='ml')['status'],'available')
 def test_lower_prerequisite_score_relocks_dependents(self):
    self.s.submit(self.id,'diagnostic',None,self.answers('diagnostic',tuple(self.s.skills)))
    self.s.submit(self.id,'control','python',self.answers('control',(),'python'))
    p=self.s.profile(self.id);self.assertFalse(next(s for s in p['route'] if s['id']=='pandas')['status']=='completed')
 def test_persistence_and_no_rediagnosis(self):
    self.s.submit(self.id,'diagnostic',None,self.answers('diagnostic',('python',)))
    self.assertEqual(len(Study(self.s.db_path).profile(self.id)['attempts']),1)
    with self.assertRaises(ValueError):self.s.quiz(self.id)
 def test_cycle_detection(self):
    self.s.skills['python']['prerequisites']=['ml']
    with self.assertRaises(ValueError):self.s.topological(['ml'])
 def test_scripted_demo(self):
    r=demo(Path(self.tmp.name)/'report');self.assertEqual(r['before']['completed'],2);self.assertEqual(r['after']['completed'],3)
if __name__=='__main__':unittest.main()
