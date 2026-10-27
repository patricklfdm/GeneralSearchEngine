"""Original-first native certificate/application wire and physical replay.

The producer drives controls explicitly. Application ACK never means publication.
"""
import argparse
import base64
from collections import Counter, defaultdict
import copy
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import native_voting_evidence as v
from . import offline_fixture_image as image
b, c, e, need = v.b, v.c, v.e, v.need
f = e.f


def originals(root):
    root = Path(root); voting = v.validate(root/'voting'); size, kind = voting['size'], voting['kind']
    group = {f'node-{i}': c.inventory(root/f'voting/after-voting/node-{i}') for i in range(1, size+1)}
    _, local, packet = c.current(group['node-1']); cap = packet['capsule']; selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
    identities = {node: f.decode(files['node.gsr'], 'records', 'NODE')['identity'] for node, files in group.items()}
    proof = b.t.plans.read(root/'voting/proof.gsr', 16384); p = f.decode(proof, 'records', 'PROOF')
    accepted = dict(p); accepted.pop('accepts'); accept = f.encode('records', 'ACCEPT', accepted)
    def receipt(node, phase, raw):
        return f.canonical(dict(root=cap['root'], voter=node, incarnation=identities[node]['storage'], phase=phase, record=e.digest(raw)))
    proofs = [dict(voter=node, incarnation=identities[node]['storage'], receipt=e.digest(receipt(node, 'PROOF', proof))) for node in sorted(group)]
    certificate = f.encode('records', 'CERTIFICATE', dict(p, proofs=proofs))
    need(b.t.plans.read(root/'certificate.gsr', 16384) == certificate, 'application ingress exact certificate')
    certified = {}
    for node, files in group.items():
        vote = files['pending.accept']+certificate; vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]
        certified[node] = dict(files, **{'pending.accept': vote})
    before = dict(group); before['node-1'] = certified['node-1']; b.match(root, 'before-ingress', before)
    return dict(voting=voting, group=group, before=before, certified=certified, cap=cap, selected=selected, identities=identities,
                proof=proof, accept=accept, certificate=certificate, receipt=receipt, local=local, packet=packet)


def ends(root, original):
    root = Path(root); cap, selected, certificate = (original[k] for k in ('cap','selected','certificate'))
    proof = f.decode(original['proof'], 'records', 'PROOF'); kind = original['voting']['kind']; is_data = kind == 'DATA'
    raw = b.t.plans.read(root/'end-node-2/application.image', 64*e.MIB) if is_data else original['local'][cap['application']+'.image']
    previous = f.decode(original['packet']['objects'][cap['catalog']], 'records', 'CATALOG')
    root_record = f.decode(original['group']['node-1']['root.gsr'], 'records', 'ROOT')
    image.application(raw, root_record['historyId'], previous['applicationSequence']+int(is_data), [(456, 'native-payload-'+'x'*1024)] if is_data else [])
    if not is_data: need(raw == original['local'][cap['application']+'.image'], 'application ingress barrier image')
    after = copy.deepcopy(previous); after['cut'] = dict(cap['cut'], index=proof['index'], entry=proof['entry'])
    if is_data: after.update(application=e.digest(raw), applicationSequence=previous['applicationSequence']+1, lastDataIndex=proof['index'])
    catalog = f.encode('records', 'CATALOG', after)
    start = f.decode(original['packet']['objects'][cap['items'][0]['statement']], 'records', 'CHECKPOINT') if cap['items'] else dict(
        root=cap['root'], scope='RANGE', start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])
    statement = f.encode('records', 'CHECKPOINT', dict(start, end=after['cut'], catalogAfter=e.digest(catalog), applicationAfter=after['application']))
    lower = f.encode('records', 'CHECKPOINT', dict(f.decode(statement, 'records', 'CHECKPOINT'), start=cap['cut'], catalogBefore=cap['catalog'], applicationBefore=cap['application'])) if is_data else None
    result = {}
    for node, files in original['certified'].items():
        def ack(value): return f.encode('records', 'CHECKPOINT_ACK', dict(root=cap['root'], voter=node,
            incarnation=original['identities'][node]['storage'], cut=after['cut'], statement=e.digest(value)))
        end = dict(zip(('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr'),
            (files['selector.gsr'], certificate, catalog, statement, raw, ack(statement))))
        if lower: end.update({'parent-statement.gsr': lower, 'parent-ack.gsr': ack(lower)})
        end['plan.json'] = f.canonical(dict(schema='gse-v53-applied-end/1.3', root=cap['root'], node=node,
            files=[dict(path=k, **e.info(value)) for k, value in sorted(end.items())]))
        result[node] = end
    return result


