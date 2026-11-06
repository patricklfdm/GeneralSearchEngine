"""Native SOURCE-count refusal inside a complete application recovery original.

The probe calls the real private receiver using the native node's pool. It is
not remote wire admission, a learner, byte saturation or a full resource gate.
"""
import argparse
import copy
import json
from pathlib import Path
import re
from . import native_application_overlap as overlap
from .node_process_evidence import transcript

admission=overlap.admission;h=admission.h;need=h.need;t=overlap.t
POINT='RETIREMENT_BORROW_PREFIX_WRITTEN'
SCHEMA='gse-v53-native-count-refusal-v1'
FIELDS={'schema','status','life','node','eventIndex','point','callbackSequence','beforeSequence','afterSequence',
        'beforeUsage','afterUsage','authorityFiles','sourcePath','packetFile','packetSha256','rejection','scratchRemoved',
        'originalPool','wireAdmissionQualified','wholeRuntimeResourcesQualified','phase3Complete'}


def state_at(trace,sequence):
    need(type(sequence) is int and 0<=sequence<len(trace['changes']),'native refusal original sequence')
    state={}
    for row in trace['changes'][:sequence+1]:
        for v in row['removed']:del state[t.key(v)]
        for v in row['added']:state[t.key(v)]=v
    return state


def check_record(record,row,trace,boundary,next_sequence,packet):
    need(type(record) is dict and set(record)==FIELDS and record['schema']==SCHEMA and record['status']=='PARTIAL' and
         record['originalPool'] is True and record['scratchRemoved'] is True and record['rejection']=='resource ownership/count' and
         all(record[k] is False for k in ('wireAdmissionQualified','wholeRuntimeResourcesQualified','phase3Complete')),
         'native refusal exact scope')
    need(all(type(record[k]) is int and record[k]==row[k] for k in ('life','eventIndex')) and
         record['node']==row['node'] and record['point']==row['point']==POINT,'native refusal original callback')
    first=record['beforeSequence'];last=record['afterSequence'];at=record['callbackSequence']
    need(all(type(v) is int for v in (at,first,last)) and at==boundary['sequence'] and
         0<=at<=first and last==first+2 and last<=next_sequence<len(trace['changes']),
         'native refusal exact checkpoints')
    limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
    before=state_at(trace,first);after=state_at(trace,last)
    t.same_usage(record['beforeUsage'],t.usage(before,limits));t.same_usage(record['afterUsage'],t.usage(after,limits))
    need(before==after,'native refusal original charges preserved')
    changes=trace['changes'][first+1:last+1];reserve,release=changes
    added=reserve['added']
    need(reserve['event']=='RESERVE' and reserve['removed']==[] and len(added)==1 and
         added[0]['unit']=='CONTROL' and added[0]['bytes']==4096 and added[0]['claimSource']=='' and
         re.fullmatch(r'received-records-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',added[0]['owner']) and
         release['event']=='RELEASE' and release['added']==[] and release['removed']==added,
         'native refusal temporary control only')
    files={k:v['sha256'] for k,v in row['files'].items() if 'bytes' in v}
    need(record['authorityFiles']==[dict(path=k,sha256=v) for k,v in sorted(files.items())],'native refusal original physical files')
    physical=admission.storage.coverage.compare(row['files'],before,row['ordinals'])
    counts={k:sum(v['unit']==k and v['bytes']>0 for v in physical['required']) for k in overlap.COUNTS}
    need(counts==overlap.COUNTS and all(record['beforeUsage']['counts'].get(k)==v for k,v in counts.items()),
         'native refusal simultaneous nonempty owners')
    source=record['sourcePath']
    need(type(source) is str and re.fullmatch(r'sources/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/source\.gscp',source) and
         source in files and record['packetFile']==record['node']+'.gscp','native refusal original source path')
    need(type(packet) is bytes and len(packet)==row['files'][source]['bytes'] and
         h.digest(packet)==record['packetSha256']==files[source],'native refusal original source packet')
    return dict(life=row['life'],node=row['node'],eventIndex=row['eventIndex'],point=POINT,
        callbackSequence=at,beforeSequence=first,afterSequence=last,nonemptyPhysicalOwnerCounts=counts,
        physicalBytes=physical['physicalBytes'],originalFilesSha256=h.digest(h.snapshot.f.canonical(files)),
        packetSha256=h.digest(packet),temporaryControlReturned=True,originalChargesPreserved=True)


def index_nodes(index,identity,life):
    need(type(index) is dict and set(index)=={'schema','life','pid','terminal','nodes','phase3Complete'} and
         index['schema']=='gse-v53-native-count-refusals-v1' and type(index['life']) is int and index['life']==life and
         type(index['pid']) is int and index['pid']==identity['pid'] and index['terminal']==identity['terminal']==('CUT_PREFIX' if life==1 else 'CLOSED') and
         index['phase3Complete'] is False,'native refusal original process lifetime')
    nodes=index['nodes'];need(type(nodes) is list and 1<=len(nodes)<=4 and all(type(n) is str and n in ('node-1','node-2','node-3','node-4') for n in nodes) and
         nodes==sorted(set(nodes)),'native refusal exact observed owners')
    return nodes


