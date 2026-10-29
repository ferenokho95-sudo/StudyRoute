import argparse
from common import ROOT,serve
from core import Study,demo

def routes(study):
 def route(method,path,query,body):
    if method=='GET' and path=='/api/goals':return study.goals
    if method=='GET' and path=='/api/learners':return study.learners()
    if method=='GET' and path=='/api/profile':return study.profile(int(query.get('id',['0'])[0]))
    if method=='GET' and path=='/api/quiz':return study.quiz(int(query.get('id',['0'])[0]),query.get('phase',['diagnostic'])[0],query.get('skill',[None])[0])
    if method=='POST' and path=='/api/create':return study.create(body.get('name'),body.get('goal'))
    if method=='POST' and path=='/api/submit':return study.submit(body.get('id'),body.get('phase'),body.get('skill'),body.get('answers'))
    raise LookupError()
 return route

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['serve','demo'],nargs='?',default='serve');p.add_argument('--port',type=int,default=8014);a=p.parse_args()
 if a.command=='serve':serve(routes(Study()),a.port,'StudyRoute')
 else:
    r=demo(ROOT/'reports/example');print(f"Прогресс: {r['before']['completed']} → {r['after']['completed']}")
if __name__=='__main__':main()
