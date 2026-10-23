"""Original-first unmarked PROMISE/damaged-prefix evidence; no repair or power-loss claim."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import format_fixture as f
from . import grant_evidence as g
from . import current_generation_evidence as current
from . import capture_journal_evidence as capture
from .journal_application_evidence import inventory
from .applied_end_evidence import read, digest
from .membership_model import need


def profiles():
    rows = [dict(size=size, through=through, mode=mode, cut='PROMISE_FORCED')
            for size in (3, 4, 5) for through in (0, 6, 7) for mode in ('halt', 'kill')]
    rows += [dict(size=3, through=1, mode=mode, cut=cut)
             for cut in ('PROMISE_BEFORE_WRITE', 'PROMISE_WRITTEN', 'DAMAGED_HEADER', 'DAMAGED_BODY') for mode in ('halt', 'kill')]
    return rows


def name(row): return f"{row['size']}-{row['through']}-{row['mode']}-{row['cut']}"


def output(root, row, label, events, terminal=None):
    need(read(root/(label+'.stderr')) == b'', 'promise unexpected stderr')
    rows = [json.loads(line) for line in read(root/(label+'.stdout'), 256*1024).splitlines()]
    expected = list(events) + ([] if terminal is None else [terminal])
    need(rows == expected, 'promise process events/receipt: '+label)
    code = (73 if row['profile']['mode'] == 'halt' else 137) if label == 'fault' else 0
    need(type(row['processes'][label]) is int and row['processes'][label] == code, 'promise child exit code')


def event_rows(events): return [dict(event=e) for e in events]


def validate_case(root, row):
    p = row['profile']; point = p['cut']; damaged = point.startswith('DAMAGED_'); untouched = point == 'PROMISE_BEFORE_WRITE'
    need(json.loads(read(root/'profile.json')) == p and row['status'] == 'PASS', 'promise profile binding')
    # Verify the original authority before consulting any resumed candidate.
    _, prior, generation, packet = current.current(root/'initial', p['size'])
    initial = inventory(root/'initial'); root_hash = initial['root.gsr'][16:48].hex()
    need(len(prior) == 1 and prior[0][0] == 'PROMISE' and prior[0][2]['ballot']['counter'] == 10
         and generation['cut']['index'] == p['through'] and generation['ownedTail'] is not None, 'promise original profile')
    vote = dict(prior[0][2]['ballot'], counter=20)
    crash = dict(initial); promise = None
    if not untouched:
        raw = read(root/'original-promise.gsr', 8192); promise = f.decode(raw, 'records', 'PROMISE', root_hash)
        need(promise == dict(prior[0][2], ballot=vote, basisId=promise['basisId'])
             and promise['basisId'] != prior[0][2]['basisId'] and promise['basisId'] is not None, 'promise original request')
        length = 17 if point == 'DAMAGED_HEADER' else len(raw)//2 if damaged else len(raw)
        crash['grants.gsr'] += raw[:length]
    need(inventory(root/'crash') == crash and inventory(root/'inspected') == crash, 'promise unchanged crash/inspection bytes')
    fault_events = list(current.OPEN)+['CURRENT_BEFORE_CAPTURE', 'PROMISE_BEFORE_WRITE']
    if not untouched: fault_events += ['PROMISE_WRITTEN']
    if point == 'PROMISE_FORCED': fault_events += ['PROMISE_FORCED']
    fault = event_rows(fault_events)
    if damaged: fault += [dict(event=point, retainedPrefix=length)]
    if p['mode'] == 'kill': fault += [dict(event='AWAITING_KILL', cut=point)]
    output(root, row, 'fault', fault)
    if damaged:
        reason = 'torn grant journal header' if point == 'DAMAGED_HEADER' else 'torn grant journal body'
        # The damaged journal must fail independently, not just claim a Java refusal.
        try: g.journal(crash['grants.gsr'], root_hash, 'node-1')
        except ValueError as e: need(str(e) == reason, 'promise independent damaged-prefix reason')
        else: raise ValueError('promise damaged journal accepted')
        terminal = dict(status='PASS', disposition='OPEN_REFUSED', reason=reason, liveLeases=0)
        for label in ('inspect', 'inspectAgain'): output(root, row, label, [], terminal)
        need(inventory(root/'final') == inventory(root/'node-1') == crash, 'promise damaged authority repaired')
        commands = {'fault', 'inspect', 'inspectAgain'}; snapshots = {'initial', 'crash', 'inspected', 'final', 'node-1'}
    else:
        opened, incomplete, unchanged, _ = current.current(root/'crash', p['size'])
        need(unchanged == generation and len(incomplete) == (1 if untouched else 2) and all(k == 'PROMISE' for k, _, _ in incomplete), 'promise no invented BASIS')
        inspect_events = list(current.OPEN)+([] if untouched else ['CURRENT_BEFORE_CAPTURE'])
        output(root, row, 'inspect', event_rows(inspect_events), dict(status='PASS', disposition='NO_BASIS', counter=10 if untouched else 20))
        _, completed, latest, _ = current.current(root/'resumed', p['size'])
        need(completed[:len(incomplete)] == incomplete and len(completed) == len(incomplete)+2
             and [k for k, _, _ in completed[-2:]] == ['PROMISE', 'BASIS'] and latest == generation, 'promise fresh completion preserves original history')
        new, basis = completed[-2:]; counter = 20 if untouched else 21
        need(new[2] == dict(prior[0][2], ballot=dict(vote, counter=counter), basisId=new[2]['basisId'])
             and new[2]['basisId'] is not None and new[2]['basisId'] not in {v['basisId'] for _, _, v in incomplete}, 'promise fresh identity/ballot')
        expected_basis = dict(new[2], voter='node-1', cut=generation['cut'], capsule=generation['capsule'], inventory=digest(packet['indexBytes']), accepted=generation['ownedTail'])
        need(basis[2] == expected_basis, 'promise exact fresh original source')
        final = dict(initial); final['grants.gsr'] = crash['grants.gsr']+new[1]+f.encode('records', 'BASIS', expected_basis)
        source = 'sources/'+new[2]['basisId']; final[source] = None; prefix = 'generations/'+generation['generation']+'/'
        final[source+'/source.gscp'] = initial[prefix+'source.gscp']
        final.update({source+'/'+h+'.image': initial[prefix+h+'.image'] for h in packet['images']})
        for snapshot in ('resumed', 'final', 'node-1'): need(inventory(root/snapshot) == final, 'promise exact fresh/duplicate bytes')
        terminal = dict(status='PASS', disposition='NEW_GRANT', counter=counter, basis=digest(basis[1]), accepted=generation['ownedTail'])
        output(root, row, 'resume', event_rows(capture.ORDER), terminal)
        output(root, row, 'duplicate', event_rows(current.OPEN+('CURRENT_BEFORE_CAPTURE',)), terminal)
        commands = {'fault', 'inspect', 'resume', 'duplicate'}; snapshots = {'initial', 'crash', 'inspected', 'resumed', 'final', 'node-1'}
    need(set(row['processes']) == commands, 'promise process inventory')
    need({v.name for v in root.iterdir()} == snapshots | {'profile.json'} | (set() if untouched else {'original-promise.gsr'})
         | {label+suffix for label in commands for suffix in ('.stdout', '.stderr')}, 'promise complete case inventory')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); cases = profiles()
    need(set(receipt) == {'execution', 'cases', 'expectedCases', 'freshJvms', 'historicalOwnership', 'damageInjection', 'powerLoss', 'runtimeEnabled'}
         and receipt['execution'] == 'private-promise-boundaries' and receipt['expectedCases'] == 26 and receipt['freshJvms'] == 100
         and receipt['historicalOwnership'] == 'conditional-fixture' and receipt['damageInjection'] == 'test-only-truncate-after-whole-frame-write'
         and receipt['powerLoss'] is False and receipt['runtimeEnabled'] is False, 'promise qualification scope')
    need([row['profile'] for row in receipt['cases']] == cases and {v.name for v in root.iterdir()} == {'receipt.json'} | {name(p) for p in cases}, 'promise complete matrix')
    for row in receipt['cases']: validate_case(root/name(row['profile']), row)
    return dict(status='PASS', cases=26, freshJvms=100, unmarkedProcessCrashes=22, injectedDamageCases=4, originalFirst=True,
                exactPhaseOrder=True, powerLoss=False, runtimeEnabled=False, tornPromiseRepair=False)


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = ('false-initial', 'changed-promise', 'dropped-promise', 'invented-basis', 'changed-tail', 'lost-promise-force',
                'lost-basis-force', 'lowered-fresh-ballot', 'repaired-prefix', 'false-rejection', 'false-exit', 'missing-case')
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-promise-negative-') as tmp:
            copy = Path(tmp)/'raw'; shutil.copytree(root, copy); case = copy/name(profiles()[0])
            if variant == 'false-initial': (case/'initial/selector.gsr').write_bytes(b'changed')
            elif variant == 'changed-promise': (case/'original-promise.gsr').write_bytes(read(case/'initial/grants.gsr'))
            elif variant == 'dropped-promise': (case/'inspected/grants.gsr').write_bytes(read(case/'initial/grants.gsr'))
            elif variant == 'invented-basis': (case/'inspected/grants.gsr').write_bytes(read(case/'resumed/grants.gsr'))
            elif variant == 'changed-tail': (case/'final/generations/a/owned-tail.gsr').write_bytes(b'changed')
            elif variant in ('lost-promise-force', 'lost-basis-force', 'lowered-fresh-ballot'):
                label = 'fault' if variant == 'lost-promise-force' else 'resume'; path = case/(label+'.stdout'); rows = [json.loads(v) for v in read(path).splitlines()]
                if variant == 'lowered-fresh-ballot': rows[-1]['counter'] = 20
                else: rows = [r for r in rows if r != dict(event='PROMISE_FORCED' if label == 'fault' else 'BASIS_FORCED')]
                path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in rows))
            elif variant in ('repaired-prefix', 'false-rejection'):
                case = copy/'3-1-halt-DAMAGED_BODY'
                if variant == 'repaired-prefix': (case/'final/grants.gsr').write_bytes(read(case/'initial/grants.gsr')+read(case/'original-promise.gsr'))
                else:
                    path = case/'inspect.stdout'; row = json.loads(read(path)); row['reason'] = 'unrelated exception'; path.write_bytes(f.canonical(row)+b'\n')
            elif variant == 'false-exit':
                path = copy/'receipt.json'; receipt = json.loads(read(path)); receipt['cases'][0]['processes']['fault'] = 0; path.write_bytes(f.canonical(receipt))
            else: shutil.rmtree(case)
            try: validate(copy)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted promise evidence mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-promise-portable-') as tmp:
        copy = Path(tmp)/'raw'; shutil.copytree(root, copy); need(validate(copy) == result, 'promise relocated replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root'); a = p.parse_args(); print(json.dumps(qualify(a.root), sort_keys=True))
