"""Lightweight Phase 0 contract integrity; no implementation acceptance claim."""
import json
from pathlib import Path
import re

from .format_fixture import ROOT,catalog,generate
from .membership_model import need

DOCS=ROOT/'docs/v5x/v5.3'
REQUIRED=('PHASE_0_CONTRACT.md','MEMBERSHIP_PROTOCOL.md','API_FORMAT_AND_COMPATIBILITY.md',
          'RESOURCE_AND_LIFETIME_LIMITS.md','ACCEPTANCE_REGISTER.md','PHASE_0_CHECKLIST.md','PHASE_1_ENTRY_PLAN.md')


def plan_check(plan):
    need(plan['schema']=='gse-v53-acceptance-plan-v1','acceptance schema')
    profiles={(v['initial'],v['kind']) for v in plan['profiles']}
    need(profiles=={(3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE')} and len(plan['profiles'])==7,'profile inventory')
    for field,prefix,count in (('scenarios','S',10),('negatives','N',24),('measurements','M',12)):
        need([v['id'] for v in plan[field]]==[f'{prefix}{i:02}' for i in range(1,count+1)],field+' inventory')
    for row in plan['scenarios']:
        need(row['profiles'] in ('all-seven','old-joint-new','add-and-replace','stable-3-4-5') and
             all(row[k] and len(set(row[k]))==len(row[k]) for k in ('boundaries','cuts','modes')),'scenario axes')
    need(all(v['repetitions']==3 for v in plan['measurements']),'canonical repetitions')
    w=plan['workload']
    need(w['measurementCalls']==w['ratePerSecond']*w['measurementSeconds'] and
         w['warmupCalls']==w['ratePerSecond']*w['warmupSeconds'] and w['measurementCalls']%len(w['cycle'])==0,
         'window call arithmetic')
    need(sorted(w['transitionCallIndices'])==w['transitionCallIndices'] and len(set(w['transitionCallIndices']))==4 and
         all(0<i<w['measurementCalls'] for i in w['transitionCallIndices']),'transition schedule')
    e=plan['experiment'];need(e['members']==['experiment','failure-drill','canonical-1','canonical-2','canonical-3'] and
        e['sameSource'] is True and e['sameSequence'] is True and e['measurementRetries'] is False and
        e['paidCloudAuthorizationRequired'] is True,'cohort authority')
    return dict(scenarios=10,negatives=24,measurementHistories=36)


def run():
    for name in REQUIRED:need((DOCS/name).is_file() and (DOCS/name).stat().st_size>100,'missing deliverable '+name)
    links=0
    for file in DOCS.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',file.read_text()):
            if ':' in target or target.startswith('#'):continue
            need((file.parent/target.split('#')[0]).exists(),f'broken local link {file.name}: {target}');links+=1
    c=catalog()
    for family,count in (('records',24),('wire',21)):
        ids=[v['id'] for v in c[family].values()]
        need(len(ids)==len(set(ids))==count and sorted(ids)==list(range(1,count+1)),family+' kind inventory')
    need(json.loads((DOCS/'byte-fixtures.json').read_text())==generate(),'byte fixture drift')
    result=plan_check(json.loads((DOCS/'acceptance-plan.json').read_text()))
    return dict(status='PASS',localLinks=links,byteFixtures=45,commandFixtures=9,readTokenFixtures=1,**result)


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
