"""Original-first replay of a leader JVM death and its original-disk successor.

The two unchanged followers stay live. Physical and complete TCP replay precede
process claims; stdout observations must exactly match each leader lifetime.
Exit/lock observations establish process loss, never host power-loss durability.
"""
import argparse
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from . import node_owner_network as net

n, p, f, e, need = net.n, net.p, net.f, net.e, net.need


def inventory(root):
    from .discovered_selection_evidence import inventory as regular
    regular(root)
    p.b.selection.layout(root, {'history', 'process'}, 'node process roots')
    p.b.selection.layout(root/'process', {'spec.json', 'result.json'} |
        {f'life-{life}.{suffix}' for life in (1, 2) for suffix in ('jsonl', 'stderr')}, 'node process retained inputs')


def children(result, *, cut='AFTER_DATA_RETURN'):
    need(type(result) is dict and set(result) == {'mode', 'cut', 'children', 'status', 'powerLoss', 'phase3Complete'}
         and result['mode'] in ('halt', 'kill') and result['cut'] == cut
         and result['status'] == 'PARTIAL' and result['powerLoss'] is False and result['phase3Complete'] is False,
         'node process producer scope')
    rows = result['children']
    need(type(rows) is list and len(rows) == 2 and all(type(v) is dict for v in rows), 'node process children')
    need(all(type(row.get('pid')) is int and row['pid'] > 0 for row in rows) and rows[0]['pid'] != rows[1]['pid'],
         'node process fresh child identities')
    for life, row in enumerate(rows, 1):
        expected = dict(life=life, pid=row['pid'], started=dict(life=life, pid=row['pid'], mode=result['mode']),
            exit=(73 if result['mode'] == 'halt' else 137) if life == 1 else 0)
        expected.update(dict(lockHeldBeforeDeath=True, lockReleasedAfterDeath=True) if life == 1 else dict(drained=True))
        need(row == expected and f.canonical(row) == f.canonical(expected),
             'node process exact death and drain')
    return rows


def transcript(path):
    raw = path.read_bytes()
    need(0 < len(raw) <= 16*e.MIB and raw.endswith(b'\n'), 'node process complete bounded transcript')
    lines = raw.splitlines(); need(len(lines) <= 32768 and all(lines), 'node process transcript lines')
    result = []
    for line in lines:
        message = e.parse(line)
        need(type(message) is dict and set(message) == {'action', 'value'} and line == f.canonical(message),
             'node process canonical message')
        result.append(message)
    return result


def observations(root, rows, *, cut='AFTER_DATA_RETURN', reconciled=False):
    return _observations(root,rows,cut=cut,reconciled=reconciled,failed=False)


