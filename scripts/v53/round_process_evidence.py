"""Independent original-first phase/publication/repeated-process recovery replay.

The seed has real local votes and ends after a conditional bootstrap. Derive the
third-slot candidate before inspecting any crashed/final candidate; simulate exact
prefixes, selector switching and covered-only deletions. No power-loss/READY claim.
"""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import format_fixture as f
from .applied_end_evidence import read, digest
from .journal_application_evidence import inventory
from .journal_publication_evidence import steps, EMPTY, COVERAGE
from .published_generation_evidence import OPEN
from .parent_checkpoint_evidence import application
from .round_storage_evidence import original_slot, project_slot, current, votes, NODES
from .membership_model import need

CUTS = (
    ('ACCEPT_PREFIX_WRITTEN', 'ACCEPT_CANDIDATE_FORCED'),
    ('PROOF_PREFIX_WRITTEN', 'PROOF_CANDIDATE_FORCED'),
    ('CERTIFICATE_PREFIX_WRITTEN', 'CERTIFICATE_CANDIDATE_FORCED'),
    ('APPLY_ANCESTOR_0_ACK_PREFIX_WRITTEN', 'APPLY_ANCESTOR_0_ACK_FORCED'),
    ('ROUND_COVERAGE_WRITTEN', 'ROUND_COVERAGE_FORCED'),
    ('ROUND_COVERAGE_FORCED', 'INSTALL_GENERATION_FORCED'),
    ('INSTALL_SELECTOR_RENAMED', 'COVERED_VOTE_CANDIDATE_FORCED'),
    ('PUBLICATION_SELECTOR_FORCED', 'COVERED_END_FILE_DELETED'),
    ('COVERED_END_FILE_DELETED', 'COVERED_VOTE_PREFIX_WRITTEN'),
    ('COVERED_VOTE_PREFIX_WRITTEN', 'COVERED_VOTE_CANDIDATE_FORCED'),
    ('COVERED_VOTE_RENAMED', 'ACCEPT_ACTIVE_FORCED'))
PHASES = ('ACCEPT', 'PROOF', 'CERTIFICATE')


