"""Independent physical-prefix and public seven-query checks; no product token decoder."""
import copy
import json
from pathlib import Path
from scripts.v51 import runtime_evidence as physical, recovery_inspector as recovery
from scripts.v51 import performance_bundle as bundle, performance_artifacts, public_trace
from scripts.v51.performance_model import strict_json
from . import token
from .evidence import need, digest, encoded


def read(path): return strict_json(Path(path).read_bytes())


def context(root, traces):
    raw=(root/'node-1/manifest.gsr').read_bytes()
    manifest=dict(physical.f.inspect(raw,'MANIFEST'),digest=raw[16:48].hex())
    genesis=physical.f.inspect((root/'node-1/genesis.gsr').read_bytes(),'GENESIS')
    entries={};voters={}
    for node,rows in traces.items():
        for row in rows:
            if row['event']=='FORCE' and row['kind']=='ACCEPT':
                vote=physical.frame(row['record'],'ACCEPT',manifest)
                entry=physical.frame(vote['entry'],'ENTRY',manifest);entries[vote['entryDigest']]=entry
                voters.setdefault((vote['epoch'],vote['incarnation'],vote['entryDigest']),set()).add(node)
    chosen={key[2]:entries[key[2]] for key,nodes in voters.items() if len(nodes)>=2}
    return manifest,genesis,chosen


def prefix(snapshot, manifest, genesis, entries):
    indexes,initial=physical.application(physical.raw(genesis['application']))
    documents=dict(initial);sequence=genesis['baseSequence'];commands=[]
    for index,anchor in enumerate(snapshot['anchors'],1):
        need(anchor['entryDigest'] in entries,'unobserved read ancestor')
        entry=entries[anchor['entryDigest']];need(entry['index']==index,'read ancestor position')
        operation=entry['operation'];items=[]
        if operation in (1,2,4,5):
            items=physical.documents_command(physical.raw(entry['payload']))
            need(operation in (4,5) or len(items)==1,'single read-prefix mutation')
            for key,value in items:
                need((key in documents)==(operation in (2,5)),'read-prefix mutation precondition')
                documents[key]=value
            sequence+=1
        else: need(operation==9,'undeclared read fixture operation')
        commands.append(dict(operation=operation,documents=[dict(id=k,value=v) for k,v in items]))
    actual_indexes,actual=physical.application(physical.raw(snapshot['application']))
    need(indexes==actual_indexes and list(documents.items())==list(actual.items()) and sequence==snapshot['applicationSequence'],
         'read publication differs from chosen prefix')
    return dict(historyId=manifest['historyId'],sequence=sequence,commands=commands,
                documents=[dict(id=k,value=v) for k,v in documents.items()])


def oracle_inputs(root, traces):
    manifest,genesis,entries=context(root,traces);inputs={}
    for rows in traces.values():
        for row in rows:
            if row['event'] in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest)
                value=prefix(snapshot,manifest,genesis,entries);inputs[digest(encoded(value))]=value
    return inputs


def traces_at(root):return {f'node-{i}':public_trace.fault_rows(root,f'node-{i}') for i in (1,2,3)}


