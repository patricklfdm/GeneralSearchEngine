"""Independent service continuation of the original discovered 5-to-4 history."""
import argparse
import base64
from collections import Counter, defaultdict, deque
import copy
import json
from pathlib import Path
import re
import struct
from . import discovered_selection_evidence as selection
from . import authority_transition_evidence as transition

c, e, f, need = selection.c, selection.e, selection.f, selection.need
native, s = selection.native, selection.s
VOTERS, LEADER = selection.VOTERS, selection.LEADER


class Service(transition.NativeSlot):
    voters = VOTERS
    proposer = LEADER

    def __init__(self, root, group):
        self.root = root; self.group = copy.deepcopy(group); self.active = list(VOTERS)
        self.slot = 7; self.counter = 4; self.first = None; self.documents = []
        self.required = set(); self.observed = set(); self.phases = {}; self.snapshots = {}; self.rounds = []
        self.history = f.decode(group[LEADER]['root.gsr'], 'records', 'ROOT')['historyId']
        self.events = native.read(root/'events.json')

    def data_documents(self):
        return [(207, 'discovered-survivor')]

    def checkpoint_voters(self, view, node):
        # This original fixture has no selected/installed node 3. Its failed
        # source exchanges are retained and separately checked by network().
        need(node in VOTERS and view['old'] == view['new'] == ['node-1','node-2','node-3','node-4']
             and view['operation'] is None, 'discovered service stable checkpoint quorum')
        return set(VOTERS)

    def requested(self, slot, entry, payload):
        rows = [v for v in self.events if v['event'] == 'ROUND_SLOT_BEGIN' and
                f.decode(base64.b64decode(v['bytes'], validate=True), 'records', 'ENTRY')['index'] == slot]
        need(rows == [dict(node=LEADER, event='ROUND_SLOT_BEGIN', record=e.digest(entry),
                          bytes=base64.b64encode(entry).decode())], 'discovered service exact requested entry')
        self.entry = entry; self.payload = payload

    def application_image(self, slot, nodes):
        _, members, packet = c.current(self.group[LEADER])
        if slot == 8: return members[packet['capsule']['application']+'.image']
        need(slot == 9, 'discovered service declared slot')
        # Only image bytes are observed; the backup parser checks their identity,
        # sequence, codec and exact document, before deriving the catalog/hash.
        _, members, packet = c.current(c.inventory(self.root/'after-close'/LEADER))
        return members[packet['capsule']['application']+'.image']

    def snapshot(self, label, group):
        if label.endswith('-applied'): self.applied = copy.deepcopy(group)
        if label.endswith('-published'):
            self.pending_cleanup = {}
            self.publication_group(group, before_local_cleanup=self.pending_cleanup)
        self.snapshots[label] = copy.deepcopy(group)

    def run(self):
        for kind in ('BARRIER', 'DATA'):
            before = copy.deepcopy(self.group)
            self.group = transition.maintenance(self.group, VOTERS)
            maintained = copy.deepcopy(self.group)
            text = b'207:discovered-survivor'
            payload = b'\x01'+struct.pack('>HIII', 1, 1, 4, 207)+struct.pack('>I', len(text))+text if kind == 'DATA' else None
            self.publish(kind, payload)
            self.rounds.append(dict(index=self.slot, before=before, maintained=maintained, applied=self.applied,
                published=copy.deepcopy(self.group), pending=self.pending_cleanup, entry=self.entry, payload=self.payload))
        return self


def physical(root):
    selection.inventory(root)
    walk, adoptions, before, maintained, prepared, chosen, installed = selection.physical(root)
    expected = walk.snapshots | {'initial','after-close','calls.json','events.json','wire.json','failures.json',
        'observations.json','original-plan.gsbp','original-application.image','discovered-transition-result.json'}
    expected |= {f'{name}-{index}.{suffix}' for index in range(1,8) for name,suffix in (('entry','gsr'),('payload','bin'))}
    selection.a.p.selection.layout(root,expected,'discovered service history')
    activation = selection.network(root, before, maintained, prepared, chosen, installed)
    service = Service(root, installed).run()
    selection.a.p.match(root, 'after-close', service.group)
    return service, dict(snapshots=len(walk.snapshots)+1, activation=activation, adoptions=adoptions)


