"""Independent replay of capsule endorsements and learner durable transitions.

Uses the earlier transition history checker and structural decoder, never the
capsule verifier, learner guards, state transition methods, or live model objects.
"""
import json

from . import transition_model as t
from . import recovery_research as rr
from .recovery_oracle import safe


def raw(value):
    return json.loads(t.encoded(value))


class Observer:
    def __init__(self, record):
        decoded = rr.decode(dict(old=record['old'], sourceEvents=record['input'],
                                 events=[dict(chain=record['chain'])]))
        t.check_history(record['root'], decoded['old'], decoded['sourceEvents'])
        self.chain = decoded['events'][0]['chain']
        self.root, self.old = record['root'], decoded['old']
        prefixes = {}; self.source_voters = set(); self.source_installed = set()
        for event in decoded['sourceEvents']:
            if event['event'] == 'install-force':
                prefixes[event['node']] = event['chain']; self.source_installed.add(event['node'])
            if event['event'] == 'slot' and event['detail']['event'] in ('promise-force','accept-force','proof-force'):
                self.source_voters.add(event['detail']['message'].voter)
        safe(any(self.chain == c[:len(self.chain)] for c in prefixes.values()), 'unobserved source chain')
        self.views, self.states = [], [t.digest(dict(root=self.root, application='abstract-genesis'))]
        old = new = self.old; generation = 0; operation = ''
        parent = t.digest(dict(root=self.root, voters=self.old))
        for index in range(len(self.chain)+1):
            self.views.append(dict(root=self.root, index=index+1, predecessor=parent, generation=generation,
                                   old=list(old), new=list(new), operation=operation))
            if index == len(self.chain): break
            cert = self.chain[index]; entry = json.loads(cert.value)
            safe(raw(cert.authority) == self.views[-1], 'source certificate continuity')
            if entry['kind'] == 'INTENT':
                new = tuple(entry['target']); operation = entry['operation']; generation += 1
            elif entry['kind'] == 'FINAL':
                old = new; operation = ''
            state = self.states[-1]
            if entry['kind'] == 'DATA': state = t.digest(dict(previous=state, data=entry['payload']))
            self.states.append(state); parent = cert.entry_id
        self.endorsed, pending = {}, {}
        self.capsules = 0
        self.source_size = len(record['events'])
        for sequence,event in enumerate(record['events'],1):
            kind = event['event']
            if kind == 'endorsement-stage':
                node, statement = event['node'], event['statement']; first, end = self.gap(statement)
                safe(node in self.views[first]['old'] and node not in pending and
                     node in prefixes and len(prefixes[node]) >= end and
                     prefixes[node][:end] == self.chain[:end], 'endorsement source/custody')
                pending[node] = statement
            elif kind == 'endorsement-force':
                node, statement = event['node'], event['statement']
                safe(pending.pop(node, None) == statement, 'endorsement without staged verified bytes')
                self.endorsed.setdefault((node, t.digest(statement)),sequence)
            elif kind == 'endorser-crash': pending.pop(event['node'], None)
            elif kind == 'capsule': self.packet(event['packet'],sequence); self.capsules += 1
            else: safe(False, 'unknown authority evidence')

    def gap(self, statement):
        first, end = statement['start']['index']-1, statement['after']['index']-1
        safe(0 <= first < end <= len(self.chain), 'unobserved gap range')
        safe(statement == dict(start=self.views[first], after=self.views[end],
                               stateBefore=self.states[first], stateAfter=self.states[end]), 'gap bytes/cut')
        safe(all(json.loads(c.value)['kind'] in ('DATA','BARRIER') for c in self.chain[first:end]),
             'hidden membership certificate')
        return first, end

    def packet(self, packet, through=None):
        if through is None: through = self.source_size
        safe(set(packet) == {'root','initial','items','next','state'} and
             packet['root'] == self.root and packet['initial'] == list(self.old), 'packet root')
        index = changes = 0
        safe(len(packet['items']) <= 13, 'packet capacity')
        for item in packet['items']:
            if item['kind'] == 'gap':
                safe(set(item) == {'kind','statement','owners'}, 'gap fields')
                first, end = self.gap(item['statement']); owners = item['owners']
                safe(first == index and not self.views[index]['operation'], 'gap continuity')
                voters = set(self.views[index]['old'])
                safe(len(set(owners)) == len(owners) and set(owners) <= voters and
                     len(owners)*2 > len(voters) and
                     all(self.endorsed.get((n,t.digest(item['statement'])),self.source_size+1) <= through
                         for n in owners), 'unforced gap quorum')
                index = end
            else:
                safe(item['kind'] == 'configuration' and set(item) == {'kind','certificate'} and
                     index < len(self.chain), 'configuration row')
                cert = self.chain[index]; kind = json.loads(cert.value)['kind']
                safe(item['certificate'] == raw(cert) and kind in ('INTENT','FINAL'), 'configuration omitted/changed')
                changes += kind == 'INTENT'; index += 1
        safe(changes <= 4 and packet['next'] == self.views[index] and packet['state'] == self.states[index],
             'packet final state/capacity')
        return index


