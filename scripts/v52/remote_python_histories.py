"""Complete declared histories over installed helpers; local-only qualification."""
import argparse
import json
from pathlib import Path
import time
from . import remote_python_runtime_qualification as runtime,remote_history as h
from .evidence import need

DEFAULTS=('candidate-minimum-untimed-smoke','m03-p4',*h.recovery.CASES)


def selection(names):
    names=list(names)
    need(names and len(names)==len(set(names)),'installed history duplicate/empty selection')
    for name in names:runtime.receiver_type(name)
    return names


def run(output,names=DEFAULTS):
    names=selection(names);root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    source=h.source();began=time.monotonic()
    receipt=dict(schema='gse-v52-installed-history-qualification-v1',status='FAIL',sourceBinding=source,
        selected=names,histories=[],sharedPythonCheckout=False,independentHosts=False,
        qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    try:
        for name in names:
            print(json.dumps(dict(history=name,status='RUNNING')),flush=True)
            record=dict(history=name,status='FAIL');receipt['histories'].append(record)
            try:
                value=runtime.run(root/name,name)
                need(value['sourceBinding']==source and value['history']==name and value['status']=='PASS' and
                     value['fullRemoteQualification'] is False and value['paidCloud'] is False,'installed history source/result')
                record.update(status='PASS',originalReads=value['originalReads'],originalUpdates=value['originalUpdates'],
                    elapsedSeconds=value['elapsedSeconds'],archiveSha256=value['archiveSha256'],
                    negativesPerLocation=value['negativesPerLocation'],pythonNegatives=len(value['pythonNegatives']),
                    faultNegatives=len(value.get('faultNegatives',[])),selectedBasisNegatives=len(value.get('selectedBasisNegatives',[])),
                    deliveryNegatives=len(value['deliveryNegatives']),lifecycleNegatives=len(value['lifecycleNegatives']),
                    stoppedServices=value['stoppedServices'])
                need(h.source()==source,'installed history source changed')
                print(json.dumps(record),flush=True)
            except BaseException as error:
                record.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
            finally:h.runtime.save(root/'receipt.json',receipt)
        receipt['status']='PASS';return receipt
    finally:
        receipt['elapsedSeconds']=round(time.monotonic()-began,3);h.runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--history',action='append');args=parser.parse_args()
    print(json.dumps(run(args.output,args.history or DEFAULTS)),flush=True)
