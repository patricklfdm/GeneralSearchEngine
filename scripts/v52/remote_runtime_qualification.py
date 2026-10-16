"""Real local receiver pipes using one unchanged public smoke program; no GCP."""
import argparse
import json
from pathlib import Path
from . import measurement_runtime as runtime,measurement_model as model
from .evidence import need

ROOT=Path(__file__).resolve().parents[2]


def smoke(root,mode,expected):
    from . import remote_history
    return remote_history.run(root,mode+'-untimed-smoke',expected)


def run(output,only=None):
    need(only is None or only in model.MODES,'remote qualification mode')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    def source():return runtime.build.binding(ROOT,runtime.subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    frozen=source()
    receipt=dict(status='FAIL',execution='local-receiver-runtime-pipes-only',binding=frozen,qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False,cases=[])
    try:
        for mode in model.MODES:
            if only and mode!=only:continue
            need(source()==frozen,'remote source changed between histories')
            value=smoke(root/mode,mode,frozen)
            need(source()==frozen,'remote source changed during history')
            receipt['cases'].append(value);print(json.dumps(dict(mode=mode,status='PASS')),flush=True)
        need(source()==frozen,'remote final source changed')
        receipt['status']='PARTIAL' if only else 'PASS';return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