def check(record):
    observer = Observer(record['source'])
    request, identities = record['request'], record['identities']
    safe(set(request) == {'root','operation','expected','target','joining'} and request['root'] == observer.root
         and type(request['operation']) is str and 0 < len(request['operation']) <= 128, 'operation identity')
    initial = request['expected']; cut = initial['index']-1
    safe(0 <= cut < len(observer.chain) and initial == observer.views[cut] and not initial['operation'],
         'request predecessor')
    old, target = set(initial['old']), set(request['target'])
    joining, identity = target-old, request['joining']
    safe(3 <= len(target) <= 5 and request['target'] == sorted(target) and
         (len(joining),len(old-target)) in ((1,0),(1,1)) and identity['voter'] in joining, 'learner target')
    safe(not (joining & (observer.source_voters | observer.source_installed)), 'learner already used by source fixture')
    safe(set(identity) == {'voter','storage','endpoint'} and
         all(type(v) is str and v.isascii() and 0 < len(v) <= 128 for v in identity.values()) and
         old <= {row['voter'] for row in identities}, 'identity descriptor')
    for key in identity:
        values = [row[key] for row in identities]
        safe(len(set(values)) == len(values) and identity[key] not in values, 'reused identity')
    durable, pending, alive, session, eligible, seen = {}, None, True, 1, 0, 0
    for event in record['events']:
        through = event['sourceThrough']
        safe(type(through) is int and seen <= through <= observer.source_size, 'source evidence order')
        seen = through
        action = event['event']
        if action == 'stage':
            kind, value = event['kind'], event['value']
            safe(alive and pending is None, 'overlapping/offline learner write')
            if kind == 'reservation': safe(value == request and kind not in durable, 'reservation changed')
            elif kind == 'image':
                safe('reservation' in durable and 'receipt' not in durable and observer.packet(value,through) == cut,
                     'image before reservation/wrong cut/sealed')
            elif kind == 'receipt':
                safe('image' in durable and value == dict(request=t.digest(request), identity=identity,
                     image=t.digest(durable['image']), cut=initial), 'early/unbound materialization receipt')
            elif kind == 'authority':
                safe('receipt' in durable and 'image' in durable and
                     durable['receipt']['image'] == t.digest(durable['image']), 'authority before receipt')
                end = observer.packet(value,through)
                entry = json.loads(observer.chain[cut].value)
                safe(end in (cut+1,cut+2) and entry['kind'] == 'INTENT' and
                     entry['operation'] == t.digest(request) and entry['target'] == request['target'] and
                     (end == cut+1 or json.loads(observer.chain[cut+1].value)['kind'] == 'FINAL'),
                     'foreign intent/authority')
                safe('authority' not in durable or durable['authority']['next']['index'] <= value['next']['index'],
                     'authority rollback')
            else: safe(False, 'unknown learner record')
            pending = (kind,value)
        elif action == 'force':
            safe(alive and pending == (event['kind'],event['value']), 'unstaged learner force')
            durable[pending[0]] = pending[1]; pending = None
        elif action == 'crash':
            safe(alive, 'duplicate crash'); alive = False; pending = None
        elif action == 'restart':
            safe(not alive and event['session'] == session+1, 'invalid session restart')
            session += 1; alive = True
        elif action == 'eligible':
            safe(alive and pending is None and 'authority' in durable and
                 event['view'] == durable['authority']['next'] and event['identity'] == identity and
                 event['session'] == session and identity['voter'] in set(event['view']['old']+event['view']['new']),
                 'premature/foreign/stale eligibility')
            eligible += 1
        else: safe(False, 'unknown learner evidence')
    return dict(events=len(record['events'])+len(record['source']['events']), capsules=observer.capsules,
                eligible=eligible, final=bool('authority' in durable and not durable['authority']['next']['operation']))