class Transfers:
    def __init__(self, entries, selected, identities):
        self.selected, self.identities = selected, identities
        traces = defaultdict(list)
        for entry in entries: traces[entry['request']['trace']].append(entry)
        self.count = len(traces); self.traces = set(traces); self.available = []
        for trace, values in traces.items():
            logical = defaultdict(list)
            for value in values: logical[value['request']['sequence']].append(value)
            need(sorted(logical) == list(range(1, len(logical)+1)), 'discovered service contiguous source trace')
            ordered = [logical[i][0] for i in sorted(logical)]
            delivered = [selection.identical_attempts(logical[i]) for i in sorted(logical)]
            need(all(delivered[i] < ordered[i+1]['offered'] for i in range(len(ordered)-1)),
                 'discovered service source delivery order')
            request = ordered[0]['request']
            self.available.append(dict(trace=trace, sender=request['sender']['node'], peer=request['recipient']['node'],
                reference=request['payload']['digest'], offered=ordered[0]['offered'], delivered=delivered[-1],
                rows=[v['row'] for v in ordered]))

    def consume(self, sender, peer, variants, lower, upper):
        refs = {v[0][0] for v in variants}
        matches = [v for v in self.available if v['sender'] == sender and v['peer'] == peer
                   and v['reference'] in refs and lower < v['offered'] < v['delivered'] < upper]
        need(len(matches) == 1, 'discovered service original source before dependent force')
        value = matches[0]; self.available.remove(value)
        matching = [v for v in variants if v[0][0] == value['reference']]
        expected = next((v for v in matching if len(value['rows']) ==
                        sum(2+(len(raw)+4*e.MIB-1)//(4*e.MIB) for _, raw, _ in v)), None)
        need(expected is not None, 'discovered service complete source shape')
        selection.d.transfer.transcript(value['rows'], expected, self.selected['root'], self.selected['view'],
            self.selected['ballot'], self.identities[sender], self.identities[peer],
            'discovered service source', chunk_bytes=4*e.MIB)


def retained_futures(round, selected):
    """Derive both recording rounds, including each owner's exact future frame."""
    upper = c.anchor(c.current(round['published'][LEADER])[2]['capsule'])
    parent = c.anchor(c.current(round['maintained'][LEADER])[2]['capsule'])
    frames, _ = c.pending(round['applied'][LEADER]['pending.accept'], ('PROOF','CERTIFICATE'))
    states = []; prior = {n: round['maintained'][n][native.future.FILE] for n in VOTERS}
    for ordinal, target in enumerate((n for n in VOTERS if n != LEADER), 1):
        identity = selection.a.u.identity(round['maintained'][target])
        intent = dict(selection=e.digest(f.encode('records','SELECTED',selected)), certificate=e.digest(frames['CERTIFICATE']),
                      peer=identity, lower=parent, parent=parent, upper=upper)
        current = {}
        for node in VOTERS:
            files = round['applied'][node]; _, local, packet = c.current(files)
            ends = {k.removeprefix('applied-end/'): v for k,v in files.items() if k.startswith('applied-end/')}
            records = {k: ends[k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr')}
            records.update({k: local[k] for k in ('promise.gsr','selected.gsr')})
            records.update(dict(zip(('entry.gsr','accept.gsr','proof.gsr'), (frames[k] for k in ('ENTRY','ACCEPT','PROOF')))))
            raw = round['maintained'][node][native.future.FILE]
            revision = json.loads(raw[48:48+int.from_bytes(raw[44:48],'big')])['revision']
            peers = [dict(identity=selection.a.u.identity(round['maintained'][n]), lower=parent)
                     for n in VOTERS if n != LEADER][:ordinal]
            current[node] = native.future.frame(dict(native.future.initial(files), revision=revision+ordinal,
                previous=e.digest(prior[node]), parent=c.anchor(packet['capsule']), peers=peers), records)
        states.append(dict(intent=intent, frames=current, revision=3*(round['index']-8)+ordinal))
        prior = current
    need(all(prior[n] == round['pending'][n][native.future.FILE] for n in VOTERS),
         'discovered service final pending future')
    return states


def slot_network(root, events, round, start, stop):
    identities = {n: selection.a.u.identity(v) for n,v in round['before'].items()}
    selected_raw = c.current(round['maintained'][LEADER])[1]['selected.gsr']
    selected = f.decode(selected_raw, 'records', 'SELECTED')
    frames, _ = c.pending(round['applied'][LEADER]['pending.accept'], ('PROOF','CERTIFICATE'))
    entries = selection.exchanges(root, events, start, stop, identities)
    controls = defaultdict(list); source_entries = []
    for value in entries:
        req = value['request']
        need(req['root'] == selected['root'] and req['view'] == selected['view'] and req['ballot'] == selected['ballot']
             and req['sender']['node'] in VOTERS and req['recipient']['node'] in VOTERS,
             'discovered service current selected wire authority')
        if value['kind'] in ('CHUNK','TRANSFER_COMMIT'): source_entries.append(value)
        else: controls[value['kind'], req['recipient']['node']].append(value)
    transfers = Transfers(source_entries, selected, identities)
    used_traces = set(transfers.traces)

    def fresh_trace(rows, sequence):
        trace = rows[0]['request']['trace']
        need(trace not in used_traces and all(v['request']['trace'] == trace and
             v['request']['sequence'] == sequence for v in rows), 'discovered service separate control trace')
        used_traces.add(trace)
        return trace
    own = {n: [(i,v['event']) for i,v in enumerate(events) if start < i < stop and v['node'] == n] for n in identities}

    def at(node, name):
        values = [i for i,v in own[node] if v == name]
        need(len(values) == 1, 'discovered service one force: '+node+': '+name)
        return values[0]

    def record(raw, observation=False):
        reference = e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3', receipt=e.digest(raw)))) if observation else e.digest(raw)
        return [[(reference, raw, 'RECORD')]]

    def observed(node, phase):
        return f.canonical(dict(root=selected['root'], voter=node, incarnation=identities[node]['storage'],
                                phase=phase, record=e.digest(frames[phase])))

    for node in VOTERS:
        names = [v for _,v in own[node]]
        s.ordered(names, ['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
            *(['RETENTION_PARENT_FORCED']*3), 'RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED',
            'RETIREMENT_CLEARED','FLOOR_RELEASE_PARENT_FORCED','FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_BEFORE_RETURN',
            'ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED',
            'FUTURE_RETENTION_PARENT_FORCED','FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED',
            'FUTURE_RETENTION_PROMOTED','FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],
            'discovered service slot '+str(round['index'])+' '+node)
        for name in ('FLOOR_PARENT_FORCED','ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED',
                     'APPLY_ACK_DIRECTORY_FORCED','PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN'):
            at(node,name)
        for peer in VOTERS:
            if peer == node: continue
            directory, members, packet = c.current(round['before'][peer])
            transfers.consume(node, peer, native.maintenance_prefixes(members,packet,c.current(round['before'][node])[1]), start,at(node,'FLOOR_PARENT_FORCED'))
            transfers.consume(node, peer, native.maintenance_generations(round['before'][peer][directory+'generation.gsr'],members,packet),start,at(node,'FLOOR_PARENT_FORCED'))
            key = ('STATUS_PROBE',peer); rows = [v for v in controls[key] if v['request']['sender']['node'] == node]
            delivery = selection.identical_attempts(rows); q = rows[0]['request']; response = rows[0]['response']
            fresh_trace(rows, 1)
            need(q['sequence'] == 1 and rows[0]['answer'] == 'STATUS' and response['payload'] ==
                 dict(cut=packet['capsule']['cut'],nonce=q['payload']['nonce'],ready=False) and delivery < at(node,'FLOOR_PARENT_FORCED'),
                 'discovered service original floor probe')
            for row in rows: controls[key].remove(row)
            if not controls[key]: del controls[key]
    need(not own['node-3'] and not own['node-5'], 'discovered service no unselected writes')

    applied_deliveries = []
    for peer in (n for n in VOTERS if n != LEADER):
        for kind in ('ACCEPT','ENTRY') + (('PAYLOAD',) if round['payload'] else ()):
            transfers.consume(peer,LEADER,record(frames[kind]),at(LEADER,'ACCEPT_PARENT_FORCED'),at(peer,'ACCEPT_PARENT_FORCED'))
        transfers.consume(peer,LEADER,record(observed(LEADER,'ACCEPT'),True),at(LEADER,'ACCEPT_PARENT_FORCED'),at(peer,'ACCEPT_PARENT_FORCED'))
        transfers.consume(LEADER,peer,record(observed(peer,'ACCEPT'),True),at(peer,'ACCEPT_PARENT_FORCED'),at(LEADER,'PROOF_PARENT_FORCED'))
        transfers.consume(peer,LEADER,record(frames['PROOF']),at(LEADER,'PROOF_PARENT_FORCED'),at(peer,'PROOF_PARENT_FORCED'))
        for source in VOTERS:
            if source != peer:
                transfers.consume(peer,source,record(observed(source,'ACCEPT'),True),
                    max(at(source,'ACCEPT_PARENT_FORCED'),at(peer,'ACCEPT_PARENT_FORCED')),at(peer,'PROOF_PARENT_FORCED'))
        transfers.consume(LEADER,peer,record(observed(peer,'PROOF'),True),at(peer,'PROOF_PARENT_FORCED'),at(LEADER,'CERTIFICATE_PARENT_FORCED'))
        transfers.consume(peer,LEADER,record(frames['CERTIFICATE']),at(LEADER,'CERTIFICATE_PARENT_FORCED'),at(peer,'CERTIFICATE_PARENT_FORCED'))
        for source in VOTERS:
            if source != peer:
                for phase in ('ACCEPT','PROOF'):
                    transfers.consume(peer,source,record(observed(source,phase),True),
                        max(at(source,phase+'_PARENT_FORCED'),at(peer,'PROOF_PARENT_FORCED')),at(peer,'CERTIFICATE_PARENT_FORCED'))

    # Endorsements are fetched from the exact original applied owners, including
    # the parent bridge on DATA 9; an APPLY/PUBLISH ACK cannot replace them.
    for node in VOTERS:
        for peer in VOTERS:
            if node != peer:
                ends = round['applied'][peer]
                for name in ('ack.gsr',) + (('parent-ack.gsr',) if round['index'] == 9 else ()):
                    transfers.consume(node,peer,record(ends['applied-end/'+name]),at(peer,'APPLY_ACK_DIRECTORY_FORCED'),at(node,'PUBLICATION_SELECTOR_FORCED'))
    need(not transfers.available, 'discovered service no unclassified source')

    def control(kind, peer, payload, response, answer, force):
        key = (kind,peer); rows = [v for v in controls[key] if v['request']['payload'] == payload]
        delivered = selection.identical_attempts(rows)
        need(all(v['request']['sender'] == identities[LEADER] and v['answer'] == answer and
                 v['response']['payload'] == response and force < v['offered'] for v in rows),
             'discovered service exact control acknowledgement')
        for row in rows: controls[key].remove(row)
        if not controls[key]: del controls[key]
        return delivered, rows

    for peer in (n for n in VOTERS if n != LEADER):
        for kind, key in (('ACCEPT','acceptance'),('PROOF','proof')):
            delivery,rows = control(kind,peer,{key:e.digest(frames[kind])},
                dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer,kind))),kind+'_ACK',at(peer,kind+'_PARENT_FORCED'))
            fresh_trace(rows, 1)
            need(delivery < at(LEADER,('PROOF' if kind == 'ACCEPT' else 'CERTIFICATE')+'_PARENT_FORCED'),
                 'discovered service vote ACK before next phase')
        end = round['applied'][peer]
        payload = dict(certificate=e.digest(frames['CERTIFICATE']),selection=e.digest(selected_raw))
        response = dict(payload,statement=e.digest(end['applied-end/statement.gsr']),acknowledgement=e.digest(end['applied-end/ack.gsr']))
        delivery,rows = control('APPLY',peer,payload,response,'APPLY_ACK',at(peer,'APPLY_ACK_DIRECTORY_FORCED'))
        fresh_trace(rows, 1)
        applied_deliveries.append(delivery)

    future = retained_futures(round,selected)
    quorums = [(i,v) for i,v in enumerate(events) if start < i < stop and v['event'] == 'SLOT_FUTURE_QUORUM_COMPLETE']
    need(len(quorums) == 2 and all(v == dict(node=LEADER,event='SLOT_FUTURE_QUORUM_COMPLETE',
         record=e.digest(frames['CERTIFICATE']),voters=list(VOTERS)) for _,v in quorums), 'discovered service exact future quorums')
    forces = {n:[i for i,v in own[n] if v == 'FUTURE_RETENTION_PARENT_FORCED'] for n in VOTERS}
    need(all(len(v) == 3 for v in forces.values()), 'discovered service future force count')
    def slot_event(name):
        rows = [(i,v) for i,v in enumerate(events) if start < i < stop and v['event'] == name]
        need(len(rows) == 1 and rows[0][1] == dict(node=LEADER,event=name,record=e.digest(frames['CERTIFICATE']),voters=list(VOTERS)),
             'discovered service exact slot boundary')
        return rows[0][0]
    applied_at = slot_event('SLOT_APPLIED')
    need(max(applied_deliveries+[at(LEADER,'APPLY_ACK_DIRECTORY_FORCED')]) < applied_at < forces[LEADER][0],
         'discovered service applied before future recording')
    publication_traces = {}
    for ordinal, state in enumerate(future):
        quorum = quorums[ordinal][0]
        need(forces[LEADER][ordinal] < quorum, 'discovered service local recording before quorum')
        if ordinal: need(quorums[ordinal-1][0] < forces[LEADER][ordinal], 'discovered service recording rounds serialized')
        trace = None
        for sequence, peer in enumerate((n for n in VOTERS if n != LEADER), 2):
            response = dict(intent=e.digest(f.canonical(state['intent'])),storage='FUTURE',revision=state['revision'],digest=e.digest(state['frames'][peer]))
            delivery,rows = control('FUTURE_RETENTION_INTENT',peer,state['intent'],response,'FUTURE_RETENTION_ACK',forces[peer][ordinal])
            if trace is None: trace = fresh_trace(rows, sequence)
            need(all(v['request']['trace'] == trace and v['request']['sequence'] == sequence for v in rows),
                 'discovered service exact recording trace')
            need(delivery < quorum, 'discovered service delivered recording before quorum')
        publication_traces[state['intent']['peer']['node']] = trace
    sends = [(i,v) for i,v in enumerate(events) if start < i < stop and v['event'] == 'PUBLICATION_SEND_BOUNDARY']
    need(sends and min(i for i,_ in sends) > quorums[-1][0], 'discovered service all quorums before publication send')
    send_hashes = set()
    for peer in (n for n in VOTERS if n != LEADER):
        files = round['published'][peer]; directory,_,packet = c.current(files)
        payload = dict(certificate=e.digest(frames['CERTIFICATE']))
        response = dict(payload,selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),generation=e.digest(files[directory+'generation.gsr']))
        delivery, rows = control('PUBLISH',peer,payload,response,'PUBLISH_ACK',at(peer,'PUBLICATION_BEFORE_RETURN'))
        need(all(v['request']['trace'] == publication_traces[peer] and v['request']['sequence'] == 5 for v in rows),
             'discovered service publication bound to recording')
        need(delivery < at(LEADER,'PUBLICATION_SELECTOR_FORCED'), 'discovered service remote completion before local publication')
        for row in rows:
            request_hash = e.digest(base64.b64decode(row['row']['request'],validate=True));send_hashes.add(request_hash)
            need(any(v == dict(node=LEADER,event='PUBLICATION_SEND_BOUNDARY',request=request_hash) and i < row['offered'] for i,v in sends),
                 'discovered service actual publication send')
    need({v['request'] for _,v in sends} == send_hashes and all(v['node'] == LEADER for _,v in sends),
         'discovered service no foreign publication send')
    need(not controls, 'discovered service no unclassified control')
    need(at(LEADER,'PUBLICATION_BEFORE_RETURN') < slot_event('SLOT_PUBLISHED') < stop,
         'discovered service publication before completion')
    return dict(index=round['index'],transfers=transfers.count,exchanges=len(entries),recordingQuorums=2)


def preparation(root):
    calls = native.read(root/'calls.json'); expected = []; checks = {}
    all_nodes = ['node-'+str(i) for i in range(1,6)]; governing = all_nodes[:3]; online = governing+['node-5']
    def phase(name, nodes, required):
        expected.extend((n,name) for n in nodes); checks[name] = required
    def settled(label,nodes,obsolete=False):
        phase(label+'-copy',nodes,['FLOOR_COPY_BEFORE_RETURN'])
        phase(label+'-maintain',nodes,['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED',
            'FLOOR_BEFORE_RETURN','RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_CLEARED']+
            (['SOURCE_RETIREMENT_PARENT_FORCED','JOURNAL_ROTATION_PARENT_FORCED','SOURCE_RETIREMENT_BEFORE_RETURN'] if obsolete else [])+
            ['FLOOR_RELEASE_PARENT_FORCED','FLOOR_RELEASE_BEFORE_RETURN'])
    def campaign(number,nodes,label,obsolete=False):
        phase('allocate-'+str(number),['node-1'],['ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN'])
        phase('prepare-'+str(number),nodes,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'])
        phase('select-'+str(number),nodes,['SELECTED_FORCED','SELECTED_BEFORE_RETURN'])
        phase('install-'+str(number),nodes,['INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
        settled(label,nodes,obsolete)
    phase('initialize-retention',all_nodes,['RETENTION_PARENT_FORCED','FUTURE_RETENTION_PARENT_FORCED'])
    campaign(1,all_nodes,'round-1-settled')
    for index in range(1,8):
        nodes = online if index < 7 else governing
        if index == 7: campaign(3,nodes,'campaign-3-settled',True)
        phase('publication-original-ancestry',['node-1'],['FLOOR_COPY_BEFORE_RETURN'])
        phase('inspect-context',['node-1'],['FLOOR_COPY_BEFORE_RETURN'])
        for name, required in (
            ('accept',['ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN']),
            ('proof',['PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN']),
            ('certificate',['CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN']),
            ('apply',['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN']*2),
            ('publish',['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'])):
            phase(name+'-'+str(index),nodes,required)
        if index in (6,7): phase('configuration-retention',nodes,['RETENTION_PARENT_FORCED'])
        settled('slot-'+str(index)+'-settled',nodes)
        if index in (1,5): phase('inspect-context',['node-1'],['FLOOR_COPY_BEFORE_RETURN'])
    phase('stale-survivor-original',['node-4'],['CURRENT_DIRECTORY_FORCED'])
    phase('removed-original',['node-5'],['CURRENT_DIRECTORY_FORCED'])
    phase('inspect-context',['node-1'],['FLOOR_COPY_BEFORE_RETURN'])
    need(type(calls) is list and len(calls) == len(expected) and all(set(v) == {'node','operation','events'}
         and isinstance(v['events'],list) and all(type(item) is str for item in v['events']) for v in calls),
         'discovered service original preparation calls')
    need([(v['node'],v['operation']) for v in calls] == expected, 'discovered service preparation order/owners')
    for row in calls: s.ordered(row['events'],checks[row['operation']],'discovered service preparation '+row['operation'])
    return len(calls)


def rejection_diagnostics(root):
    rows = native.read(root/'failures.json'); grouped = defaultdict(list)
    reasons = {'CHUNK':'java.lang.IllegalArgumentException: activation endpoint scope unavailable',
               'FUTURE_RETENTION_INTENT':'java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required'}
    need(type(rows) is list and len(rows) <= 30, 'discovered service bounded rejection diagnostics')
    for row in rows:
        need(set(row) == {'node','kind','request','failure'} and row['node'] == 'node-3'
             and row['kind'] in reasons and row['failure'] == reasons[row['kind']]
             and isinstance(row['request'],str) and re.fullmatch('[0-9a-f]{64}',row['request']),
             'discovered service unselected rejection classification')
        grouped[row['request']].append(row)
    need(all(len(values) <= 3 and all(v == values[0] for v in values) for values in grouped.values()),
         'discovered service bounded failed exchange')
    return dict(records=len(rows),exchanges=len(grouped),authority=False,requestBodiesRetained=False)


def lifecycle(service):
    events = service.events
    rows = [(i,v) for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    expected = [('node-5','ADOPTED'),(LEADER,'ADOPTED'),(LEADER,'INSTALLED'),
                (LEADER,'SLOT_BEGIN'),(LEADER,'SLOT_COMPLETE'),(LEADER,'BEFORE_READY'),
                (LEADER,'SLOT_BEGIN'),(LEADER,'SLOT_COMPLETE')]
    need([(v['node'],v['event']) for _,v in rows] == [(n,'ROUND_'+kind) for n,kind in expected],
         'discovered service exact round lifecycle')
    for at,row in rows[:2]:
        s.ordered([v['event'] for v in events[:at] if v['node'] == row['node']],
            ['ADOPTION_INSTALL_VALIDATED','PROMISE_FORCED','ADOPTION_INSTALL_FENCED',
             'INSTALL_GENERATION_FORCED','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','ADOPTION_INSTALL_BEFORE_RETURN'],
            'discovered service adoption durability')
    boundaries = [(rows[3][0],rows[4][0]),(rows[6][0],rows[7][0])]
    for round,(_,stop) in zip(service.rounds,boundaries):
        row = events[stop]; raw = base64.b64decode(row['bytes'],validate=True); ack = f.decode(raw,'wire','PUBLISH_ACK')
        files = round['published'][LEADER]; directory,members,packet = c.current(files)
        chosen = f.decode(members['selected.gsr'],'records','SELECTED'); identity = selection.a.u.identity(files)
        payload = dict(certificate=e.digest(round['applied'][LEADER]['applied-end/certificate.gsr']),
            selection=e.digest(members['selected.gsr']),published=c.anchor(packet['capsule']),generation=e.digest(files[directory+'generation.gsr']))
        need(set(row) == {'node','event','record','bytes'} and row['record'] == e.digest(raw) and
             ack['root'] == chosen['root'] and ack['view'] == chosen['view'] and ack['ballot'] == chosen['ballot']
             and ack['sender'] == ack['recipient'] == identity and ack['sequence'] == 1 and ack['payload'] == payload,
             'discovered service original round completion')
    need(rows[5][1] == dict(rows[4][1],event='ROUND_BEFORE_READY'), 'discovered service ready after fresh barrier')
    return boundaries


def network_coverage(root, events, boundaries):
    """Every retained offer and delivery belongs to one checked stage."""
    decoded = defaultdict(deque)
    for row in native.read(root/'wire.json'):
        request = base64.b64decode(row['request'], validate=True)
        response = base64.b64decode(row['response'], validate=True)
        kind, message = selection.d.transfer.t.wire(row['response'])
        _, query = selection.d.transfer.t.wire(row['request'])
        decoded[e.digest(request), e.digest(response)].append((kind, message, query))
    adopted = [selection.event_boundary(events,n,'ROUND_ADOPTED') for n in ('node-5',LEADER)]
    installed = selection.event_boundary(events,LEADER,'ROUND_INSTALLED')
    intervals = [(-1,adopted[0]),(adopted[0],adopted[1]),(adopted[1],installed),*boundaries]
    counts = [0]*len(intervals); offered = Counter(); delivered = 0
    for at,row in enumerate(events):
        if row['event'] == 'WIRE_RESPONSE':
            key = row['request'],row['response']
            need(bool(decoded[key]), 'discovered service response inventory')
            kind,message,query = decoded[key].popleft()
            stages = [i for i,(start,stop) in enumerate(intervals) if start < at < stop]
            need(len(stages) == 1, 'discovered service response outside checked stages')
            stage = stages[0]; counts[stage] += 1
            if stage < 2:
                node = ('node-5',LEADER)[stage]
                _,members,packet = c.current(c.inventory(root/'before-network'/node))
                ballot = f.decode(members['selected.gsr'],'records','SELECTED')['ballot']
                need(message['recipient']['node'] == node and query['sender']['node'] == node and
                     query['ballot'] == ballot and query['view'] == e.authority(packet['capsule']['root'],packet['capsule']['cut']['view']),
                     'discovered service adoption exchange owner')
            offered[message['recipient']['node'],kind,row['response']] += 1
        elif row['event'] == 'NETWORK_RECEIVED':
            need(set(row) == {'node','event','kind','response'}, 'discovered service received event schema')
            key = row['node'],row['kind'],row['response']
            need(offered[key] > 0, 'discovered service received without original offer')
            offered[key] -= 1; delivered += 1
    need(not any(decoded.values()), 'discovered service unmatched wire row')
    # The two strict recovery transcripts each consume a probe and two complete
    # transfers. No other request may hide before/after their adoption boundary.
    need(all(10 <= count <= 30 for count in counts[:2]), 'discovered service complete adoption exchanges')
    return dict(offered=sum(counts),delivered=delivered,byStage=counts)


def inspect(root):
    root = Path(root); service, original = physical(root)
    calls = preparation(root); boundaries = lifecycle(service)
    network = [slot_network(root,service.events,round,*bounds) for round,bounds in zip(service.rounds,boundaries)]
    coverage = network_coverage(root,service.events,boundaries)
    rejections = rejection_diagnostics(root)
    need(native.read(root/'discovered-transition-result.json') == dict(status='PASS',profile='5-to-4-remove',
        staleSurvivor='node-4',removed='node-5',publicRuntime=False,autonomousElection=False,independentReplay=False),
        'discovered service producer scope')
    return dict(status='PASS', scope='single-native-5-to-4-service-history', originalFirst=True, original=original,
        preparationCalls=calls,slots=network,finalIndex=9,physicalQualified=True,serviceNetworkQualified=True,
        networkCoverage=coverage,rejectedDiagnostics=rejections,autonomousElection=False,publicRuntime=False,phase3Complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('--qualify',action='store_true'); args = parser.parse_args()
    if args.qualify:
        from .discovered_service_negatives import qualify
        result = qualify(Path(args.directory))
    else: result = inspect(Path(args.directory))
    print(json.dumps(result, sort_keys=True))