def validate(root, expected, queries, *, traces=None, history=None):
    root=Path(root).resolve();binding=read(root/'binding.json')
    need(binding==expected,'read source/build/run/attempt binding')
    need(read(root/'bundle-members.json')==bundle.members(root),'read raw inventory')
    need(all(digest((root/'artifacts'/name).read_bytes())==sha for name,sha in binding['artifacts'].items()),'read artifact binding')
    need(all(digest((root/name).read_bytes())==sha for name,sha in binding['classes'].items()),'read compiled consumer/control binding')
    location=performance_artifacts.EvidenceLocation(root,binding['origin'])
    traces=traces_at(root) if traces is None else traces
    history=read(root/'history.json') if history is None else history
    base=physical.validate(root,traces,evidence_location=location,require_restart=False)
    manifest,genesis,entries=context(root,traces);processes=read(root/'processes.json')
    need(len(processes)==3 and len({p['pid'] for p in processes})==3 and all(p['exitCode']==0 for p in processes),'three stopped public JVMs')
    pids={p['node']:p['pid'] for p in processes};attempts={a['opId']:a for a in history}
    need(len(attempts)==len(history),'duplicate public read operation')
    callbacks={};successes={};barriers=set();policies=set();local_reads=0
    for node,rows in traces.items():
        invoked={};admitted={};validated={};active=None;published={};latest=None;promised=0;calls={};forces={};installed=set();proofs=set()
        for row in rows:
            need(row['node']==node and row['pid']==pids[node] and row['generation']==1 and
                 row['manifestDigest']==manifest['digest'] and row['groupId']==manifest['groupId'],'read process/manifest identity')
            event=row['event'];pid=row['pid'];order=row['order']
            if event=='CLIENT_INVOKE':
                identity=row['opId'];need(identity in attempts and identity not in calls,'duplicate/unrecorded client invocation')
                attempt=attempts[identity]
                keys=(('kind',None),('documents',None)) if row['kind']=='addAll' else (
                        ('kind',None),('policy',None),('minimum',''),('waitTimeoutMillis',0))
                for key,default in keys:
                    need(row.get(key,default)==attempt.get(key,default),'controller/worker read options differ')
                calls[identity]=row
            elif event=='FORCE':
                value=physical.frame(row['record'],row['kind'],manifest)
                if row['kind']=='PROMISE':promised=value['epoch']
                if row['kind']=='ACCEPT':forces[value['entryDigest']]=order
                if row['kind']=='PROOF':proofs.add(digest(physical.raw(row['record'])))
            elif event=='REJOIN_INSTALLED':installed.add(row['snapshot'])
            elif event in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest);index=len(snapshot['anchors'])
                if event=='APPLICATION_RESTORED':need(index==0,'fresh public fixture restored a non-genesis prefix')
                if event=='LOCAL_PUBLISHED' and index:
                    need(digest(physical.raw(snapshot['terminalProof'])) in proofs or row['snapshot'] in installed,
                         'local publication precedes forced proof or verified install')
                value=prefix(snapshot,manifest,genesis,entries)
                need(digest(encoded(value)) in queries,'missing independently executed query control')
                published[index]=(snapshot,row['applicationGeneration'],value,order);latest=index
            elif event=='REPLICA_READ_INVOKED':
                need(row['readId'] not in invoked,'duplicate read invocation');invoked[row['readId']]=row
            elif event=='REPLICA_READ_ADMITTED':
                identity=row['readId'];need(identity in invoked and identity not in admitted,'read admission lacks own invocation');admitted[identity]=row
            elif event=='REPLICA_READ_CAPTURE_VALIDATED':
                identity=row['readId'];need(identity in admitted and identity not in validated,'read capture lacks own admission')
                request=invoked[identity];index=row['index'];need(index==latest and index in published,'read lacks exact current publication')
                snapshot,generation,value,publication_order=published[index]
                decoded=token.decode(physical.raw(row['token']))
                need(decoded==dict(version=1,groupId=manifest['groupId'],historyId=manifest['historyId'],manifestDigest=manifest['digest'],index=index),
                     'read token does not identify captured publication')
                need(row['historyId']==manifest['historyId'] and row['applicationGeneration']==generation and row['sequence']==value['sequence'],
                     'read sequence/generation differs from publication')
                need(request['policy']==row['policy'] and request['deadlineNanos']==row['deadlineNanos'] and
                     request['localNanos']<=row['captureNanos']<row['deadlineNanos'] and
                     request['order']<admitted[identity]['order']<order and publication_order<order,'read deadline/order/policy')
                need(1<=row['owned']<=15 and row['captured']==1 and row['waiting']+row['captured']+row['settling']==row['owned']
                     and row['alarms']<=row['waiting'] and row['highWater']<=15,'read ownership bounds')
                if row['policy']=='LEADER_STRONG':
                    proof=physical.frame(snapshot['terminalProof'],'PROOF',manifest);last=snapshot['anchors'][-1]['entryDigest']
                    need(row['barrierIndex']==index and row['barrierEpoch']==promised==proof['epoch'] and entries[last]['operation']==9
                         and request['order']<forces.get(last,0)<order and last not in barriers,'fresh strong read barrier')
                    barriers.add(last)
                elif row['policy']=='AT_LEAST_INDEX':
                    minimum=token.decode(physical.raw(request['minimum']))
                    need(all(minimum[k]==decoded[k] for k in ('version','groupId','historyId','manifestDigest')) and minimum['index']<=index,'minimum read bound/identity')
                else:need(row['policy']=='STALE_ALLOWED','unknown read policy')
                validated[identity]=(row,value)
            elif event=='REPLICA_READ_CAPTURED':
                identity=row['readId'];need(active is None and identity in validated,'overlapping/missing read capture')
                original,value=validated[identity]
                need(all(row[k]==original[k] for k in ('token','index','sequence','policy','applicationGeneration','captureNanos')),'changed captured cut')
                active=dict(capture=original,value=value,opId=None)
            elif event=='REPLICA_READ_CALLBACK':
                need(active is not None and active['opId'] is None and row['opId'] in calls,'callback lacks own public capture')
                active['opId']=row['opId'];request=invoked[active['capture']['readId']]
                call=calls[row['opId']]
                need(call['order']<request['order'],'public invocation after runtime read')
                need(all(call.get(k,default)==request.get(k,default) for k,default in
                         (('policy',None),('minimum',''),('waitTimeoutMillis',0))),'runtime read options differ from public call')
                active['callbackOrder']=order
            elif event=='REPLICA_READ_RELEASED':
                need(active is not None and active['opId'] is not None and row['token']==active['capture']['token'],'release lacks exact live view')
                need(active['opId'] not in callbacks,'callback invoked twice');active['releaseOrder']=order
                callbacks[active['opId']]=active;active=None
            elif event=='CLIENT_SUCCESS' and row['kind']=='read':
                identity=row['opId'];need(identity in callbacks and identity in attempts and identity not in successes,'success before view release')
                capture=callbacks[identity];cut=capture['capture'];request=calls[identity]
                need(capture['releaseOrder']<order and row['token']==cut['token'] and row['sequence']==cut['sequence'] and row['policy']==request['policy']==cut['policy'],
                     'response changed policy/token/sequence')
                need(row['report']==queries[digest(encoded(capture['value']))] and row['documents']==capture['value']['documents'],'query differs from published V4.4 prefix replay')
                attempt=attempts[identity]
                need(attempt['node']==node and attempt['pid']==pid and attempt['generation']==1 and attempt['response']=={k:v for k,v in row.items()
                     if k not in ('event','order','pid','generation','localNanos','node','groupId','manifestDigest')},'controller/worker read response differs')
                need(attempt['outcome']=='SUCCESS' and attempt['startNanos']<attempt['endNanos'],'public response interval')
                policies.add(row['policy']);local_reads+=row['policy']!='LEADER_STRONG';successes[identity]=row
            elif event=='CLIENT_SUCCESS' and row['kind']=='addAll':
                identity=row['opId'];need(identity in attempts and identity in calls,'unrecorded bulk response')
                attempt=attempts[identity]
                need(attempt['node']==node and attempt['pid']==pid and attempt['outcome']=='SUCCESS' and
                     attempt['documents']==calls[identity]['documents']==row['documents'] and
                     attempt['response']=={k:v for k,v in row.items() if k not in
                         ('event','order','pid','generation','localNanos','node','groupId','manifestDigest')},'controller/worker bulk response differs')
        need(active is None,'unreleased public view')
    reads=[a for a in history if a['kind']=='read']
    need(len(successes)==len(reads) and policies=={'LEADER_STRONG','STALE_ALLOWED','AT_LEAST_INDEX'} and local_reads>=3,'incomplete public policy matrix')
    writes=[a for a in history if a['kind']=='addAll'];strong=[a for a in reads if a['policy']=='LEADER_STRONG']
    need(len(writes)==3 and strong and all(w['outcome']=='SUCCESS' and w['endNanos']<strong[0]['startNanos'] for w in writes),
         'missing confirmed-write-before-token ordering')
    return dict(status='PASS',execution='public-replica-read-three-jvm',paidCloud=False,reads=len(reads),policies=sorted(policies),physical=base)


