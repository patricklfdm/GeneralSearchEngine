"""Bind successful joining metadata charges to admitted original content.

Native entry requires the complete physical/network/content/maintenance replay.
Component captures below only prove conditional handler accounting, not native
capability, voting authority or whole-runtime resource qualification.
"""
import argparse
import base64
from collections import Counter
import copy
import json
from pathlib import Path
from . import joining_export_request_evidence as requests
from . import joining_control_evidence as control

need=requests.need;exports=requests.exports;f=control.f;sha=control.sha
INTENT_RECORDS={'ENTRY','ACCEPT','PROOF','CERTIFICATE','CATALOG','CHECKPOINT'}
FIELDS={
 'gse-v53-joining-intent-metadata/1.3':{'schema','root','owner','learner','request','parent','target','records','payload'},
 'gse-v53-joining-preparation-hint/1.3':{'schema','root','cut','joining','ballot','sources'},
 'gse-v53-joining-completion/1.3':{'schema','root','cut','joining'},
}


def decoded(value):
    need(type(value) is str,'joining metadata encoded original')
    try:raw=base64.b64decode(value,validate=True)
    except ValueError:raise ValueError('joining metadata encoded original') from None
    need(base64.b64encode(raw).decode()==value,'joining metadata encoded original')
    return raw


def classify(raw,pending_ack=None):
    need(type(raw) is bytes and 0<len(raw)<=64*1024*1024,'joining metadata bounded original content')
    if pending_ack is not None and raw==pending_ack:
        f.decode(raw,'records','CHECKPOINT_ACK')
        return 'joining-checkpoint-export',len(raw)
    if not raw.startswith(b'{'):return None
    try:body=json.loads(raw)
    except (ValueError,UnicodeError):raise ValueError('joining metadata canonical original content') from None
    if type(body) is not dict:return None
    schema=body.get('schema');fragment=set(body)=={'basis','envelope','peers','learner'}
    if not fragment and schema not in FIELDS:return None
    need(f.canonical(body)==raw,'joining metadata canonical original content')
    if fragment:
        need(len(raw)<=2*1024*1024,'joining metadata retention fragment extent')
        return 'joining-retention-export',6*1024*1024
    need(set(body)==FIELDS[schema],'joining metadata original content fields')
    if schema=='gse-v53-joining-intent-metadata/1.3':
        need(len(raw)<=8*1024*1024 and type(body['records']) is dict and set(body['records'])==INTENT_RECORDS,
             'joining metadata original INTENT records')
        originals=[decoded(body['payload'])]
        for name in sorted(INTENT_RECORDS):
            record=decoded(body['records'][name]);f.decode(record,'records',name);originals.append(record)
        return 'joining-intent',65536+4*sum(map(len,originals))
    need(len(raw)<=16384,'joining metadata hint extent')
    role='joining-preparation-export' if schema=='gse-v53-joining-preparation-hint/1.3' else 'joining-completion-export'
    return role,32768


def expectation(initial,raw,*,pending_ack=None,manifest=None):
    kind,q=requests.source.network.t.wire(initial)
    need(kind=='CHUNK' and q['sequence']==1 and q['payload']['action']=='REQUEST' and
         q['payload']['offset']==0 and q['payload']['bytes']=='','joining metadata original first request')
    identified=classify(raw,pending_ack);need(identified is not None,'joining metadata original family')
    role,size=identified;nested=role in ('joining-retention-export','joining-intent')
    need((manifest is not None)==nested,'joining metadata original prefix requirement')
    if nested:
        fields=f.decode(manifest,'records','GENERATION')
        need(fields['node']==q['recipient']['node'] and fields['root']==q['root'],'joining metadata original prefix owner')
    return dict(node=q['recipient']['node'],role=role,bytes=size,contentSha256=sha(raw),contentBytes=len(raw),
                prefixSha256=sha(manifest) if nested else None)