def wire(root, original, targets):
    cap, selected, certificate, identities = (original[k] for k in ('cap','selected','certificate','identities'))
    receipt = original['receipt']; rows = v.read(root/'wire.json'); events = v.read(root/'events.json'); traces = defaultdict(list); controls = []
    for row in rows:
        need(set(row) == {'request','response','withheld'} and row['withheld'] is False, 'application ingress wire row')
        kind, sent = v.transfer.wire(row['request']); response_kind, reply = v.transfer.wire(row['response'])
        source, target = sent['sender']['node'], sent['recipient']['node']
        need(source in identities and target in identities and source != target and sent['sender'] == identities[source] and sent['recipient'] == identities[target]
             and sent['root'] == cap['root'] and sent['view'] == selected['view'] and sent['ballot'] == selected['ballot'], 'application ingress wire authority')
        need({k:x for k,x in reply.items() if k != 'payload'} == dict({k:x for k,x in sent.items() if k != 'payload'},
            sender=sent['recipient'], recipient=sent['sender']), 'application ingress wire correlation')
        if kind == 'APPLY':
            end = targets[target]
            need(source == 'node-1' and target != 'node-1' and response_kind == 'APPLY_ACK' and sent['sequence'] == 1
                 and sent['payload'] == dict(certificate=e.digest(certificate), selection=e.digest(original['local']['selected.gsr']))
                 and reply['payload'] == dict(sent['payload'], statement=e.digest(end['statement.gsr']), acknowledgement=e.digest(end['ack.gsr'])),
                 'application ingress exact acknowledgement')
            own = [event for event in events if event.get('node') == target]; positions = []
            for name in ('CERTIFICATE_PARENT_FORCED','NATIVE_CERTIFICATE_RETAINED','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLICATION_ACK_BEFORE_RETURN'):
                found = [i for i,event in enumerate(own) if event.get('event') == name]
                need(len(found) == 1, 'application ingress force before ACK'); positions += found
            sent_at = [i for i,event in enumerate(own) if event == dict(node=target, event='WIRE_RESPONSE', request=e.digest(base64.b64decode(row['request'],validate=True)), response=e.digest(base64.b64decode(row['response'],validate=True)))]
            need(len(sent_at) == 1 and positions == sorted(set(positions)) and positions[-1] < sent_at[0], 'application ingress force before ACK')
            controls.append(target)
        else: traces[sent['trace']].append((kind, sent, response_kind, reply))
    need(Counter(controls) == Counter(n for n in identities if n != 'node-1'), 'application ingress complete controls')
    content = {e.digest(certificate): certificate}; references = {e.digest(certificate): e.digest(certificate)}
    for node in identities:
        for phase, raw in [('ACCEPT',original['accept']),('PROOF',original['proof'])]:
            value = receipt(node, phase, raw); digest = e.digest(value); content[digest] = value
            references[digest] = e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=digest)))
    observed = Counter()
    for trace in traces.values():
        need(len(trace) >= 3, 'application ingress complete transfer'); first_kind, first, reply_kind, offer = trace[0]
        a, z = first['payload'], offer['payload']; digest = z['digest']; tid = a['id']
        need(digest in content and (first_kind,reply_kind) == ('CHUNK','SOURCE_OFFER') and a == dict(id=tid,action='REQUEST',offset=0,digest=references[digest],bytes='')
             and z == dict(id=tid,kind='RECORD',digest=digest,bytes=len(content[digest])), 'application ingress original offer')
        raw = content[digest]; offset = 0
        for index,(kind,sent,response_kind,reply) in enumerate(trace):
            need(sent['sender'] == first['sender'] and sent['recipient'] == first['recipient'] and sent['sequence'] == index+1, 'application ingress transfer sequence')
            a,z = sent['payload'],reply['payload']
            if not index: continue
            if index == len(trace)-1:
                need((kind,response_kind) == ('TRANSFER_COMMIT','TRANSFER_COMMIT') and a == z == dict(id=tid,digest=digest) and offset == len(raw), 'application ingress complete transfer')
            else:
                part = base64.b64decode(z['bytes'],validate=True)
                need((kind,response_kind) == ('CHUNK','CHUNK') and a == dict(id=tid,action='REQUEST',offset=offset,digest=digest,bytes='')
                     and z == dict(id=tid,action='DATA',offset=offset,digest=e.digest(part),bytes=base64.b64encode(part).decode()) and 0 < len(part) <= 4*e.MIB
                     and part == raw[offset:offset+len(part)], 'application ingress original transfer bytes'); offset += len(part)
        observed[(first['sender']['node'],first['recipient']['node'],digest)] += 1
    wanted = Counter()
    for node in identities:
        if node == 'node-1': continue
        wanted[(node,'node-1',e.digest(certificate))] += 1
        for peer in identities:
            if node == peer: continue
            for phase,raw in [('ACCEPT',original['accept']),('PROOF',original['proof'])]: wanted[(node,peer,e.digest(receipt(peer,phase,raw)))] += 1
    need(observed == wanted, 'application ingress complete original-owner observations')
    return len(controls), sum(observed.values())