def negatives(root,expected,queries):
    original=traces_at(root);history=read(Path(root)/'history.json');validate(root,expected,queries,traces=original,history=history)
    cases=[]
    for name,event,field,value in (
            ('changed-token','CLIENT_SUCCESS','token','AA=='),
            ('changed-policy','CLIENT_SUCCESS','policy','STALE_ALLOWED'),
            ('changed-sequence','CLIENT_SUCCESS','sequence',-1),
            ('changed-generation','REPLICA_READ_CAPTURE_VALIDATED','applicationGeneration',999),
            ('capture-at-deadline','REPLICA_READ_CAPTURE_VALIDATED','captureNanos',None),
            ('changed-public-wait','CLIENT_INVOKE','waitTimeoutMillis',17),
            ('changed-public-minimum','CLIENT_INVOKE','minimum','AA=='),
            ('changed-query','CLIENT_SUCCESS','report',{})):
        changed=copy.deepcopy(original)
        target=next(r for rows in changed.values() for r in rows if r['event']==event and r.get('policy')=='LEADER_STRONG')
        target[field]=target['deadlineNanos'] if value is None else value
        try:validate(root,expected,queries,traces=changed,history=history)
        except ValueError as error:cases.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('invalid public read evidence accepted: '+name)
    for event in ('REPLICA_READ_RELEASED','REPLICA_READ_ADMITTED','FORCE'):
        changed={n:[r for r in rows if r['event']!=event] for n,rows in original.items()}
        try:validate(root,expected,queries,traces=changed,history=history)
        except ValueError as error:cases.append(dict(case='missing-'+event.lower(),status='REJECTED',reason=str(error)))
        else:raise ValueError('missing public evidence accepted: '+event)
    return cases
