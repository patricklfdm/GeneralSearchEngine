"""Owned healthy V5.0 evidence: sealed 1.1 bytes and serialized public calls.

Reuse the configured force/quorum oracle. Reads use the already published prefix;
the published control has no V5.1 per-read NO_OP or capture/release protocol.
"""
from copy import deepcopy
from pathlib import Path
import uuid
from scripts.v50 import admission_format as f, runtime_format as runtime
from . import cloud_package as package, performance_model as m, performance_plan as plan, performance_physical as physical
from . import performance_evidence as legacy, guest_authority as authority


def member(directory, cfg):
    directory=Path(directory);node=cfg['binding']['node']
    # This bounded healthy slice never rotates a generation or performs recovery.
    m.need(set(authority.inventory(directory))==set(f.ROOT_FILES)|{'bootstrap-prepared.gsr','bootstrap-seal.gsr'},
           'configured healthy authority inventory')
    raw=(directory/'genesis.gsr').read_bytes();genesis=f.genesis(raw);genesis['raw']=raw
    manifest_raw=(directory/'manifest.gsr').read_bytes();manifest=f.manifest(manifest_raw,genesis)
    m.need(manifest['group']==uuid.UUID(cfg['groupId']).bytes and manifest['members']==[
        ('node-'+str(i+1),host,port) for i,(host,port) in enumerate(zip(cfg['hosts'],cfg['ports']))] and
        manifest['leader']==package.control_node(cfg) and manifest['configuration']=='phase6-local-v1' and
        (manifest['codec'],manifest['codecVersion'],manifest['schema'])==('semantic-codec',1,'semantic-schema'),
        'guest physical manifest topology')
    initial=m.initial(plan.load())
    m.need(genesis['source'][0]==1 and genesis['base']==initial.sequence and genesis['app']==initial.application(),
           'configured physical genesis corpus')
    report=runtime.inspect(directory)
    m.need(report['node']==node and report['origin']==0, 'configured physical authority owner')
    seal=f.record((directory/'bootstrap-seal.gsr').read_bytes(),20)
    m.need(seal.text()==node,'configured physical seal owner');receipt=seal.blob();seal.end()
    descriptor,inventories=f.plan(f.record(receipt,19).blob(),manifest,genesis,manifest_raw)
    original=Path(cfg['root'])
    for replica in descriptor['replicas']:
        for bound,wanted in ((replica['target'],original/replica['node']),
                             (replica['materialization']['directory'],original/('app-'+replica['node']))):
            m.need(bound['path']==str(wanted) and bound['parentRealPath']==str(original),
                   'configured physical original sealed path')
    # Bind initialization markers too, not just the evolving journals. These are
    # their original planned bytes; inode/store metadata is never compared to the
    # collector machine's filesystem.
    for name,kind,size,digest in inventories[manifest['nodes'].index(node)]:
        if name in ('entries.gsr','proofs.gsr','promises.gsr'):continue
        data=(directory/name).read_bytes()
        m.need(len(data)==size and f.sha(data)==digest,'configured physical initial bytes')
    return manifest


def observations(root, traces, exchanges):
    """Bind every client observation to original exchanges and physical prefixes."""
    raw=(root/'node-1/genesis.gsr').read_bytes();genesis=f.genesis(raw);genesis['raw']=raw
    manifest=f.manifest((root/'node-1/manifest.gsr').read_bytes(),genesis);leader=manifest['leader']
    state=m.application(genesis['app'],genesis['base']);prefixes={0:state.copy()}
    journals={node:{kind:set(runtime.journal(root/node/file,number,manifest,node)) for kind,file,number in
        [('ENTRY','entries.gsr',5),('PROOF','proofs.gsr',6),('PROMISE','promises.gsr',4)]} for node in traces}
    for raw in runtime.journal(root/leader/'entries.gsr',5,manifest,leader):
        r=f.record(raw,5,1<<20);r.take(56);index,op=r.number('q'),r.number('B');r.take(48)
        size=r.number('i');r.take(32);state.apply(op,r.take(size));r.end();prefixes[index]=state.copy()
    for node,events in traces.items():
        original=iter(exchanges[node]);current=None;published=0;before=0
        for event in events:
            kind=event['event']
            if kind=='FORCE':
                m.need(physical.raw(event['record']) in journals[node].get(event['kind'],set()),
                       'configured force differs from retained bytes')
            elif kind=='AFTER_APPLICATION_PUBLICATION' and node==leader:
                m.need(event['index']==published+1 and event['index'] in prefixes,'configured publication prefix order')
                published=event['index']
            elif kind=='CLIENT_INVOKE':
                m.need(current is None,'configured overlapping invocation')
                current=next(original,None);before=published
                observed={k:v for k,v in event.items() if k not in ('event','localNanos','order','node','pid','window')}
                wanted={} if current is None else {k:v for k,v in current['request'].items() if k!='window'}
                m.need(current is not None and observed==wanted,'configured original invocation binding')
            elif kind=='CLIENT_RESULT':
                m.need(current is not None,'configured result without invocation')
                observed={k:v for k,v in event.items() if k not in ('event','localNanos','order','window')}
                m.need(observed==current['response'],'configured original result binding')
                m.need(event['outcome']=='SUCCESS','configured unsuccessful original response')
                if event['command']=='call':
                    call=event['call'];cut=prefixes[published]
                    m.need(node==leader and call['beforeSequence']==prefixes[before].sequence and
                           call['afterSequence']==cut.sequence,'configured call published sequence')
                    if call['operation'] not in m.OP_IDS:
                        answer=cut.answer(call['operation'],call['cycle'])
                        m.need(before==published and call['answer']==answer and call['answerSha256']==m.sha(m.canonical(answer)),
                               'configured read differs from published prefix')
                elif event['command']=='backup':
                    m.need(node==leader and before==published and event['sequence']==prefixes[published].sequence,
                           'configured backup published sequence')
                current=None
        m.need(current is None and next(original,None) is None,'configured original trace coverage')