def contexts(root):
    raw=Path(root)/'original';observed=raw/admission.OBSERVED;model=admission.transients
    parts,_=model.model.plans(observed);rows,_=model.combine(dict(model.prerequisite.application_plans(observed),**parts))
    ordinals=admission.storage.coverage.ordinal_plans(rows)
    by_callback={(r['life'],r['node'],r['eventIndex']):dict(r,ordinals=ordinals[r['life'],r['node'],r['eventIndex']]) for r in rows}
    result=[]
    directory=Path(root)/'refusals'
    need({p.name for p in directory.iterdir()}=={'life-1','life-2'},'native refusal complete lifetimes')
    for life in (1,2):
        folder=directory/f'life-{life}';index=read(folder/'index.json')
        resource_dir=observed/f'resources/life-{life}';identity=read(resource_dir/'index.json');boundaries=read(resource_dir/'boundaries.json',32*1024*1024)
        nodes=index_nodes(index,identity,life)
        need({p.name for p in folder.iterdir()}=={'index.json',*(n+'.json' for n in nodes),*(n+'.gscp' for n in nodes)},'native refusal exact sidecar inventory')
        # Original process stdout fixes whether the callback preceded fresh READY.
        stdout=transcript(observed/f'history/process/life-{life}.jsonl')
        observed_events=[i for i,v in enumerate(stdout) if v['action'] in ('event','response')]
        ready=[i for i,v in enumerate(stdout) if v['action']=='ready']
        need(len(observed_events)==len(boundaries),'native refusal complete stdout boundaries')
        for node in nodes:
            record=read(folder/(node+'.json'))
            need(type(record) is dict and type(record.get('eventIndex')) is int,'native refusal typed callback')
            key=(life,node,record['eventIndex'])
            need(key in by_callback,'native refusal captured callback required');row=by_callback[key]
            at=row['eventIndex'];boundary=boundaries[at]
            need(boundary['node']==node and boundary['eventIndex']==at,'native refusal original boundary')
            if life==2:need(len(ready)==1 and observed_events[at]<ready[0],'native refusal before admitted completion')
            _,trace=t.read(resource_dir/(node+'.json'));t.replay(trace,require_closed=life==2)
            next_seq=next((b['sequence'] for b in boundaries[at+1:] if b['node']==node),len(trace['changes'])-1)
            packet=h.snapshot.s.regular(folder/(node+'.gscp'),32*t.MIB)
            result.append((record,row,trace,boundary,next_seq,packet))
    return result


def read(path,maximum=65536):
    data=h.snapshot.s.regular(Path(path),maximum);return json.loads(data)


NEGATIVES={
    'whole-runtime-claim':'native refusal exact scope','wire-claim':'native refusal exact scope',
    'wrong-rejection':'native refusal exact scope','scratch-leak':'native refusal exact scope',
    'foreign-owner':'native refusal original callback','boolean-event':'native refusal original callback',
    'wrong-checkpoint':'native refusal exact checkpoints','late-sequence':'native refusal exact checkpoints',
    'altered-usage':'resource transitions derived usage','omitted-file':'native refusal original physical files',
    'foreign-source':'native refusal original source path','changed-packet':'native refusal original source packet',
}


def mutate(record,name):
    if name=='whole-runtime-claim':record['wholeRuntimeResourcesQualified']=True
    elif name=='wire-claim':record['wireAdmissionQualified']=True
    elif name=='wrong-rejection':record['rejection']='shared staging capacity'
    elif name=='scratch-leak':record['scratchRemoved']=False
    elif name=='foreign-owner':record['node']='node-9'
    elif name=='boolean-event':record['eventIndex']=True
    elif name=='wrong-checkpoint':record['callbackSequence']+=1
    elif name=='late-sequence':record['afterSequence']+=1
    elif name=='altered-usage':record['afterUsage']['metadata']+=1
    elif name=='omitted-file':record['authorityFiles'].pop()
    elif name=='foreign-source':record['sourcePath']='../source.gscp'
    elif name=='changed-packet':record['packetSha256']='0'*64
    else:raise ValueError('native refusal unknown negative')


def qualify(root,case):
    root=Path(root);before=h.inventory(root)
    need({p.name for p in root.iterdir()}=={'original','refusals'},'native refusal wrapper inventory')
    original=admission.transients.validate(root/'original');admission.check_original(original,case)
    collected=admission.collect(root/'original',case)
    values=contexts(root);positive=[check_record(*args) for args in values]
    negatives=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(values[0][0]);mutate(changed,name)
        try:check_record(changed,*values[0][1:])
        except ValueError as error:need(str(error)==reason,'native refusal unrelated negative '+name+': '+str(error))
        else:raise ValueError('native refusal accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason,mutationScope='in-memory-probe-record'))
    need(h.inventory(root)==before,'native refusal original changed')
    return dict(status='PARTIAL',case=case,original=admission.compact_original(original),probes=positive,negatives=negatives,
        originalPreserved=True,originalInventorySha256=h.digest(h.snapshot.f.canonical(collected['inventory'])),
        admittedRecoveryCompleted=True,wireAdmissionQualified=False,byteLimitQualified=False,wholeRuntimeResourcesQualified=False,
        cohortAdmitted=False,phase3Complete=False)


def run(root,case,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);receipt=dict(status='FAIL',phase3Complete=False)
    try:
        with overlap.progress('native-application-refusal',case):value=qualify(root,case)
        h.save(output/'qualification.json',value)
        from .remove_process_matrix import read as bounded_read
        need(bounded_read(output/'qualification.json')==value,'native refusal bounded result')
        receipt.update(status='PARTIAL',case=case,probes=len(value['probes']),negativeCases=len(value['negatives']),
            admittedRecoveryCompleted=True,originalPreserved=True,wholeRuntimeResourcesQualified=False,cohortAdmitted=False)
    except BaseException as error:receipt.update(failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--case',choices=admission.CASES,required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.root,a.case,a.output),sort_keys=True))
