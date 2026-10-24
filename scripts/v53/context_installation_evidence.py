"""Exact local slot reuse under a retained voting context and governing floor."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_selection_evidence as selection
from . import generation_install_evidence as install
from . import retirement_evidence as retirement

e, owner, source = selection.e, selection.owner, selection.source
NODES = selection.NODES


def initial(root):
    selection.publication.validate(root/'reference')
    original = selection.states(root/'reference/carried-snapshots/source-retired')
    observed = selection.states(root/'selected'); prepared = {}
    for node, (files, dirs) in original.items():
        frame, _ = selection.capture.new_promise(files, observed[node][0], 22)
        prepared[node] = selection.capture.transaction(files, dirs, frame)[-1][1:]
    raw_selected, selected = selection.decision(prepared, 22)
    bases = {n: e.decode(files['pending.context'])[0][3] for n, (files, _) in prepared.items()}
    installed = {}; plans = {}
    for node, (files, dirs) in selected.items():
        selection.capture.match(root/'selected'/node, files, dirs, 'installation selected')
        segments, _, binding = e.decode(files['pending.context']); basis = e.f.decode(bases[node], 'records', 'BASIS')
        prefix = 'sources/'+basis['basisId']+'/'
        packet_raw = files[prefix+'source.gscp']; packet = e.p.decode(packet_raw)
        vote, _ = e.votes(files['pending.accept'], packet['capsule']['cut'])
        members = {'promise.gsr': segments[2], 'basis.gsr': bases[node], 'selected.gsr': raw_selected,
            'selected-sources.gsr': b''.join(bases[n] for n in NODES), 'source.gscp': packet_raw,
            'owned-tail.gsr': vote['ACCEPT'], **{h+'.image': files[prefix+h+'.image'] for h in packet['images']}}
        selector, generation = selection.publication.carried.generation(members, packet['capsule'], node, 'a', binding['accept'])
        members['generation.gsr'] = generation['generations/a/generation.gsr']
        installed[node] = (dict(files, **{k:v for k,v in generation.items() if v is not None}, **{'selector.gsr':selector}), dirs|{'generations/a'})
        plans[node] = (members, selector)
    return selected, installed, plans


def accepted(files, dirs):
    _, current, packet = e.current(files)
    vote, values = e.votes(files['pending.accept'], packet['capsule']['cut'])
    ballot = e.f.decode(current['promise.gsr'], 'records', 'PROMISE')['ballot']
    new_accept = e.f.encode('records', 'ACCEPT', dict(values['ACCEPT'], ballot=ballot))
    raw = e.container([files['selector.gsr'], current['promise.gsr'], current['selected.gsr'], vote['ENTRY'], new_accept], vote['PAYLOAD'])
    return ({k:v for k,v in dict(files, **{'pending.accept':raw}).items() if k != 'pending.context' and not k.startswith('floor-copies/')},
            {d for d in dirs if d != 'floor-copies' and not d.startswith('floor-copies/')})


def install_steps(before, dirs, members, selector):
    events, writes = install.transaction(members); result = []
    for at, event in enumerate(events):
        files = dict(before); directories = set(dirs)
        if at >= 1: directories.add('generations/a')
        for name, index in writes.items():
            if at >= index: files['generations/a/'+name] = members[name]
        if at >= events.index('INSTALL_SELECTOR_RENAMED'): files['selector.gsr'] = selector
        elif at >= events.index('INSTALL_SELECTOR_WRITTEN'): files['selector.pending.gsr'] = selector
        result.append((event, files, directories))
    result += [(event, dict(result[-1][1]), set(result[-1][2])) for event in selection.CURRENT+['INSTALL_BEFORE_RETURN']]
    return result


def retirement_steps(files, dirs):
    original = {p.removeprefix('generations/b/'):v for p,v in files.items() if p.startswith('generations/b/')}
    context = e.decode(files['pending.context'])[2]
    record = e.f.encode('records', 'RETIREMENT', dict(root=context['root'], node=context['node'],
        floor=e.digest(files['floor-copies/floor.gsr']), selector=e.digest(files['selector.gsr']),
        files=[dict(path='generations/b/'+p, size=len(v), sha256=e.digest(v)) for p,v in sorted(original.items())]))
    state = selection.retirement.inventory(files, dirs)
    return state, original, record, retirement.transaction(state, original, record, slot='b')[0]


def validate(root):
    root = Path(root); receipt = source.load(root/'receipt.json'); schema = receipt.get('schema')
    cuts = install.CUTS if schema == 'gse-v53-context-installation-cuts-v1' else retirement.CUTS[:25] if schema == 'gse-v53-context-intermediate-retirement-v1' else None
    names = {'reference','selected','receipt.json'} | (set(cuts) if cuts else {'installed','retired','accepted'})
    if cuts == retirement.CUTS[:25]: names.add('installed')
    selection.layout(root, names, 'installation evidence')
    selected, installed, plans = initial(root)
    if not cuts:
        for name in ('installed','retired','accepted'): selection.states(root/name)
        for node, (files, dirs) in installed.items():
            selection.capture.match(root/'installed'/node, files, dirs, 'installation clean')
            retired = ({p:v for p,v in files.items() if not p.startswith('generations/b/')}, dirs-{'generations/b'})
            selection.capture.match(root/'retired'/node, *retired, 'installation retired intermediate')
            selection.capture.match(root/'accepted'/node, *accepted(*retired), 'installation successor')
        expected = dict(schema='gse-v53-context-installation-v1',status='PASS',nodes=3,installedBallot=22,originalVote=20,
                        intermediateBallot=21,freshProcesses=False,runtimeEnabled=False)
    else:
        is_retirement = cuts == retirement.CUTS[:25]
        before, dirs = installed['node-1'] if is_retirement else selected['node-1']
        prefix, full = selection.reseal(before)
        opening = selection.CURRENT+full+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','OPEN_RETURNED']
        if is_retirement:
            selection.capture.match(root/'installed', before, dirs, 'installation before retirement')
            state, old, record, steps = retirement_steps(before, dirs)
        else: steps = install_steps(before, dirs, *plans['node-1'])
        for cut in cuts:
            row = root/cut
            selection.layout(row, {'crash','recovery-crash','final','events.json'} | ({'accepted'} if is_retirement else set()), 'installation cut')
            at = next(i for i, step in enumerate(steps) if step[0] == cut)
            first = steps[at][1]; final = steps[-1][1]
            if is_retirement:
                for name in ('crash','recovery-crash'):
                    e.need(source.state(row/name) == first, 'context installation exact retirement '+name)
                e.need(source.state(row/'final') == final, 'context installation exact retired inventory')
                retired = ({p:v for p,v in before.items() if not p.startswith('generations/b/')}, dirs-{'generations/b'})
                selection.capture.match(row/'accepted', *accepted(*retired), 'installation retirement successor')
                resumed_steps = retirement.transaction(first, old, record, slot='b')[0]
                resume = opening+[step[0] for step in resumed_steps]+['EXPLICIT_RETIRE_RETURNED']+full
            else:
                for name in ('crash','recovery-crash'):
                    selection.capture.match(row/name, first, steps[at][2], 'installation '+name)
                selection.capture.match(row/'final', final, steps[-1][2], 'installation explicit return')
                persisted = at >= next(i for i, step in enumerate(steps) if step[0] == 'INSTALL_SELECTOR_RENAMED')
                resume = opening+([] if persisted else [step[0] for step in steps])+['EXPLICIT_INSTALL_RETURNED']*2+full
            trace = source.load(row/'events.json', 131072); e.exact(trace, 'first recovery resume')
            e.need(trace['first'] == [step[0] for step in steps[:at+1]], 'context installation first force order')
            e.need(trace['recovery'] == selection.CURRENT+prefix, 'context installation second force order')
            e.need(trace['resume'] == resume, 'context installation explicit completion order')
        expected = dict(schema=schema,status='PASS',cuts=list(cuts),interruptions='injected-IOException',freshProcesses=False,runtimeEnabled=False)
    e.need(receipt == expected, 'context installation receipt scope')
    return dict(status='PASS',cases=len(cuts) if cuts else 3,originalFirst=True,originalVote=20,installedBallot=22,
                freshProcesses=False,runtimeEnabled=False,powerLoss=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    schema = source.load(root/'receipt.json')['schema']
    cut = install.CUTS[0] if schema.endswith('installation-cuts-v1') else retirement.CUTS[0] if schema.endswith('intermediate-retirement-v1') else None
    variants = ('original','missing','selected','context','vote','selector','floor','source','first','second','return','scope')
    variants += ('first-state','second-state') if cut else ('retired','accepted')
    if schema.endswith('intermediate-retirement-v1'): variants += ('accepted',)
    for name in variants:
        if not cut and name in ('first','second','return'): continue
        with tempfile.TemporaryDirectory(prefix='v53-context-install-negative-') as tmp:
            moved = Path(tmp)/'evidence'; shutil.copytree(root,moved); final = moved/cut/'final' if cut else moved/'installed/node-1'
            final_reason = 'context installation exact retired inventory' if schema.endswith('intermediate-retirement-v1') else 'context capture exact installation '+('explicit return' if cut else 'clean')
            reason = final_reason
            if name == 'original':
                (moved/'reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed');reason='context publication exact source-retired: node-1'
            elif name == 'missing':
                shutil.rmtree(moved/cut if cut else moved/'installed');reason='context selection installation evidence inventory'
            elif name == 'selected':
                (moved/'selected/node-1/pending.accept').write_bytes(b'changed');reason='context capture exact installation selected'
            elif name in ('context','vote','selector','floor'):
                (final/{'context':'pending.context','vote':'pending.accept','selector':'selector.gsr','floor':'floor-copies/floor.gsr'}[name]).write_bytes(b'changed')
            elif name == 'source': next((final/'sources').rglob('source.gscp')).unlink()
            elif name in ('first-state','second-state'):
                stage = 'crash' if name == 'first-state' else 'recovery-crash'
                (moved/cut/stage/'pending.accept').write_bytes(b'changed')
                reason = ('context installation exact retirement ' if schema.endswith('intermediate-retirement-v1') else 'context capture exact installation ')+stage
            elif name in ('retired','accepted'):
                path = moved/cut/'accepted' if cut else moved/name/'node-1'
                (path/'pending.accept').write_bytes(b'changed')
                reason = 'context capture exact installation '+('retirement successor' if cut else 'successor' if name == 'accepted' else 'retired intermediate')
            elif name == 'scope':
                path=moved/'receipt.json';value=source.load(path);value['runtimeEnabled']=True;path.write_bytes(e.f.canonical(value));reason='context installation receipt scope'
            else:
                path=moved/cut/'events.json';value=source.load(path,131072);value[{'first':'first','second':'recovery','return':'resume'}[name]].insert(0,'INSTALL_BEFORE_RETURN');path.write_bytes(e.f.canonical(value))
                reason='context installation '+{'first':'first force order','second':'second force order','return':'explicit completion order'}[name]
            try: validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong context installation negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else: raise ValueError('accepted context installation mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-context-install-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'context installation portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
