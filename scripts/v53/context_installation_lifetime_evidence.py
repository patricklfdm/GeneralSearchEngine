"""Independent inventory replay of repeated context installations and source reclamation.

Every generation is derived from the preceding actual three-owner capture. This
qualifies local storage using a conditional historical bootstrap, not a network
installation or a full-capacity workload.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_installation_evidence as installation

selection = installation.selection
e, owner, source = selection.e, selection.owner, selection.source
ROUNDS = tuple(range(22, 28))


def install(group, selected):
    bases = {n: e.decode(files['pending.context'])[0][3] for n, (files, _) in group.items()}
    result = {}
    for node, (files, dirs) in group.items():
        segments, _, binding = e.decode(files['pending.context'])
        basis = e.f.decode(bases[node], 'records', 'BASIS'); prefix = 'sources/'+basis['basisId']+'/'
        current = e.f.decode(files['selector.gsr'], 'records', 'SELECTOR')
        slot = 'b' if current['generation'] == 'a' else 'a'
        e.need('generations/'+slot not in dirs, 'installation lifetime occupied destination')
        packet_raw = files[prefix+'source.gscp']; packet = e.p.decode(packet_raw)
        vote, _ = e.votes(files['pending.accept'], packet['capsule']['cut'])
        members = {'promise.gsr': segments[2], 'basis.gsr': bases[node], 'selected.gsr': selected,
            'selected-sources.gsr': b''.join(bases[n] for n in selection.NODES), 'source.gscp': packet_raw,
            'owned-tail.gsr': vote['ACCEPT'], **{h+'.image': files[prefix+h+'.image'] for h in packet['images']}}
        selector, generation = selection.publication.carried.generation(members, packet['capsule'], node, slot, binding['accept'])
        result[node] = (dict(files, **{k:v for k,v in generation.items() if v is not None}, **{'selector.gsr':selector}), dirs|{'generations/'+slot})
    return result


def retire_generation(files, dirs):
    current = e.f.decode(files['selector.gsr'], 'records', 'SELECTOR')
    old = 'generations/'+('b' if current['generation'] == 'a' else 'a')
    e.need(old in dirs, 'installation lifetime absent predecessor')
    return {p:v for p,v in files.items() if not p.startswith(old+'/')}, dirs-{old}


def check_group(path, group, label):
    selection.states(path)
    for node, state in group.items(): selection.capture.match(path/node, *state, 'installation lifetime '+label)


def validate_lifetime(root):
    selection.publication.validate(root/'reference')
    current = selection.states(root/'reference/carried-snapshots/source-retired')
    for counter in ROUNDS:
        row = root/f'round-{counter}'
        prior = {n: e.f.decode(e.decode(files['pending.context'])[0][3], 'records', 'BASIS')['basisId'] for n,(files,_) in current.items()}
        captured = selection.captured(current, row/'captured', counter)
        selected_raw, selected = selection.decision(captured, counter)
        check_group(row/'selected', selected, 'selection')
        installed = install(selected, selected_raw); check_group(row/'installed', installed, 'install')
        retired = {n:retire_generation(*state) for n,state in installed.items()}
        check_group(row/'generation-retired', retired, 'generation retirement')
        for node,(files,dirs) in retired.items():
            final = selection.retirement.retirement(files,dirs,prior[node])[2][-1][1] if counter>22 else selection.retirement.inventory(files,dirs)
            e.need(source.state(row/'source-retired'/node)==final, 'installation lifetime source retirement')
        current=selection.states(row/'source-retired')
        for files,_ in current.values():
            e.need(sum(p.endswith('.image') for p in files)==5 and sum(p.startswith('sources/') and p.endswith('source.gscp') for p in files)==2,
                   'installation lifetime steady inventory')
    check_group(root/'accepted', {n:installation.accepted(*state) for n,state in current.items()}, 'successor')
    return dict(status='PASS', rounds=list(ROUNDS), owners=3, originalVote=20, finalBallot=27,
                originalFirst=True, historicalBootstrap='conditional-fixture', freshProcesses=False,
                runtimeEnabled=False, powerLoss=False, maximalCapacity=False)


def validate(root):
    root=Path(root); receipt=source.load(root/'receipt.json')
    selection.layout(root, {'reference','receipt.json','accepted',*(f'round-{n}' for n in ROUNDS)}, 'installation lifetime')
    for counter in ROUNDS:
        selection.layout(root/f'round-{counter}', {'captured','selected','installed','generation-retired','source-retired'}, 'installation lifetime round')
    result=validate_lifetime(root)
    e.need(receipt==dict(schema='gse-v53-context-installation-lifetime-v1',status='PASS',rounds=list(ROUNDS),
                        nodes=3,originalVote=20,floorBallot=21,freshProcesses=False,runtimeEnabled=False), 'installation lifetime scope')
    return result


def qualify(root):
    root=Path(root);result=validate(root); negatives=[]
    variants={'original':'context publication exact source-retired: node-1',
              'missing':'context selection installation lifetime inventory',
              'capture':'context capture exact selection capture',
              'selected':'context capture exact installation lifetime selection',
              'installed':'context capture exact installation lifetime install',
              'generation':'context capture exact installation lifetime generation retirement',
              'context':'installation lifetime source retirement','vote':'installation lifetime source retirement',
              'floor':'installation lifetime source retirement','journal':'installation lifetime source retirement',
              'kept-source':'installation lifetime source retirement','latest-source':'installation lifetime source retirement',
              'accepted':'context capture exact installation lifetime successor',
              'scope':'installation lifetime scope','linked':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-installation-lifetime-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);row=moved/'round-23';node=row/'source-retired/node-1'
            if name=='original':(moved/'reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(moved/'round-27')
            elif name in ('capture','selected','installed','generation','accepted'):
                path=moved/'accepted/node-1' if name=='accepted' else row/{'capture':'captured','selected':'selected','installed':'installed','generation':'generation-retired'}[name]/'node-1'
                (path/'pending.accept').write_bytes(b'changed')
            elif name in ('context','vote','floor','journal'):
                (node/{'context':'pending.context','vote':'pending.accept','floor':'floor-copies/floor.gsr','journal':'grants.gsr'}[name]).write_bytes(b'changed')
            elif name=='kept-source':
                old=next(p for p in (row/'generation-retired/node-1/sources').iterdir() if not (node/'sources'/p.name).exists())
                shutil.copytree(old,node/'sources'/old.name)
            elif name=='latest-source':
                basis=e.f.decode(e.decode((node/'pending.context').read_bytes())[0][3],'records','BASIS')
                (node/'sources'/basis['basisId']/'source.gscp').unlink()
            elif name=='linked':
                path=node/'pending.context';path.unlink();path.symlink_to((root/'round-23/source-retired/node-1/pending.context').resolve())
            else:
                path=moved/'receipt.json';value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong installation lifetime negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted installation lifetime mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-installation-lifetime-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'installation lifetime portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
