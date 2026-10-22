"""Replay original disabled-entry evidence before ten portable corruption cases."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
from . import foundation as f


def run(original, output):
    original=Path(original); output=Path(output); output.mkdir(parents=True, exist_ok=False)
    receipt=json.loads((original/'receipt.json').read_text()); source=deepcopy(receipt['source'])
    f.replay(original, source)
    changes={
        'source':lambda r:r['source'].update(source='0'*40),
        'checkout':lambda r:r['source'].update(checkoutSha256='0'*64),
        'runtime-promotion':lambda r:r.update(runtimeEnabled=True),
        'physical-promotion':lambda r:r.update(physicalMembershipEvidence=True),
        'missing-size':lambda r:r['cases'].pop(),
        'failed-process':lambda r:r['cases'][0].update(exitCode=1),
        'created-storage':lambda r:r['cases'][0].update(createdFiles=['ROOT']),
        'jar-identity':lambda r:r['jars'][0].update(sha256='0'*64),
    }
    results=[]
    with tempfile.TemporaryDirectory(prefix='v53-declaration-negatives-') as temp:
        for name in (*changes, 'stdout-bytes', 'class-bytes'):
            target=Path(temp)/name; shutil.copytree(original, target)
            value=deepcopy(receipt)
            if name in changes:
                changes[name](value); f.save(target/'receipt.json', value)
            else:
                path=target/'process-3.stdout' if name=='stdout-bytes' else next((target/'classes').rglob('*.class'))
                path.write_bytes(path.read_bytes()+b'corruption')
            try: f.replay(target, source)
            except ValueError as error: results.append(dict(case=name,status='REJECTED',reason=str(error)))
            else: raise ValueError('accepted corrupted declaration evidence: '+name)
        # Verify that copies remain replayable after the original absolute producer path changes.
        relocated=Path(temp)/'relocated'; shutil.copytree(original, relocated); f.replay(relocated, source)
    f.need(len(results)==10, 'declaration negative inventory')
    result=dict(schema='gse-v53-declaration-negatives-v1', status='PASS', originalSource=source,
                runtimeEnabled=False, relocatedReplay='PASS', cases=results)
    f.save(output/'receipt.json', result); print(json.dumps(dict(status='PASS',negativeCases=len(results),relocatedReplay='PASS')))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original');p.add_argument('output');a=p.parse_args();run(a.original,a.output)
