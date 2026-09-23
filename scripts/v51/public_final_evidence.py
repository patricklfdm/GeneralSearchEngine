"""Independent causal checks for delayed heartbeat fencing and lost authority."""
import copy
import json
from pathlib import Path
from . import runtime_evidence as a, storage_inspector as storage, public_recovery_evidence as recovery
from .public_selection_evidence import paused, higher_between
from .public_promise_evidence import retained_files
from .storage_harness import ROOT, need

CUTS = {'heartbeat-request': 'WIRE_AFTER_REQUEST_READ_HEARTBEAT',
        'heartbeat-response': 'WIRE_AFTER_RESPONSE_READ_HEARTBEAT'}


def refused(operations, identities, node, after):
    need(len(identities)==2 and len(set(identities))==2, 'missing independent read/write refusal')
    for identity, kind, outcome in zip(identities, ('read', 'addAll'), ('NOT_APPLICABLE', 'NOT_SUBMITTED')):
        op = operations[identity]
        need(op['node']==node and op['kind']==kind and op['outcome']==outcome
             and op['startNanos']>after and op['endNanos']>op['startNanos']
             and op.get('reasonCode') in ('NOT_LEADER', 'QUORUM_UNAVAILABLE', 'STALE_EPOCH'), 'unsafe public refusal')


def validate(root, traces, history, receipt):
    root=Path(root); case=receipt['case']; operations={h['opId']:h for h in history}
    encoded=(root/'node-1/manifest.gsr').read_bytes()
    manifest=dict(a.f.inspect(encoded, 'MANIFEST'), digest=encoded[16:48].hex())
    if case in CUTS:
        node=receipt['target']; old=receipt['oldLeader']; need(node==('node-3' if case=='heartbeat-request' else old), 'wrong held endpoint')
        boundary,released,own=paused(traces[node], receipt['pause'], CUTS[case])
        request=a.f.wire(a.raw(boundary['request']), manifest)
        need(request['type']=='HEARTBEAT' and request['sender']==old and request['epoch']==receipt['oldEpoch'], 'wrong held heartbeat')
        promise=higher_between(own, receipt['pause'], released, receipt['higherPromise'], request['epoch'])
        delivered=receipt['delivered']
        need(delivered in own and delivered['pid']==released['pid'] and delivered['order']>released['order']
             and delivered['request']==boundary['request'] and delivered['event']==('REPLY' if case=='heartbeat-request' else 'RECEIVED'), 'held heartbeat was not processed after release')
        response=a.f.wire(a.raw(delivered['frame']), manifest)
        if case=='heartbeat-request':
            need(request['recipient']==node and response['type']=='REJECT' and response['payload']['reason']=='STALE_EPOCH'
                 and response['payload']['promised']['epoch']>=promise['epoch'], 'stale heartbeat reset follower instead of rejection')
        else:
            need(response['type']=='HEARTBEAT_ACK' and response['epoch']==request['epoch']
                 and delivered['frame']==boundary['frame'], 'old heartbeat acknowledgement replaced')
        for key,kind in [('majorityRead','read'),('majorityWrite','addAll')]:
            op=operations[receipt[key]]
            need(op['node']==receipt['newLeader']!=old and op['kind']==kind and op['outcome']=='SUCCESS', 'missing new majority service')
        refused(operations, receipt['denied'], old, operations[receipt['majorityWrite']]['endNanos'])
        for identity in receipt['denied']:
            op=operations[identity]
            invocation=next(r for r in traces[old] if r['event']=='CLIENT_INVOKE' and r.get('opId')==identity)
            promises=[r for r in traces[old] if r['pid']==op['pid'] and r['event']=='FORCE' and r['kind']=='PROMISE'
                      and a.f.inspect(a.raw(r['record']), 'PROMISE')['epoch']>request['epoch'] and r['order']<invocation['order']]
            need(promises, 'refusal not fenced by actual higher promise')
            if node==old: need(invocation['order']>delivered['order'], 'refusal predates delayed acknowledgement')
        retained_files(root, old, receipt['retained'])
        starts=[r for r in traces[old] if r['event']=='STARTED']
        need(len(starts)==2 and len({r['pid'] for r in starts})==2 and {r['generation'] for r in starts}=={1,2}, 'missing retained restart')
        later=operations[receipt['laterWrite']]; final=operations[receipt['finalRead']]
        need(later['outcome']==final['outcome']=='SUCCESS' and later['kind']=='addAll' and final['kind']=='read'
             and later['endNanos']<final['startNanos'] and final['documents']==receipt['expected'], 'missing post-restart service')
        return dict(status='PASS', retiredEpoch=request['epoch'], promisedEpoch=promise['epoch'], heldType=response['type'])

    need(case in ('one-disk-loss','two-disk-loss'), 'unknown final coverage case')
    victims={'node-3'} if case=='one-disk-loss' else {'node-2','node-3'}
    need(set(receipt['retiredVoters'])==set(receipt['probes'])==victims
         and {r['node'] for r in receipt['losses']}==victims and len(receipt['losses'])==len(victims), 'missing disk loss')
    for loss in receipt['losses']:
        node=loss['node']; before=receipt['retiredVoters'][node]
        need(loss['exitCode']==-9 and any(r['event']=='STARTED' and r['pid']==loss['pid'] for r in traces[node]), 'wrong stopped process')
        storage.inspect_archive(root/'lost'/node, root/node, before)
        recovery.admission(before, storage.inventory(root/'lost'/node), receipt['probes'][node])
        for attempt, result in enumerate(receipt['probes'][node], 1):
            need(json.loads((root/f'absent-{node}-{attempt}.stdout').read_text())==result, 'missing raw startup refusal')
    after=max(r['atNanos'] for r in receipt['losses'])
    if case=='one-disk-loss':
        write=operations[receipt['survivorWrite']]; read=operations[receipt['survivorRead']]
        need(write['outcome']==read['outcome']=='SUCCESS' and write['kind']=='addAll' and read['kind']=='read'
             and write['node'] not in victims and read['node'] not in victims
             and after<write['startNanos']<write['endNanos']<read['startNanos'], 'missing surviving majority service')
    else: refused(operations, receipt['denied'], 'node-1', after)
    backup=receipt['backup']; op=operations[receipt['backupOperation']]
    need(op['kind']=='backup' and op['outcome']=='SUCCESS' and op['response']==backup and op['endNanos']<min(r['atNanos'] for r in receipt['losses']), 'backup not completed before loss')
    need(any(r['event']=='CLIENT_SUCCESS' and r.get('opId')==op['opId'] and r.get('contentIdentity')==backup['contentIdentity']
             and r.get('sequence')==backup['sequence'] and r.get('sourceHistory')==backup['sourceHistory'] for r in traces[op['node']]), 'backup lacks public completion')
    need(storage.inventory(root/'backup')==storage.inventory(root/'new-group/import-backup')==receipt['backupInventory'], 'backup bytes changed')
    control=receipt['control']; pins=json.loads((ROOT/'docs/v5x/v5.1/published-controls.json').read_text())
    need(any(p['version']=='4.4.0' and p['artifact']=='general-search-engine' and p['sha256']==control['jarSha256'] for p in pins['artifacts']), 'unpublished backup control')
    raw=json.loads((root/'published-v44.stdout').read_text())
    need(raw=={k:control[k] for k in ('sequence','documents')} and control['sequence']==backup['sequence']
         and control['documents']==receipt['backupDocuments'], 'published restore differs from backup cut')
    newroot=root/'new-group'; recovery.imported(newroot, control)
    newmanifest=a.f.inspect((newroot/'node-1/manifest.gsr').read_bytes(), 'MANIFEST')
    need(newmanifest['groupId']!=manifest['groupId'] and newmanifest['historyId'] not in (manifest['historyId'], backup['sourceHistory']), 'lost authority reused old group/history')
    newhistory=json.loads((newroot/'history.json').read_text()); newops={h['opId']:h for h in newhistory}
    first=newops[receipt['newInitialRead']]; last=newops[receipt['newFinalRead']]
    need(first['outcome']==last['outcome']=='SUCCESS' and first['kind']==last['kind']=='read'
         and first['documents']==control['documents'] and last['documents']==receipt['newExpected']
         and after<first['startNanos']<first['endNanos']<last['startNanos'], 'new group did not preserve verified cut before later service')
    return dict(status='PASS', lostDisks=len(victims), refusedStarts=2*len(victims), backupSequence=backup['sequence'], newGroupId=newmanifest['groupId'])


