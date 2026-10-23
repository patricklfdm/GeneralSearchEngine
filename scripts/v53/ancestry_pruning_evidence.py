"""Six-to-one original-first pruning replay. Earlier six bridges are conditional history.

Current votes, peer ends, member force order, whole inventories and preserved old
authority are checked. This does not infer public bootstrap or power-loss safety.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import parent_checkpoint_evidence as parent
from . import selected_sources_evidence as sources
from .journal_publication_evidence import steps
from .journal_application_evidence import inventory
from .applied_end_evidence import read, digest
from . import format_fixture as f
from . import source_packet as p
from .membership_model import need

CUTS = ('SELECTED_SOURCES_WRITTEN', 'SELECTED_SOURCES_FORCED', 'PUBLICATION_SELECTOR_FORCED',
        'COVERED_END_FILE_DELETED', 'COVERED_VOTE_PREFIX_WRITTEN')


def frames(raw):
    result = []; offset = 0
    need(0 < len(raw) <= 6*16*1024, 'pruning ancestry bound')
    while offset < len(raw):
        need(len(raw)-offset >= 48, 'pruning partial frame')
        size = 48+int.from_bytes(raw[offset+12:offset+16], 'big')
        need(48 < size <= 16384 and size <= len(raw)-offset, 'pruning frame size')
        result.append(raw[offset:offset+size]); offset += size
    return result


def original_sources(root, original, cap, before, observations):
    """Bind every original selected frame and all six conditional bridge groups.

