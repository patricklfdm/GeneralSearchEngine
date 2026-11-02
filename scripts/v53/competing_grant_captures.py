"""Original competing-owner grant copies, independent of the winning campaign.

This collection gate checks copied bytes and complete grant-write observations.
It does not derive arbitrary campaign/install/publication history or network
authority. A successful collection remains PARTIAL, including on failed runs.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile

from . import competing_node_evidence as p
from . import joining_grant_captures as g
from . import joining_network_evidence as network
from . import joining_history_run as h

need, f = g.need, g.f
FILE = 'grant-capture-events.json'
LINK_FIELDS = {'node','scope','event','capture','sha256','basis','returnEvent','capturedAfterEvent','nanoTime'}


def timelines(root):
    root = Path(root)
    original = h.read_json(root, 'events.json', 16*g.MIB)
    events = p.trace(root)  # Validate every original event, not just grant callbacks.
    _, links = g.json_file(root/FILE)
    need(type(links) is list and 0 < len(links) <= g.MAXIMUM_CAPTURES, 'competing capture bounded links')
    pending, seen, previous, last_time = {}, set(), -1, -1
    for ordinal, row in enumerate(links, 1):
        need(type(row) is dict and set(row) == LINK_FIELDS and row['event'] == g.EVENT
             and row['scope'] == 'network-owner' and row['node'] in p.c.NODES,
             'competing capture link shape')
        lower, upper, at = row['returnEvent'], row['capturedAfterEvent'], row['nanoTime']
        need(type(lower) is int and type(upper) is int and 0 <= lower <= upper < len(events),
             'competing capture event positions')
        need(lower not in seen and events[lower] == dict(node=row['node'], event='GRANT_BEFORE_RETURN'),
             'competing capture exact return')
        need(upper >= previous and type(at) is int and at >= last_time and original[upper]['nanoTime'] <= at
             and (upper+1 == len(events) or at <= original[upper+1]['nanoTime']),
             'competing capture monotonic interval')
        need(not any(v['node'] == row['node'] and v['event'] in p.OWNER_POINTS for v in events[lower+1:upper+1]),
             'competing capture writer advanced before copy')
        need(row['capture'] == f'{g.DIRECTORY}/capture-{ordinal:04d}', 'competing capture ordered path')
        pending.setdefault(upper, []).append({k:v for k,v in row.items() if k not in ('returnEvent','capturedAfterEvent','nanoTime')})
        seen.add(lower); previous, last_time = upper, at
    need(seen == {i for i,v in enumerate(events) if v['event'] == 'GRANT_BEFORE_RETURN'},
         'competing capture complete returns')
    # Merge only recorded annotations. No force, grant or wire observation is
    # reconstructed; the indices are checked against the original full trace.
    merged = []
    for i, event in enumerate(events):
        merged.append(event); merged.extend(pending.get(i, []))
    return merged


def originals(root):
    group = p.n.s.initialize(p.b.original(root, 3, False))
    group = {node:dict(files, **{p.n.future.FILE:p.n.future.frame(p.n.future.initial(files), {})})
             for node,files in group.items()}
    p.b.match(root, 'before-network', group)
    return group


def validate(root):
    root = Path(root); p.exchange.inventory(root)
    events = timelines(root); initial = originals(root)
    copies = g.collect(root, events, learner_retention=False)
    used = set()
    for copy in copies:
        files = initial.get(copy['node'])
        need(files is not None and files['root.gsr'][16:48].hex() == copy['root']
             and f.decode(files['node.gsr'], 'records', 'NODE')['identity'] == copy['identity'],
             'competing capture admitted owner')
        starts = [i for i,v in enumerate(events[:copy['returnEvent']]) if v == dict(node=copy['node'], event='CURRENT_BEFORE_CAPTURE')]
        need(starts, 'competing capture grant start absent')
        members, _, _ = g.inventory(root/copy['capture']/'replica')
        packet = g.disk.p.decode(members['sources/'+copy['basisId']+'/source.gscp'])
        positions = network.grant_capture_order(events, copy['node'], None, starts[-1], copy['returnEvent'], packet)
        need(not positions.intersection(used), 'competing capture reused writes'); used.update(positions)
    need(used == {i for i,v in enumerate(events) if network.capture_callback(v['event'])},
         'competing capture unbound writes')
    return dict(status='PARTIAL', scope='competing-original-grant-collection', captures=len(copies),
                bytes=sum(v['bytes'] for v in copies), admittedOwners=True, completeGrantWrites=True,
                allCampaignsQualified=False, fullNetworkQualified=False, publicationQualified=False,
                processDeathQualified=False, phase3Complete=False)


NEGATIVES = {
    'missing-link': 'competing capture complete returns',
    'duplicate-return': 'competing capture exact return',
    'foreign-node': 'competing capture link shape',
    'wrong-owner': 'competing capture exact return',
    'boolean-position': 'competing capture event positions',
    'out-of-range': 'competing capture event positions',
    'before-return': 'competing capture event positions',
    'early-clock': 'competing capture monotonic interval',
    'late-clock': 'competing capture monotonic interval',
    'path-traversal': 'competing capture ordered path',
    'missing-force': 'joining network durable grant order',
}


def mutate(root, name):
    _, links = g.json_file(root/FILE); events = h.read_json(root, 'events.json', 16*g.MIB)
    first = links[0]
    if name == 'missing-link': links.pop()
    elif name == 'duplicate-return': links.insert(1, dict(first))
    elif name == 'foreign-node': first['node'] = 'node-99'
    elif name == 'wrong-owner': first['node'] = 'node-2' if first['node'] != 'node-2' else 'node-1'
    elif name == 'boolean-position': first['returnEvent'] = True
    elif name == 'out-of-range': first['capturedAfterEvent'] = len(events)
    elif name == 'before-return': first['capturedAfterEvent'] = first['returnEvent']-1
    elif name == 'early-clock': first['nanoTime'] = events[first['capturedAfterEvent']]['nanoTime']-1
    elif name == 'late-clock':
        chosen = next((v for v in links if v['capturedAfterEvent']+1 < len(events)), None)
        need(chosen is not None, 'competing capture negative requires subsequent event')
        chosen['nanoTime'] = events[chosen['capturedAfterEvent']+1]['nanoTime']+1
    elif name == 'path-traversal': first['capture'] = '../outside'
    elif name == 'missing-force':
        row = next(v for v in events if v['event'] == 'BASIS_FORCED'); row['event'] = 'NODE_OPEN'
    else: raise ValueError('unknown competing capture mutation')
    (root/FILE).write_bytes(f.canonical(links)); (root/'events.json').write_bytes(f.canonical(events))


def qualify(root):
    root = Path(root); original = validate(root)  # Never count an invalid original as negative coverage.
    need(original['captures'] >= 2, 'competing capture qualification needs multiple grants')
    copies = g.qualify(root, timelines(root), learner_retention=False)
    outcomes = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-competing-capture-negative-') as temp:
            target = Path(temp)/'raw'; shutil.copytree(root, target); mutate(target, name)
            try: validate(target)
            except ValueError as error:
                need(str(error) == reason, 'unrelated competing capture negative: '+name+': '+str(error))
            else: raise ValueError('competing capture mutation accepted: '+name)
            outcomes.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, copyNegatives=copies['negatives'], timelineNegatives=outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('raw'); parser.add_argument('--qualify', action='store_true')
    args = parser.parse_args(); print(json.dumps((qualify if args.qualify else validate)(args.raw), sort_keys=True))
