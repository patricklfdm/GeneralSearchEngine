"""Original-first pending target replay. These are native local storage histories,
not replicated retention, network dispatch, installed targets or public readiness.
No new production storage/wire format is introduced by this evidence layout.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
from . import native_application_evidence as n

p, c, f, e, need = n.p, n.c, n.f, n.e, n.need


def target(root, node, original, end):
    """Compare every exposed byte with the independently derived original end."""
    _, current, packet = c.current(original)
    cap = packet['capsule']; catalog = f.decode(end['catalog.gsr'], 'records', 'CATALOG')
    expected = {name: end[name] for name in ('selector.gsr', 'certificate.gsr', 'catalog.gsr', 'statement.gsr', 'ack.gsr')}
    expected.update({name: current[name] for name in ('promise.gsr', 'selected.gsr')})
    identity = f.decode(original['node.gsr'], 'records', 'NODE')['identity']
    need(identity['node'] == node, 'pending target permanent owner')
    expected['target.json'] = f.canonical(dict(owner=identity,
        parent=dict(cut=cap['cut'], catalog=cap['catalog'], application=cap['application']),
        target=dict(cut=catalog['cut'], catalog=e.digest(end['catalog.gsr']), application=catalog['application'])))
    need(c.inventory(root) == expected, 'pending target exact original records')


def applied(original, end, actual):
    expected = dict(original, **{'applied-end': None})
    expected.update({'applied-end/'+name: value for name, value in end.items()})
    need(actual == expected, 'pending target complete original applied end')


def validate(root):
    root = Path(root); p.selection.layout(root, {'histories', 'process'}, 'pending target evidence')
    names = {f'size-{size}-{kind}' for size in (3, 4, 5) for kind in ('empty', 'backup')}
    p.selection.layout(root/'histories', names, 'pending target histories')
    nodes = 0
    for size in (3, 4, 5):
        for backup in (False, True):
            path = root/'histories'/f"size-{size}-{'backup' if backup else 'empty'}"
            for i in range(1, size+1):
                node = f'node-{i}'; original, end, _, _ = n.certified(path, size, backup, node)
                target(path/(node+'-target'), node, original, end)
                applied(original, end, c.inventory(path/'applied'/node)); nodes += 1
            rows = n.read_json(path/'calls.json')
            applications = [v for v in rows if v['operation'] == 'pending-apply']
            need([v['node'] for v in applications] == [f'node-{i}' for i in range(1, size+1)], 'pending target actual native owners')
            for row in applications:
                n.native_order(row['events'], 1)
                need(not any(v.startswith('PUBLICATION_') for v in row['events']), 'pending target unexpected publication')
    path = root/'process'; original, end, _, _ = n.certified(path)
    for run in (1, 2):
        target(path/f'process-{run}', 'node-1', original, end)
        applied(original, end, c.inventory(path/f'recovered-{run}'))
        lines, events = n.lines(path/f'process-{run}.log'); n.native_order(events, 1)
        need([line for line in lines if not line.startswith('EVENT ')] == ['RESULT PASS'], 'pending target worker completion')
    return dict(status='PASS', histories=6, nativeTargets=nodes, freshProcesses=2,
        published=False, durableFutureRetention=False, dispatch=False, phase3Complete=False)


def negatives(root):
    validate(root)  # Unrelated failures in original evidence can never count as negatives.
    cases = [
        ('catalog', 'histories/size-3-empty/node-1-target/catalog.gsr', 'pending target exact original records'),
        ('acknowledgement', 'histories/size-3-empty/node-1-target/ack.gsr', 'pending target exact original records'),
        ('target', 'histories/size-3-empty/node-1-target/target.json', 'pending target exact original records'),
        ('applied-end', 'histories/size-3-empty/applied/node-1/applied-end/ack.gsr', 'pending target complete original applied end'),
        ('recovered-selector', 'process/recovered-2/selector.gsr', 'pending target complete original applied end'),
        ('force-order', 'process/process-2.log', 'native application exact force order'),
    ]
    results = []
    for name, relative, reason in cases:
        with tempfile.TemporaryDirectory(prefix='v53-pending-target-negative-') as temporary:
            copy = Path(temporary)/'raw'; shutil.copytree(root, copy)
            path = copy/relative; data = path.read_bytes()
            if name == 'force-order':
                data = data.replace(b'EVENT NATIVE_CERTIFICATE_RETAINED\n', b'', 1)
            else:
                data = data[:-1]+bytes([data[-1]^1])
            path.write_bytes(data)
            try:
                validate(copy)
            except ValueError as error:
                need(str(error) == reason, f'pending target wrong negative reason: {name}: {error}')
            else:
                raise ValueError('pending target negative accepted: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason))
    return results


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('root', type=Path); parser.add_argument('--negatives', action='store_true')
    args = parser.parse_args(); result = validate(args.root)
    if args.negatives: result['negatives'] = negatives(args.root)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
