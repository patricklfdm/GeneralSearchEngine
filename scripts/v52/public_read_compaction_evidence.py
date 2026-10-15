"""An old token outlives actual two-source retirement and snapshot installation."""
import copy
from . import public_reads_evidence as e,public_read_lifecycle_evidence as lifecycle,token
from .evidence import need
from scripts.v51 import public_reclamation_evidence as reclamation,rejoin_evidence as rejoin

CASES=('token-below-floor',)


def schedule(root,traces,history,processes):
    details=e.read(root/'read-compaction.json');need(details['scenario']==CASES[0],'read compaction scenario')
    attempts={a['opId']:a for a in history};carried=attempts[details['carriedOp']]['response'];lower=token.decode(e.physical.raw(carried['token']))
    leader=details['leader'];follower=details['follower'];manifest=e.context(root,traces)[0]
    need(all(a['outcome']=='SUCCESS' for a in history),'compaction unsuccessful public call')
    for process in processes:lifecycle.ownership([r for r in traces[process['node']] if r['pid']==process['pid']],False)
    selected=e.physical.frame(details['selectedBeforeIsolation'],'SELECTED',manifest)
    need(any(r['event']=='PROMISE_QUORUM' and r['selected']==details['selectedBeforeIsolation'] for r in traces[leader]) and
         follower not in {v['node'] for v in selected['bases']},'compaction removed selected quorum')
    baseline=details['baselineFloor'];need(baseline in traces[leader] and baseline['event']=='RECOVERY_FLOOR' and baseline['index']==lower['index'],'missing original token floor')
    old=rejoin.packet(baseline['local'],manifest);old_generation=old['selector']['generation']
    need(len(old['snapshot']['anchors'])==lower['index'],'old token source index')
    for node,key in ((leader,'leaderRead'),(follower,'followerRead')):
        rows=traces[node];attempt=attempts[details[key]]
        invoke=next(r for r in rows if r['event']=='CLIENT_INVOKE' and r['opId']==attempt['opId'])
        floors=[r for r in rows if r['event']=='RECOVERY_FLOOR' and r['index']>lower['index'] and r['order']<invoke['order']]
        need(floors,'minimum read preceded actual newer floor');floor_event=floors[-1]
        files={p.relative_to(root/node).as_posix():p.read_bytes() for p in (root/node).rglob('*') if p.is_file()}
        floor,packets,sources=reclamation.floor_state(files,manifest,node)
        need(floor['index']==floor_event['index']>lower['index'],'durable newer floor mismatch')
        local=rejoin.packet(floor_event['local'],manifest);remote=rejoin.packet(floor_event['remote'],manifest)
        need({local['seal']['node'],remote['seal']['node']}=={v['node'] for v in floor['sources']} and
             local['sealDigest'] in {v['generationDigest'] for v in floor['sources']} and
             remote['sealDigest'] in {v['generationDigest'] for v in floor['sources']},'floor event source binding')
        reclamation.require_download(packets,node,floor_event,reclamation.downloads(rows,manifest))
        generation=local['selector']['generation']
        for name,kind in (('accepted.gsr','ACCEPT'),('proofs.gsr','PROOF')):
            need(not reclamation.journal_rows(files[generation+'/'+name],kind,manifest),'current source still needs old journal entries')
        need(attempt['node']==node and attempt['policy']=='AT_LEAST_INDEX' and attempt['minimum']==carried['token'] and
             attempt['response']['sequence']==carried['sequence']+1 and
             token.decode(e.physical.raw(attempt['response']['token']))['index']==floor['index'],'below-floor minimum result')
        need(attempt['response']['documents']==details['documents'],'below-floor application changed')
        if node==leader:
            need(generation!=old_generation and not (root/node/old_generation).exists(),'old token retained previous generation')
            cuts=[r for r in rows if r['event']=='STORAGE_CUT' and r['cut']=='DELETE_AFTER_DIRECTORY' and
                  baseline['order']<r['order']<floor_event['order']]
            need(cuts,'missing physical prior-generation deletion')
            need(any(not any(name.startswith(old_generation+'/') for name in reclamation.authority(r)) for r in cuts),
                 'old generation not deleted at observed cut')
        else:
            installs=[r for r in rows if r['event']=='REJOIN_INSTALLED' and r['order']<invoke['order'] and
                      len(e.recovery.snapshot(e.physical.raw(r['snapshot']),manifest)['anchors'])==floor['index']]
            need(installs and any(r['event']=='NETWORK_DROP' for rs in traces.values() for r in rs),'missing actual isolated-follower snapshot catch-up')
    return dict(status='PASS',oldIndex=lower['index'],newFloor=floor['index'])


def negatives(root,binding,queries):
    cases=e.negatives(root,binding,queries);original=e.traces_at(root);details=e.read(root/'read-compaction.json')
    for node in (details['leader'],details['follower']):
        traces=copy.deepcopy(original);old=details['baselineFloor']['index']
        traces[node]=[r for r in traces[node] if not (r['event']=='RECOVERY_FLOOR' and r['index']>old)]
        try:e.validate(root,binding,queries,traces=traces)
        except ValueError as error:
            need(str(error)=='minimum read preceded actual newer floor','unexpected compaction negative: '+str(error))
            cases.append(dict(case='missing-newer-floor-'+node,status='REJECTED',reason=str(error)))
        else:raise ValueError('old floor accepted as compaction evidence')
    traces=copy.deepcopy(original);leader=details['leader']
    traces[leader]=[r for r in traces[leader] if not (r['event']=='STORAGE_CUT' and r['cut']=='DELETE_AFTER_DIRECTORY')]
    try:e.validate(root,binding,queries,traces=traces)
    except ValueError as error:
        need(str(error)=='missing physical prior-generation deletion','unexpected deletion negative: '+str(error))
        cases.append(dict(case='missing-prior-generation-deletion',status='REJECTED',reason=str(error)))
    else:raise ValueError('compaction without physical deletion accepted')
    return cases