def validate(root):
    root = Path(root); o = originals(root); size, kind = o['voting']['size'], o['voting']['kind']
    need(v.read(root/'ingress-result.json') == dict(status='PASS',size=size,kind=kind,applications=size-1), 'application ingress result scope')
    targets = ends(root,o); expected = dict(o['before'])
    for node in o['group']:
        if node == 'node-1': continue
        end = targets[node]; need(c.inventory(root/('end-'+node)) == end, 'application ingress original end')
        b.typed_image(root/('typed-'+node),end['application.image'])
        expected[node] = dict(o['certified'][node], **{'applied-end':None}, **{'applied-end/'+k:x for k,x in end.items()})
    b.match(root,'after-ingress',expected)
    applications, transfers = wire(root,o,targets)
    return dict(status='PASS',size=size,kind=kind,applications=applications,transfers=transfers,independentImageSemantics=True,published=False,autonomous=False)


def qualify(root):
    original = validate(root); results = []
    cases = [('scope','application ingress result scope'),('certificate','application ingress exact certificate'),('end','application ingress original end'),
             ('published','admitted exact after-ingress'),('force','application ingress force before ACK'),('ack','application ingress exact acknowledgement'),
             ('owner','application ingress wire authority'),('observation','application ingress complete original-owner observations'),
             ('commit','application ingress complete transfer')]
    for name,reason in cases:
        with tempfile.TemporaryDirectory(prefix='v53-application-ingress-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root,target)
            if name == 'scope':
                path=target/'ingress-result.json'; value=v.read(path); value['published']=True; path.write_text(json.dumps(value))
            elif name in ('certificate','end','published'):
                path=target/({'certificate':'certificate.gsr','end':'end-node-2/ack.gsr','published':'after-ingress/node-2/selector.gsr'}[name]); path.write_bytes(b'changed')
            elif name == 'force':
                path=target/'events.json'; value=v.read(path); path.write_text(json.dumps([r for r in value if r.get('event') != 'APPLY_ACK_DIRECTORY_FORCED']))
            else:
                path=target/'wire.json'; rows=v.read(path)
                if name == 'observation':
                    trace=v.transfer.wire(rows[0]['request'])[1]['trace']; rows=[r for r in rows if v.transfer.wire(r['request'])[1]['trace'] != trace]
                elif name == 'commit': rows.pop(next(i for i,r in enumerate(rows) if v.transfer.wire(r['request'])[0] == 'TRANSFER_COMMIT'))
                else:
                    row=next(r for r in rows if v.transfer.wire(r['request'])[0] == 'APPLY'); field='request' if name == 'owner' else 'response'; kind,value=v.transfer.wire(row[field])
                    if name == 'owner': value['sender']['storage']='00000000-0000-0000-0000-000000000099'
                    else: value['payload']['acknowledgement']='0'*64
                    row[field]=base64.b64encode(f.encode('wire',kind,value)).decode()
                path.write_text(json.dumps(rows))
            try: validate(target)
            except ValueError as error: need(reason in str(error),'application ingress unrelated negative '+name+': '+str(error))
            else: raise ValueError('application ingress accepted negative '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--negatives',action='store_true');a=p.parse_args();print(json.dumps(qualify(a.root) if a.negatives else validate(a.root),sort_keys=True))
