"""Original-first physical and actual TCP replay of native incoming phased votes.

Explicit outgoing driver only. No certificate/application/public service claim.
"""
import argparse
import base64
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import bootstrap_publication_evidence as b
from . import source_exchange_evidence as transfer

e, c, need = b.e, b.c, b.e.need


def read(path):
    return json.loads(b.t.plans.read(path, 8*e.MIB))


def validate(root):
    root = Path(root); result = read(root/'result.json')
    size, kind = result.get('size'), result.get('kind')
    need(size in (3, 4, 5) and kind in ('BARRIER', 'DATA') and result == dict(status='PASS', size=size, kind=kind, acknowledgements=2*(size-1)), 'native voting result scope')
    group = b.campaign(root, b.original(root, size, False), 1)
    if kind == 'DATA': group, _ = b.publication(root, group, 1, None, [])
    b.match(root, 'before-voting', group)
    _, local, packet = c.current(group['node-1']); cap = packet['capsule']; selected = e.f.decode(local['selected.gsr'], 'records', 'SELECTED')
    identities = {node: e.f.decode(files['node.gsr'], 'records', 'NODE')['identity'] for node, files in group.items()}
    text = b'456:native-payload-' + b'x'*1024
    payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, 456)+struct.pack('>I', len(text))+text if kind == 'DATA' else b''
    entry = e.f.encode('records', 'ENTRY', dict(root=cap['root'], authority=selected['view'], index=cap['cut']['index']+1, previous=cap['cut']['entry'], origin=selected['ballot'], kind=kind, payload=e.digest(payload)))
    need(b.t.plans.read(root/'entry.gsr', 16384) == entry and b.t.plans.read(root/'payload.bin', 8*e.MIB) == payload, 'native voting original entry/payload')
    accept = e.f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=selected['view'], ballot=selected['ballot'], index=cap['cut']['index']+1, entry=e.digest(entry)))

    def receipt(node, phase, record):
        return e.f.canonical(dict(root=cap['root'], voter=node, incarnation=identities[node]['storage'], phase=phase, record=e.digest(record)))

    witnesses = [dict(voter=node, incarnation=identities[node]['storage'], receipt=e.digest(receipt(node, 'ACCEPT', accept))) for node in sorted(group)]
    proof = e.f.encode('records', 'PROOF', dict(e.f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses))
    need(b.t.plans.read(root/'proof.gsr', 16384) == proof, 'native voting original proof')
    after = {}
    for node, files in group.items():
        _, local, _ = c.current(files)
        raw = e.container([files['selector.gsr'], local['promise.gsr'], local['selected.gsr'], entry, accept], payload)+proof
        raw = raw[:8]+struct.pack('>I', len(raw))+raw[12:]
        after[node] = dict(files, **{'pending.accept': raw})
    b.match(root, 'after-voting', after)
    rows = read(root/'wire.json'); events = read(root/'events.json'); traces = defaultdict(list); controls = []
    for row in rows:
        need(set(row) == {'request', 'response', 'withheld'} and row['withheld'] is False, 'native voting original wire row')
        request_kind, sent = transfer.wire(row['request']); reply_kind, reply = transfer.wire(row['response'])
        source, target = sent['sender']['node'], sent['recipient']['node']
        need(source in identities and target in identities and source != target and sent['sender'] == identities[source] and sent['recipient'] == identities[target]
             and sent['root'] == cap['root'] and sent['view'] == selected['view'] and sent['ballot'] == selected['ballot'], 'native voting wire authority')
        need({k: v for k, v in reply.items() if k != 'payload'} == dict({k: v for k, v in sent.items() if k != 'payload'}, sender=sent['recipient'], recipient=sent['sender']), 'native voting wire correlation')
        if request_kind in ('ACCEPT', 'PROOF'):
            record = accept if request_kind == 'ACCEPT' else proof
            need(source == 'node-1' and target != 'node-1' and reply_kind == request_kind+'_ACK' and sent['sequence'] == 1
                 and sent['payload'] == {('acceptance' if request_kind == 'ACCEPT' else 'proof'): e.digest(record)}
                 and reply['payload'] == dict(entry=e.digest(entry), receipt=e.digest(receipt(target, request_kind, record))), 'native voting original acknowledgement')
            controls.append((target, request_kind))
            native = [event for event in events if event.get('node') == target]
            forced = [i for i, event in enumerate(native) if event.get('event') == request_kind+'_PARENT_FORCED']
            acknowledged = [i for i, event in enumerate(native) if event.get('event') == request_kind+'_ACK_BEFORE_RETURN']
            sent_at = [i for i, event in enumerate(native) if event == dict(node=target, event='WIRE_RESPONSE', request=e.digest(base64.b64decode(row['request'], validate=True)), response=e.digest(base64.b64decode(row['response'], validate=True)))]
            need(len(forced) == len(acknowledged) == len(sent_at) == 1 and forced[0] < acknowledged[0] < sent_at[0], 'native voting force before wire ACK')
        else: traces[sent['trace']].append((request_kind, sent, reply_kind, reply))
    need(Counter(controls) == Counter((node, phase) for node in group if node != 'node-1' for phase in ('ACCEPT', 'PROOF')), 'native voting complete control set')
    originals = {e.digest(raw): raw for raw in (entry, accept, proof)}
    if payload: originals[e.digest(payload)] = payload
    references = {digest: digest for digest in originals}
    for node in group:
        for phase, raw in (('ACCEPT', accept), ('PROOF', proof)):
            content = receipt(node, phase, raw); digest=e.digest(content); originals[digest] = content
            references[digest] = e.digest(e.f.canonical(dict(schema='gse-v53-vote-observation/1.3', receipt=digest)))
    observed = Counter()
    for history in traces.values():
        first_kind, first, offer_kind, offered = history[0]; a, offer = first['payload'], offered['payload']; digest = offer['digest']; tid = a['id']
        need(digest in originals and (first_kind, offer_kind) == ('CHUNK', 'SOURCE_OFFER') and a == dict(id=tid, action='REQUEST', offset=0, digest=references[digest], bytes='')
             and offer == dict(id=tid, kind='RECORD', digest=digest, bytes=len(originals[digest])), 'native voting original offer')
        raw = originals[digest]; offset = 0
        for index, (request_kind, sent, reply_kind, reply) in enumerate(history):
            need(sent['sender'] == first['sender'] and sent['recipient'] == first['recipient'] and sent['sequence'] == index+1, 'native voting transfer sequence')
            a, v = sent['payload'], reply['payload']
            if index == 0: continue
            if index == len(history)-1:
                need((request_kind, reply_kind) == ('TRANSFER_COMMIT', 'TRANSFER_COMMIT') and a == v == dict(id=tid, digest=digest) and offset == len(raw), 'native voting complete original transfer')
            else:
                part = base64.b64decode(v['bytes'], validate=True)
                need((request_kind, reply_kind) == ('CHUNK', 'CHUNK') and a == dict(id=tid, action='REQUEST', offset=offset, digest=digest, bytes='')
                     and v == dict(id=tid, action='DATA', offset=offset, digest=e.digest(part), bytes=base64.b64encode(part).decode())
                     and 0 < len(part) <= 4*e.MIB and part == raw[offset:offset+len(part)], 'native voting original transfer bytes')
                offset += len(part)
        need(len(history) >= 3, 'native voting complete original transfer')
        observed[(first['sender']['node'], first['recipient']['node'], digest)] += 1
    wanted = Counter()
    for node in group:
        if node == 'node-1': continue
        for raw in (accept, entry, proof, receipt('node-1', 'ACCEPT', accept), *([payload] if payload else [])): wanted[(node, 'node-1', e.digest(raw))] += 1
        for peer in group:
            if peer != node: wanted[(node, peer, e.digest(receipt(peer, 'ACCEPT', accept)))] += 1
        for phase, raw in (('ACCEPT', accept), ('PROOF', proof)): wanted[('node-1', node, e.digest(receipt(node, phase, raw)))] += 1
    need(observed == wanted, 'native voting complete original-owner observations')
    return dict(status='PASS', size=size, kind=kind, acknowledgements=len(controls), transfers=sum(observed.values()), publicRuntime=False, autonomous=False)


