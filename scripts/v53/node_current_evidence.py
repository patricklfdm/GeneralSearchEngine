"""Current peer-debt replay for an interrupted native node history.

Select this model explicitly. Historical parent-force readers retain their old
projection; neither mode can use a producer receipt as physical authority.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import shutil
import tempfile
from . import node_inflight_evidence as p
from . import remove_maintenance_evidence as current
from . import node_current_network as network
from .joining_same_view_physical import floor_voters

n, b, c, e, f, need = p.n, p.b, p.c, p.e, p.f, p.need


def maintenance(group, voters, *, after_accept=False):
    """Keep unresolved old votes; only a reaccepted current vote permits floor work.

    The settled projection changes generations, sources and peer ledgers only.
    Validate the new ACCEPT independently before projecting those same fields,
    then restore its exact bytes. A pending PROOF is never silently erased.
    """
    copies = copy.deepcopy(group); eligible = []; pending = {}; transferred = {}
    for node in voters:
        files = group[node]; vote = files['pending.accept']
        if vote != c.EMPTY:
            if not after_accept: continue
            frames, _ = c.pending(vote, ())
            _, members, packet = c.current(files)
            selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
            accepted = f.decode(frames['ACCEPT'], 'records', 'ACCEPT')
            entry = f.decode(frames['ENTRY'], 'records', 'ENTRY')
            need(frames['SELECTOR'] == files['selector.gsr'] and frames['PROMISE'] == members['promise.gsr']
                 and frames['SELECTED'] == members['selected.gsr'] and accepted == dict(root=selected['root'],
                 authority=selected['view'], ballot=selected['ballot'], index=packet['capsule']['cut']['index']+1,
                 entry=e.digest(frames['ENTRY'])) and entry['index'] == accepted['index']
                 and entry['payload'] == e.digest(frames['PAYLOAD']), 'current node exact reaccepted vote')
            pending[node] = vote; copies[node]['pending.accept'] = c.EMPTY
            if (selected['nextEntry'] == e.digest(frames['ENTRY']) and entry['kind'] in ('DATA','BARRIER')
                    and 'pending.context' not in files):
                transferred[node] = (frames, packet)
        eligible.append(node)
    # Floor copies still use the entire governing cohort, including unchanged
    # copies whose pending vote prevents their own maintenance.
    result = copy.deepcopy(group)
    if not eligible: return result
    projected_group = current.maintenance(copies, voters, owners=eligible)
    for node in eligible:
        projected = projected_group[node]
        result[node] = projected
        if node in pending:
            if node in transferred:
                frames, packet = transferred[node]
                retained_carried_sources(group[node], projected, node, frames, packet)
            else:
                # A newly proposed entry (or retained context) cannot borrow the
                # exact installed carried vote's maintenance permission.
                projected.update({k:v for k,v in group[node].items() if k == 'grants.gsr' or k.startswith('sources/')})
            projected['pending.accept'] = pending[node]
    return result


def retained_carried_sources(before, after, node, frames, packet):
    """Every removed tail above the floor stays in the installed original packet
    and under this exact successor ACCEPT. Ancestry/floor coverage is already
    established by the enclosing maintenance projection.
    """
    rows=c.journal(before['grants.gsr'],packet['capsule']['root'],node)
    bases={value['basisId']:(raw,value) for kind,raw,value in rows if kind=='BASIS'}
    for name, raw in before.items():
        if not name.startswith('sources/') or not name.endswith('/source.gscp') or name in after:continue
        basis,value=bases[name.split('/')[1]]; original=e.p.decode(raw);e.p.bind(original,basis)
        if value['accepted'] is None:continue
        accept=f.decode(original['objects'][value['accepted']],'records','ACCEPT')
        if accept['index']<=packet['capsule']['cut']['index']:continue
        entry=f.decode(original['objects'][accept['entry']],'records','ENTRY')
        need(all(packet['objects'].get(h)==original['objects'][h]
                 for h in (value['accepted'],accept['entry'],entry['payload']))
             and accept['entry']==e.digest(frames['ENTRY']), 'current node retained carried source tail')


class Service(p.Service):
    def maintenance(self, group, voters, *, after_accept=False):
        return maintenance(group, voters, after_accept=after_accept)

    def merge_peers(self, before, sources):
        return current.merge(self.group, before, sources)

    def grant_identifier(self, prior, rows, ballot, selected):
        if selected or rows[:len(prior)] == prior:
            return super().grant_identifier(prior, rows, ballot, selected)
        # A lagging unselected peer may retire a superseded same-cut source
        # after forcing its fresh grant. Only the random source identity comes
        # from this suffix; after_grant derives the whole pruned journal/source
        # inventory independently and installed-N must match it byte for byte.
        suffix=[row for row in rows if row[2].get('ballot') == ballot]
        need([row[0] for row in suffix] == ['PROMISE','BASIS'] and rows[-2:] == suffix,
             'current node unselected fresh grant suffix')
        return suffix[0][2]['basisId']

    def after_grant(self, group, node, files):
        _,members,packet=c.current(files);cap=packet['capsule']
        rows=c.journal(files['grants.gsr'],cap['root'],node)
        latest=next(value['ballot'] for kind,_,value in reversed(rows) if kind=='PROMISE')
        promises={value['basisId']:(raw,value) for kind,raw,value in rows if kind=='PROMISE' and value['basisId'] is not None}
        bases={value['basisId']:(raw,value) for kind,raw,value in rows if kind=='BASIS'}
        required=False
        for name in files:
            if not name.startswith('sources/') or not name.endswith('/source.gscp'):continue
            identifier=name.split('/')[1];promise,prior=promises[identifier];basis,value=bases[identifier]
            required |= (promise != members['promise.gsr'] and basis != members.get('basis.gsr') and
                         value['accepted'] is None and value['cut'] == cap['cut'] and
                         prior['ballot']['counter'] < latest['counter'])
        if not required:return files
        # This original-backed same-cut path has no retired accepted tail.
        # Another unaccepted source must not lend it a retirement trigger.
        for identifier,(promise,prior) in promises.items():
            if ('sources/'+identifier+'/source.gscp' in files and promise != members['promise.gsr']
                    and prior['ballot']['counter'] < latest['counter']):
                need(bases[identifier][1]['accepted'] is None, 'current node same-cut retirement accepted tail')
        copies=dict(group,**{node:files});voters=floor_voters(copies,node)
        after=current.maintenance(copies,voters,owners=(node,))[node]
        # Network replay consumes independently derived pre/post-grant bytes,
        # never the installed snapshot as authority for a retired source.
        if not hasattr(self,'grant_retirements'):self.grant_retirements={}
        key=(latest['counter'],node)
        need(key not in self.grant_retirements,'current node duplicate grant retirement')
        self.grant_retirements[key]=dict(before=copy.deepcopy(copies),after=copy.deepcopy(after),voters=voters)
        return after

    def installation_ancestry(self, files, packet, sources):
        _, old, previous = c.current(files)
        points = [c.anchor(previous['capsule'])]
        merged = self.merge_peers(files[n.s.FILE], [v[n.s.FILE] for v in sources])
        for raw in (files[n.s.FILE], merged):
            plan = n.s.r.decode(raw)['plan']
            points += [v for row in plan['peers'] for v in [*row.get('renewals', []), *row['possible']]]
        points += [c.anchor(e.p.decode(raw)['capsule']) for name, raw in files.items()
                   if name.startswith('sources/') and name.endswith('/source.gscp')]
        direct = current.confirmation.endpoints(packet, b'')
        required = {v['cut']['index'] for v in points if v['cut']['index'] not in direct}
        groups = []
        for raw in current.confirmation.frames(old['ancestry.gsr']) if old.get('ancestry.gsr') else ():
            if int.from_bytes(raw[8:10], 'big') == f.catalog()['records']['CHECKPOINT']['id']: groups.append([raw])
            else:
                need(groups, 'current node orphan installation ancestry'); groups[-1].append(raw)
        ancestry = b''.join(raw for rows in groups if f.decode(rows[0], 'records', 'CHECKPOINT')['start']['index'] in required for raw in rows)
        available = current.confirmation.endpoints(packet, ancestry)
        need(all(available.get(v['cut']['index']) == v for v in points), 'current node complete installation ancestry')
        return ancestry

    def data_documents(self):
        count = 2 if self.slot >= 5 else 1 if self.slot >= 2 else 0
        return [(i, 'node-owner-'+str(i)) for i in range(100, 100+count)]

    def advance(self, kind):
        if self.slot == 4:
            need(kind == 'DATA', 'current node reconciled client DATA')
            self.group = self.maintenance(self.group, self.voters)
            self.publish(kind, p.carried.payload(101, 'node-owner-101'))
        else: super().advance(kind)


def physical(root, point):
    root = Path(root); need(point in p.RENAME_CUTS, 'current node rename scope')
    p.p.inventory(root, reconciled=True)
    group = n.s.initialize(b.original(root, 3, False))
    group = {node:dict(files, **{n.future.FILE:n.future.frame(n.future.initial(files), {})}) for node,files in group.items()}
    b.match(root, 'before-network', group)
    service = Service(root, group); service.campaign(1, 2); service.advance('BARRIER')
    b.match(root, 'first-ready', service.group); service.interrupt(point)
    service.campaign(2, 3); service.advance('DATA'); service.advance('BARRIER')
    b.match(root, 'second-ready', service.group)
    service.campaign(3, 4); service.advance('BARRIER'); service.advance('DATA')
    b.match(root, 'after-close', service.group)
    return service


def maintenance_network(phase, before, owner, ballot, lower, upper, *, voters, after_accept=False):
    """Bind each conditional ledger write to the real complete floor copies."""
    a = p.net.a; peer = next(v for v in voters if v != owner)
    floor = phase.at(owner, 'FLOOR_PARENT_FORCED')
    need(lower < floor < upper, 'current node maintenance before work')
    raw = before[owner][n.s.FILE]; writes = 0
    for node in (owner, peer):
        changed = current.observation.observe_same_cut(raw, before[owner], before[node], defer_renewal=True)
        writes += changed != raw; raw = changed
    copies = copy.deepcopy(before)
    for node in voters: copies[node]['pending.accept'] = c.EMPTY
    projected = current.maintenance(copies, voters)[owner]
    removed = [name for name in before[owner]
        if name.startswith('sources/') and before[owner][name] is not None and name not in projected]
    retention = ('RETENTION_FORCED', 'RETENTION_PARENT_FORCED')
    retired = ('RETIREMENT_AUTHORITY_FORCED','RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED',
               'RETIREMENT_CLEARED','RETIREMENT_BEFORE_RETURN')
    released = ('FLOOR_RELEASE_AUTHORITY_FORCED','FLOOR_RELEASE_PARENT_FORCED',
                'FLOOR_RELEASE_RELINQUISHED','FLOOR_RELEASE_BEFORE_RETURN')
    source = current.SOURCE[:5]+('SOURCE_RETIREMENT_FILE_DELETED',)*len(removed)+current.SOURCE[6:] if removed else ()
    expected = current.FLOOR+retention*writes+retired+source+released
    critical = set(current.FLOOR+retention+retired+current.SOURCE+released)
    observed = [v['event'] for v in phase.events[lower+1:upper] if v['node']==owner and v['event'] in critical]
    need(observed == list(expected), 'current node exact maintenance forces: '+owner)
    prefix, members, packet = c.current(before[peer])
    phase.probe(owner, peer, ballot, packet['capsule']['cut'], lower, floor)
    phase.transfer(owner, peer, n.maintenance_prefixes(members,packet,c.current(before[owner])[1]),ballot,lower,floor)
    phase.transfer(owner, peer, n.maintenance_generations(before[peer][prefix+'generation.gsr'],members,packet),ballot,lower,floor)


def validate(root):
    root = Path(root); p.process.inventory(root)
    result = n.read(root/'process/result.json'); raw=root/'history'; point=result.get('cut')
    service=physical(raw, point); events,death=p.lifecycle(raw,point,reconciled=True)
    from .node_grant_maintenance import Replay
    from .node_late_prepare import collect
    grants=Replay(getattr(service,'grant_retirements',{}))
    replay=p.network(raw,events,death,point,reconciled=True,maintenance_replay=maintenance_network,
        background_replay=network.heartbeats,grant_maintenance_replay=grants,
        late_prepare_replay=lambda *args:collect(*args,grants.derived))
    grants.complete()
    p.process.configuration(root); rows=p.process.children(result,cut=point)
    messages=p.process.observations(root,rows,cut=point,reconciled=True)
    need(n.read(raw/'node-result.json')==dict(status='PARTIAL',producerPassed=True,coldReopens=1,barriers=3,dataCalls=2,
        physicalReplay=False,processRestart=True,phase3Complete=False,serviceBudgetNanos=180_000_000_000),'current node producer scope')
    return dict(status='PASS', scope='current-node-rename-recovery', mode=result['mode'], cut=point,
        originalFirst=True, physicalReplay=True, network=replay, childMessages=messages,
        campaigns=3, publishedSlots=5, freshLeaderJvms=2, processRestart=True,
        interruptedClientSuccess=False, carriedOriginalEntry=True, powerLoss=False,
        publicRuntime=False, phase3Complete=False)


EXTRA_NEGATIVES = {
    'reconciliation-barrier': 'admitted exact published-4: node-1',
    'reconciled-client-vote': 'admitted exact applied-5: node-1',
    'reused-installation-number': 'node process original installed record',
    'genesis-ledger-write': 'current node exact maintenance forces: node-1',
    'missing-source-retirement-force': 'current node exact maintenance forces: node-1',
    'missing-selected-retention-force': 'current node selected retention forces: node-1',
    'pending-source-retired': 'admitted exact applied-2: node-1',
    'lost-installation-ancestry': 'admitted exact installed-3: node-1',
    'changed-current-ledger': 'admitted exact published-3: node-1',
    'heartbeat-stale-request': 'current heartbeat original request cut',
    'heartbeat-stale-reply': 'current heartbeat original reply cut',
    'heartbeat-no-contact': 'current heartbeat contact before continuation',
}


def heartbeat_mutation(root, name):
    raw=root/'history'; events=n.read(raw/'events.json'); wire=n.read(raw/'wire.json')
    first=next(v for v in events if v['event']=='NETWORK_SEND' and v['kind']=='HEARTBEAT')
    query=f.decode(base64.b64decode(first['bytes']),'wire','HEARTBEAT'); trace=query['trace']
    replacements={}; bytes_by_hash={}; delivery_hashes=set()
    def rewrite(row):
        kind,q=n.transfer.t.wire(row['request'])
        if kind!='HEARTBEAT' or q['trace']!=trace:return row
        r=f.decode(base64.b64decode(row['response']),'wire','HEARTBEAT_ACK')
        delivery_hashes.add(e.digest(base64.b64decode(row['response'])))
        if name=='heartbeat-no-contact':return row
        result=dict(row)
        field,value,wire_kind=('request',q,'HEARTBEAT') if name=='heartbeat-stale-request' else ('response',r,'HEARTBEAT_ACK')
        value=copy.deepcopy(value);value['payload']['cut']['index']+=1
        old=base64.b64decode(row[field]);new=f.encode('wire',wire_kind,value)
        replacements[e.digest(old)]=e.digest(new);bytes_by_hash[e.digest(old)]=base64.b64encode(new).decode()
        result[field]=base64.b64encode(new).decode();return result
    changed=[rewrite(v) for v in wire]
    def event(row):
        if name=='heartbeat-no-contact' and row['event']=='NETWORK_RECEIVED' and row.get('response') in delivery_hashes:return None
        value=dict(row)
        if value['event']=='NETWORK_SEND' and value.get('request') in bytes_by_hash:value['bytes']=bytes_by_hash[value['request']]
        for field in ('request','response'):
            if value.get(field) in replacements:value[field]=replacements[value[field]]
        return value
    (raw/'wire.json').write_bytes(f.canonical(changed))
    (raw/'events.json').write_bytes(f.canonical([value for row in events if (value:=event(row)) is not None]))
    for life in (1,2):
        path=root/f'process/life-{life}.jsonl';rows=p.process.transcript(path);out=[]
        for row in rows:
            if row['action']=='event':
                value=event(row['value'])
                if value is None:continue
                row=dict(action='event',value=value)
            elif row['action']=='response':row=dict(action='response',value=dict(event=event(row['value']['event']),wire=rewrite(row['value']['wire'])))
            out.append(row)
        path.write_bytes(b'\n'.join(f.canonical(v) for v in out)+b'\n')


def mutate(root, name):
    from . import node_late_prepare as late
    if name in late.NEGATIVES:return late.mutate(root,name)
    if name not in EXTRA_NEGATIVES:return p.mutate(root,name)
    raw=root/'history'
    files={'reconciliation-barrier':'published-4/node-1/selector.gsr',
        'reconciled-client-vote':'applied-5/node-1/pending.accept',
        'lost-installation-ancestry':'installed-3/node-1/generations/a/ancestry.gsr',
        'changed-current-ledger':'published-3/node-1/'+n.s.FILE}
    if name in files:(raw/files[name]).write_bytes(b'changed');return
    if name=='pending-source-retired':
        node=raw/'applied-2/node-1'
        selected=f.decode(c.current(c.inventory(node))[1]['selected.gsr'],'records','SELECTED')
        current_ids={v['basisId'] for v in selected['sources']}
        protected=next(v for v in (node/'sources').iterdir() if v.name in current_ids)
        shutil.rmtree(protected);return
    if name=='reused-installation-number':
        path=root/'process/life-2.jsonl';rows=p.process.transcript(path)
        next(v for v in rows if v['action']=='installed' and v['value']['number']==3)['value']['number']=2
        path.write_bytes(b'\n'.join(f.canonical(v) for v in rows)+b'\n');return
    if name.startswith('heartbeat-'):heartbeat_mutation(root,name);return
    # Edit only event messages, preserving all non-event message positions.
    inserted=False;deleted=False
    def change_rows(rows, *, child=False):
        nonlocal inserted,deleted
        inserted=False;deleted=False;out=[]
        for row in rows:
            value=row['value'] if child and row['action']=='event' else None if child else row
            if value and value['node']=='node-1':
                if name=='genesis-ledger-write' and not inserted and value['event']=='RETIREMENT_AUTHORITY_FORCED':
                    for event in ('RETENTION_FORCED','RETENTION_PARENT_FORCED'):
                        v=dict(value,event=event);out.append(dict(action='event',value=v) if child else v)
                    inserted=True
                missing = 'RETENTION_FORCED' if name=='missing-selected-retention-force' else 'SOURCE_RETIREMENT_FORCED'
                if (name in ('missing-source-retirement-force','missing-selected-retention-force') and not deleted
                        and value['event']==missing and (name!='missing-selected-retention-force' or value.get('incarnation')==2)):
                    deleted=True;continue
            out.append(row)
        return out
    (raw/'events.json').write_bytes(f.canonical(change_rows(n.read(raw/'events.json'))))
    # The genesis mutation belongs to life 1, source retirement to life 2.
    life=1 if name=='genesis-ledger-write' else 2;path=root/f'process/life-{life}.jsonl'
    path.write_bytes(b'\n'.join(f.canonical(v) for v in change_rows(p.process.transcript(path),child=True))+b'\n')


def qualify(root):
    from . import node_late_prepare as late
    root=Path(root);original=validate(root);negatives=[]
    cases=p.negative_cases(original['cut'])|EXTRA_NEGATIVES
    if original['network'].get('lateUnusedPrepares'):cases.update(late.NEGATIVES)
    for name,reason in cases.items():
        with tempfile.TemporaryDirectory(prefix='v53-current-node-negative-') as temp:
            path=Path(temp)/'raw';shutil.copytree(root,path);mutate(path,name)
            try:validate(path)
            except ValueError as error:need(str(error)==reason,'current node unrelated negative '+name+': '+str(error))
            else:raise ValueError('current node accepted negative '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify',action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
