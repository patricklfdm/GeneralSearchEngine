"""Complete rich JVM execution, independent replay and binary retention. No GCP."""
import argparse
from pathlib import Path
import signal
import tempfile
from . import remote_workload,remote_rich_evidence as evidence,remote_rich_negatives as negatives
from . import remote_collection as collection,performance_model as m
from .performance_harness import save


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='local-guest-rich-workload-only',paidCloud=False,fullRemoteQualification=False)
    try:
        execution=remote_workload.run(root/'raw')
        result=evidence.validate(root/'raw');save(root/'raw'/'validation.json',result)
        rejected=negatives.verify(root/'raw');save(root/'raw'/'negatives.json',rejected)
        binding=m.sha(m.canonical(execution))
        parts=collection.pack(root/'raw',root/'parts',binding)
        with tempfile.TemporaryDirectory(prefix='v51-rich-replay-') as temp:
            retained=collection.unpack(root/'parts',Path(temp)/'raw',binding)
            replay=evidence.validate(Path(temp)/'raw')
            m.need(replay==result,'relocated rich validation changed')
        receipt.update(status='PASS',calls=sum(c['calls'] for c in result['cells']),negativeCases=len(rejected),
                       bindingSha256=binding,collection=retained,parts=len(parts['parts']))
        return receipt
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        save(root/'receipt.json',receipt)
        print(m.canonical(receipt).decode(),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args()
    def terminate(*_):raise TimeoutError('rich qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(args.output)
