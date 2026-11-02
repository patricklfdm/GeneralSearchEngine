"""Original physical replay of native process loss during an unreturned DATA.

No client success is inferred from the interrupted vote. A retained old entry
must be reaccepted under the new ballot before a separate fresh READY barrier.
Complete process/network qualification is layered on this physical reducer.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import struct
import tempfile
import uuid
from . import node_owner_evidence as p
from . import distinct_minority_evidence as carried
from . import node_owner_network as net
from . import node_process_evidence as process

n, b, c, e, f, need = p.n, p.b, p.c, p.e, p.f, p.need
CUTS = ('ACCEPT_PARENT_FORCED', 'PROOF_PARENT_FORCED')
RENAME_CUTS = ('ACCEPT_RENAMED', 'PROOF_RENAMED')


def pending_phase(point):
    need(point in (*CUTS, *RENAME_CUTS), 'inflight original crash point')
    return 'ACCEPT' if point in (CUTS[0], RENAME_CUTS[0]) else 'PROOF'


def rename_prefix(events, point):
    """A process-visible rename is not a directory force or an ACK."""
    phase = pending_phase(point)
    if point not in RENAME_CUTS: return
    observed = [v['event'] for v in events if v['node'] == 'node-1' and v['event'].startswith(phase+'_')]
    expected = [phase+'_'+v for v in ('VALIDATED', 'CANDIDATE_CREATED', 'PREFIX_WRITTEN',
        'CANDIDATE_WRITTEN', 'CANDIDATE_FORCED', 'CANDIDATE_PARENT_FORCED', 'RENAMED')]
    need(observed == expected, 'inflight exact pre-directory-force prefix')


class Service(p.Service):
    def interrupt(self, point):
        phase = pending_phase(point)
        self.point = point; self.old_voters = self.voters
        before = self.group; maintained = self.maintenance(before, self.voters)
        self.group = dict(before)
        names = ('node-1',) if phase == 'ACCEPT' else self.voters
        for node in names: self.group[node] = maintained[node]
        _, local, packet = c.current(self.group['node-1']); cap = packet['capsule']
        selected = f.decode(local['selected.gsr'], 'records', 'SELECTED')
        self.body = carried.payload(100, 'node-owner-100')
        self.carried = carried.entry(self.group, self.body, selected['ballot'])
        accept = f.encode('records', 'ACCEPT', dict(root=cap['root'], authority=selected['view'], ballot=selected['ballot'],
            index=2, entry=e.digest(self.carried)))
        witnesses = [dict(voter=node, incarnation=n.future.identity(before[node])['storage'],
            receipt=e.digest(f.canonical(dict(root=cap['root'], voter=node, incarnation=n.future.identity(before[node])['storage'],
                phase='ACCEPT', record=e.digest(accept))))) for node in self.voters]
        proof = f.encode('records', 'PROOF', dict(f.decode(accept, 'records', 'ACCEPT'), accepts=witnesses))
        self.pending_phases = {}
        for node in names:
            files = self.group[node]; _, members, _ = c.current(files)
            vote = e.container([files['selector.gsr'], members['promise.gsr'], members['selected.gsr'], self.carried, accept], self.body)
            phases = ('PROOF',) if node == 'node-1' and phase == 'PROOF' else ()
            if phases: vote += proof; vote = vote[:8]+struct.pack('>I', len(vote))+vote[12:]
            self.group[node] = dict(files, **{'pending.accept': vote}); self.pending_phases[node] = phases
        b.match(self.root, 'before-reopen', self.group)

    def campaign(self, number, counter):
        if number != 2: return super().campaign(number, counter)
        chosen = (self.root/'selected-2.gsr').read_bytes(); observed = f.decode(chosen, 'records', 'SELECTED')
        voters = tuple(v['voter'] for v in observed['sources'])
        need(voters in (('node-1', 'node-2'), ('node-1', 'node-3')), 'inflight selected majority')
        own = n.future.identity(self.group['node-1']); ballot = dict(counter=counter, proposer='node-1', incarnation=own['storage'])
        maintained = self.maintenance(self.group, self.old_voters)
        prepared = {}; frozen = {}; ids = set(); tails = {}
        for node, previous in self.group.items():
            actual = c.inventory(self.root/'installed-2'/node)
            if node not in voters and actual['grants.gsr'] == previous['grants.gsr']: continue
            files = previous; prefix, members, packet = c.current(files)
            inactive = any(k.startswith('generations/') and k not in (prefix[:-1],) and not k.startswith(prefix) for k in files)
            if files['pending.accept'] == c.EMPTY and inactive:
                need(node in self.old_voters, 'inflight original maintenance cohort'); files = maintained[node]
            _, members, _ = c.current(files)
            raw, tail = carried.captured(files, self.pending_phases.get(node, ())); packet = e.p.decode(raw); cap = packet['capsule']
            prior = c.journal(files['grants.gsr'], cap['root'], node); rows = c.journal(actual['grants.gsr'], cap['root'], node)
            need(rows[:len(prior)] == prior and [v[0] for v in rows[len(prior):]] ==
                 ['PROMISE', 'BASIS']+(['SELECTED'] if node in voters else []), 'inflight original grant extension')
            identifier = rows[len(prior)][2]['basisId']
            need(str(uuid.UUID(identifier)) == identifier and identifier not in ids
                 and all(v[2].get('basisId') != identifier for v in prior), 'inflight fresh source identity')
            ids.add(identifier)
            value = dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']), ballot=ballot, basisId=identifier)
            promise = f.encode('records', 'PROMISE', value); wrapper = n.s.s.wrap(promise, files[n.s.FILE])
            raw = c.packet_bytes(cap, dict(packet['objects'], **{e.digest(wrapper): wrapper}), packet['images']); packet = e.p.decode(raw)
            basis = f.encode('records', 'BASIS', dict(value, voter=node, cut=cap['cut'], capsule=e.digest(packet['capsuleBytes']),
                inventory=e.digest(packet['indexBytes']), accepted=tail))
            source = 'sources/'+identifier
            prepared[node] = dict(files, **{'grants.gsr':files['grants.gsr']+promise+basis, source:None, source+'/source.gscp':raw},
                **{source+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
            if node == 'node-1': prepared[node]['allocator.gsr'] = f.encode('records', 'ALLOCATOR', dict(root=cap['root'], node=node, counter=counter))
            frozen[node] = dict(promise=promise, basis=basis, packet=packet, wrapper=wrapper, members=members); tails[node] = tail
        source = frozen['node-1']; cap = source['packet']['capsule']; tail = tails['node-1']
        need(tail is not None and all(frozen[node]['packet']['capsule']['cut']['index'] <= cap['cut']['index'] for node in voters),
             'inflight retained proposer source')
        accepted = source['packet']['objects'][tail]; original_accept = f.decode(accepted, 'records', 'ACCEPT')
        need(original_accept['entry'] == e.digest(self.carried) and original_accept['index'] == cap['cut']['index']+1,
             'inflight exact retained next entry')
        for node in voters:
            if tails[node] is not None:
                need(frozen[node]['packet']['objects'][tails[node]] == accepted, 'inflight same original accepted value')
        selected = f.encode('records', 'SELECTED', dict(root=cap['root'], view=e.authority(cap['root'], cap['cut']['view']),
            ballot=ballot, cut=cap['cut'], nextEntry=e.digest(self.carried), sources=[dict(voter=node,
                basisId=f.decode(frozen[node]['basis'], 'records', 'BASIS')['basisId'], basisDigest=e.digest(frozen[node]['basis'])) for node in voters]))
        need(selected == chosen, 'inflight original selected tail')
        installed = dict(self.group, **prepared)
        for node in voters:
            files = prepared[node]; prefix = c.current(files)[0]
            intent = n.s.intent(n.future.identity(files), selected, files[n.s.FILE],
                [(frozen[v]['basis'], frozen[v]['packet'], frozen[v]['wrapper']) for v in voters])
            objects = dict(n.slot.prefix(source['packet'], files['root.gsr']), **{e.digest(intent):intent, tail:accepted,
                e.digest(self.carried):self.carried, e.digest(self.body):self.body})
            raw = c.packet_bytes(cap, objects, source['packet']['images'])
            members = dict(zip(('promise.gsr', 'basis.gsr'), (frozen[node]['promise'], frozen[node]['basis'])),
                **{'selected.gsr':selected, 'selected-sources.gsr':b''.join(frozen[v]['basis'] for v in voters),
                   'source.gscp':raw, 'owned-tail.gsr':accepted},
                **{h+'.image':source['members'][h+'.image'] for h in source['packet']['images']})
            selector, generation = c.generation(members, cap, node, 'b' if prefix == 'generations/a/' else 'a', tail)
            installed[node] = dict(files, **generation, **{'selector.gsr':selector, 'grants.gsr':files['grants.gsr']+selected,
                n.s.FILE:self.merge_peers(files[n.s.FILE], [prepared[v][n.s.FILE] for v in voters])})
        self.group = installed; self.voters = voters; self.active = list(voters); self.first = None; self.selection_anchor = c.anchor(cap)
        b.match(self.root, 'installed-2', self.group)

    def entry_bytes(self, fields):
        if fields['index'] != 2: return super().entry_bytes(fields)
        old = f.decode(self.carried, 'records', 'ENTRY')
        need(dict(old, origin=fields['origin']) == fields, 'inflight exact carried request')
        return self.carried

    def snapshot(self, label, group):
        if self.slot == 2 and label == 'slot-2-accepted':
            # The new ballot must first force the old value on the selected
            # owners. Only then does the real driver establish/retire the floor.
            self.group = self.maintenance(group, self.voters, after_accept=True)
        return super().snapshot(label, group)

    def advance(self, kind):
        if self.slot == 1:
            need(kind == 'DATA', 'inflight recovery publishes original DATA first'); self.publish(kind, self.body)
        else: super().advance(kind)


def physical(root, point):
    root = Path(root); p.inventory(root)
    group = n.s.initialize(b.original(root, 3, False))
    group = {node:dict(files, **{n.future.FILE:n.future.frame(n.future.initial(files), {})}) for node, files in group.items()}
    b.match(root, 'before-network', group)
    service = Service(root, group); service.campaign(1, 2); service.advance('BARRIER')
    b.match(root, 'first-ready', service.group); service.interrupt(point)
    service.campaign(2, 3); service.advance('DATA'); service.advance('BARRIER')
    b.match(root, 'second-ready', service.group); service.advance('DATA'); b.match(root, 'after-close', service.group)
    return service


def lifecycle(root, point, *, reconciled=False):
    events = n.read(root/'events.json')
    initial = [dict(node=node,incarnation=1,event=event) for node in ('node-1','node-2','node-3') for event in (*p.wait.REOPEN,'NODE_OPEN')]
    need(events[:len(initial)] == initial, 'inflight original opens')
    p.wait.lifecycle(n.read(root/'calls.json'),
        [dict(node=node,event=event) for node in ('node-1','node-2','node-3') for event in p.wait.REOPEN],('node-1','node-2','node-3'))
    marks = [(i,row) for i,row in enumerate(events) if row['event'].startswith(('NODE_','ROUND_'))]
    first = ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY','SLOT_BEGIN']
    second = ['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY','SLOT_BEGIN','SLOT_COMPLETE']
    if reconciled: second = second[:-2]+['INSTALLED','SLOT_BEGIN','SLOT_COMPLETE','BEFORE_READY']+second[-2:]
    expected = ['NODE_OPEN']*3+['ROUND_'+v for v in first]+['NODE_CRASH','NODE_OPEN']+['ROUND_'+v for v in second]+['NODE_CLOSED']
    need([v['event'] for _,v in marks] == expected, 'inflight exact lifecycle order')
    death, opened = marks[8][0],marks[9][0]
    # Recovery forces the original pending phase. A retained PROOF must not be
    # treated as the empty/ACCEPT recovery used by the completed-DATA fixture.
    phase = pending_phase(point)
    reopen = (*p.wait.REOPEN[:-2], phase+'_ACTIVE_FORCED', phase+'_ACTIVE_PARENT_FORCED')
    need(events[death+1:opened] == [dict(node='node-1',incarnation=2,event=event) for event in reopen], 'inflight exact original reopen')
    for at,row in enumerate(events):
        need(row.get('node') in ('node-1','node-2','node-3') and
             ('incarnation' in row or row['event'] in ('FUTURE_QUORUM_COMPLETE','PUBLICATION_SEND_BOUNDARY')), 'inflight event lifetime required')
        if 'incarnation' in row:
            need(type(row['incarnation']) is int and row['incarnation'] == (2 if at>death and row['node']=='node-1' else 1), 'inflight original event lifetime')
    selection = None; completion = None; entry = None; begins = []; original = None; begin_at = -1; campaign = 0
    for at,row in marks[3:]:
        life = 1 if at<=death else 2
        need(row['node']=='node-1' and row['incarnation']==life, 'inflight original leader lifetime')
        if row['event'].startswith('NODE_'):
            need(set(row)=={'node','incarnation','event'},'inflight original node marker'); continue
        need(set(row)=={'node','incarnation','event','record','bytes'},'inflight round shape')
        raw=base64.b64decode(row['bytes'],validate=True);need(e.digest(raw)==row['record'],'inflight round digest')
        if row['event']=='ROUND_INSTALLED':
            campaign += 1
            need(raw==(root/f'selected-{campaign}.gsr').read_bytes(),'inflight original installed selection')
            selection=f.decode(raw,'records','SELECTED');selected_raw=raw
        elif row['event']=='ROUND_SLOT_BEGIN':
            entry=f.decode(raw,'records','ENTRY');slot=entry['index'];begins.append((life,slot));begin_at=at
            _,_,packet=c.current(c.inventory(root/f'published-{slot}/node-1'))
            need(e.digest(raw)==packet['capsule']['cut']['entry'],'inflight original entry')
            if (life,slot)==(1,2):original=raw
            if (life,slot)==(2,2):
                need(raw==original and selection['nextEntry']==e.digest(raw) and entry['origin']!=selection['ballot'], 'inflight carried entry unchanged')
            else:need(entry['origin']==selection['ballot'],'inflight fresh entry ballot')
        elif row['event']=='ROUND_SLOT_COMPLETE':
            need((life,slot)!=(1,2),'inflight interrupted call cannot succeed')
            files=c.inventory(root/f'published-{slot}/node-1');prefix,_,packet=c.current(files);own=n.future.identity(files)
            applied=c.inventory(root/f'applied-{slot}/node-1');ack=f.decode(raw,'wire','PUBLISH_ACK')
            need(ack==dict(root=selection['root'],view=selection['view'],ballot=selection['ballot'],sender=own,recipient=own,
                trace=ack['trace'],sequence=1,payload=dict(certificate=e.digest(applied['applied-end/certificate.gsr']),
                selection=e.digest(selected_raw),published=c.anchor(packet['capsule']),generation=e.digest(files[prefix+'generation.gsr']))), 'inflight original completion')
            for voter in (v['voter'] for v in selection['sources']):
                n.s.ordered([v['event'] for v in events[begin_at:at] if v['node']==voter],
                    ['ACCEPT_PARENT_FORCED']+(['FLOOR_PARENT_FORCED'] if (life,slot)==(2,2) else [])+
                    ['PROOF_PARENT_FORCED','CERTIFICATE_PARENT_FORCED','APPLY_ACK_DIRECTORY_FORCED','PUBLICATION_SELECTOR_FORCED',
                     'PUBLICATION_BEFORE_RETURN','PUBLICATION_ACK_BEFORE_RETURN'],'inflight actual publication '+voter)
            completion=raw
        else:
            need(slot==(1 if life==1 else 4 if reconciled and campaign==3 else 3) and entry['kind']=='BARRIER' and entry['origin']==selection['ballot'] and raw==completion,
                 'inflight fresh barrier before readiness')
    need(begins==[(1,1),(1,2),(2,2),(2,3),(2,4)]+([(2,5)] if reconciled else []),'inflight exact attempted slots')
    return events,death


def interrupted(root, events, entries, start, stop, identities, point, *, maintenance_replay=None):
    a=net.a;before=a.group(root,'published-1');after=a.group(root,'before-reopen')
    maintain = maintenance_replay or a.maintenance
    selected=f.decode(c.current(before['node-1'])[1]['selected.gsr'],'records','SELECTED');ballot=selected['ballot']
    voters=tuple(v['voter'] for v in selected['sources']);peer=voters[1]
    phase=a.Phase(events,entries,start,stop,identities)
    pending = pending_phase(point);rename_prefix(events[start+1:stop],point)
    for node in (('node-1',) if pending=='ACCEPT' else voters):
        end = point if node=='node-1' and pending=='ACCEPT' else 'ACCEPT_PARENT_FORCED'
        maintain(phase,before,node,ballot,start,phase.at(node,end),voters=voters)
        phase.ordered(node,['ACCEPT_CANDIDATE_FORCED',end])
    need(not any(v['event'].startswith(('CERTIFICATE_','APPLY_','PUBLICATION_')) for v in events[start+1:stop]),'inflight no premature publication')
    if pending=='ACCEPT':
        need(not any(v['event'].startswith('PROOF_') for v in events[start+1:stop]),'inflight no proof before interrupted accept')
    else:
        frames,_=c.pending(after['node-1']['pending.accept'],('PROOF',))
        def observed(node):return f.canonical(dict(root=selected['root'],voter=node,incarnation=identities[node]['storage'],phase='ACCEPT',record=e.digest(frames['ACCEPT'])))
        lower=phase.at('node-1','ACCEPT_PARENT_FORCED');remote=phase.at(peer,'ACCEPT_PARENT_FORCED');upper=phase.at('node-1',point)
        for kind in ('ACCEPT','ENTRY','PAYLOAD'):
            phase.transfer(peer,'node-1',a.record(frames[kind]),ballot,lower,remote)
        phase.transfer(peer,'node-1',a.record(observed('node-1'),True),ballot,lower,remote)
        phase.transfer('node-1',peer,a.record(observed(peer),True),ballot,remote,upper)
        phase.control('ACCEPT','node-1',peer,dict(acceptance=e.digest(frames['ACCEPT'])),'ACCEPT_ACK',
            dict(entry=e.digest(frames['ENTRY']),receipt=e.digest(observed(peer))),ballot,remote,upper)
        phase.ordered('node-1',['PROOF_CANDIDATE_FORCED',point])
        need(not any(v['node']!= 'node-1' and v['event'].startswith('PROOF_') for v in events[start+1:stop]),'inflight proof not yet dispatched')
    return phase.finish()


def network(root, originals, death, point, *, reconciled=False, maintenance_replay=None, background_replay=None):
    a=net.a;events=[{k:v for k,v in row.items() if k!='incarnation'} for row in originals]
    identities={node:n.future.identity(files) for node,files in a.group(root,'before-network').items()}
    entries=a.x.exchanges(root,events,-1,len(events),identities);a.deliveries(events,entries)
    selected=f.decode((root/'selected-1.gsr').read_bytes(),'records','SELECTED')
    need(all(v['request']['root']==selected['root'] and v['request']['view']==selected['view'] for v in entries),'inflight original authority')
    sent=net.request_attempts(events,entries,identities,selected['root'],selected['view'])
    held=[i for i,row in enumerate(events) if row['event'].startswith('ROUND_')]
    boundaries=[(-1,held[0]),(held[0],held[2]),(held[2],death),(death,held[5]),(held[5],held[7]),(held[7],held[9]),(held[9],held[12])]
    if reconciled: boundaries=boundaries[:6]+[(held[9],held[11]),(held[11],held[13]),(held[13],held[16])]
    net.request_phases(sent,boundaries,originals)
    background = background_replay(root,events,entries,sent,boundaries) if background_replay else None
    work_entries = [v for v in entries if v['kind'] != 'HEARTBEAT'] if background else entries
    ignored = background.pop('_events') if background else set()
    results=[];traces=background.pop('_traces') if background else set();silents=[]
    for ordinal,(start,stop) in enumerate(boundaries):
        if ordinal in ((0,3,6) if reconciled else (0,3)):
            result=net.activate(root,events,work_entries,start,stop,identities,{0:1,3:2,6:3}[ordinal],
                carried=ordinal==3,reconciled=ordinal==6,maintenance_replay=maintenance_replay)
        elif ordinal==2:result=interrupted(root,events,work_entries,start,stop,identities,point,maintenance_replay=maintenance_replay)
        else:
            index=({1:1,4:2,5:3,7:4,8:5} if reconciled else {1:1,4:2,5:3,6:4})[ordinal]
            stage={1:'installed-1',2:'installed-2',3:'published-2',4:'installed-3' if reconciled else 'published-3',5:'published-4'}[index]
            voters=tuple(v['voter'] for v in f.decode(c.current(a.group(root,stage)['node-1'])[1]['selected.gsr'],'records','SELECTED')['sources'])
            result=a.slot(root,events,work_entries,start,stop,identities,index,before_stage=stage,voters=voters,
                received_requests=True,carried=ordinal==4,maintenance_replay=maintenance_replay,background_events=ignored)
            silents.append((start,stop,index,result.pop('_rejected'),voters))
        own=result.pop('_traces');need(not traces.intersection(own),'inflight disjoint phase traces');traces.update(own);results.append(result)
    need(sum(v['exchanges'] for v in results)==len(work_entries),'inflight complete response coverage')
    unanswered={digest:rows for digest,rows in sent.items() if not any(v['response'] is not None for v in rows)
                and not (background and rows[0]['kind']=='HEARTBEAT')}
    silent=net.silent_attempts(root,events,unanswered,silents,identities,traces)
    result=dict(exchanges=len(entries),requests=sum(len(v) for v in sent.values()),phases=results,
        silentRequests=sum(v['attempts'] for v in silent),silent=silent,fullWireReplay=True)
    if background: result['background']=background
    return result


def validate(root):
    root=Path(root);process.inventory(root);raw=root/'history';result=n.read(root/'process/result.json');point=result.get('cut')
    pending_phase(point);physical(raw,point);events,death=lifecycle(raw,point)
    replay=network(raw,events,death,point);process.configuration(root)
    rows=process.children(result,cut=point);messages=process.observations(root,rows,cut=point)
    need(n.read(raw/'node-result.json')==dict(status='PARTIAL',producerPassed=True,coldReopens=1,barriers=2,dataCalls=2,
        physicalReplay=False,processRestart=True,phase3Complete=False,serviceBudgetNanos=180_000_000_000),'inflight producer scope')
    return dict(status='PASS',scope='native-node-interrupted-write-recovery',mode=result['mode'],cut=point,originalFirst=True,
        physicalReplay=True,network=replay,childMessages=messages,freshLeaderJvms=2,processRestart=True,
        interruptedClientSuccess=False,carriedOriginalEntry=True,powerLoss=False,publicRuntime=False,phase3Complete=False)


NEGATIVES = {
    'interrupted-vote':'admitted exact before-reopen: node-1',
    'unexpected-follower-vote':'admitted exact before-reopen: node-3',
    'drop-selected-tail':'inflight original selected tail',
    'installed-tail':'admitted exact installed-2: node-1',
    'reaccepted-vote':'admitted exact applied-2: node-1',
    'wrong-fresh-barrier':'admitted exact published-3: node-1',
    'interrupted-success':'inflight exact lifecycle order',
    'freshened-carried-origin':'inflight original entry',
    'early-retirement':'selected retention force order: inflight actual publication node-1',
    'missing-reaccept':'selected retention force order: inflight actual publication node-1',
    'stale-ready':'inflight fresh barrier before readiness',
    'missing-send':'node network received request without write',
    'unreceived-selected-prepare':'discovered selection response delivered',
    'wrong-exit':'node process exact death and drain',
    'missing-lock-probe':'node process exact death and drain',
    'wrong-disk':'node process original disk paths',
    'missing-cut':'node process terminal boundary',
    'missing-child-send':'node process exact child lifetime events',
    'wrong-cut-event':'node process exact interrupted force',
    'wrong-reopen-phase':'inflight exact original reopen',
}

RENAME_NEGATIVES = {
    'invented-parent-force': 'inflight exact pre-directory-force prefix',
    'missing-candidate-force': 'inflight exact pre-directory-force prefix',
}


def negative_cases(point):
    pending_phase(point)
    cases = dict(NEGATIVES)
    if point in RENAME_CUTS:
        cases['wrong-cut-event'] = 'inflight exact pre-directory-force prefix'
        cases.update(RENAME_NEGATIVES)
    return cases


def mutate(root, name):
    if name in process.NEGATIVES:
        process.mutate(root,name); return
    raw=root/'history'
    if name in RENAME_NEGATIVES:
        point=n.read(root/'process/result.json')['cut'];need(point in RENAME_CUTS,'inflight rename mutation scope')
        phase=pending_phase(point);event=dict(node='node-1',incarnation=1,event=phase+'_PARENT_FORCED')
        path=raw/'events.json';events=n.read(path);death=next(i for i,v in enumerate(events) if v['event']=='NODE_CRASH')
        begin=max(i for i,v in enumerate(events[:death]) if v['event']=='ROUND_SLOT_BEGIN')
        if name=='invented-parent-force': events.insert(death,event)
        else:
            at=next(i for i in range(begin,death) if events[i]['node']=='node-1' and events[i]['event']==phase+'_CANDIDATE_FORCED')
            events.pop(at)
        path.write_bytes(f.canonical(events))
        path=root/'process/life-1.jsonl';messages=process.transcript(path)
        if name=='invented-parent-force':messages.insert(-1,dict(action='event',value=event))
        else:
            at=max(i for i,v in enumerate(messages) if v['action']=='event' and v['value']['event']==phase+'_CANDIDATE_FORCED')
            messages.pop(at)
        path.write_bytes(b'\n'.join(f.canonical(v) for v in messages)+b'\n');return
    files={'interrupted-vote':'before-reopen/node-1/pending.accept','unexpected-follower-vote':'before-reopen/node-3/pending.accept',
        'installed-tail':'installed-2/node-1/sources/extra','reaccepted-vote':'applied-2/node-1/pending.accept','wrong-fresh-barrier':'published-3/node-1/selector.gsr'}
    if name in files:(raw/files[name]).write_bytes(b'changed');return
    if name=='drop-selected-tail':
        path=raw/'selected-2.gsr';value=f.decode(path.read_bytes(),'records','SELECTED');value['nextEntry']=None
        path.write_bytes(f.encode('records','SELECTED',value));return
    if name=='missing-send':net.mutate(raw,name);return
    if name=='wrong-cut-event':
        path=root/'process/life-1.jsonl';messages=process.transcript(path)
        point=n.read(root/'process/result.json')['cut']
        phase=pending_phase(point) if point in RENAME_CUTS else 'ACCEPT'
        event=dict(node='node-1',incarnation=1,event=phase+'_BEFORE_RETURN');messages.insert(-1,dict(action='event',value=event))
        path.write_bytes(b'\n'.join(f.canonical(v) for v in messages)+b'\n')
        path=raw/'events.json';events=n.read(path);at=next(i for i,v in enumerate(events) if v['event']=='NODE_CRASH')
        events.insert(at,event);path.write_bytes(f.canonical(events));return
    path=raw/'events.json';events=n.read(path)
    begins=[v for v in events if v['event']=='ROUND_SLOT_BEGIN']
    if name=='wrong-reopen-phase':
        death=next(i for i,row in enumerate(events) if row['event']=='NODE_CRASH')
        row=next(row for row in events[death+1:] if row['node']=='node-1' and row['event'] in ('ACCEPT_ACTIVE_FORCED','PROOF_ACTIVE_FORCED'))
        row['event']='ACCEPT_ACTIVE_FORCED' if row['event']=='PROOF_ACTIVE_FORCED' else 'PROOF_ACTIVE_FORCED'
    elif name=='interrupted-success':
        completed=next(v for v in events if v['event']=='ROUND_SLOT_COMPLETE')
        events.insert(events.index(begins[1])+1,dict(completed))
    elif name=='freshened-carried-origin':
        selected=f.decode((raw/'selected-2.gsr').read_bytes(),'records','SELECTED');row=begins[2]
        entry=f.decode(base64.b64decode(row['bytes'],validate=True),'records','ENTRY');entry['origin']=selected['ballot']
        encoded=f.encode('records','ENTRY',entry);row.update(bytes=base64.b64encode(encoded).decode(),record=e.digest(encoded))
    elif name in ('early-retirement','missing-reaccept'):
        after=events.index(begins[2]);at=next(i for i in range(after,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='ACCEPT_PARENT_FORCED')
        if name=='missing-reaccept':events.pop(at)
        else:
            floor=next(i for i in range(after,len(events)) if events[i]['node']=='node-1' and events[i]['event']=='FLOOR_PARENT_FORCED')
            row=events.pop(floor);events.insert(at,row)
    elif name=='stale-ready':
        rows=[v for v in events if v['event']=='ROUND_BEFORE_READY'];rows[1].update(record=rows[0]['record'],bytes=rows[0]['bytes'])
    else:raise ValueError('unknown inflight mutation')
    path.write_bytes(f.canonical(events))


def qualify(root):
    root=Path(root);original=validate(root);negatives=[]
    for name,reason in negative_cases(original['cut']).items():
        with tempfile.TemporaryDirectory(prefix='v53-node-inflight-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);mutate(path,name)
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'inflight unrelated negative '+name+': '+str(error))
            else:raise ValueError('inflight accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
