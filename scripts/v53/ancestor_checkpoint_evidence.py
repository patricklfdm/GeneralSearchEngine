"""Actual bounded ancestor renewal qualification; earlier bridge observations remain conditional."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from .applied_end_evidence import read
from .parent_checkpoint_evidence import validate_case
from .format_fixture import canonical
from .membership_model import need

CUTS = ('APPLY_ANCESTOR_0_STATEMENT_PREFIX_WRITTEN', 'APPLY_ANCESTOR_1_ACK_PREFIX_WRITTEN', 'APPLY_ANCESTOR_1_ACK_FORCED',
        'PUBLICATION_SELECTOR_FORCED', 'COVERED_END_FILE_DELETED', 'COVERED_VOTE_PREFIX_WRITTEN')


def validate(root):
    root = Path(root); receipt = json.loads(read(root/'receipt.json')); pairs = [(m, c) for m in ('halt', 'kill') for c in CUTS]
    need(receipt['execution'] == 'private-ancestor-renewal-publication' and receipt['expectedCases'] == 12 and receipt['freshJvms'] == 36
         and receipt['historicalAuthority'] == 'conditional-fixture' and receipt['currentObservations'] == 'actual-local-votes-and-ends'
         and receipt['selectorPublication'] is True and receipt['powerLoss'] is False, 'ancestor qualification scope')
    need([(r['mode'], r['cut']) for r in receipt['cases']] == pairs and {p.name for p in root.iterdir()} == {'receipt.json'} | {m+'-'+c for m, c in pairs}, 'ancestor complete matrix')
    for row in receipt['cases']: validate_case(root/(row['mode']+'-'+row['cut']), row, renewal=True)
    return dict(status='PASS', cases=12, freshJvms=36, originalSources=[1, 2, 4], publishedEnd=5, renewedGroups=3, earlierAuthority='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); row = json.loads(read(root/'receipt.json'))['cases'][0]; source = root/(row['mode']+'-'+row['cut']); rejected = []
    for variant in ('missing-original-basis', 'missing-prior-bridge', 'false-current-observation', 'wrong-lower', 'substituted-ack', 'early-ack', 'missing-force', 'changed-coverage', 'changed-ancestry', 'unrelated-delete'):
        with tempfile.TemporaryDirectory(prefix='v53-ancestor-negative-') as temp:
            case = Path(temp)/'case'; shutil.copytree(source, case)
            if variant == 'missing-original-basis': (case/'original/generations/b/basis.gsr').unlink()
            elif variant == 'missing-prior-bridge': (case/'original/generations/b/ancestry.gsr').write_bytes(b'')
            elif variant == 'false-current-observation':
                path = case/'observations.json'; data = json.loads(read(path)); data['bridges'] = []; path.write_bytes(canonical(data))
            elif variant == 'wrong-lower': (case/'bridge-1-statement.gsr').write_bytes(read(case/'bridge-2-statement.gsr'))
            elif variant == 'substituted-ack': (case/'bridge-1-node-2.gsr').write_bytes(read(case/'bridge-2-node-2.gsr'))
            elif variant == 'early-ack': (case/'crash/applied-end/ancestor-1-ack.gsr').write_bytes(read(case/'bridge-2-node-2.gsr'))
            elif variant == 'changed-coverage': (case/'final/generations/a/selected-coverage.json').write_bytes(b'{}')
            elif variant == 'changed-ancestry': (case/'final/generations/a/ancestry.gsr').write_bytes(b'')
            elif variant == 'unrelated-delete': (case/'final/generations/b/selected.gsr').unlink()
            else:
                path = case/'resume.stdout'; path.write_bytes(read(path, 2*1024*1024).replace(canonical(dict(event='APPLY_ANCESTOR_1_ACK_FORCED'))+b'\n', b''))
            try: validate_case(case, row, renewal=True)
            except (ValueError, OSError, KeyError, TypeError): rejected.append(variant)
            else: raise ValueError('accepted ancestor mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-ancestor-portable-') as temp:
        dest = Path(temp)/'evidence'; shutil.copytree(root, dest); need(validate(dest) == result, 'ancestor portable replay')
    return dict(result, negatives=rejected, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args(); print(json.dumps(qualify(args.root), sort_keys=True))
