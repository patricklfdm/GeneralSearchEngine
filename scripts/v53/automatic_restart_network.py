"""Whole original-wire continuation of automatic_restart_evidence.

Physical originals are replayed first. Each dependent force then requires its
actual delivered source/ACK; unused capture data can never supply a quorum.
This qualifies one retained history, not the Phase 3 process/profile matrix.
"""
import argparse
import base64
from collections import defaultdict, deque
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import automatic_restart_evidence as p
from . import discovered_selection_evidence as x
from . import election_wait_evidence as wait

n, c, e, f, need = p.n, p.c, p.e, p.f, p.need
VOTERS = p.VOTERS


def record(raw, observation=False):
    reference = e.digest(f.canonical(dict(schema='gse-v53-vote-observation/1.3', receipt=e.digest(raw)))) if observation else e.digest(raw)
    return [[(reference, raw, 'RECORD')]]


class Phase:
    def __init__(self, events, entries, start, stop, identities):
        self.events, self.start, self.stop, self.identities = events, start, stop, identities
        self.entries = [v for v in entries if start < v['offered'] < stop]
        self.sources = []; self.controls = defaultdict(list); traces = defaultdict(list)
        self.used = set(); self.unfinished = 0
        for row in self.entries:
            if row['kind'] in ('CHUNK','TRANSFER_COMMIT'): traces[row['request']['trace']].append(row)
            else: self.controls[row['kind'],row['request']['sender']['node'],row['request']['recipient']['node']].append(row)
        for trace, rows in traces.items():
            need(str(uuid.UUID(trace)) == trace and uuid.UUID(trace).int != 0, 'restart network source trace')
            logical = defaultdict(list)
            for row in rows: logical[row['request']['sequence']].append(row)
            need(sorted(logical) == list(range(1,len(logical)+1)), 'restart network source sequence')
            ordered = []; arrivals = []
            for index in sorted(logical):
                attempts = logical[index]
                need(0 < len(attempts) <= 3 and all(v['row'] == attempts[0]['row'] for v in attempts),
                     'restart network identical source attempts')
                ordered.append(attempts[0]); arrivals.append(sorted({at for v in attempts for at in v['deliveries'] if at < stop}))
            need(all(arrivals[i] and arrivals[i][0] < ordered[i+1]['offered'] for i in range(len(ordered)-1)),
                 'restart network source before next request')
            request = ordered[0]['request']
            self.sources.append(dict(trace=trace, sender=request['sender']['node'], peer=request['recipient']['node'],
                first=request['payload']['digest'], ballot=request['ballot'], offered=ordered[0]['offered'],
                ordered=ordered, arrivals=arrivals))
        self.transfer_count = len(self.sources); self.used.update(traces)

    def at(self, node, event):
        found = [i for i in range(self.start+1,self.stop) if self.events[i].get('node') == node and self.events[i].get('event') == event]
        need(len(found) == 1, 'restart network one force: '+node+': '+event)
        return found[0]

    def ordered(self, node, names):
        n.s.ordered([v['event'] for v in self.events[self.start+1:self.stop] if v['node'] == node], names, 'restart network '+node)

    def recording(self, node):
        positions = [i for i in range(self.start+1,self.stop) if self.events[i] == dict(node=node,event='FUTURE_RETENTION_PARENT_FORCED')]
        need(len(positions) == 2 and positions[0] < self.at(node,'PUBLICATION_SELECTOR_FORCED') < positions[1]
             < self.at(node,'PUBLICATION_BEFORE_RETURN'), 'restart network record/promote force order')
        return positions[0]

    def transfer(self, reader, peer, variants, ballot, lower, upper, *, unused_offer=False):
        refs = {v[0][0] for v in variants}
        found = [v for v in self.sources if v['sender'] == reader and v['peer'] == peer and v['first'] in refs
                 and lower < v['offered'] and v['ordered'][-1]['offered'] < upper]
        need(len(found) == 1, 'restart network required original source')
        value = found[0]; self.sources.remove(value)
        ordered, arrivals = value['ordered'], value['arrivals']
        need(value['ballot'] == ballot and lower < value['offered'] and ordered[-1]['offered'] < upper,
             'restart network source before dependent force')
        complete = ordered[-1]['answer'] == 'TRANSFER_COMMIT'
        need(complete or unused_offer and ordered[-1]['answer'] == 'SOURCE_OFFER', 'restart network incomplete authority source')
        checked = ordered if complete else ordered[:-1]
        length = len(checked)
        expected = next((v for v in variants if v[0][0] == value['first'] and
            sum(2+(len(raw)+4*e.MIB-1)//(4*e.MIB) for _,raw,_ in (v if complete else v[:-1])) == length), None)
        need(expected is not None, 'restart network exact source shape')
        request = ordered[0]['request']
        need(all(v and v[0] < upper for v in (arrivals if complete else arrivals[:-1])), 'restart network original source delivered')
        n.transfer.transcript([v['row'] for v in checked], expected if complete else expected[:-1],
            request['root'], request['view'], ballot, self.identities[reader], self.identities[peer],
            'restart network source', chunk_bytes=4*e.MIB)
        if not complete:
            self.unfinished += 1
            # The sole admitted incomplete trace ends at an original unused
            # capsule offer. Its missing body/commit is never treated as arrival.
            tail = ordered[-1]; q, answer = tail['request'], tail['response']; reference, raw, kind = expected[-1]
            tid = q['payload']['id']; ids = {v['request']['payload']['id'] for v in checked}
            need(tid not in ids and q == dict(request, sequence=length+1,
                 payload=dict(id=tid,action='REQUEST',offset=0,digest=reference,bytes=''))
                 and answer == dict(q,sender=q['recipient'],recipient=q['sender'],
                     payload=dict(id=tid,kind=kind,digest=e.digest(raw),bytes=len(raw))),
                 'restart network unused original offer')
        return value

    def take(self, kind, sender, peer, *, predicate=lambda v:True):
        key = kind,sender,peer; rows = [v for v in self.controls[key] if predicate(v)]
        need(rows, 'restart network required control: '+kind)
        for v in rows:self.controls[key].remove(v)
        if not self.controls[key]:del self.controls[key]
        return rows

    def control(self, kind, sender, peer, payload, answer, reply, ballot, lower, upper, *, sequence=1, trace=None):
        rows = self.take(kind,sender,peer,predicate=lambda v:v['request']['payload'] == payload)
        delivery = x.identical_attempts(rows); q = rows[0]['request']
        need(all(v['answer'] == answer and v['response']['payload'] == reply and v['request']['ballot'] == ballot
             and v['request']['sequence'] == sequence and lower < v['offered'] < upper for v in rows)
             and delivery < upper, 'restart network exact delivered control')
        if trace is None:
            need(q['trace'] not in self.used, 'restart network distinct control trace'); self.used.add(q['trace'])
        else:need(q['trace'] == trace, 'restart network original control trace')
        return delivery,q['trace'],rows

    def probe(self, sender, peer, ballot, cut, lower, upper):
        rows = self.controls['STATUS_PROBE',sender,peer]
        eligible = [v for v in rows if v['request']['ballot'] == ballot and lower < v['offered'] < upper]
        need(eligible, 'restart network original status probe')
        trace = min(eligible,key=lambda v:v['offered'])['request']['trace']
        group = [v for v in eligible if v['request']['trace'] == trace]
        q = group[0]['request']
        return self.control('STATUS_PROBE',sender,peer,q['payload'],'STATUS',dict(cut=cut,nonce=q['payload']['nonce'],ready=False),
            ballot,lower,upper)[0]

    def finish(self):
        need(not self.sources and not self.controls, 'restart network unclassified exchange')
        return dict(exchanges=len(self.entries),transfers=self.transfer_count,unusedIncompleteTransfers=self.unfinished,_traces=self.used)


def maintenance(phase, before, owner, ballot, lower, upper, *, voters=VOTERS):
    peer = next(v for v in voters if v != owner)
    floor = phase.at(owner,'FLOOR_PARENT_FORCED')
    phase.ordered(owner,['FLOOR_COPIES_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN',
        'RETENTION_PARENT_FORCED','RETENTION_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_CLEARED',
        'FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_BEFORE_RETURN'])
    need(lower < floor < upper, 'restart network maintenance before work')
    prefix,members,packet = c.current(before[peer])
    phase.probe(owner,peer,ballot,packet['capsule']['cut'],lower,floor)
    phase.transfer(owner,peer,n.maintenance_prefixes(members,packet,c.current(before[owner])[1]),ballot,lower,floor)
    phase.transfer(owner,peer,n.maintenance_generations(before[peer][prefix+'generation.gsr'],members,packet),ballot,lower,floor)


def group(root, stage):return {node:c.inventory(root/stage/node) for node in ('node-1','node-2','node-3')}


def frozen(files, ballot):
    rows = c.journal(files['grants.gsr'],c.current(files)[2]['capsule']['root'],n.future.identity(files)['node'])
    promises = [raw for kind,raw,value in rows if kind == 'PROMISE' and value['ballot'] == ballot]
    bases = [raw for kind,raw,value in rows if kind == 'BASIS' and value['ballot'] == ballot]
    need(len(promises) == len(bases) == 1, 'restart network exact original grant')
    basis = f.decode(bases[0],'records','BASIS'); prefix = 'sources/'+basis['basisId']+'/'
    raw = files[prefix+'source.gscp']; packet = e.p.decode(raw)
    return promises[0],bases[0],raw,packet


def activate(root, events, entries, start, stop, identities, number):
    before = group(root,'before-network' if number == 1 else 'after-fence'); installed = group(root,f'installed-{number}')
    chosen = (root/f'selected-{number}.gsr').read_bytes(); selected = f.decode(chosen,'records','SELECTED'); ballot = selected['ballot']
    old = (f.decode(c.current(before['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot'] if number == 1
           else f.decode((root/'fence-request.gsw').read_bytes(),'wire','HEARTBEAT')['ballot'])
    phase = Phase(events,entries,start,stop,identities)
    # The authenticated fault has already been checked by the physical reader.
    if number == 2:
        heartbeat = phase.take('HEARTBEAT','node-2','node-1'); need(len(heartbeat) == 1, 'restart network one fence')
        phase.used.add(heartbeat[0]['request']['trace'])
    allocation = phase.at('node-1','ALLOCATOR_BEFORE_WRITE')
    discovery_end = allocation if number == 1 else phase.at('node-1','FLOOR_PARENT_FORCED')
    previous = start
    for peer in ('node-2','node-3'):
        previous = phase.probe('node-1',peer,old,c.current(before[peer])[2]['capsule']['cut'],previous,discovery_end)
    if number == 2:maintenance(phase,before,'node-1',old,previous,allocation)
    local_promise,_,_,_ = frozen(installed['node-1'],ballot)
    for node in VOTERS:
        phase.ordered(node,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN',
            'SELECTED_FORCED','SELECTED_BEFORE_RETURN','INSTALL_SELECTOR_FORCED','INSTALL_PARENT_FORCED','INSTALL_BEFORE_RETURN'])
    phase.ordered('node-1',['ALLOCATOR_FORCED','ALLOCATOR_DIRECTORY_FORCED','ALLOCATOR_BEFORE_RETURN','PROMISE_FORCED'])
    if number == 2:maintenance(phase,before,'node-2',ballot,allocation,phase.at('node-2','PROMISE_FORCED'))
    local_selected = phase.at('node-1','SELECTED_FORCED')
    prepared_peers = [peer for peer in ('node-2','node-3') if ('PREPARE','node-1',peer) in phase.controls]
    need(prepared_peers in (['node-2'],['node-2','node-3']) and (number == 2 or prepared_peers == ['node-2']),
         'restart network bounded activation candidates')
    campaign_trace = None
    for ordinal,peer in enumerate(prepared_peers,1):
        promise,basis,raw,packet = frozen(installed[peer],ballot)
        phase.ordered(peer,['PROMISE_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'])
        phase.transfer(peer,'node-1',record(local_promise),ballot,phase.at('node-1','BASIS_FORCED'),phase.at(peer,'PROMISE_FORCED'))
        delivery,trace,_ = phase.control('PREPARE','node-1',peer,dict(promise=e.digest(local_promise)),
            'PROMISE',dict(basis=e.digest(basis)),ballot,phase.at(peer,'GRANT_BEFORE_RETURN'),stop,sequence=ordinal,trace=campaign_trace)
        if campaign_trace is None:campaign_trace = trace
        expected = [(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),(e.digest(packet['capsuleBytes']),raw,'CAPSULE')]
        phase.transfer('node-1',peer,[expected],ballot,max(phase.at(peer,'BASIS_FORCED'),delivery),
            stop if peer=='node-3' else local_selected,unused_offer=peer=='node-3')
    phase.transfer('node-2','node-1',record(chosen),ballot,local_selected,phase.at('node-2','SELECTED_FORCED'))
    promise,basis,raw,packet = frozen(installed['node-1'],ballot)
    phase.transfer('node-2','node-1',[[(e.digest(basis),basis,'RECORD'),(e.digest(promise),promise,'RECORD'),
        (e.digest(packet['capsuleBytes']),raw,'CAPSULE')]],ballot,phase.at('node-1','BASIS_FORCED'),phase.at('node-2','SELECTED_FORCED'))
    delivered,_,_ = phase.control('SELECTED','node-1','node-2',dict(selection=e.digest(chosen)),
        'INSTALL_ACK',dict(selection=e.digest(chosen),cut=selected['cut']),ballot,phase.at('node-2','INSTALL_BEFORE_RETURN'),stop,
        sequence=len(prepared_peers)+1,trace=campaign_trace)
    need(delivered < phase.at('node-1','INSTALL_SELECTOR_FORCED'), 'restart network peer installed before local installation')
    if 'node-3' in prepared_peers:
        need(not any(v['node']=='node-3' and v['event'] in ('SELECTED_FORCED','INSTALL_SELECTOR_FORCED') for v in events[start+1:stop]),
             'restart network unused source cannot install')
    return phase.finish()


def slot(root, events, entries, start, stop, identities, index, *, before_stage=None, voters=VOTERS, received_requests=False, carried=False):
    # Both callers physically reconstruct these exact snapshots first. A cold
    # reopen may select a different peer whose own future ledger starts lower;
    # its revision is derived from that original frame, never from slot number.
    # Receive-only events are allowed only after the caller validates raw sends.
    before = group(root,before_stage or ('installed-1' if index == 1 else 'installed-2' if index == 2 else 'published-2'))
    need(voters in (('node-1','node-2'),('node-1','node-3')), 'restart network stable pair')
    peer = voters[1]; unused = next(node for node in identities if node not in voters)
    applied = group(root,f'applied-{index}'); published = group(root,f'published-{index}')
    selected_raw = c.current(before['node-1'])[1]['selected.gsr']; selected = f.decode(selected_raw,'records','SELECTED'); ballot = selected['ballot']
    frames,_ = c.pending(applied['node-1']['pending.accept'],('PROOF','CERTIFICATE'))
    phase = Phase(events,entries,start,stop,identities)
    need(type(carried) is bool and (not carried or selected['nextEntry'] == e.digest(frames['ENTRY'])
         and f.decode(frames['ENTRY'],'records','ENTRY')['origin'] != ballot), 'restart network original carried entry')
    for value in phase.entries:
        need(value['request']['ballot'] == ballot and value['request']['sender']['node'] in voters
             and value['request']['recipient']['node'] in voters,'restart network current slot authority')
    for node in voters:
        maintenance(phase,before,node,ballot,phase.at(node,'ACCEPT_PARENT_FORCED') if carried else start,
            phase.at(node,'PROOF_PARENT_FORCED') if carried else phase.at(node,'ACCEPT_PARENT_FORCED'),voters=voters)
        phase.ordered(node,['ACCEPT_PARENT_FORCED','PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED',
            'FUTURE_RETENTION_PARENT_FORCED','PUBLICATION_SELECTOR_FORCED','FUTURE_RETENTION_PROMOTED','PUBLICATION_BEFORE_RETURN'])
    need(not any(v['node']==unused and not (received_requests and v['event']=='NETWORK_REQUEST') for v in events[start+1:stop]),
         'restart network no unselected slot work')
    def observed(node,kind):return f.canonical(dict(root=selected['root'],voter=node,incarnation=identities[node]['storage'],
        phase=kind,record=e.digest(frames[kind])))
    for kind in ('ACCEPT','ENTRY') + (('PAYLOAD',) if f.decode(frames['ENTRY'],'records','ENTRY')['kind'] == 'DATA' else ()):
        phase.transfer(peer,'node-1',record(frames[kind]),ballot,phase.at('node-1','ACCEPT_PARENT_FORCED'),phase.at(peer,'ACCEPT_PARENT_FORCED'))
    phase.transfer(peer,'node-1',record(observed('node-1','ACCEPT'),True),ballot,
        phase.at('node-1','ACCEPT_PARENT_FORCED'),phase.at(peer,'ACCEPT_PARENT_FORCED'))
    phase.transfer('node-1',peer,record(observed(peer,'ACCEPT'),True),ballot,
        phase.at(peer,'ACCEPT_PARENT_FORCED'),phase.at('node-1','PROOF_PARENT_FORCED'))
    phase.transfer(peer,'node-1',record(frames['PROOF']),ballot,
        phase.at('node-1','PROOF_PARENT_FORCED'),phase.at(peer,'PROOF_PARENT_FORCED'))
    phase.transfer(peer,'node-1',record(observed('node-1','ACCEPT'),True),ballot,
        phase.at(peer,'ACCEPT_PARENT_FORCED'),phase.at(peer,'PROOF_PARENT_FORCED'))
    phase.transfer('node-1',peer,record(observed(peer,'PROOF'),True),ballot,
        phase.at(peer,'PROOF_PARENT_FORCED'),phase.at('node-1','CERTIFICATE_PARENT_FORCED'))
    phase.transfer(peer,'node-1',record(frames['CERTIFICATE']),ballot,
        phase.at('node-1','CERTIFICATE_PARENT_FORCED'),phase.at(peer,'CERTIFICATE_PARENT_FORCED'))
    for kind in ('ACCEPT','PROOF'):
        phase.transfer(peer,'node-1',record(observed('node-1',kind),True),ballot,
            phase.at(peer,'PROOF_PARENT_FORCED'),phase.at(peer,'CERTIFICATE_PARENT_FORCED'))
    for node in voters:
        other = next(v for v in voters if v != node)
        for name,raw in applied[other].items():
            if name.startswith('applied-end/') and name.endswith('ack.gsr'):
                phase.transfer(node,other,record(raw),ballot,phase.at(other,'APPLY_ACK_DIRECTORY_FORCED'),phase.at(node,'PUBLICATION_SELECTOR_FORCED'))
    for kind,key in (('ACCEPT','acceptance'),('PROOF','proof')):
        phase.control(kind,'node-1',peer,{key:e.digest(frames[kind])},kind+'_ACK',
            dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer,kind))),ballot,
            phase.at(peer,kind+'_PARENT_FORCED'),phase.at('node-1',('PROOF' if kind=='ACCEPT' else 'CERTIFICATE')+'_PARENT_FORCED'))
    certificate = e.digest(frames['CERTIFICATE']); payload = dict(certificate=certificate,selection=e.digest(selected_raw))
    phase.control('APPLY','node-1',peer,payload,'APPLY_ACK',dict(payload,
        statement=e.digest(applied[peer]['applied-end/statement.gsr']),acknowledgement=e.digest(applied[peer]['applied-end/ack.gsr'])),
        ballot,phase.at(peer,'APPLY_ACK_DIRECTORY_FORCED'),phase.recording('node-1'))
    parent = c.anchor(c.current(before['node-1'])[2]['capsule']); upper = c.anchor(c.current(published['node-1'])[2]['capsule'])
    intent = dict(selection=e.digest(selected_raw),certificate=certificate,peer=identities[peer],lower=parent,parent=parent,upper=upper)
    future_frames = {}; revisions = {}
    for node in voters:
        files = applied[node]; raw = files[n.future.FILE]
        revision = json.loads(raw[48:48+int.from_bytes(raw[44:48],'big')])['revision']+1; revisions[node] = revision
        records = {k:files['applied-end/'+k] for k in ('selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','ack.gsr')}
        local = c.current(files)[1]; records.update({k:local[k] for k in ('promise.gsr','selected.gsr')})
        records.update({kind.lower()+'.gsr':frames[kind] for kind in ('ENTRY','ACCEPT','PROOF')})
        future_frames[node] = n.future.frame(dict(n.future.initial(files),revision=revision,previous=e.digest(raw),
            parent=parent,peers=[dict(identity=identities[peer],lower=parent)]),records)
        promoted = n.future.frame(dict(n.future.initial(files),revision=revision+1,previous=e.digest(future_frames[node])),{})
        need(published[node][n.future.FILE] == promoted,'restart network original future recording')
    quorum = phase.at('node-1','FUTURE_QUORUM_COMPLETE')
    need(events[quorum] == dict(node='node-1',event='FUTURE_QUORUM_COMPLETE',index=index,voters=list(voters)),
         'restart network actual recording majority')
    need(phase.recording('node-1') < quorum,'restart network local recording before quorum')
    _,trace,future_rows = phase.control('FUTURE_RETENTION_INTENT','node-1',peer,intent,'FUTURE_RETENTION_ACK',
        dict(intent=e.digest(f.canonical(intent)),storage='FUTURE',revision=revisions[peer],digest=e.digest(future_frames[peer])),
        ballot,phase.recording(peer),quorum,sequence=sorted(identities).index(peer)+1)
    prefix,_,packet = c.current(published[peer])
    _,_,rows = phase.control('PUBLISH','node-1',peer,dict(certificate=certificate),'PUBLISH_ACK',
        dict(certificate=certificate,selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),
             generation=e.digest(published[peer][prefix+'generation.gsr'])),ballot,
        phase.at(peer,'PUBLICATION_BEFORE_RETURN'),phase.at('node-1','PUBLICATION_SELECTOR_FORCED'),sequence=4,trace=trace)
    sends = [(i,v) for i,v in enumerate(events) if start < i < stop and v['event']=='PUBLICATION_SEND_BOUNDARY']
    hashes = {e.digest(base64.b64decode(v['row']['request'],validate=True)) for v in rows}
    need(sends and all(quorum < i and v['node']=='node-1' and v['request'] in hashes for i,v in sends)
         and {v['request'] for _,v in sends} == hashes and len(sends) <= 3,
         'restart network recording before every publication send')
    for row in rows:
        digest = e.digest(base64.b64decode(row['row']['request'],validate=True))
        need(any(v['request']==digest and i < row['offered'] for i,v in sends),'restart network original publication send')
    rejected = dict(future_rows[0]['request'],recipient=identities[unused],sequence=sorted(identities).index(unused)+1)
    result = phase.finish(); result.update(index=index,recordingQuorums=1,
        _rejected=e.digest(f.encode('wire','FUTURE_RETENTION_INTENT',rejected))); return result