def seed_plan(seed):
    first, previous = original_slot(seed, 1, None, None)
    first, previous = original_slot(seed, 2, first, previous)
    _, published, ends = project_slot(seed, 3, first, previous)
    original = previous['node-1']; pref, _, cap = current(original)
    full = inventory(seed/'originals/slot-3/node-1'); frames, _ = votes(full['pending.accept'], cap['capsule']['cut'])
    bodies = {}; body = b''.join(frames[k] for k in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT')) + struct.pack('>I', len(frames['PAYLOAD']))+frames['PAYLOAD']
    for phase in PHASES:
        if phase != 'ACCEPT': body += frames[phase]
        bodies[phase] = struct.pack('>4sHHI', b'GSPV', 1, 3, len(body)+12)+body
    need(bodies['CERTIFICATE'] == full['pending.accept'], 'round process original request framing')
    need({k: v for k, v in full.items() if k not in ('pending.accept', 'applied-end') and not k.startswith('applied-end/')} ==
         {k: v for k, v in original.items() if k != 'pending.accept'}, 'round process original request parent')
    observed = json.loads(read(seed/'observations.json')); need(set(observed) == {'all', 'accepts', 'proofs'}, 'round process observation inventory')
    def normalized(rows):
        values = [f.canonical(v) for v in rows]; need(len(set(values)) == len(values), 'round duplicate observations'); return set(values)
    expected = set(); phases = {'accepts': [], 'proofs': []}
    for slot in (1, 2, 3):
        for node in NODES:
            physical = inventory(seed/'originals'/('slot-'+str(slot))/node); _, _, packet = current(physical)
            own, _ = votes(physical['pending.accept'], packet['capsule']['cut']); identity = f.decode(physical['node.gsr'], 'records', 'NODE')['identity']
            for label, phase in (('accepts', 'ACCEPT'), ('proofs', 'PROOF')):
                value = dict(voter=node, storage=identity['storage'], record=digest(own[phase]), parent=digest(f.canonical(packet['capsule']['cut'])))
                expected.add(f.canonical(value))
                if slot == 3: phases[label].append(value)
            for name, raw in physical.items():
                if name.startswith('applied-end/') and (name.endswith('-ack.gsr') or name == 'applied-end/ack.gsr'):
                    ack = f.decode(raw, 'records', 'CHECKPOINT_ACK')
                    expected.add(f.canonical(dict(voter=node, storage=identity['storage'], record=digest(raw), parent=digest(f.canonical(ack['cut'])))))
    need(normalized(observed['all']) == expected and all(normalized(observed[k]) == normalized(v) for k, v in phases.items()), 'round physical observation provenance')
    for n in NODES: need(inventory(seed/n) == inventory(seed/'originals/slot-3'/n), 'round retained seed owners unchanged')
    selector = published['node-1']['selector.gsr']; target = 'generations/'+f.decode(selector, 'records', 'SELECTOR')['generation']+'/'
    need(target == 'generations/a/' and pref == 'generations/b/', 'round expected alternating generation')
    files = {k.removeprefix(target): v for k, v in published['node-1'].items() if k.startswith(target)}
    return original, bodies, files, selector, ends['node-1']


def publication_steps(original, files, selector):
    members = sorted(n for n in files if n != 'generation.gsr' and not n.endswith('.image')); counts = {}
    for event, state in steps(original, files, selector):
        yield event, state
        if event in ('INSTALL_MEMBER_WRITTEN', 'INSTALL_MEMBER_FORCED'):
            count = counts.get(event, 0); counts[event] = count+1
            if members[count] == COVERAGE: yield event.replace('INSTALL_MEMBER', 'ROUND_COVERAGE'), state


def simulate(original, bodies, files, selector, end, stop):
    state = dict(original); events = []
    class Stopped(Exception): pass
    def event(name):
        events.append(name)
        if name == stop: raise Stopped
    def replace(phase):
        desired = bodies[phase]
        if 'pending.accept.next' not in state:
            state['pending.accept.next'] = b''; event(phase+'_CANDIDATE_CREATED')
        old = state['pending.accept.next']; need(desired.startswith(old), 'round exact interrupted phase prefix')
        state['pending.accept.next'] = desired[:len(old)+(len(desired)-len(old))//2]; event(phase+'_PREFIX_WRITTEN')
        state['pending.accept.next'] = desired
        for suffix in ('CANDIDATE_WRITTEN', 'CANDIDATE_FORCED', 'CANDIDATE_PARENT_FORCED'): event(phase+'_'+suffix)
        state['pending.accept'] = state.pop('pending.accept.next'); event(phase+'_RENAMED'); event(phase+'_PARENT_FORCED')
    def phase():
        if state['pending.accept'] == EMPTY: return None
        match = [p for p in PHASES if bodies[p] == state['pending.accept']]; need(len(match) == 1, 'round original active vote'); return match[0]
    try:
        if state['selector.gsr'] != selector:
            for e in OPEN: event(e)
            candidate = state.get('pending.accept.next')
            complete = next((p for p in PHASES if bodies[p] == candidate), None)
            if complete:
                event(complete+'_RECOVERY_VALIDATED'); replace(complete)
            active = phase() or 'ACCEPT'; event(active+'_ACTIVE_FORCED'); event(active+'_ACTIVE_PARENT_FORCED')
            for proposed in PHASES:
                active = phase()
                if active is None or PHASES.index(active) < PHASES.index(proposed):
                    event(proposed+'_VALIDATED'); replace(proposed); event(proposed+'_BEFORE_RETURN')
            staged = {k.removeprefix('applied-end/'): v for k, v in state.items() if k.startswith('applied-end/')}
            staged, exists, applied = application(end, staged, 'applied-end' in state, stop if stop and stop.startswith('APPLY_') else None)
            state = {k: v for k, v in state.items() if k != 'applied-end' and not k.startswith('applied-end/')}
            if exists: state['applied-end'] = None
            state.update({'applied-end/'+k: v for k, v in staged.items()})
            for row in applied: event(row['event'])
            # OPEN and the certificate seal already occurred before the application.
            for index, (e, physical) in enumerate(publication_steps(state, files, selector)):
                if index < len(OPEN)+2: continue
                state = physical; event(e)
        else:
            for e, physical in publication_steps(state, files, selector): state = physical; event(e)
    except Stopped: pass
    need(stop is None or events[-1] == stop, 'round process missing stop')
    return events, state


def validate_case(root, row, plan):
    original, bodies, files, selector, end = plan
    need(inventory(root/'original') == original and row['status'] == 'PASS' and row['manifest'] == digest(files['generation.gsr'])
         and (row['cut'], row['recoveryCut']) in CUTS and row['mode'] in ('halt', 'kill'), 'round process original/case identity')
    state = original
    for label, stop, snapshot, mode in (('fault', row['cut'], 'crash', row['mode']), ('recovery-fault', row['recoveryCut'], 'recovery-crash', 'halt'),
                                        ('resume', None, 'final', None), ('duplicate', None, 'node-1', None)):
        need(read(root/(label+'.stderr')) == b'', 'round process stderr')
        rows = [json.loads(raw) for raw in read(root/(label+'.stdout'), 2*1024*1024).splitlines()]; names = [r.get('event', '') for r in rows]
        expected, resulting = simulate(state, bodies, files, selector, end, stop)
        actual = [e for e in names if e.startswith(('CURRENT_', 'ACCEPT_', 'PROOF_', 'CERTIFICATE_', 'APPLY_', 'INSTALL_', 'ROUND_COVERAGE_', 'PUBLICATION_', 'COVERED_')) or e == 'FLOOR_COPY_BEFORE_RETURN']
        need(actual == expected, 'round exact phase/force/deletion order: '+label+'; actual='+str(actual)+'; expected='+str(expected))
        if any(e.startswith('APPLY_') for e in expected):
            need(names.index('APPLICATION_AUTHORITY_VALIDATED') < names.index('REPLAY_BEFORE_RETURN') < names.index('APPLY_VALIDATED'), 'round real replay before end')
            seals = [i for i, e in enumerate(names) if e in ('CERTIFICATE_ACTIVE_PARENT_FORCED', 'CERTIFICATE_PARENT_FORCED')]
            need(seals and max(seals) < names.index('APPLICATION_AUTHORITY_VALIDATED'), 'round forced original certificate before application')
            if 'PUBLICATION_VALIDATED' in expected: need(names.index('APPLY_BEFORE_RETURN') < names.index('PUBLICATION_VALIDATED'), 'round force before selector')
        elif state['selector.gsr'] == selector: need(not any(e.startswith(('APPLY_', 'REPLAY_')) for e in names), 'round covered recovery must not reapply')
        if mode is None:
            need(rows[-1] == dict(status='PASS', manifest=row['manifest'], selectedIndex=3, journalPublication=True) and sum('status' in r for r in rows) == 1, 'round process exact receipt')
        else:
            need(not any('status' in r for r in rows) and rows[-1] == (dict(event='AWAITING_KILL', cut=stop) if mode == 'kill' else dict(event=stop)), 'round premature success/wrong crash')
        need(inventory(root/snapshot) == resulting and sum(n.endswith('.image') for n in resulting) <= 7, 'round exact surviving bytes: '+label)
        state = resulting
    need(state['pending.accept'] == EMPTY and 'applied-end' not in state, 'round covered cleanup complete')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); pairs = [(m, c, r) for m in ('halt', 'kill') for c, r in CUTS]
    need(receipt['execution'] == 'private-same-round-process' and receipt['expectedCases'] == 22 and receipt['freshJvms'] == 88
         and receipt['historicalBootstrap'] == 'conditional-fixture' and receipt['runtimeEnabled'] is False and receipt['powerLoss'] is False, 'round process scope')
    need([(v['mode'], v['cut'], v['recoveryCut']) for v in receipt['cases']] == pairs
         and {v.name for v in root.iterdir()} == {'receipt.json', 'seed'} | {m+'-'+c for m, c, _ in pairs}, 'round complete process matrix')
    plan = seed_plan(root/'seed')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row, plan)
    return dict(status='PASS', cases=22, freshJvms=88, repeatedCrashes=22, currentSlot=3, originalSelectedCut=0,
                exactPhasePrefixes=True, originalFirst=True, portableInputs=True, runtimeEnabled=False, powerLoss=False)