def _observations(root, rows, *, cut, reconciled, failed):
    need(type(failed) is bool,'node process exact observation mode')
    history = root/'history'; process = root/'process'; events = n.read(history/'events.json'); wire = n.read(history/'wire.json')
    crash = next(i for i, row in enumerate(events) if row['event'] == 'NODE_CRASH')
    parts = (events[:crash], events[crash+1:]); counts = []
    for life, (row, part) in enumerate(zip(rows, parts), 1):
        failure=failed and life==2
        if not failure:need((process/f'life-{life}.stderr').read_bytes() == b'', 'node process child stderr')
        messages = transcript(process/f'life-{life}.jsonl')
        need(messages[0] == dict(action='started', value=row['started']), 'node process original child start')
        if failure:
            need(messages[-1]['action']=='event' and messages[-1]['value'].get('event')=='ROUND_SLOT_COMPLETE',
                 'node process failed terminal boundary')
        else:
            ending = dict(action='cut', value=dict(name=cut, mode=row['started']['mode'], pid=row['pid'])) if life == 1 else dict(action='closed', value=2)
            need(messages[-1] == ending, 'node process terminal boundary')
        actual = []; snapshots = []; opened = 0; installation = life-1
        for message in messages[1:] if failure else messages[1:-1]:
            action, value = message['action'], message['value']
            if action == 'event': actual.append(value)
            elif action == 'response':
                need(type(value) is dict and set(value) == {'event', 'wire'} and value['wire'] in wire,
                     'node process original child response')
                actual.append(value['event'])
                need(value['event'] == dict(node='node-1', incarnation=life, event='WIRE_RESPONSE',
                    request=e.digest(base64.b64decode(value['wire']['request'], validate=True)),
                    response=e.digest(base64.b64decode(value['wire']['response'], validate=True))), 'node process child response identity')
            elif action == 'installed':
                installation += 1
                number = installation if reconciled else life
                need(value == dict(number=number, bytes=base64.b64encode((history/f'selected-{number}.gsr').read_bytes()).decode()),
                     'node process original installed record')
                snapshots.append(f'installed-{number}')
            elif action == 'snapshot': snapshots.append(value)
            elif action == 'opened':
                need(value == life and actual[-1] == dict(node='node-1', incarnation=life, event='NODE_OPEN'),
                     'node process open before campaign')
                opened += 1
            else: raise ValueError('node process unexpected child action')
        need(opened == 1 and actual == [v for v in part if v['node'] == 'node-1'], 'node process exact child lifetime events')
        first = 2*life-1
        expected = [f'installed-{life}', f'applied-{first}', f'published-{first}', 'first-ready' if life == 1 else 'second-ready',
             f'applied-{first+1}', f'published-{first+1}']
        if cut != 'AFTER_DATA_RETURN':
            expected = expected[:-2] if life == 1 else expected[:1]+['applied-2','published-2']+expected[1:]
            if life == 1:
                need(messages[-2] == dict(action='event',value=dict(node='node-1',incarnation=1,event=cut)), 'node process exact interrupted force')
        if reconciled and life == 2:
            expected=expected[:-2]+['installed-3','applied-4','published-4','applied-5','published-5']
        need(snapshots == expected, 'node process exact child snapshots')
        counts.append(len(messages))
    return counts


def configuration(root):
    history = root/'history'; spec = n.read(root/'process/spec.json')
    plan = p.b.t.plans.decode((history/'original-plan.gsbp').read_bytes(), (history/'original-application.image').read_bytes(), details=True)
    paths = [v['path'] for v in plan['plan']['descriptor']['paths']]
    need(type(spec) is dict and set(spec) == {'nodes', 'scratch'} and spec['nodes'] ==
         [dict(replica=paths[1+2*i], application=paths[2+2*i]) for i in range(3)], 'node process original disk paths')
    scratch = PurePosixPath(spec['scratch'])
    need(scratch.is_absolute() and '..' not in scratch.parts and all(not scratch.is_relative_to(v) and
         not PurePosixPath(v).is_relative_to(scratch) for v in paths), 'node process disjoint scratch')


def validate(root):
    root = Path(root); inventory(root)
    # Validate originals before accepting exit codes or interpreting any mutation.
    physical = net.validate(root/'history', process_restart=True)
    configuration(root); result = n.read(root/'process/result.json'); rows = children(result)
    counts = observations(root, rows)
    return dict(status='PASS', scope='one-native-node-process-reopen-history', mode=result['mode'], cut=result['cut'],
        originalFirst=True, processRestart=True, freshLeaderJvms=2, survivingFollowers=2,
        childMessages=counts, network=physical, powerLoss=False, publicRuntime=False, phase3Complete=False)