def deliveries(events, entries):
    """Every observed client delivery has a distinct preceding real response.

    A duplicate response may remain undelivered after cancellation. Invented,
    early or duplicated delivery events cannot satisfy a source/majority gate.
    """
    available = defaultdict(deque); offered = defaultdict(list)
    for value in entries:
        digest = e.digest(base64.b64decode(value['row']['response'],validate=True))
        offered[value['offered']].append((value['request']['sender']['node'],value['answer'],digest))
    for at,row in enumerate(events):
        for key in offered[at]: available[key].append(at)
        if row['event'] != 'NETWORK_RECEIVED':continue
        need(set(row)=={'node','event','kind','response'},'restart network delivery shape')
        key = row['node'],row['kind'],row['response']
        need(available[key] and available[key][0] < at,'restart network delivery without original response')
        available[key].popleft()


def validate(root):
    root = Path(root); physical = p.validate(root)
    events = n.read(root/'events.json'); identities = {node:n.future.identity(files) for node,files in group(root,'before-network').items()}
    wait.lifecycle(n.read(root/'calls.json'),events[:len(wait.REOPEN)*len(identities)],identities)
    entries = x.exchanges(root,events,-1,len(events),identities)
    deliveries(events,entries)
    root_hash = c.current(group(root,'before-network')['node-1'])[2]['capsule']['root']
    view = f.decode((root/'selected-1.gsr').read_bytes(),'records','SELECTED')['view']
    need(all(v['request']['root']==root_hash and v['request']['view']==view for v in entries),'restart network original root/view')
    held = [(i,v) for i,v in enumerate(events) if v['event'].startswith('ROUND_')]
    boundaries = [(-1,held[0][0]),(held[0][0],held[2][0]),(held[2][0],held[4][0]),
        (held[4][0],held[6][0]),(held[6][0],held[9][0])]
    results = []; traces = set(); rejected = []
    for ordinal,(start,stop) in enumerate(boundaries):
        result = (activate(root,events,entries,start,stop,identities,1 if ordinal==0 else 2) if ordinal in (0,2)
                  else slot(root,events,entries,start,stop,identities,{1:1,3:2,4:3}[ordinal]))
        own = result.pop('_traces')
        need(not traces.intersection(own) and all(str(uuid.UUID(v))==v and uuid.UUID(v).int!=0 for v in own),
             'restart network fresh cross-phase traces')
        traces.update(own)
        if '_rejected' in result:rejected.append(result.pop('_rejected'))
        results.append(result)
    need(sum(v['exchanges'] for v in results)==len(entries),'restart network full history coverage')
    # Diagnostic failures are not vote authority. Retain all three finite
    # unselected intent groups, with exact pre-/post-PREPARE error classes.
    failures = n.read(root/'failures.json'); groups = []
    for row in failures:
        need(set(row)=={'node','kind','request','failure'} and row['node']=='node-3'
             and row['kind']=='FUTURE_RETENTION_INTENT' and len(row['request'])==64
             and all(v in '0123456789abcdef' for v in row['request']),'restart network rejection owner')
        if not groups or groups[-1][0]['request'] != row['request']:groups.append([])
        groups[-1].append(row)
    need(len(groups)==3 and len({v[0]['request'] for v in groups})==3 and all(1<=len(v)<=3 for v in groups),
         'restart network bounded unused rejections')
    for index,rows in enumerate(groups):
        reason = ('higher ballot observed; fresh campaign required' if index==0 else 'retention intent installed selection required')
        need(all(v['failure']=='java.lang.IllegalArgumentException: '+reason and v['request']==rejected[index] for v in rows),
             'restart network original rejection kind')
    transfers=sum(v['transfers'] for v in results); unfinished=sum(v['unusedIncompleteTransfers'] for v in results)
    return dict(status='PASS',scope='one-native-automatic-two-campaign-history',originalFirst=True,physical=physical,
        phases=results,exchanges=len(entries),transfers=transfers,completeTransfers=transfers-unfinished,unusedIncompleteTransfers=unfinished,
        fullWireReplay=True,processRestart=False,publicRuntime=False,phase3Complete=False)


