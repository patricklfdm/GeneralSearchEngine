"""Original source-component cleanup calls, distinct from final zero accounting.

The annotations run inside existing monitors without calling outside code. They
identify the cleanup-performing invocation, not concurrent no-op close callers.
Joining endpoints, export internals and whole-runtime shutdown remain separate.
"""
import argparse
import json
from pathlib import Path
from . import source_control_resource_evidence as source

a=source.a
need=a.need
DIRECTORY='control-close-captures'
ROLES=('transfer-service','transfer-trace','source-session','joining-checkpoint-service','joining-checkpoint-trace')
SERVICES={'transfer-service':'transfer-trace','joining-checkpoint-service':'joining-checkpoint-trace'}
MAXIMUM=65536
CHILDREN_MAXIMUM=262144
DIRECT_ROLES={'ACTIVATION':'source-export','SELECTED':'source-export','MAINTENANCE':'prefix-export'}
DIRECT_EVENTS={phase+'_BORROW_'+event:(phase,event) for phase in DIRECT_ROLES
               for event in ('ACQUIRED','CLOSE_BEGIN','RETURNED')}


def role(owner):
    return next((v for v in ROLES if owner.startswith(v+'-')),None)


def load(root,index):
    directory=Path(root)/DIRECTORY
    need(directory.is_dir() and not directory.is_symlink(),'control close missing original capture')
    captured=a.collection.read_json(directory,'index.json',16384)
    need(type(captured) is dict and set(captured)=={'schema','root','eventsSha256','owners'} and
         captured['schema']=='gse-v53-control-close-capture-v1' and captured['root']==index['root'] and
         captured['eventsSha256']==index['eventsSha256'] and type(captured['owners']) is list and
         len(captured['owners'])==len(index['owners']),'control close original index')
    traces={};names={'index.json'};total=0
    for ref,original in zip(captured['owners'],index['owners']):
        need(type(ref) is dict and set(ref)=={'identity','path','sha256','resourceSha256'} and
             ref['identity']==original['identity'] and ref['path']==original['path'] and
             ref['resourceSha256']==original['sha256'],'control close original resource binding')
        raw=a.collection.snapshot.s.regular(directory/ref['path'],64*a.transitions.MIB);total+=len(raw)
        need(total<=256*a.transitions.MIB and a.collection.digest(raw)==ref['sha256'],'control close capture digest/capacity')
        traces[ref['identity']['node']]=a.collection.read_json(directory,ref['path'],64*a.transitions.MIB);names.add(ref['path'])
    need({p.name for p in directory.iterdir()}==names,'control close capture inventory')
    return traces


def allocations(trace):
    a.transitions.replay(trace);result={}
    for row in trace['changes']:
        if row['event']=='RESERVE':
            for value in row['added']:
                if value['unit']!='CONTROL':continue
                name=value['owner'];need(name not in result,'control close reused allocation')
                result[name]=dict(start=row['sequence'],end=None)
        elif row['event']=='RELEASE':
            for value in row['removed']:
                if value['unit']=='CONTROL':result[value['owner']]['end']=row['sequence']
    return result