def negatives(root, traces, history, receipt):
    cases=[]
    mutations=['missing-refusal','false-success','missing-higher-promise','missing-delivery','changed-held-epoch'] if receipt['case'] in CUTS else [
        'missing-probe','false-start-success','changed-archive','changed-backup-cut','changed-backup-order','unpublished-control']
    for name in mutations:
        t=copy.deepcopy(traces); h=copy.deepcopy(history); r=copy.deepcopy(receipt)
        if name=='missing-refusal': r['denied']=r['denied'][:1]
        elif name=='false-success': next(o for o in h if o['opId']==r['denied'][0])['outcome']='SUCCESS'
        elif name=='missing-higher-promise': t[r['target']].remove(r['higherPromise'])
        elif name=='missing-delivery': t[r['target']].remove(r['delivered'])
        elif name=='changed-held-epoch': r['oldEpoch']+=1
        elif name=='missing-probe': r['probes']['node-3'].pop()
        elif name=='false-start-success': r['probes']['node-3'][0]['outcome']='SUCCESS'
        elif name=='changed-archive': r['retiredVoters']['node-3']['manifest.gsr']['sha256']='0'*64
        elif name=='changed-backup-cut': r['backup']['sequence']+=1
        elif name=='changed-backup-order': r['backupDocuments'].reverse()
        else: r['control']['jarSha256']='0'*64
        try: validate(root,t,h,r)
        except ValueError as error: cases.append(dict(case=name,status='REJECTED',reason=str(error)))
        else: raise ValueError('final coverage oracle admitted '+name)
    if receipt['case'] not in CUTS:
        from . import public_qualification_evidence as physical
        op=next(h for h in history if h['opId']==receipt['backupOperation'])
        for name in ('backup-without-invocation','backup-without-release','backup-wrong-view-sequence'):
            changed=copy.deepcopy(traces); rows=changed[op['node']]
            invoke=next(r for r in rows if r['event']=='CLIENT_INVOKE' and r.get('opId')==op['opId'])
            complete=next(r for r in rows if r['event']=='CLIENT_SUCCESS' and r.get('opId')==op['opId'])
            if name=='backup-without-invocation': rows.remove(invoke)
            elif name=='backup-without-release':
                release=next(r for r in rows if r['pid']==op['pid'] and r['event']=='READ_RELEASED' and invoke['order']<r['order']<complete['order'])
                rows.remove(release)
            else: complete['sequence']+=1
            try: physical.physical(root,[h for h in history if h['kind'] in ('read','addAll')],changed,retired_voters=receipt['retiredVoters'])
            except ValueError as error: cases.append(dict(case=name,status='REJECTED',reason=str(error)))
            else: raise ValueError('backup capture oracle admitted '+name)
    return cases
