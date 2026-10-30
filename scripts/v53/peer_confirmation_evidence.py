"""Replay the native three-owner complete-copy confirmation history from originals.

The original generation is derived from actual bootstrap/votes/publication bytes.
A decoded manifest is only binding metadata, never a force receipt. This focused
history does not qualify joining, process crashes or automatic competing owners.
"""
from __future__ import annotations
import argparse
import base64
import copy
import json
import shutil
import tempfile
from pathlib import Path
from . import selected_retention_evidence as e
from .selected_prefix_evidence import prefix

f, b, r = e.f, e.b, e.r
need, sha = e.need, e.sha


def confirmation(value, root, identity):
    need(type(value) is str and len(value) <= 32768, 'peer confirmation encoding/capacity')
    raw = base64.b64decode(value, validate=True)
    need(base64.b64encode(raw).decode() == value, 'peer confirmation canonical base64')
    record = f.decode(raw, 'records', 'GENERATION')
    need(record['root'] == root and record['node'] == identity['node'], 'peer confirmation root/identity')
    return {k: record[k] for k in ('cut', 'catalog', 'application')}


def plan(value):
    need(type(value) is dict and set(value) == {'root', 'view', 'peers'}, 'peer retention plan fields')
    types = f.catalog()['types']
    f.check_type(value['root'], 'hash', types); f.check_type(value['view'], 'view', types)
    def view_binding(view):
        old, new = view['old'], view['new']
        need(view['generation'] <= 256 and old == sorted(set(old)) and new == sorted(set(new))
             and len(set(old+new)) <= 6 and (old == new) == (view['operation'] is None)
             and len(set(old)-set(new)) <= 1 and len(set(new)-set(old)) <= 1, 'peer retention view binding')
    view_binding(value['view'])
    rows = value['peers']; voters = sorted(set(value['view']['old'] + value['view']['new']))
    need(type(rows) is list and 3 <= len(rows) <= 6, 'peer retention plan count')
    names = []
    for row in rows:
        need(type(row) is dict and {'identity', 'possible'} <= set(row) <= {'identity', 'possible', 'confirmation', 'renewals'}, 'peer retention peer fields')
        f.check_type(row['identity'], 'identity', types); names.append(row['identity']['node'])
        points = row['possible']; need(type(points) is list and 1 <= len(points) <= 2, 'peer retention point count')
        renewals = row.get('renewals', [])
        if 'renewals' in row: need(type(renewals) is list and 1 <= len(renewals) <= 2, 'peer retention pending renewal capacity')
        prior = -1
        for point in [*renewals, *points]:
            need(type(point) is dict and set(point) == {'cut', 'catalog', 'application'}, 'peer retention anchor fields')
            f.check_type(point['cut'], 'cut', types)
            view_binding(point['cut']['view'])
            for key in ('catalog', 'application'): f.check_type(point[key], 'hash', types)
            need(prior < point['cut']['index'], 'peer retention endpoint order'); prior = point['cut']['index']
        if 'confirmation' in row:
            need(confirmation(row['confirmation'], value['root'], row['identity']) == points[0], 'peer confirmation retained endpoint')
    need(names == voters, 'peer retention exact governing identities')
    need(len(f.canonical(value)) <= 32768, 'peer retention plan capacity')
    return value


def _confirmed_merge(before, sources, generation):
    """Pure expected-state derivation, called only after original physical replay.

    This fixture has exactly one observation, node 3's original publication 2.
    Every confirmation must be byte-identical to that derived original; neither
    revision, claimed source cut nor a confirmation boolean substitutes for it.
    """
    initial = r.decode(before); result = copy.deepcopy(initial['plan']); plan(result)
    points = {row['identity']['node']: {} for row in result['peers']}; identities = {row['identity']['node']: row['identity'] for row in result['peers']}
    proofs = {}; history = {}; original = f.decode(generation, 'records', 'GENERATION'); encoded = base64.b64encode(generation).decode()
    for raw in [before, *sources]:
        state = r.decode(raw); p = plan(state['plan'])
        need(p['root'] == result['root'] and p['view'] == result['view'], 'peer confirmation selected root/view')
        for row in p['peers']:
            node = row['identity']['node']; need(row['identity'] == identities[node], 'peer confirmation selected permanent identity')
            for point in [*row.get('renewals', []), *row['possible']]:
                index = point['cut']['index']
                need(index not in history or history[index] == point, 'peer confirmation conflicting original endpoint')
                history[index] = point; points[node][index] = point
            if 'confirmation' in row:
                need(node == original['node'] and row['confirmation'] == encoded, 'peer confirmation exact observed generation')
                proofs[node] = encoded
    for row in result['peers']:
        node = row['identity']['node']; retained = points[node]
        row.pop('renewals', None); row.pop('confirmation', None)
        if node in proofs:
            retained = {i: a for i, a in retained.items() if i >= original['cut']['index']}; row['confirmation'] = proofs[node]
        need(1 <= len(retained) <= 2, 'peer confirmation unresolved endpoint capacity')
        row['possible'] = [retained[i] for i in sorted(retained)]
    plan(result)
    return before if result == initial['plan'] else r.frame(dict(initial, revision=initial['revision']+1, previous=sha(before), plan=result))