def qualify(root):
    root = Path(root); result = validate(root); row = json.loads(read(root/'receipt.json'))['cases'][0]; negatives = []
    for variant in ('missing-first-vote', 'missing-original-selection', 'false-observation', 'changed-current-payload', 'missing-ancestor-ack',
                    'missing-phase-force', 'missing-coverage-force', 'early-selector', 'early-vote-clear', 'changed-first-coverage', 'old-generation-deleted', 'changed-prefix', 'false-crash-cut'):
        with tempfile.TemporaryDirectory(prefix='v53-round-process-negative-') as tmp:
            case = Path(tmp)/'evidence'; shutil.copytree(root, case); seed = case/'seed'; work = case/(row['mode']+'-'+row['cut'])
            if variant == 'missing-first-vote': (seed/'originals/slot-1/node-2/pending.accept').write_bytes(EMPTY)
            elif variant == 'missing-original-selection': (seed/'originals/slot-3/node-3/generations/b/selected-sources.gsr').unlink()
            elif variant == 'false-observation':
                path = seed/'observations.json'; data = json.loads(read(path)); data['all'] = []; path.write_bytes(f.canonical(data))
            elif variant == 'changed-current-payload':
                path = seed/'originals/slot-3/node-3'; physical = inventory(path); _, _, packet = current(physical)
                frames, _ = votes(physical['pending.accept'], packet['capsule']['cut'])
                raw = bytearray(physical['pending.accept']); at = 16+sum(len(frames[k]) for k in ('SELECTOR', 'PROMISE', 'SELECTED', 'ENTRY', 'ACCEPT')); raw[at] ^= 1
                (path/'pending.accept').write_bytes(raw)
            elif variant == 'missing-ancestor-ack': (seed/'originals/slot-3/node-2/applied-end/ancestor-0-ack.gsr').unlink()
            elif variant in ('missing-phase-force', 'missing-coverage-force'):
                path = work/'resume.stdout'; rows = [json.loads(v) for v in read(path).splitlines()]; target = 'CERTIFICATE_CANDIDATE_FORCED' if variant == 'missing-phase-force' else 'ROUND_COVERAGE_FORCED'
                at = next(i for i, v in enumerate(rows) if v.get('event') == target)
                if variant == 'missing-coverage-force':
                    need(rows[at-1] == dict(event='INSTALL_MEMBER_FORCED'), 'round coverage force adjacency'); at -= 1
                del rows[at]; path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in rows))
            elif variant == 'early-selector': (work/'crash/selector.gsr').write_bytes(read(work/'final/selector.gsr'))
            elif variant == 'early-vote-clear': (case/'halt-CERTIFICATE_PREFIX_WRITTEN/crash/pending.accept').write_bytes(EMPTY)
            elif variant == 'changed-first-coverage': (work/'final/generations/a'/COVERAGE).write_bytes(b'{}')
            elif variant == 'old-generation-deleted': shutil.rmtree(work/'final/generations/b')
            elif variant == 'changed-prefix': (work/'crash/pending.accept.next').write_bytes(b'changed')
            else:
                path = work/'fault.stdout'; rows = [json.loads(v) for v in read(path).splitlines()]; rows[-1]['event'] = 'ACCEPT_CANDIDATE_FORCED'; path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in rows))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted round process mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-round-process-portable-') as tmp:
        case = Path(tmp)/'evidence'; shutil.copytree(root, case); need(validate(case) == result, 'round process portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