NEGATIVES = {
    'missing-discovery': 'restart network original status probe',
    'discovery-cut': 'restart network exact delivered control',
    'missing-response-row': 'discovered selection unmatched response event',
    'invented-delivery': 'restart network delivery without original response',
    'early-delivery': 'restart network delivery without original response',
    'source-bytes': 'restart network source exact data',
    'source-reference': 'restart network required original source',
    'source-offer': 'restart network source original offer',
    'missing-authority-commit': 'restart network incomplete authority source',
    'unused-capsule-offer': 'restart network unused original offer',
    'missing-unused-offer': 'restart network exact source shape',
    'missing-basis-force': 'selected retention force order: restart network node-2',
    'missing-install-force': 'selected retention force order: restart network node-2',
    'basis-reply': 'restart network exact delivered control',
    'late-basis-delivery': 'restart network required original source',
    'reply-identity': 'discovered selection wire correlation',
    'vote-receipt': 'restart network exact delivered control',
    'apply-statement': 'restart network exact delivered control',
    'future-revision': 'restart network exact delivered control',
    'future-digest': 'restart network exact delivered control',
    'early-quorum': 'restart network local recording before quorum',
    'wrong-quorum': 'restart network actual recording majority',
    'early-publication': 'restart network recording before every publication send',
    'missing-retirement': 'selected retention force order: restart network node-1',
    'foreign-rejection': 'restart network original rejection kind',
    'cross-phase-trace': 'restart network fresh cross-phase traces',
    'missing-parent-ack': 'restart network required original source',
    'excessive-control-attempts': 'discovered selection identical bounded attempts',
    'bootstrap-force': 'closed election wait initialization',
}


