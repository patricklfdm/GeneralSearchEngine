"""Actual failed-export cleanup handles and original component call boundaries.

Native integration accounts for the marked leases, but these conditional
constructor probes do not qualify full native joining or every constructor.
"""
import argparse
import base64
import json
from pathlib import Path
from . import session_export_evidence as exports
from . import joining_export_request_evidence as requests

close=exports.close;need=close.need
CASES={
 'retention-capacity':('joining-retention-export',3*2*1024*1024,0,'IllegalArgumentException','prefix export owner capacity'),
 'retention-expiry':('joining-retention-export',3*2*1024*1024,1,'IllegalArgumentException','prefix export closed/expired/replaced'),
 'preparation-guard':('joining-preparation-export',2*16384,0,'IOException','revoked preparation after reservation'),
}


def expectation(case):
    need(type(case) is dict and set(case)=={'schema','case','node','request','before','after','failureType','failureMessage','completeNativeHistory'} and
         case['schema']=='gse-v53-export-rollback-component-v1' and case['completeNativeHistory'] is False and type(case['case']) is str and case['case'] in CASES and
         type(case['request']) is str and type(case['node']) is str and case['node'] in {'node-'+str(i) for i in range(1,7)},
         'export rollback original component scope')
    role,extent,children,kind,message=CASES[case['case']]
    need(case['failureType']==kind and case['failureMessage']==message,'export rollback original failure')
    request_kind,request=requests.source.network.t.wire(case['request'])
    need(request_kind=='CHUNK' and type(request['sequence']) is int and request['sequence']==1 and
         request['recipient']['node']==case['node'] and request['payload']['action']=='REQUEST' and
         type(request['payload']['offset']) is int and request['payload']['offset']==0 and request['payload']['bytes']=='',
         'export rollback original initial request')
    digest=requests.source.component.physical.e.digest(base64.b64decode(case['request'],validate=True))
    return dict(case,role=role,bytes=extent,children=children,requestDigest=digest)


def replay(traces,closes,cases):
    account=close.replay(traces,closes,export_ownership=True)
    need(type(cases) is list and 0<len(cases)<=close.MAXIMUM,'export rollback complete observed calls')
    plans=[expectation(case) for case in cases];groups={(node,name):group for node,owner in account['owners'].items() for name,group in owner['exportRollbacks'].items()}
    need(plans and len(plans)==len(groups),'export rollback complete observed calls')
    used=set();claimed=set();leases=0;revoked=0
    for plan in plans:
        node=plan['node'];need(node in traces,'export rollback original node');owner=account['owners'][node];life=owner['lifetimes']
        before,after=plan['before'],plan['after']
        need(type(before) is int and type(after) is int and 0<=before<after<len(traces[node]['changes']),
             'export rollback original operation boundaries')
        prefix=plan['role']+'-'+plan['requestDigest']+'-'
        choices=[(name,value) for (n,name),value in groups.items() if n==node and name.startswith(prefix) and (n,name) not in used]
        need(len(choices)==1,'export rollback original request allocation');name,value=choices[0];exports.kind(name);used.add((node,name))
        begin=value['begin']['resourceSequence'];end=value['returned']['resourceSequence']
        need(before<life[name]['start']<=begin<life[name]['end']<=end<=after,'export rollback original operation interval')
        children=value['begin']['children'];need(len(children)==plan['children'],'export rollback exact owned group')
        actual=[name,*children]
        foreign={n for attachment in owner['exportAttachments'].values() for n in attachment['children']}|set(owner['directExports'])
        foreign|={n for primary,probe in owner['probeExports'].items() for n in (primary,*probe['acquired']['children'])}
        for item in actual:
            need((node,item) not in claimed and item not in foreign,'export rollback exclusive original ownership');claimed.add((node,item))
            changes=[(row['event'],charge) for row in traces[node]['changes'] for charge in row['added']+row['removed'] if charge['owner']==item]
            need(len(changes)==2 and [v[0] for v in changes]==['RESERVE','RELEASE'] and changes[0][1]==changes[1][1] and
                 changes[0][1]['unit']=='CONTROL' and not changes[0][1]['claimSource'],'export rollback immutable allocation')
            need(changes[0][1]['bytes']==(plan['bytes'] if item==name else 4096),'export rollback original metadata extent')
            if item!=name:
                need(exports.kind(item)=='prefix-export','export rollback original prefix child')
                revoked+=life[item]['end']<=begin
            leases+=1
    need(used==set(groups),'export rollback complete observed calls')
    return dict(status='PASS',scope='original-failed-export-cleanup-invocations',rollbackCalls=len(used),ownedAllocations=leases,
                revokedChildrenBeforeCleanup=revoked,declaredRollbackReleaseQualified=True,
                allExportConstructorsQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def validate_component(directory,*,qualify=False):
    from .native_resource_evidence import collection
    root=Path(directory);before=collection.inventory(root,maximum=16*1024*1024)
    need(not before['directories'] and set(before['files'])=={'case.json','resources.json','closes.json'},'export rollback exact component inventory')
    load=lambda name:collection.read_json(root,name,16*1024*1024)
    case=load('case.json');plan=expectation(case);node=plan['node'];traces={node:load('resources.json')};closes={node:load('closes.json')}
    # The component is synchronous: unrelated original ownership survives the
    # failed call unchanged. The full native concurrent gate cannot assume this.
    rows=traces[node]['changes'];close.a.transitions.replay(traces[node]);states={};state={}
    need(type(case['before']) is int and type(case['after']) is int and 0<=case['before']<case['after']<len(rows),
         'export rollback original operation boundaries')
    for row in rows:
        for v in row['removed']:del state[(v['unit'],v['owner'])]
        for v in row['added']:state[v['unit'],v['owner']]=v
        if row['sequence'] in (case['before'],case['after']):states[row['sequence']]=dict(state)
    need(states[case['before']]==states[case['after']],'export rollback unchanged original baseline')
    if case['case']=='retention-capacity':
        need(sum(exports.kind(name)=='prefix-export' for unit,name in states[case['before']] if unit=='CONTROL')==6,
             'export rollback actual prefix capacity')
    if qualify:
        from . import export_rollback_negatives
        result=export_rollback_negatives.replay(traces,closes,[case])
    else:result=replay(traces,closes,[case])
    need(collection.inventory(root)==before,'export rollback original changed')
    return dict(status='PARTIAL',scope='conditional-original-constructor-rollback',case=case['case'],component=result,inventory=before,
                nativeJoiningQualified=False,allExportConstructorsQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(validate_component(a.root,qualify=a.qualify),sort_keys=True))