def qualify(root):
    original = validate(root); results = []
    variants = [('scope', 'native voting result scope'), ('payload', 'native voting original entry/payload'), ('proof', 'native voting original proof'),
                ('pending', 'admitted exact after-voting'), ('force', 'native voting force before wire ACK'), ('withheld', 'native voting original wire row'),
                ('identity', 'native voting wire authority'), ('correlation', 'native voting wire correlation'), ('receipt', 'native voting original acknowledgement'),
                ('missing-vote', 'native voting complete control set'), ('missing-observation', 'native voting complete original-owner observations'),
                ('missing-commit', 'native voting complete original transfer'), ('bytes', 'native voting original transfer bytes')]
    for name, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-voting-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target)
            if name == 'scope':
                path=target/'result.json'; value=read(path); value['publicRuntime']=True; path.write_text(json.dumps(value))
            elif name in ('payload', 'proof', 'pending'):
                path=target/({'payload':'payload.bin','proof':'proof.gsr','pending':'after-voting/node-2/pending.accept'}[name]); path.write_bytes(b'changed')
            elif name == 'force':
                path=target/'events.json'; value=read(path); value=[v for v in value if v.get('event') != 'ACCEPT_PARENT_FORCED']; path.write_text(json.dumps(value))
            else:
                path=target/'wire.json'; value=read(path)
                control=next(i for i,v in enumerate(value) if transfer.wire(v['request'])[0]=='ACCEPT')
                if name=='withheld': value[control]['withheld']=True
                elif name=='missing-vote': value.pop(control)
                elif name=='missing-observation':
                    trace=transfer.wire(value[0]['request'])[1]['trace']; value=[v for v in value if transfer.wire(v['request'])[1]['trace']!=trace]
                elif name=='missing-commit':
                    index=next(i for i,v in enumerate(value) if transfer.wire(v['request'])[0]=='TRANSFER_COMMIT'); value.pop(index)
                else:
                    index=next(i for i,v in enumerate(value) if transfer.wire(v['response'])[0]=='CHUNK') if name=='bytes' else control
                    field='request' if name=='identity' else 'response'; kind, frame=transfer.wire(value[index][field])
                    if name=='identity': frame['sender']['storage']='00000000-0000-0000-0000-000000000099'
                    elif name=='correlation': frame['sequence']+=1
                    elif name=='receipt': frame['payload']['receipt']='0'*64
                    else: frame['payload']['bytes']=base64.b64encode(b'changed').decode(); frame['payload']['digest']=e.digest(b'changed')
                    value[index][field]=base64.b64encode(e.f.encode('wire',kind,frame)).decode()
                path.write_text(json.dumps(value))
            try: validate(target)
            except ValueError as error: need(reason in str(error), 'native voting unrelated negative '+name+': '+str(error))
            else: raise ValueError('native voting accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original, negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify',action='store_true'); args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
