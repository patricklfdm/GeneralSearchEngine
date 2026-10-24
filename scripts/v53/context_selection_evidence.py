"""Original-first replay of protected local selection, without later installation.

Actual three-owner sources fix one immutable decision. Exception cuts test local
reopen; they are neither process-death nor online membership qualification.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_publication_evidence as publication
from . import context_capture_evidence as capture
from . import context_backing_retirement_evidence as retirement

e, owner, source = capture.e, capture.owner, capture.source
NODES = ('node-1', 'node-2', 'node-3')
CUTS = ('SELECTED_BEFORE_WRITE', 'SELECTED_WRITTEN', 'SELECTED_FORCED', 'SELECTED_BEFORE_RETURN')
CURRENT = ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
           'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED']


def layout(path, members, label):
    e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()} == set(members),
           'context selection '+label+' inventory')


def states(path):
    layout(path, NODES, 'owner')
    return {node: owner.read_snapshot(path/node) for node in NODES}


def captured(before, path, counter):
    actual = states(path); result = {}
    for node, (files, dirs) in before.items():
        frame, _ = capture.new_promise(files, actual[node][0], counter)
        steps = capture.transaction(files, dirs, frame)
        result[node] = steps[-1][1:]
        capture.match(path/node, *result[node], 'selection capture')
    return result


def decision(group, counter):
    bases = {}; binding = None
    for node, (files, _) in group.items():
        segments, _, own = e.decode(files['pending.context'])
        basis = e.f.decode(segments[3], 'records', 'BASIS')
        e.need(own['node'] == node and basis['voter'] == node and basis['ballot']['counter'] == counter,
               'context selection exact source identity')
        packet = e.p.decode(files['sources/'+basis['basisId']+'/source.gscp'])
        e.p.bind(packet, segments[3])
        if binding is not None:
            e.need(own['entry'] == binding['entry'] and basis['cut'] == previous['cut']
                   and basis['ballot'] == previous['ballot'], 'context selection common original parent')
        binding, previous = own, basis
        bases[node] = (segments[3], basis)
    e.need(len({v[1]['basisId'] for v in bases.values()}) == 3, 'context selection distinct local sources')
    raw = e.f.encode('records', 'SELECTED', dict(root=basis['root'], view=basis['view'], ballot=basis['ballot'],
        cut=basis['cut'], nextEntry=binding['entry'], sources=[dict(voter=n, basisId=bases[n][1]['basisId'],
        basisDigest=e.digest(bases[n][0])) for n in NODES]))
    return raw, {node: (dict(files, **{'grants.gsr': files['grants.gsr']+raw}), dirs)
                 for node, (files, dirs) in group.items()}


def reseal(files):
    segments, _, _ = e.decode(files['pending.context'])
    basis = e.f.decode(segments[3], 'records', 'BASIS')
    count = sum(p.startswith('sources/'+basis['basisId']+'/') for p in files)
    prefix = ['CONTEXT_OWNER_VALIDATED']+['CONTEXT_SOURCE_MEMBER_FORCED']*count+[
        'CONTEXT_SOURCE_DIRECTORY_FORCED', 'CONTEXT_SOURCE_PARENT_FORCED']
    return prefix, prefix+['CONTEXT_ACTIVE_FORCED', 'CONTEXT_ACTIVE_PARENT_FORCED', 'CONTEXT_OWNER_BEFORE_RETURN']


def validate(root):
    root = Path(root); receipt = source.load(root/'receipt.json')
    matrix = receipt.get('schema') == 'gse-v53-context-selection-cuts-v1'
    layout(root, {'reference', 'prepared', 'receipt.json'} | (set(CUTS) if matrix else {
        'selected', 'next-prepared', 'continued', 'events-1.json', 'events-2.json', 'events-3.json'}), 'evidence')
    publication.validate(root/'reference')
    original = states(root/'reference/carried-snapshots/source-retired')
    prepared = captured(original, root/'prepared', 22)
    _, selected = decision(prepared, 22)
    if matrix:
        files, dirs = prepared['node-1']; final, final_dirs = selected['node-1']; prefix, full = reseal(files)
        for at, cut in enumerate(CUTS):
            row = root/cut; layout(row, {'crash', 'recovery-crash', 'final', 'events.json'}, 'cut')
            first = files if at == 0 else final
            capture.match(row/'crash', first, dirs, 'selection first interruption')
            capture.match(row/'recovery-crash', first, dirs, 'selection second interruption')
            capture.match(row/'final', final, final_dirs, 'selection explicit return')
            trace = source.load(row/'events.json', 131072); e.exact(trace, 'first recovery resume')
            e.need(trace['first'] == list(CUTS[:at+1]), 'context selection first force order')
            e.need(trace['recovery'] == CURRENT+prefix, 'context selection second force order')
            expected = CURRENT+full+['CERTIFICATE_ACTIVE_FORCED', 'CERTIFICATE_ACTIVE_PARENT_FORCED', 'OPEN_RETURNED']
            expected += list(CUTS) if at == 0 else []
            expected += ['EXPLICIT_SELECTED_RETURNED']*2+full
            e.need(trace['resume'] == expected, 'context selection explicit return order')
        expected_receipt = dict(schema='gse-v53-context-selection-cuts-v1', status='PASS', cuts=list(CUTS),
            interruptions='injected-IOException', freshProcesses=False, runtimeEnabled=False)
    else:
        states(root/'selected')
        for n, node in enumerate(NODES, 1):
            capture.match(root/'selected'/node, *selected[node], 'selection committed')
            _, seal = reseal(selected[node][0])
            e.need(source.load(root/f'events-{n}.json', 131072) == list(CUTS)+['EXPLICIT_SELECTED_RETURNED']*2+seal,
                   'context selection clean force order')
        later = captured(selected, root/'next-prepared', 23); _, later_selected = decision(later, 23)
        states(root/'continued')
        for node, (files, dirs) in later_selected.items():
            old_segments, _, _ = e.decode(prepared[node][0]['pending.context'])
            old = e.f.decode(old_segments[3], 'records', 'BASIS')['basisId']
            final = retirement.retirement(files, dirs, old)[2][-1][1]
            e.need(source.state(root/'continued'/node) == final, 'context selection exact intermediate retirement')
        expected_receipt = dict(schema='gse-v53-context-selection-v1', status='PASS', nodes=3, ballots=[22, 23],
            installedBallot=21, originalVote=20, freshProcesses=False, runtimeEnabled=False)
    e.need(receipt == expected_receipt, 'context selection receipt scope')
    return dict(status='PASS', cases=len(CUTS) if matrix else 3, originalFirst=True, installedBallot=21,
                originalVote=20, freshProcesses=False, runtimeEnabled=False, laterInstallEnabled=False,
                historicalBootstrap='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); matrix = (root/CUTS[0]).is_dir(); negatives = []
    final_reason = 'context capture exact selection '+('explicit return' if matrix else 'committed')
    variants = {'original': 'context publication exact source-retired: node-1',
        'missing': 'context selection evidence inventory', 'prepared': 'context capture exact selection capture',
        'vote': final_reason, 'context': final_reason, 'selector': final_reason, 'source': final_reason,
        'journal': final_reason, 'floor': final_reason, 'scope': 'context selection receipt scope',
        'order': 'context selection '+('first force order' if matrix else 'clean force order'),
        'return': 'context selection '+('explicit return order' if matrix else 'clean force order'),
        'link': 'owner context linked/nonregular member'}
    if matrix: variants.update(second='context capture exact selection second interruption',
                               recovery='context selection second force order')
    else: variants.update(next='context capture exact selection capture',
                          retirement='context selection exact intermediate retirement')
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-context-selection-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
            row = moved/CUTS[0] if matrix else moved
            final = row/'final' if matrix else moved/'selected/node-1'
            if name == 'original': (moved/'reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name == 'missing': shutil.rmtree(row if matrix else moved/'selected')
            elif name in ('prepared', 'next', 'second', 'retirement'):
                target = {'prepared': moved/'prepared/node-1', 'next': moved/'next-prepared/node-1',
                          'second': row/'recovery-crash', 'retirement': moved/'continued/node-1'}[name]
                (target/'pending.accept').write_bytes(b'changed')
            elif name in ('vote', 'context', 'selector', 'journal', 'floor'):
                (final/{'vote':'pending.accept', 'context':'pending.context', 'selector':'selector.gsr',
                        'journal':'grants.gsr', 'floor':'floor-copies/floor.gsr'}[name]).write_bytes(b'changed')
            elif name == 'source': next((final/'sources').rglob('source.gscp')).unlink()
            elif name == 'link':
                path = final/'pending.context'; path.unlink(); path.symlink_to((root/'prepared/node-1/pending.context').resolve())
            elif name == 'scope':
                path = moved/'receipt.json'; value = source.load(path); value['runtimeEnabled'] = True; path.write_bytes(e.f.canonical(value))
            else:
                path = row/'events.json' if matrix else moved/'events-1.json'; value = source.load(path, 131072)
                trace = value[{'order':'first', 'return':'resume', 'recovery':'recovery'}[name]] if matrix else value
                if name == 'order': trace.remove('SELECTED_BEFORE_WRITE')
                else: trace.insert(0, 'EXPLICIT_SELECTED_RETURNED')
                path.write_bytes(e.f.canonical(value))
            try: validate(moved)
            except ValueError as error:
                e.need(str(error) == reason, 'wrong context selection negative: '+name+': '+str(error))
                negatives.append(dict(case=name, reason=reason))
            else: raise ValueError('accepted context selection mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-selection-portable-') as tmp:
        moved = Path(tmp)/'evidence'; shutil.copytree(root, moved)
        e.need(validate(moved) == result, 'context selection portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