Verify original manifests as well as unchanged storage copies; final output never
chooses which old bridge or original source is considered required.
"""
    selected = f.decode(original['generations/b/selected.gsr'], 'records', 'SELECTED', cap['root'])
    retained = sources.retained(original, 'generations/b/')
    need(set(retained) == {sources.FILE} and sources.cuts(retained[sources.FILE], selected) == [cap['cut']]*3,
         'pruning entire original selected set at eight')
    raw = original['generations/b/ancestry.gsr']; parts = frames(raw)
    need(len(parts) == 24, 'pruning exactly six old groups')
    identities = {v['node']: v['storage'] for v in before['identities'] if v['node'] in cap['cut']['view']['old']}
    need(sorted(identities) == ['node-1', 'node-2', 'node-3'], 'pruning original voters')
    for i in range(6):
        statement = parts[i*4]; value = f.decode(statement, 'records', 'CHECKPOINT', cap['root'])
        need(value['scope'] == 'RANGE' and value['start']['index'] == i+1 and value['start']['view'] == cap['cut']['view']
             and value['end'] == cap['cut'] and value['catalogAfter'] == cap['catalog']
             and value['applicationBefore'] == value['applicationAfter'] == cap['application'], 'pruning old bridge endpoints')
        for n, ack in zip(sorted(identities), parts[i*4+1:i*4+4]):
            expected = dict(root=cap['root'], voter=n, incarnation=identities[n], cut=cap['cut'], statement=digest(statement))
            need(f.decode(ack, 'records', 'CHECKPOINT_ACK', cap['root']) == expected, 'pruning old endorsement binding')
            need(dict(voter=n, storage=identities[n], record=digest(ack), parent=digest(f.canonical(cap['cut']))) in observations['historical'], 'pruning conditional observation binding')
    originals = []
    for n in sorted(identities):
        physical = original if n == 'node-1' else inventory(root/n)
        need(sources.retained(physical, 'generations/b/') == retained and physical['generations/b/ancestry.gsr'] == raw, 'pruning peer original ancestry and sources')
        manifest = f.decode(physical['generations/b/generation.gsr'], 'records', 'GENERATION', cap['root'])
        actual = {k.removeprefix('generations/b/'): v for k, v in physical.items() if k.startswith('generations/b/') and k != 'generations/b/generation.gsr'}
        need(manifest['files'] == [dict(path=k, size=len(v), sha256=digest(v)) for k, v in sorted(actual.items())], 'pruning exact original inventory')
        basis = physical['generations/b/basis.gsr']; basis_value = f.decode(basis, 'records', 'BASIS', cap['root']); originals.append(basis)
        packet = p.decode(physical['sources/'+basis_value['basisId']+'/source.gscp']); p.bind(packet, basis)
        need(basis_value['voter'] == n and packet['capsule']['cut'] == cap['cut'], 'pruning original source binding')
        for h, size in packet['images'].items():
            image = physical['sources/'+basis_value['basisId']+'/'+h+'.image']; need(len(image) == size and digest(image) == h, 'pruning original source image')
    need(b''.join(originals) == retained[sources.FILE], 'pruning exact original voter frames')


def publication_steps(original, files, selector):
    members = sorted(n for n in files if n != 'generation.gsr' and not n.endswith('.image')); counts = {}
    for event, state in steps(original, files, selector):
        yield event, state
        if event in ('INSTALL_MEMBER_WRITTEN', 'INSTALL_MEMBER_FORCED'):
            count = counts.get(event, 0); counts[event] = count+1
            if members[count] == sources.FILE: yield event.replace('INSTALL_MEMBER', 'SELECTED_SOURCES'), state


def validate_case(root, row):
    root = Path(root); current = inventory(root/'original'); files, selector, end = parent.original_plan(root, current, pruning=True)
    need(len(frames(files['ancestry.gsr'])) == 3 and files[sources.FILE] == current['generations/b/'+sources.FILE], 'pruning exact one-group output')
    recovery = 'INSTALL_IMAGE_WRITTEN' if row['cut'].startswith('SELECTED_SOURCES_') else 'COVERED_VOTE_CANDIDATE_FORCED'
    parent.replay_case(root, row, current, files, selector, end, 9, recovery, publication_steps)


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); pairs = [(m, c) for m in ('halt', 'kill') for c in CUTS]
    need(receipt['execution'] == 'private-ancestry-pruning-publication' and receipt['expectedCases'] == 10 and receipt['freshJvms'] == 30
         and receipt['historicalAuthority'] == 'conditional-fixture' and receipt['currentObservations'] == 'actual-local-votes-and-ends'
         and receipt['selectorPublication'] is True and receipt['powerLoss'] is False, 'pruning qualification scope')
    need([(r['mode'], r['cut']) for r in receipt['cases']] == pairs and {p.name for p in root.iterdir()} == {'receipt.json'} | {m+'-'+c for m, c in pairs}, 'pruning complete matrix')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row)
    return dict(status='PASS', cases=10, freshJvms=30, originalGroups=6, publishedGroups=1, originalSources=[8, 8, 8], publishedEnd=9, earlierAuthority='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); row = json.loads(read(root/'receipt.json'))['cases'][0]; source = root/(row['mode']+'-'+row['cut']); rejected = []
    variants = ('missing-original-selected-sources', 'missing-remote-source', 'changed-old-ancestry', 'missing-historical-observation',
                'missing-current-vote', 'false-current-observation', 'changed-barrier-image', 'missing-source-force',
                'early-selector', 'early-vote-clear', 'old-groups-in-new-generation', 'changed-coverage', 'missing-final-originals', 'old-ancestry-deleted')
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-pruning-negative-') as temp:
            case = Path(temp)/'case'; shutil.copytree(source, case)
            if variant == 'missing-original-selected-sources': (case/'original/generations/b'/sources.FILE).unlink()
            elif variant == 'missing-remote-source': (case/'node-2/generations/b/basis.gsr').unlink()
            elif variant == 'changed-old-ancestry': (case/'original/generations/b/ancestry.gsr').write_bytes(b'')
            elif variant in ('missing-historical-observation', 'false-current-observation'):
                path = case/'observations.json'; data = json.loads(read(path)); data['historical' if variant.startswith('missing') else 'parents'] = []; path.write_bytes(f.canonical(data))
            elif variant == 'missing-current-vote': (case/'node-2/pending.accept').unlink()
            elif variant == 'changed-barrier-image': (case/'node-2/applied-end/application.image').write_bytes(b'changed')
            elif variant == 'missing-source-force':
                path = case/'resume.stdout'; rows = [json.loads(line) for line in read(path, 2*1024*1024).splitlines()]
                at = next(i for i, r in enumerate(rows) if r.get('event') == 'SELECTED_SOURCES_FORCED'); need(rows[at-1] == dict(event='INSTALL_MEMBER_FORCED'), 'negative source force adjacency')
                del rows[at-1]; path.write_bytes(b''.join(f.canonical(r)+b'\n' for r in rows))
            elif variant == 'early-selector': (case/'crash/selector.gsr').write_bytes(read(case/'final/selector.gsr'))
            elif variant == 'early-vote-clear': (case/'crash/pending.accept').write_bytes(parent.EMPTY)
            elif variant == 'old-groups-in-new-generation': (case/'final/generations/a/ancestry.gsr').write_bytes(read(case/'original/generations/b/ancestry.gsr'))
            elif variant == 'changed-coverage': (case/'final/generations/a'/parent.COVERAGE).write_bytes(b'{}')
            elif variant == 'missing-final-originals': (case/'final/generations/a'/sources.FILE).unlink()
            else: (case/'final/generations/b/ancestry.gsr').unlink()
            try: validate_case(case, row)
            except (ValueError, OSError, KeyError, TypeError): rejected.append(variant)
            else: raise ValueError('accepted pruning mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-pruning-portable-') as temp:
        dest = Path(temp)/'evidence'; shutil.copytree(root, dest); need(validate(dest) == result, 'pruning portable replay')
    return dict(result, negatives=rejected, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
