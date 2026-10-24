"""Original-first physical replay of protected capture/intermediate source deletion.

The producer uses local exception cuts; this is not process-death or online-runtime
qualification. Image files and the empty completion reservation stay distinct.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_capture_evidence as capture

source, owner, e = capture.source, capture.owner, capture.e
release = source.release
CUTS = source.CUTS
ROUNDS = tuple(range(22, 29))


def inventory(files, dirs):
    return {**{p: release.r.entry(raw) for p, raw in files.items()}, **{p: dict(directory=True) for p in dirs}}


def retirement(files, dirs, old):
    segments, _, binding = e.decode(files['pending.context'])
    backing = e.f.decode(segments[3], 'records', 'BASIS')
    rows = owner.journal(files['grants.gsr'], binding['root'], binding['node'])
    promises = [row for row in rows if row[0] == 'PROMISE' and row[2].get('basisId') == old]
    bases = [row for row in rows if row[0] == 'BASIS' and row[2].get('basisId') == old]
    e.need(len(promises) == len(bases) == 1, 'backing retirement original frames')
    promise, basis = promises[0], bases[0]
    e.need(21 < promise[2]['ballot']['counter'] < backing['ballot']['counter'] and basis[2]['accepted'] == backing['accepted'],
           'backing retirement intermediate authority')
    prefix = 'sources/'+old+'/'
    packet = e.p.decode(files[prefix+'source.gscp']); e.p.bind(packet, basis[1])
    record = e.f.encode('records', 'RETIREMENT', dict(root=binding['root'], node=binding['node'],
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path=p, size=len(raw), sha256=e.digest(raw)) for p, raw in sorted(files.items()) if p.startswith(prefix)]))
    authority = record+promise[1]+basis[1]+packet['capsuleBytes']
    # SELECTED refers to the local grant through its ballot/source set, not a
    # top-level basisId. Reclaim the entire unprotected grant group, including
    # its selection, while retaining installed and latest grant groups.
    compact = b''.join(raw for _, raw, value in rows if value['ballot'] != promise[2]['ballot'])
    return authority, compact, release.transaction(inventory(files, dirs), authority, compact, old)


def derive_captures(files, dirs, observed, counters):
    _, _, binding = e.decode(files['pending.context'])
    rows = owner.journal(observed['grants.gsr'], binding['root'], binding['node'])
    for counter in counters:
        promises = [raw for kind, raw, value in rows if kind == 'PROMISE' and value['ballot']['counter'] == counter]
        e.need(len(promises) == 1, 'backing retirement seed grant')
        steps = capture.transaction(files, dirs, promises[0]); files, dirs = steps[-1][1:]
    return files, dirs


def validate(root):
    root = Path(root); receipt = source.load(root/'receipt.json')
    matrix = receipt.get('schema') == 'gse-v53-context-backing-retirement-cuts-v1'
    expected = {'reference', 'receipt.json'} | ({'initial', *CUTS} if matrix else {'reopened', *(f'round-{n}' for n in ROUNDS)})
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == expected, 'backing retirement evidence inventory')
    source.validate(root/'reference'); initial, dirs = owner.read_snapshot(root/'reference/reopened')
    if matrix:
        observed, _ = owner.read_snapshot(root/'initial'); initial, dirs = derive_captures(initial, dirs, observed, (22, 23))
        capture.match(root/'initial', initial, dirs, 'retirement initial')
        _, _, binding = e.decode(initial['pending.context']); rows = owner.journal(initial['grants.gsr'], binding['root'], binding['node'])
        old = next(value['basisId'] for kind, _, value in rows if kind == 'BASIS' and value['ballot']['counter'] == 22)
        authority, compact, steps = retirement(initial, dirs, old)
        for cut in CUTS:
            case = root/cut
            e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} ==
                   {'crash', 'recovery-crash', 'final', 'events.json'}, 'backing retirement cut inventory')
            at = next(i for i, row in enumerate(steps) if row[0] == cut); crash = steps[at][1]
            e.need(source.state(case/'crash') == crash, 'backing retirement exact first interruption')
            e.need(source.state(case/'recovery-crash') == crash, 'backing retirement exact second interruption')
            e.need(source.state(case/'final') == steps[-1][1], 'backing retirement exact recovered deletion')
            trace = source.load(case/'events.json', 131072); e.exact(trace, 'first recovery resume')
            e.need(source.selected_events(trace['first']) == [name for name, _ in steps[:at+1]], 'backing retirement first force order')
            e.need(source.selected_events(trace['recovery']) == [] and trace['recovery'][-1] == 'CONTEXT_SOURCE_PARENT_FORCED',
                   'backing retirement second force order')
            again = release.transaction(crash, authority, compact, old)
            e.need(source.selected_events(trace['resume']) == [name for name, _ in again], 'backing retirement resume force order')
        expected_receipt = dict(schema='gse-v53-context-backing-retirement-cuts-v1',status='PASS',cuts=list(CUTS),interruptions='injected-IOException',freshProcesses=False,runtimeEnabled=False)
    else:
        previous = None
        for counter in ROUNDS:
            case = root/f'round-{counter}'
            e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} == {'captured', 'retired', 'events.json'}, 'backing retirement round inventory')
            observed, _ = owner.read_snapshot(case/'captured'); frame, promise = capture.new_promise(initial, observed, counter)
            captured = capture.transaction(initial, dirs, frame); files, captured_dirs = captured[-1][1:]
            capture.match(case/'captured', files, captured_dirs, 'retirement capture')
            e.need(sum(p.endswith('.image') for p in files) == (5 if previous is None else 6), 'backing retirement peak physical images')
            steps = [] if previous is None else retirement(files, captured_dirs, previous)[2]
            final = steps[-1][1] if steps else inventory(files, captured_dirs)
            e.need(source.state(case/'retired') == final, 'backing retirement exact deletion')
            trace = source.load(case/'events.json', 131072); prefix = [name for name, _, _ in captured]+['EXPLICIT_GRANT_RETURNED']
            e.need(trace[:len(prefix)] == prefix, 'backing retirement capture force order')
            e.need(source.selected_events(trace[len(prefix):]) == [name for name, _ in steps], 'backing retirement deletion force order')
            initial, dirs = owner.read_snapshot(case/'retired')
            e.need(sum(p.endswith('.image') for p in initial) == 5 and len([p for p in initial if p.startswith('sources/') and p.endswith('source.gscp')]) == 2,
                   'backing retirement steady physical inventory')
            previous = promise['basisId']
        capture.match(root/'reopened', initial, dirs, 'retirement reopen')
        expected_receipt = dict(schema='gse-v53-context-backing-retirement-v1',status='PASS',rounds=list(ROUNDS),peakImages=7,steadyImages=6,freshProcesses=False,runtimeEnabled=False)
    e.need(receipt == expected_receipt, 'backing retirement receipt scope')
    return dict(status='PASS', cases=len(CUTS) if matrix else len(ROUNDS), originalFirst=True,
                freshProcesses=False, runtimeEnabled=False, selectedInstallEnabled=False, peakImageFiles=6,
                steadyImageFiles=5, reservedCompletionImages=1, historicalBootstrap='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); matrix = (root/'initial').exists(); negatives = []
    exact = 'backing retirement exact recovered deletion' if matrix else 'backing retirement exact deletion'
    variants = {'bad-original': 'context checksum', 'missing': 'backing retirement evidence inventory',
                'context': exact, 'vote': exact, 'installed-source': exact, 'newest-source': exact,
                'journal': exact, 'floor': exact, 'kept-source': exact,
                'order': 'backing retirement first force order' if matrix else 'backing retirement deletion force order',
                'ack': 'context source old acknowledgement', 'scope': 'backing retirement receipt scope',
                'link': 'owner context linked/nonregular member'}
    if matrix: variants.update(first='backing retirement exact first interruption', second='backing retirement exact second interruption')
    else: variants.update(capture='context capture exact retirement capture', reopen='context capture exact retirement reopen')
    for name, reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-backing-retirement-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved)
            case=moved/CUTS[0] if matrix else moved/'round-23'; final=case/('final' if matrix else 'retired')
            before=moved/'initial' if matrix else case/'captured'
            if name=='bad-original':
                path=moved/'reference/original-retirement/initial/pending.context';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='missing':shutil.rmtree(case)
            elif name in ('context','vote','journal','floor'):
                (final/{'context':'pending.context','vote':'pending.accept','journal':'grants.gsr','floor':'floor-copies/floor.gsr'}[name]).write_bytes(b'changed')
            elif name in ('installed-source','newest-source'):
                segments,_,binding=e.decode((final/'pending.context').read_bytes());backing=e.f.decode(segments[3],'records','BASIS')['basisId']
                sources=[p for p in (final/'sources').iterdir() if p.name!=backing];target=final/'sources'/backing if name=='newest-source' else sources[0]
                (target/'source.gscp').unlink()
            elif name=='kept-source':
                old=next(p for p in (before/'sources').iterdir() if not (final/'sources'/p.name).exists());shutil.copytree(old,final/'sources'/old.name)
            elif name in ('order','ack'):
                path=case/'events.json';value=source.load(path,131072);trace=value['first'] if matrix else value
                if name=='order':trace.remove('SOURCE_RETIREMENT_CREATED')
                else:trace.append('ACCEPT_BEFORE_RETURN')
                path.write_bytes(e.f.canonical(value))
            elif name=='scope':
                path=moved/'receipt.json';value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            elif name=='link':
                path=final/'pending.context';path.unlink();path.symlink_to((root/'reference/reopened/pending.context').resolve())
            else:
                place=case/({'first':'crash','second':'recovery-crash','capture':'captured'}[name]) if name!='reopen' else moved/'reopened'
                (place/'pending.accept').write_bytes(b'changed')
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong backing retirement negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted backing retirement mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-backing-retirement-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'backing retirement portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