def replay(traces,closes,*,export_ownership=False):
    need(type(export_ownership) is bool,'control close export policy')
    need(type(closes) is dict and set(closes)==set(traces) and traces,'control close complete original budgets')
    owners={};total=0;children_total=0
    for node,trace in traces.items():
        life=allocations(trace);value=closes[node]
        need(type(value) is dict and set(value)=={'schema','maximum','observations','truncated','failed','rows'} and
             value['schema']=='gse-v53-control-close-observations-v1' and type(value['maximum']) is int and
             0<value['maximum']<=MAXIMUM and value['truncated'] is False and value['failed'] is False and
             type(value['observations']) is int and type(value['rows']) is list and
             value['observations']==len(value['rows'])<=value['maximum'],'control close complete bounded recorder')
        pairs={};calls={};attachments={};direct={};cursor=0;child_count=0
        for seq,row in enumerate(value['rows']):
            need(type(row) is dict and set(row)=={'sequence','event','call','resourceSequence','owner','children'} and
                 type(row['sequence']) is int and row['sequence']==seq and type(row['call']) is int and
                 type(row['event']) is str and
                 type(row['resourceSequence']) is int and cursor<=row['resourceSequence']<len(trace['changes']) and
                 type(row['owner']) is str and row['owner'] in life and
                 (role(row['owner']) is not None or export_ownership and row['event'] in DIRECT_EVENTS) and
                 type(row['children']) is list and all(type(v) is str for v in row['children']) and
                 row['children']==sorted(set(row['children'])) and len(row['children'])<=256,
                 'control close exact ordered row')
            cursor=row['resourceSequence'];name=row['owner'];owned=life[name]
            child_count+=len(row['children']);need(child_count<=CHILDREN_MAXIMUM,'control close child capacity')
            if row['event'] in DIRECT_EVENTS:
                phase,event=DIRECT_EVENTS[row['event']]
                need(export_ownership and not row['children'] and name.startswith(DIRECT_ROLES[phase]+'-'),
                     'control close direct export scope')
                if event=='ACQUIRED':
                    need(name not in direct and row['call']==seq and owned['end'] is not None and owned['start']<=cursor,
                         'control close original direct acquisition')
                    direct[name]=dict(phase=phase,acquired=row,begin=None,returned=None)
                else:
                    need(name in direct and direct[name]['phase']==phase and row['call']==direct[name]['acquired']['sequence'],
                         'control close original direct call')
                    observed=direct[name]
                    if event=='CLOSE_BEGIN':
                        need(observed['begin'] is None and observed['returned'] is None,'control close unique direct cleanup')
                        observed['begin']=row
                    else:
                        need(observed['begin'] is not None and observed['returned'] is None and owned['end']<=cursor,
                             'control close direct release before return')
                        observed['returned']=row
            elif row['event']=='ATTACHED':
                need(export_ownership and role(name)=='source-session' and row['call']==seq and
                     name not in attachments and name not in pairs and owned['end'] is not None and
                     owned['start']<=cursor<owned['end'] and 0<len(row['children'])<=2,
                     'control close original export attachment')
                need(all(child!=name and child in life and life[child]['end'] is not None and
                         life[child]['start']<owned['start'] for child in row['children']),
                     'control close original export allocation')
                attachments[name]=row
            elif row['event']=='BEGIN':
                need(row['call']==seq and name not in pairs and owned['end'] is not None and
                     owned['start']<=cursor<owned['end'],'control close original live invocation')
                need(all(child!=name and child in life and life[child]['end'] is not None and
                         life[child]['start']<=cursor<life[child]['end'] for child in row['children']),
                     'control close original live children')
                calls[seq]=name;pairs[name]=dict(begin=row,returned=None)
            else:
                need(row['event']=='RETURNED' and not row['children'] and calls.get(row['call'])==name and
                     pairs[name]['returned'] is None,'control close matched normal return')
                pair=pairs[name];need(owned['end']<=cursor and pair['begin']['resourceSequence']<owned['end'],
                                      'control close release before normal return')
                pair['returned']=row
        expected={name for name in life if role(name)}
        need(set(pairs)==expected and all(v['returned'] is not None for v in pairs.values()),
             'control close complete cleanup intervals')
        need(all(v['begin'] is not None and v['returned'] is not None for v in direct.values()),
             'control close incomplete direct cleanup')
        parent={};session_parent={}
        for name,pair in pairs.items():
            kind=role(name);start=pair['begin'];end=pair['returned'];owned=life[name]
            for child in start['children']:
                need(life[child]['end']<=owned['end'],'control close child release order')
                if kind=='source-session':
                    need(len(start['children'])==1 and child.startswith('source-response-'),
                         'control close session response child')
                else:
                    wanted=SERVICES.get(kind,'source-session')
                    need(role(child)==wanted and child in pairs and child not in parent,
                         'control close child scope')
                    need(owned['start']<life[child]['start'],'control close parent allocation order')
                    nested=pairs[child];need(start['sequence']<nested['begin']['sequence']<nested['returned']['sequence']<end['sequence'],
                                            'control close nested invocation order')
                    parent[child]=name
        for name in expected:
            kind=role(name)
            if kind in SERVICES.values():need(name in parent,'control close trace missing service')
            if kind!='source-session':continue
            binding=name[len('source-session-'):len('source-session-')+64]
            candidates=[p for p in expected if role(p) in SERVICES.values() and p.startswith(role(p)+'-'+binding+'-') and
                        life[p]['start']<life[name]['start']<life[name]['end']<life[p]['end']]
            need(len(candidates)==1,'control close original trace session');p=candidates[0];session_parent[name]=p
            if life[name]['end']>pairs[p]['begin']['resourceSequence']:
                need(parent.get(name)==p,'control close active session omitted')
            else:need(name not in parent and pairs[name]['returned']['sequence']<pairs[p]['begin']['sequence'],
                      'control close completed session order')
        if export_ownership:
            need(set(attachments)==set(session_parent),'control close complete export attachments')
        owners[node]=dict(pairs=pairs,lifetimes=life,sessionParents=session_parent,exportAttachments=attachments,directExports=direct)
        total+=len(pairs);children_total+=child_count
    need(total>0,'control close unobserved cleanup')
    return dict(status='PASS',cleanupIntervals=total,childReferences=children_total,owners=owners,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


def component(traces,closes,events,boundaries):
    result=replay(traces,closes);all_pairs=[(node,name,pair) for node,owner in result['owners'].items() for name,pair in owner['pairs'].items()]
    need(len(all_pairs)==3 and {role(name) for _,name,_ in all_pairs}==set(ROLES[:3]) and
         all(node=='node-1' for node,_,_ in all_pairs),'control close exact component scope')
    owner=result['owners']['node-1'];pairs=owner['pairs'];life=owner['lifetimes']
    for name,pair in pairs.items():
        if role(name)=='source-session':
            at=pair['begin']['resourceSequence']
            response=sorted(p for p,v in life.items() if p.startswith('source-response-') and v['start']<=at<v['end'])
            need(pair['begin']['children']==response,'control close complete response inventory')
        elif role(name)=='transfer-service':
            positions={event['event']:i for i,event in enumerate(events) if event['event'].startswith('SOURCE_SERVICE_CLOSE_')}
            need(set(positions)=={'SOURCE_SERVICE_CLOSE_BEGIN','SOURCE_SERVICE_CLOSE_RETURNED'},'control close external call pair')
            first,last=(boundaries[positions['SOURCE_SERVICE_CLOSE_'+v]]['sequence'] for v in ('BEGIN','RETURNED'))
            need(first<=pair['begin']['resourceSequence']<life[name]['end']<=pair['returned']['resourceSequence']<=last,
                 'control close external call interval')
    return dict(status='PASS',scope='original-source-component-cleanup-performing-invocations',
                cleanupIntervals=result['cleanupIntervals'],childReferences=result['childReferences'],
                sourceComponentCloseIntervalsQualified=True,wholeRuntimeResourcesQualified=False,phase3Complete=False)


def case(root,name):
    original,data=source.case(root,name) # Original physical and transport evidence must pass first.
    index,traces,boundaries,events=a.load(root);closes=load(root,index)
    return dict(precondition=original,**component(traces,closes,events,boundaries)),(traces,closes,events,boundaries)


def validate(root):
    root=Path(root);before=a.collection.inventory(root);source.validate(root)
    result=[dict(case=name,close=case(root/name,name)[0]) for name in source.CASES]
    need(a.collection.inventory(root)==before,'control close original changed')
    return dict(status='PASS',cases=result,wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