NEGATIVES = {
    'reused-pid': 'node process fresh child identities',
    'wrong-exit': 'node process exact death and drain',
    'missing-lock-probe': 'node process exact death and drain',
    'wrong-disk': 'node process original disk paths',
    'missing-cut': 'node process terminal boundary',
    'child-error': 'node process child stderr',
    'missing-child-send': 'node process exact child lifetime events',
    'invented-drain': 'node process unexpected child action',
    'copied-child-start': 'node process original child start',
    'incomplete-transcript': 'node process complete bounded transcript',
    'clean-close-instead-of-crash': 'node owner exact lifecycle order',
    'missing-fresh-barrier': 'node owner readiness fresh barrier',
    'wrong-physical-selector': 'admitted exact published-3: node-1',
    'missing-request-bytes': 'node network original send shape',
    'unreceived-selected-prepare': 'discovered selection response delivered',
}


def mutate(root, name):
    if name in ('reused-pid', 'wrong-exit', 'missing-lock-probe'):
        path = root/'process/result.json'; value = n.read(path)
        if name == 'reused-pid': value['children'][1]['pid'] = value['children'][0]['pid']
        elif name == 'wrong-exit': value['children'][0]['exit'] = 0
        else: value['children'][0].pop('lockHeldBeforeDeath')
        path.write_bytes(f.canonical(value))
    elif name == 'wrong-disk':
        path = root/'process/spec.json'; value = n.read(path); value['nodes'][0]['replica'] += '-copy'; path.write_bytes(f.canonical(value))
    elif name == 'child-error': (root/'process/life-1.stderr').write_text('crash failed\n')
    elif name in ('clean-close-instead-of-crash', 'missing-fresh-barrier', 'missing-request-bytes', 'unreceived-selected-prepare'):
        path = root/'history/events.json'; value = n.read(path)
        if name == 'clean-close-instead-of-crash': next(v for v in value if v['event'] == 'NODE_CRASH')['event'] = 'NODE_CLOSED'
        elif name == 'missing-fresh-barrier':
            rows = [v for v in value if v['event'] == 'ROUND_BEFORE_READY']; rows[1].update(record=rows[0]['record'], bytes=rows[0]['bytes'])
        elif name == 'missing-request-bytes': next(v for v in value if v['event'] == 'NETWORK_SEND').pop('bytes')
        else:
            selected = f.decode((root/'history/selected-2.gsr').read_bytes(), 'records', 'SELECTED')
            peer = selected['sources'][1]['voter']; digests = set()
            for row in n.read(root/'history/wire.json'):
                kind, request = n.transfer.t.wire(row['request'])
                if kind == 'PREPARE' and request['ballot'] == selected['ballot'] and request['recipient']['node'] == peer:
                    digests.add(e.digest(base64.b64decode(row['response'], validate=True)))
            need(digests, 'node process mutation requires actual selected prepare')
            value = [v for v in value if not (v['event'] == 'NETWORK_RECEIVED' and v['response'] in digests)]
        path.write_bytes(f.canonical(value))
    elif name == 'wrong-physical-selector': (root/'history/published-3/node-1/selector.gsr').write_bytes(b'changed')
    else:
        path = root/'process/life-1.jsonl'; value = transcript(path)
        if name == 'missing-cut': value.pop()
        elif name == 'missing-child-send': value.remove(next(v for v in value if v['action'] == 'event' and v['value']['event'] == 'NETWORK_SEND'))
        elif name == 'invented-drain': value.insert(-1, dict(action='closed', value=1))
        elif name == 'copied-child-start': value[0]['value']['life'] = 2
        elif name != 'incomplete-transcript': raise ValueError('unknown node process mutation')
        raw = b'\n'.join(f.canonical(v) for v in value)+b'\n'; path.write_bytes(raw[:-1] if name == 'incomplete-transcript' else raw)


def qualify(root):
    root = Path(root); original = validate(root); negatives = []
    for name, reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-node-process-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root, path); mutate(path, name)
            try: validate(path)
            except ValueError as error: need(str(error) == reason, 'node process unrelated negative '+name+': '+str(error))
            else: raise ValueError('node process accepted negative '+name)
        negatives.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(original=original, negatives=negatives)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--qualify', action='store_true'); args = parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root), sort_keys=True))