def audit(root, calls, traces, exchanges, *, final_sequence):
    observations(root,traces,exchanges)
    return legacy.configured_physical(root,calls,traces,final_sequence=final_sequence)


def qualify(root, calls, traces, exchanges, *, final_sequence):
    result=audit(root,calls,traces,exchanges,final_sequence=final_sequence)  # Reject a bad original before mutations.
    negatives=[];leader=_manifest(root)['leader']
    cases={
        'missing-invocation':'configured result without invocation',
        'changed-invocation':'configured original invocation binding',
        'changed-result':'configured original result binding',
        'failed-original':'configured unsuccessful original response',
        'changed-sequence':'configured call published sequence',
        'resealed-read':'configured read differs from published prefix',
        'foreign-force':'configured force differs from retained bytes',
        'missing-publication':'configured call published sequence',
        'missing-leader-proof':'configured publication before proof quorum',
        'missing-proof-ack':'configured publication before proof quorum',
    }
    for name,reason in cases.items():
        changed=deepcopy(traces);originals=deepcopy(exchanges);rows=changed[leader]
        invoke=next(r for r in rows if r['event']=='CLIENT_INVOKE' and r['command']=='call')
        response=next(r for r in rows if r['event']=='CLIENT_RESULT' and r['command']=='call')
        if name=='missing-invocation':rows.remove(invoke)
        elif name=='changed-invocation':invoke['opId']='borrowed'
        elif name=='changed-result':response['pid']+=1
        elif name in ('failed-original','changed-sequence','resealed-read'):
            if name=='resealed-read':response=next(r for r in rows if r['event']=='CLIENT_RESULT' and r.get('call',{}).get('operation')=='GET')
            exchange=next(e for e in originals[leader] if e['response']['opId']==response['opId'])
            for target in (response,exchange['response']):
                if name=='failed-original':target['outcome']='FAILED'
                elif name=='changed-sequence':target['call']['beforeSequence']+=1
                else:target['call'].update(answer='changed',answerSha256=m.sha(m.canonical('changed')))
        elif name=='foreign-force':next(r for r in rows if r['event']=='FORCE')['record']='AA=='
        elif name=='missing-publication':
            rows.remove(next(r for r in rows if r['event']=='AFTER_APPLICATION_PUBLICATION' and r['index']==2))
        elif name=='missing-leader-proof':rows[:]=[r for r in rows if not(r['event']=='FORCE' and r['kind']=='PROOF')]
        else:rows[:]=[r for r in rows if not(r['event']=='RECEIVED' and
            f.wire(physical.raw(r['frame']),_manifest(root))['type']=='COMMIT_PROOF_ACK')]
        try:audit(root,calls,changed,originals,final_sequence=final_sequence)
        except ValueError as error:
            m.need(str(error)==reason,'configured negative reason: '+name+': '+str(error))
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('configured negative accepted: '+name)
    return result,negatives


def _manifest(root):
    raw=(root/'node-1/genesis.gsr').read_bytes();g=f.genesis(raw);g['raw']=raw
    return f.manifest((root/'node-1/manifest.gsr').read_bytes(),g)