def mutate(root, name):
    rows = n.read(root/'wire.json'); events = n.read(root/'events.json')
    def decode(row):return n.transfer.t.wire(row['request']),n.transfer.t.wire(row['response'])
    def find(kind, predicate=lambda q,answer:True):
        return next(row for row in rows if (lambda pairs:pairs[0][0]==kind and predicate(pairs[0][1],pairs[1]))(decode(row)))
    def remove(row):
        qhash,rhash = (e.digest(base64.b64decode(row[k],validate=True)) for k in ('request','response'))
        rows.remove(row)
        events[:] = [v for v in events if not(v['event']=='WIRE_RESPONSE' and v['request']==qhash and v['response']==rhash)
                     and not(v['event']=='NETWORK_RECEIVED' and v['response']==rhash)]
    def rewrite(row, change):
        (kind,q),(answer,z)=decode(row); old_q,old_z=row['request'],row['response']
        qhash,rhash=(e.digest(base64.b64decode(v,validate=True)) for v in (old_q,old_z))
        change(q,z);qraw=f.encode('wire',kind,q);zraw=f.encode('wire',answer,z)
        for other in rows:
            if other['request']==old_q and other['response']==old_z:
                other.update(request=base64.b64encode(qraw).decode(),response=base64.b64encode(zraw).decode())
        for event in events:
            if event['event']=='WIRE_RESPONSE' and event['request']==qhash and event['response']==rhash:
                event.update(request=e.digest(qraw),response=e.digest(zraw))
            elif event['event']=='NETWORK_RECEIVED' and event['response']==rhash:event['response']=e.digest(zraw)
    def force(node, event):return next(v for v in events if v['node']==node and v['event']==event)
    if name=='missing-discovery':remove(find('STATUS_PROBE',lambda q,z:q['ballot']['counter']==1))
    elif name=='discovery-cut':rewrite(find('STATUS_PROBE',lambda q,z:q['ballot']['counter']==1),lambda q,z:z['payload']['cut'].update(index=99))
    elif name=='missing-response-row':rows.remove(find('CHUNK'))
    elif name=='invented-delivery':events.append(dict(node='node-1',event='NETWORK_RECEIVED',kind='TRANSFER_COMMIT',response='0'*64))
    elif name=='early-delivery':
        row=next(v for v in events if v['event']=='NETWORK_RECEIVED' and v['kind']=='TRANSFER_COMMIT');events.remove(row)
        at=next(i for i,v in enumerate(events) if v['event']=='WIRE_RESPONSE' and v['response']==row['response']);events.insert(at,row)
    elif name=='source-bytes':rewrite(find('CHUNK',lambda q,z:z[0]=='CHUNK'),
        lambda q,z:z['payload'].update(bytes=base64.b64encode(b'changed').decode(),digest=e.digest(b'changed')))
    elif name=='source-reference':rewrite(find('CHUNK'),lambda q,z:q['payload'].update(digest='0'*64))
    elif name=='source-offer':rewrite(find('CHUNK'),lambda q,z:z['payload'].update(digest='0'*64))
    elif name=='missing-authority-commit':remove(find('TRANSFER_COMMIT'))
    elif name in ('unused-capsule-offer','missing-unused-offer'):
        row=find('CHUNK',lambda q,z:q['recipient']['node']=='node-3' and z[0]=='SOURCE_OFFER' and z[1]['payload']['kind']=='CAPSULE')
        if name=='missing-unused-offer':remove(row)
        else:rewrite(row,lambda q,z:z['payload'].update(digest='0'*64))
    elif name in ('missing-basis-force','missing-install-force','missing-retirement'):
        node,event={'missing-basis-force':('node-2','BASIS_FORCED'),'missing-install-force':('node-2','INSTALL_PARENT_FORCED'),
            'missing-retirement':('node-1','RETIREMENT_CLEARED')}[name];events.remove(force(node,event))
    elif name=='late-basis-delivery':
        row=find('PREPARE');response=e.digest(base64.b64decode(row['response'],validate=True))
        delivery=next(v for v in events if v['event']=='NETWORK_RECEIVED' and v['response']==response)
        events.remove(delivery)
        selected=next(i for i,v in enumerate(events) if v['node']=='node-1' and v['event']=='SELECTED_FORCED')
        events.insert(selected,delivery)
    elif name in ('basis-reply','reply-identity','vote-receipt','apply-statement','future-revision','future-digest'):
        kind={'basis-reply':'PREPARE','reply-identity':'PREPARE','vote-receipt':'ACCEPT','apply-statement':'APPLY',
            'future-revision':'FUTURE_RETENTION_INTENT','future-digest':'FUTURE_RETENTION_INTENT'}[name]
        def change(q,z):
            if name=='reply-identity':z['sender']=z['recipient']
            elif name=='future-revision':z['payload']['revision']+=1
            else:z['payload'][{'basis-reply':'basis','vote-receipt':'receipt','apply-statement':'statement','future-digest':'digest'}[name]]='0'*64
        rewrite(find(kind),change)
    elif name in ('early-quorum','wrong-quorum','early-publication'):
        row=force('node-1','FUTURE_QUORUM_COMPLETE')
        if name=='wrong-quorum':row['voters']=['node-1']
        elif name=='early-quorum':
            events.remove(row);events.insert(events.index(force('node-1','FUTURE_RETENTION_PARENT_FORCED')),row)
        else:
            send=force('node-1','PUBLICATION_SEND_BOUNDARY');events.remove(send);events.insert(events.index(row),send)
    elif name=='foreign-rejection':
        failures=n.read(root/'failures.json');old=failures[0]['request']
        for v in failures:
            if v['request']==old:v['request']='0'*64
        (root/'failures.json').write_bytes(f.canonical(failures))
    elif name=='cross-phase-trace':
        old=decode(find('CHUNK'))[0][1]['trace']
        target=decode(find('CHUNK',lambda q,z:q['ballot']['counter']==3))[0][1]['trace']
        originals=[v for v in rows if decode(v)[0][1]['trace']==target]
        for row in originals:rewrite(row,lambda q,z:(q.update(trace=old),z.update(trace=old)))
    elif name=='missing-parent-ack':
        digest=e.digest((root/'applied-2/node-1/applied-end/parent-ack.gsr').read_bytes())
        row=find('CHUNK',lambda q,z:q['sender']['node']=='node-2' and q['payload']['digest']==digest)
        trace=decode(row)[0][1]['trace']
        for other in list(rows):
            if decode(other)[0][1]['trace']==trace:remove(other)
    elif name=='excessive-control-attempts':
        row=find('PREPARE',lambda q,z:q['ballot']['counter']==4 and q['recipient']['node']=='node-2')
        count=sum(v==row for v in rows);qhash,rhash=(e.digest(base64.b64decode(row[k],validate=True)) for k in ('request','response'))
        event=next(v for v in events if v['event']=='WIRE_RESPONSE' and v['request']==qhash and v['response']==rhash)
        at=events.index(event)
        for _ in range(4-count):rows.append(dict(row));events.insert(at,dict(event))
    elif name=='bootstrap-force':
        calls=n.read(root/'calls.json');calls[0]['events'].remove('RETENTION_PARENT_FORCED')
        (root/'calls.json').write_bytes(f.canonical(calls))
    else:raise ValueError('unknown restart network mutation')
    (root/'wire.json').write_bytes(f.canonical(rows));(root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    cases={**{name:pair[1] for name,pair in p.NEGATIVES.items()},**NEGATIVES}
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-automatic-network-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path)
            (mutate if name in NEGATIVES else p.mutate)(path,name)
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'restart network unrelated negative '+name+': '+str(error))
            else:raise ValueError('restart network accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
