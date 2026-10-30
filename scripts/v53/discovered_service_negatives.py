"""Original-first mutation qualification for one native discovered history."""
import base64
import copy
from pathlib import Path
import shutil
import tempfile
from . import discovered_service_evidence as d

NEGATIVES = {
    'final-selector': 'admitted exact after-close: node-2',
    'final-image': 'admitted exact after-close: node-2',
    'final-future': 'admitted exact after-close: node-1',
    'final-ledger': 'admitted exact after-close: node-4',
    'inactive-generation': 'admitted exact after-close: node-4',
    'unselected-owner': 'discovered selection unselected owner unchanged',
    'removed-owner-vote': 'discovered transition removed owner remains fenced',
    'extra-original-file': 'context selection discovered service history inventory',
    'preparation-owner': 'discovered service preparation order/owners',
    'preparation-force': 'selected retention force order: discovered service preparation proof-7',
    'missing-ready': 'discovered service exact round lifecycle',
    'forged-ready': 'discovered service ready after fresh barrier',
    'forged-completion': 'discovered service original round completion',
    'missing-floor-force': 'selected retention force order: discovered service slot 8 node-1',
    'early-floor': 'discovered service original source before dependent force',
    'missing-quorum': 'discovered service exact future quorums',
    'early-quorum': 'discovered service local recording before quorum',
    'early-publication': 'discovered service all quorums before publication send',
    'applied-boundary': 'discovered service exact slot boundary',
    'missing-delivery': 'discovered selection response delivered',
    'changed-source': 'discovered service source exact data',
    'wrong-vote-ack': 'discovered service exact control acknowledgement',
    'wrong-future-ack': 'discovered service exact control acknowledgement',
    'wrong-publish-ack': 'discovered service exact control acknowledgement',
    'wrong-apply-sequence': 'discovered service separate control trace',
    'wrong-recording-sequence': 'discovered service exact recording trace',
    'wrong-publication-trace': 'discovered service publication bound to recording',
    'fourth-attempt': 'discovered selection identical bounded attempts',
    'extra-delivery': 'discovered service received without original offer',
    'foreign-rejection': 'discovered service unselected rejection classification',
    'fourth-rejection': 'discovered service bounded failed exchange',
    'producer-claims-autonomy': 'discovered service producer scope',
}