def validate(root):
    root = Path(root); group = e.initialize(b.original(root, 3, False))
    def campaign(round, merge=e.merged):
        nonlocal group
        # Installation must cover the pre-merge local debts too. They are not
        # discarded before selector replacement and durable ledger completion.
        ancestry = {n: b.c.current(files)[1].get('ancestry.gsr', b'') for n, files in group.items()} if round == 3 else None
        prepared, selected, installed = e.campaign(root, group, round+1, f'round-{round}-prepared', merge_ledgers=merge, selected_prefix=prefix, retained_ancestry=ancestry)
        for stage, state in [('prepared', prepared), ('selected', selected), ('installed', installed)]: b.match(root, f'round-{round}-{stage}', state)
        group = b.settled(installed); b.match(root, f'round-{round}-settled', group)
    campaign(1); group, _ = b.publication(root, group, 1, None, [])
    state = r.decode(group['node-1'][e.FILE]); p = copy.deepcopy(state['plan'])
    p['peers'][2]['possible'].append(b.c.anchor(b.c.current(group['node-1'])[2]['capsule']))
    group['node-1'][e.FILE] = r.frame(dict(state, revision=state['revision']+1, previous=sha(group['node-1'][e.FILE]), plan=p))
    campaign(2); group, _ = b.publication(root, group, 2, None, []); b.match(root, 'before-confirmation', group)
    generation_prefix, _, packet = b.c.current(group['node-3'])
    generation = group['node-3'][generation_prefix+'generation.gsr']
    state = r.decode(group['node-2'][e.FILE]); p = copy.deepcopy(state['plan']); row = p['peers'][2]
    row['renewals'] = row['possible']; row['possible'] = [b.c.anchor(packet['capsule'])]; row['confirmation'] = base64.b64encode(generation).decode(); plan(p)
    group['node-2'][e.FILE] = r.frame(dict(state, revision=state['revision']+1, previous=sha(group['node-2'][e.FILE]), plan=p))
    b.match(root, 'after-confirmation', group)
    campaign(3, lambda before, sources: _confirmed_merge(before, sources, generation))
    group, _ = b.publication(root, group, 3, None, [])
    for slot in (1, 2, 3):
        for node in group:
            _, members, packet = b.c.current(b.c.inventory(root/f'slot-{slot}-settled'/node))
            image = members[packet['capsule']['application']+'.image']
            b.typed_image(root/f'typed-{slot}-{node}', image)
    calls = json.loads((root/'calls.json').read_text())
    names = sorted(group)
    def maintenance(label): return [(n, label+'-'+op) for op in ('copy', 'maintain') for n in names]
    def campaign_calls(round):
        return [('node-1', 'allocate-'+str(round))]+[(n, op+'-'+str(round)) for op in ('prepare', 'select', 'install') for n in names]+maintenance(f'round-{round}-settled')
    def publication_calls(slot):
        return [('node-1', 'entry-'+str(slot))]+[(n, op+'-'+str(slot)) for op in ('accept', 'proof', 'certificate', 'apply', 'publish') for n in names]+maintenance(f'slot-{slot}-settled')+[(n, 'inspect-'+str(slot)) for n in names]
    expected = [(n, 'initialize') for n in names]+campaign_calls(1)+publication_calls(1)+[('node-1', 'old-dispatch')]
    expected += campaign_calls(2)+publication_calls(2)+[('node-3', 'actual-original-copy'), ('node-2', 'confirmed-copy'), ('node-1', 'still-stale')]
    expected += campaign_calls(3)+[(n, 'merged-confirmed-copy') for n in names]+publication_calls(3)+[(n, 'reopened-confirmed-copy') for n in names]
    need([(v['node'], v['operation']) for v in calls] == expected, 'peer confirmation complete original calls')
    matching = [v for v in calls if v['node'] == 'node-2' and v['operation'] == 'confirmed-copy']
    need(len(matching) == 1, 'peer confirmation original observation call')
    events = matching[0]['events']; e.ordered(events, ['RETENTION_BEFORE_WRITE', 'RETENTION_FORCED', 'RETENTION_RENAMED', 'RETENTION_PARENT_FORCED'], 'peer confirmation')
    need(events.count('RETENTION_BEFORE_WRITE') == 1, 'peer confirmation repeated observation rewrote ledger')
    for node in group:
        for operation in ('select-3', 'install-3'):
            matches = [v for v in calls if v['node'] == node and v['operation'] == operation]
            need(len(matches) == 1, 'peer confirmation selected original call')
            required = ['SELECTED_FORCED', 'SELECTED_BEFORE_RETURN'] if operation == 'select-3' else ['INSTALL_PARENT_FORCED', 'RETENTION_FORCED', 'RETENTION_PARENT_FORCED', 'SELECTED_RETENTION_COMPLETED', 'INSTALL_BEFORE_RETURN']
            e.ordered(matches[0]['events'], required, 'peer confirmation '+operation)
    return dict(status='PASS', scope='native-peer-confirmation-selected-merge', originalBootstrap=True,
                originalPublication=True, campaigns=3, publications=3, phase3Complete=False,
                automaticCompetition=False, processCrash=False, joining=False)


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    variants = [('bootstrap', 'admitted original public bootstrap'), ('generation', 'admitted exact slot-2-settled: node-3'),
                ('confirmation', 'admitted exact after-confirmation: node-2'), ('renewals', 'admitted exact after-confirmation: node-2'),
                ('source', 'admitted exact round-3-prepared: node-2'), ('selected', 'admitted exact round-3-selected: node-1'),
                ('completion', 'admitted exact round-3-installed: node-1'), ('ancestry', 'admitted exact round-3-installed: node-1'),
                ('published', 'admitted exact slot-3-settled: node-1'),
                ('copy-call', 'peer confirmation complete original calls'),
                ('force', 'selected retention force order: peer confirmation'), ('early-return', 'selected retention force order: peer confirmation install-3')]
    for name, reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-peer-confirmation-') as temp:
            copied = Path(temp)/'evidence'; shutil.copytree(root, copied)
            if name == 'bootstrap': (copied/'initial/target-0/bootstrap-admission.gsbp').unlink()
            elif name == 'generation':
                path = copied/'slot-2-settled/node-3'; prefix = b.c.current(b.c.inventory(path))[0]; (path/prefix/'generation.gsr').write_bytes(b'changed')
            elif name in ('confirmation', 'renewals'):
                path = copied/'after-confirmation/node-2'/e.FILE; state = r.decode(path.read_bytes()); state['plan']['peers'][2].pop(name); path.write_bytes(r.frame(state))
            elif name == 'source': next((copied/'round-3-prepared/node-2/sources').glob('*/source.gscp')).write_bytes(b'changed')
            elif name == 'selected': (copied/'round-3-selected/node-1/grants.gsr').write_bytes(b'changed')
            elif name == 'ancestry':
                path = copied/'round-3-installed/node-1'; generation_prefix = b.c.current(b.c.inventory(path))[0]
                (path/generation_prefix/'ancestry.gsr').unlink()
            elif name in ('completion', 'published'):
                stage = 'round-3-installed' if name == 'completion' else 'slot-3-settled'; (copied/stage/'node-1'/e.FILE).write_bytes(b'changed')
            else:
                path = copied/'calls.json'; rows = json.loads(path.read_text())
                if name == 'copy-call': rows = [v for v in rows if v['operation'] != 'actual-original-copy']
                else:
                    row = next(v for v in rows if v['operation'] == ('confirmed-copy' if name == 'force' else 'install-3'))
                    row['events'].remove('RETENTION_PARENT_FORCED')
                path.write_text(json.dumps(rows))
            try: validate(copied)
            except ValueError as error:
                need(str(error) == reason, 'peer confirmation negative wrong rejection: '+name+': '+str(error)); negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('peer confirmation mutation accepted: '+name)
    return dict(original, negatives=negatives)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); a = p.parse_args(); print(json.dumps(qualify(a.root), sort_keys=True))
