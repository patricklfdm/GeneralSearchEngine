"""Original handles of explicit qualification probes, distinct from protocol owners.

Native callers must derive expectations from admitted originals. The standalone
component below binds its prefix to an original selector/manifest pair and never
claims a complete native membership history.
"""
import argparse
import json
from pathlib import Path
from . import session_export_evidence as exports
from . import joining_export_request_evidence as requests

close=exports.close;need=close.need
f=requests.source.network.t.f;digest=requests.source.component.physical.e.digest


def replay(traces,closes,expected):
    account=close.replay(traces,closes,export_ownership=True)
    groups={(node,name):value for node,owner in account['owners'].items() for name,value in owner['probeExports'].items()}
    need(type(expected) is list and expected and len(expected)==len(groups),'probe export complete observed cohort')
    used=set();claimed=set();allocations=0;revoked=0
    for plan in expected:
        need(type(plan) is dict and set(plan)=={'node','role','binding','bytes','children','before','through','after'} and
             plan['role'] in ('prefix-export','joining-intent') and type(plan['children']) is list and
             (plan['role']=='prefix-export' and not plan['children'] or plan['role']=='joining-intent' and len(plan['children'])==1),
             'probe export original expectation')
        node=plan['node'];need(type(node) is str and node in traces,'probe export original node')
        owner=account['owners'][node];life=owner['lifetimes'];before,through,after=(plan[k] for k in ('before','through','after'))
        need(all(type(v) is int for v in (before,through,after)) and 0<=before<=through<after<len(traces[node]['changes']),
             'probe export original operation boundaries')
        target=[dict(role=plan['role'],binding=plan['binding'],bytes=plan['bytes']),*plan['children']]
        for item in target:
            need(type(item) is dict and set(item)=={'role','binding','bytes'} and item['role'] in ('prefix-export','joining-intent') and
                 type(item['binding']) is str and len(item['binding'])==64 and all(c in '0123456789abcdef' for c in item['binding']) and
                 type(item['bytes']) is int and 0<item['bytes']<=8*1024*1024 and
                 (item['role']!='prefix-export' or item['bytes']==4096),'probe export original content expectation')
        need(len(target)==1 or target[1]['role']=='prefix-export','probe export original nested expectation')
        prefix=plan['role']+'-'+plan['binding']+'-'
        choices=[(name,value) for (n,name),value in groups.items() if n==node and name.startswith(prefix) and (n,name) not in used and
                 before<life[name]['start'] and value['returned']['resourceSequence']<=after]
        need(len(choices)==1,'probe export original allocation binding');name,call=choices[0];used.add((node,name))
        handles=[name,*call['acquired']['children']];need(len(handles)==len(target),'probe export exact owned group')
        acquired=call['acquired']['resourceSequence'];begin=call['begin']['resourceSequence'];returned=call['returned']['resourceSequence']
        need(acquired<=through<=begin<=returned<=after,'probe export original body interval')
        foreign={n for attachment in owner['exportAttachments'].values() for n in attachment['children']}|set(owner['directExports'])
        foreign|={n for primary,rollback in owner['exportRollbacks'].items() for n in (primary,*rollback['begin']['children'])}
        for handle,item in zip(handles,target):
            need(exports.kind(handle)==item['role'] and handle.startswith(item['role']+'-'+item['binding']+'-'),
                 'probe export original child binding')
            need((node,handle) not in claimed and handle not in foreign,'probe export exclusive original ownership');claimed.add((node,handle))
            need(before<life[handle]['start']<=acquired and through<life[handle]['end'],'probe export uninterrupted body ownership')
            changes=[(row['event'],charge) for row in traces[node]['changes'] for charge in row['removed']+row['added'] if charge['owner']==handle]
            need(len(changes)==2 and [v[0] for v in changes]==['RESERVE','RELEASE'] and changes[0][1]==changes[1][1] and
                 changes[0][1]['unit']=='CONTROL' and not changes[0][1]['claimSource'],'probe export immutable reservation')
            need(changes[0][1]['bytes']==item['bytes'],'probe export original extent')
            allocations+=1;revoked+=life[handle]['end']<=begin
    need(used==set(groups),'probe export complete observed cohort')
    return dict(status='PASS',scope='explicit-probe-export-ownership-and-cleanup',probeCalls=len(used),ownedAllocations=allocations,
                revokedBeforeCleanup=revoked,declaredProbeReleaseQualified=True,allExportAllocationsQualified=False,
                nativeProbeContentQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def validate_component(directory,*,qualify=False):
    from .native_resource_evidence import collection
    root=Path(directory);before=collection.inventory(root,maximum=16*1024*1024)
    need(not before['directories'] and set(before['files'])=={'case.json','selector.gsr','generation.gsr','resources.json','closes.json'},
         'probe export exact component inventory')
    load=lambda name:collection.read_json(root,name,16*1024*1024)
    case=load('case.json')
    need(type(case) is dict and set(case)=={'schema','node','mode','before','through','after','completeNativeHistory'} and
         case['schema']=='gse-v53-probe-export-component-v1' and case['node']=='node-1' and case['mode'] in ('close','expiry') and
         case['completeNativeHistory'] is False,'probe export conditional component scope')
    generation=collection.snapshot.s.regular(root/'generation.gsr',65536);selector=collection.snapshot.s.regular(root/'selector.gsr',4096)
    g=f.decode(generation,'records','GENERATION');s=f.decode(selector,'records','SELECTOR')
    need(s['digest']==digest(generation) and s['node']==g['node']==case['node'] and s['root']==g['root'] and s['generation']==g['generation'],
         'probe export original selected generation')
    plan=dict(node=case['node'],role='prefix-export',binding=digest(generation),bytes=4096,children=[],**{k:case[k] for k in ('before','through','after')})
    traces={case['node']:load('resources.json')};closes={case['node']:load('closes.json')}
    original=replay(traces,closes,[plan])
    need(original['revokedBeforeCleanup']==(1 if case['mode']=='expiry' else 0),'probe export original revocation mode')
    states={};state={}
    for row in traces[case['node']]['changes']:
        for value in row['removed']:del state[value['unit'],value['owner']]
        for value in row['added']:state[value['unit'],value['owner']]=value
        if row['sequence'] in (case['before'],case['after']):states[row['sequence']]=dict(state)
    need(states[case['before']]==states[case['after']],'probe export original baseline restored')
    if qualify:
        from . import probe_export_negatives
        result=probe_export_negatives.replay(traces,closes,[plan])
    else:result=original
    need(collection.inventory(root)==before,'probe export component original changed')
    return dict(status='PARTIAL',scope='conditional-original-prefix-probe',mode=case['mode'],component=result,inventory=before,
                nativeMembershipQualified=False,allProbeFamiliesQualified=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(validate_component(args.root,qualify=args.qualify),sort_keys=True))