def derive(reader):
    """Reader groups/windows must already have passed native capability checks."""
    pending=control.e.pending_ack(reader.model);result={}
    for group in reader.groups:
        first=group[0];raw=first['raw'];identified=classify(raw,pending)
        if identified is None:continue
        need(len(group)==1 and first['kind']=='RECORD','joining metadata exact single content session')
        q=first['offer']['request'];initial=f.encode('wire','CHUNK',q);binding=sha(initial)
        need(binding==first['offer']['requestHash'] and binding not in result,'joining metadata unique original request')
        manifest=None
        if identified[0] in ('joining-retention-export','joining-intent'):
            own=control.e.current(reader.windows,q['recipient']['node'],first['offer']['received'],first['commit']['offered'])
            manifest=own['manifest']
        result[binding]=expectation(base64.b64encode(initial).decode(),raw,pending_ack=pending,manifest=manifest)
    need(result,'joining metadata unobserved content')
    return result


def bind(traces,closes,initials,expected):
    original=requests.bind(traces,closes,initials)
    account=exports.close.replay(traces,closes,export_ownership=True)
    need(type(expected) is dict and expected,'joining metadata original expectations')
    used=set();families=Counter();nested_count=0
    for (node,session),initial in initials.items():
        owner=account['owners'][node];attachment=owner['exportAttachments'][session]
        metadata=[name for name in attachment['children'] if exports.kind(name) in exports.REQUEST_BOUND]
        if not metadata:continue
        need(len(metadata)==1,'joining metadata exact session group')
        name=metadata[0];binding=sha(decoded(initial['bytes']))
        need(binding in expected and binding not in used,'joining metadata complete original expectations')
        used.add(binding);plan=expected[binding];role=exports.kind(name)
        need(type(plan) is dict and set(plan)=={'node','role','bytes','contentSha256','contentBytes','prefixSha256'} and
             plan['node']==node and plan['role']==role and type(plan['bytes']) is int and 0<plan['bytes']<=384*1024*1024 and
             type(plan['contentBytes']) is int and 0<plan['contentBytes']<=8*1024*1024 and
             type(plan['contentSha256']) is str and len(plan['contentSha256'])==64 and
             all(c in '0123456789abcdef' for c in plan['contentSha256']),'joining metadata original expectation shape')
        def charge(handle):
            start=owner['lifetimes'][handle]['start']
            charges=[v for v in traces[node]['changes'][start]['added'] if v['owner']==handle]
            need(len(charges)==1 and charges[0]['unit']=='CONTROL' and not charges[0]['claimSource'],'joining metadata original CONTROL charge')
            return charges[0]['bytes']
        need(charge(name)==plan['bytes'],'joining metadata original reservation extent')
        nested=role in ('joining-retention-export','joining-intent')
        need(len(attachment['children'])==(2 if nested else 1),'joining metadata exact session group')
        if nested:
            prefix=plan['prefixSha256'];need(type(prefix) is str and len(prefix)==64 and all(c in '0123456789abcdef' for c in prefix),
                                           'joining metadata original prefix expectation')
            child=next(n for n in attachment['children'] if n!=name)
            need(child.startswith('prefix-export-'+prefix+'-'),'joining metadata original nested generation')
            need(charge(child)==4096,'joining metadata original prefix extent');nested_count+=1
        else:need(plan['prefixSha256'] is None,'joining metadata unexpected prefix expectation')
        families[role]+=1
    need(used==set(expected),'joining metadata complete original expectations')
    return dict(status=original['status'],scope='original-joining-session-metadata-and-prefix-extents',families=dict(sorted(families.items())),
                metadataAllocations=sum(families.values()),nestedPrefixes=nested_count,metadataExtentsQualified=True,
                allJoiningFamiliesObserved=set(families)==set(exports.REQUEST_BOUND),requestBindings=original,
                nativeContentAuthorityQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def qualify(traces,closes,initials,expected):
    original=bind(traces,closes,initials,expected)
    need(original['status']=='PASS','joining metadata original incomplete inventory')
    key,plan=next(iter(expected.items()));node=plan['node'];role=plan['role']
    cases={'metadata-extent':'joining metadata original reservation extent',
           'missing-content':'joining metadata original expectations' if len(expected)==1 else 'joining metadata complete original expectations',
           'extra-content':'joining metadata complete original expectations',
           'foreign-source':'joining metadata original expectation shape',
           'wrong-family':'joining metadata original expectation shape',
           'boolean-extent':'joining metadata original expectation shape',
           'foreign-first-request':'joining metadata complete original expectations'}
    if plan['prefixSha256'] is not None:
        cases.update({'prefix-binding':'joining metadata original nested generation','prefix-extent':'joining metadata original prefix extent'})
    results=[]
    for case,reason in cases.items():
        changed=copy.deepcopy((traces,closes,initials,expected));tc,_,_,ec=changed;pc=ec[key]
        if case in ('metadata-extent','prefix-extent'):
            from .direct_export_negatives import recount
            prefix=role+'-'+key+'-' if case=='metadata-extent' else 'prefix-export-'+pc['prefixSha256']+'-'
            for row in tc[node]['changes']:
                for value in row['added']+row['removed']:
                    if value['owner'].startswith(prefix):value['bytes']+=1
            recount(tc[node])
        elif case=='missing-content':ec.pop(key)
        elif case=='extra-content':ec['not-an-original-request']=copy.deepcopy(pc)
        elif case=='foreign-source':pc['node']='node-99'
        elif case=='wrong-family':pc['role']='joining-completion-export' if role!='joining-completion-export' else 'joining-preparation-export'
        elif case=='boolean-extent':pc['bytes']=True
        elif case=='foreign-first-request':ec['not-an-original-request']=ec.pop(key)
        elif case=='prefix-binding':pc['prefixSha256']='e'*64 if pc['prefixSha256']!='e'*64 else 'f'*64
        try:bind(*changed)
        except ValueError as error:need(str(error)==reason,'joining metadata unrelated rejection: '+case+': '+str(error))
        else:raise ValueError('joining metadata negative accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


def validate_component(directory,*,negatives=False):
    from .native_resource_evidence import collection
    root=Path(directory);before=collection.inventory(root,maximum=16*1024*1024)
    load=lambda name:collection.read_json(root,name,16*1024*1024)
    scope=load('scope.json');initial=load('initial.json')
    need(type(scope) is dict,'joining metadata conditional component scope');node=scope.get('node');role=scope.get('role')
    need(set(scope)=={'schema','role','node','nativeMembershipQualified'} and
         scope['schema']=='gse-v53-joining-export-request-component-v1' and scope['nativeMembershipQualified'] is False and
         node=='node-1' and role in ('joining-retention-export','joining-preparation-export'),'joining metadata conditional component scope')
    names={'scope.json','initial.json','resources.json','closes.json','content.bin'}
    if role=='joining-retention-export':names.add('generation.gsr')
    need(not before['directories'] and set(before['files'])==names,'joining metadata exact component inventory')
    need(type(initial) is dict and set(initial)=={'session','bytes','received','offered'},'joining metadata component initial shape')
    raw=collection.snapshot.s.regular(root/'content.bin',2*1024*1024)
    manifest=collection.snapshot.s.regular(root/'generation.gsr',65536) if 'generation.gsr' in names else None
    plan=expectation(initial['bytes'],raw,manifest=manifest);need(plan['role']==role,'joining metadata component original family')
    session=initial.pop('session');traces={node:load('resources.json')};closes={node:load('closes.json')}
    result=(qualify if negatives else bind)(traces,closes,{(node,session):initial},{sha(decoded(initial['bytes'])):plan})
    need(collection.inventory(root)==before,'joining metadata component original changed')
    return dict(status='PARTIAL',scope='conditional-original-joining-metadata-extent',component=result,inventory=before,
                nativeMembershipQualified=False,allJoiningFamiliesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(validate_component(a.root,negatives=a.qualify),sort_keys=True))
