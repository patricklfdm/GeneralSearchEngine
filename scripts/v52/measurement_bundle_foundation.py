"""Replay unchanged real smoke evidence through the large package; no workload run."""
import argparse
from pathlib import Path
import shutil
from . import measurement_bundle as bundle,measurement_runtime_evidence as evidence
from . import measurement_trace as trace
from .evidence import need,encoded,digest
from scripts.v51.performance_model import strict_json


def save(path,value):path.write_bytes(encoded(value)+b'\n')


def run(source,output):
    source=Path(source).resolve();root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    binding=strict_json((source/'binding.json').read_bytes())
    receipt=dict(status='FAIL',measured=False,paidCloud=False,execution='large-package-replay-only',sourceBinding=binding)
    try:
        baseline=evidence.replay(source,binding,root/'baseline')
        # Copy the original bytes; do not rewrite the retained original inventory.
        original_inventory=digest((source/'bundle-members.json').read_bytes())
        raw=root/'raw';shutil.copytree(source,raw)
        fixture=raw/'packaging-fixture';fixture.mkdir()
        # Explicit package-admission fixture, never a runtime/authority observation.
        # The actual three-JVM history is unchanged. The predecessor package must
        # reject this file count; this package must preserve and replay it exactly.
        for i in range(4001):(fixture/f'{i:04}.bin').write_bytes(i.to_bytes(4,'big'))
        archive=root/'history.tar.gz';index=bundle.pack(raw,archive)
        try:evidence.bundle.members(raw)
        except ValueError as error:need(str(error)=='bundle evidence ceiling','unrelated predecessor packaging rejection')
        else:raise ValueError('predecessor unexpectedly accepted large measurement fixture')
        checked=evidence.replay(raw,binding,root/'raw-validation',package=bundle)
        relocated=bundle.unpack(archive,root/'relocated')
        portable=evidence.replay(relocated,binding,root/'portable-validation',package=bundle)
        need(baseline==checked==portable,'large package physical/query/negative replay differs')
        need(digest((source/'bundle-members.json').read_bytes())==original_inventory,'modified original evidence inventory')
        receipt.update(status='PASS',files=len(index),archiveBytes=archive.stat().st_size,archiveSha256=bundle.sha_file(archive),
                       inventorySha256=digest((raw/'bundle-members.json').read_bytes()),base=checked['base'],reads=checked['reads'],updates=checked['updates'],
                       negativesPerReplay=len(checked['negatives']),limits=bundle.LIMITS,
                       decodedBudgetsPerNode=vars(trace.Limits()),fixtureMembers=4001,qualifiedMeasurement=False)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('output');a=parser.parse_args()
    result=run(a.source,a.output);print(encoded({k:result[k] for k in ('status','execution','files','reads','updates','negativesPerReplay')}).decode())