def mutate(path, name):
    c,e,f = d.c,d.e,d.f
    targets = {'final-selector':'after-close/node-2/selector.gsr',
        'final-future':'after-close/node-1/'+d.native.future.FILE,
        'final-ledger':'after-close/node-4/'+d.s.FILE,
        'unselected-owner':'after-close/node-3/allocator.gsr',
        'removed-owner-vote':'after-close/node-5/grants.gsr'}
    if name in targets: (path/targets[name]).write_bytes(b'changed'); return
    if name in ('final-image','inactive-generation'):
        node = 'node-2' if name == 'final-image' else 'node-4'
        own = path/'after-close'/node; files = c.inventory(own); directory,_,packet = c.current(files)
        if name == 'final-image': target = directory+packet['capsule']['application']+'.image'
        else: target = next(k for k in files if k.startswith('generations/') and not k.startswith(directory) and k.endswith('generation.gsr'))
        (own/target).write_bytes(b'changed'); return
    if name == 'extra-original-file': (path/'unexpected').write_bytes(b'changed'); return
    if name.startswith('preparation-'):
        rows = d.native.read(path/'calls.json')
        row = next(v for v in rows if v['operation'] == 'proof-7')
        if name == 'preparation-owner': row['node'] = 'node-5'
        else: row['events'].remove('PROOF_PARENT_FORCED')
        (path/'calls.json').write_bytes(f.canonical(rows)); return
    if name.endswith('rejection'):
        rows = d.native.read(path/'failures.json')
        if name == 'foreign-rejection': rows[0]['node'] = 'node-5'
        else: rows[-1] = copy.deepcopy(rows[0])
        (path/'failures.json').write_bytes(f.canonical(rows)); return
    if name == 'producer-claims-autonomy':
        target = path/'discovered-transition-result.json'; row = d.native.read(target); row['autonomousElection'] = True
        target.write_bytes(f.canonical(row)); return

    events = d.native.read(path/'events.json'); rows = d.native.read(path/'wire.json')
    start = next(i for i,v in enumerate(events) if v['event'] == 'ROUND_SLOT_BEGIN')
    stop = next(i for i,v in enumerate(events) if v['event'] == 'ROUND_SLOT_COMPLETE')
    def event(kind, node=None):
        return next(v for v in events[start:stop] if v['event'] == kind and (node is None or v['node'] == node))
    if name == 'missing-ready': events.remove(next(v for v in events if v['event'] == 'ROUND_BEFORE_READY'))
    elif name == 'forged-ready': next(v for v in events if v['event'] == 'ROUND_BEFORE_READY')['record'] = '0'*64
    elif name == 'forged-completion': events[stop]['record'] = '0'*64
    elif name == 'missing-floor-force': events.remove(event('FLOOR_PARENT_FORCED','node-1'))
    elif name == 'early-floor':
        # Preserve the required force sequence while moving the whole floor
        # authority block before its source copies arrive.
        block = [event(k,'node-1') for k in ('FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED')]
        for item in block: events.remove(item)
        events[start+1:start+1] = block
    elif name == 'missing-quorum': events.remove(event('SLOT_FUTURE_QUORUM_COMPLETE'))
    elif name in ('early-quorum','early-publication'):
        row = event('SLOT_FUTURE_QUORUM_COMPLETE' if name == 'early-quorum' else 'PUBLICATION_SEND_BOUNDARY')
        events.remove(row); events.insert(start+1,row)
    elif name == 'applied-boundary': event('SLOT_APPLIED')['voters'] = ['node-1','node-2','node-3']
    elif name == 'extra-delivery':
        row = copy.deepcopy(event('NETWORK_RECEIVED')); row['response'] = '0'*64; events.append(row)
    else:
        kinds = {'missing-delivery':'CHUNK','changed-source':'CHUNK','wrong-vote-ack':'ACCEPT',
            'wrong-future-ack':'FUTURE_RETENTION_INTENT','wrong-publish-ack':'PUBLISH',
            'wrong-apply-sequence':'APPLY','wrong-recording-sequence':'FUTURE_RETENTION_INTENT',
            'wrong-publication-trace':'PUBLISH','fourth-attempt':'ACCEPT'}
        offers = {v['request'] for v in events[start:stop] if v['event'] == 'WIRE_RESPONSE'}
        victim = next(v for v in rows if e.digest(base64.b64decode(v['request'])) in offers and
            d.selection.d.transfer.t.wire(v['request'])[0] == kinds[name] and
            (name != 'changed-source' or d.selection.d.transfer.t.wire(v['response'])[0] == 'CHUNK') and
            (name != 'wrong-recording-sequence' or d.selection.d.transfer.t.wire(v['request'])[1]['recipient']['node'] == 'node-2'))
        qraw, rraw = (base64.b64decode(victim[k]) for k in ('request','response'))
        qhash,rhash = e.digest(qraw),e.digest(rraw)
        if name == 'missing-delivery': events = [v for v in events if not(v['event'] == 'NETWORK_RECEIVED' and v['response'] == rhash)]
        elif name == 'fourth-attempt':
            original = next(v for v in events if v['event'] == 'WIRE_RESPONSE' and v['request'] == qhash)
            for _ in range(4-sum(v == victim for v in rows)):
                rows.insert(rows.index(victim),copy.deepcopy(victim)); events.insert(events.index(original),copy.deepcopy(original))
        else:
            kind,q = d.selection.d.transfer.t.wire(victim['request']); answer,r = d.selection.d.transfer.t.wire(victim['response'])
            if name == 'changed-source':
                data = bytearray(base64.b64decode(r['payload']['bytes'])); data[-1] ^= 1
                r['payload'].update(bytes=base64.b64encode(data).decode(),digest=e.digest(data))
            elif name == 'wrong-vote-ack': r['payload']['receipt'] = '0'*64
            elif name == 'wrong-future-ack': r['payload']['digest'] = '0'*64
            elif name == 'wrong-publish-ack': r['payload']['generation'] = '0'*64
            elif name in ('wrong-apply-sequence','wrong-recording-sequence'): q['sequence'] += 10; r['sequence'] = q['sequence']
            elif name == 'wrong-publication-trace': q['trace'] = '00000000-0000-0000-0000-000000000001'; r['trace'] = q['trace']
            qraw,rraw = f.encode('wire',kind,q),f.encode('wire',answer,r)
            for row in rows:
                if e.digest(base64.b64decode(row['request'])) == qhash:
                    row.update(request=base64.b64encode(qraw).decode(),response=base64.b64encode(rraw).decode())
            for row in events:
                if row.get('request') == qhash: row['request'] = e.digest(qraw)
                if row.get('response') == rhash: row['response'] = e.digest(rraw)
    (path/'events.json').write_bytes(f.canonical(events)); (path/'wire.json').write_bytes(f.canonical(rows))


def qualify(root):
    root = Path(root); original = d.inspect(root); negatives = []
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-discovered-service-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root,path); mutate(path,name)
            try: d.inspect(path)
            except ValueError as error: d.need(str(error) == reason, 'discovered service unrelated negative: '+name+': '+str(error))
            else: raise ValueError('discovered service accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)
