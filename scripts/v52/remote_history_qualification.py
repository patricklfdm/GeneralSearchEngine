"""Selected complete receiver histories; never full cohort or cloud acceptance."""
import argparse
import json
from pathlib import Path
from . import remote_owned_history as owned,remote_history as history,measurement_runtime as runtime
from .evidence import need

CASES=('candidate-explicit-strong-r1','m02-above-1000','m03-p4',
       'leader-sigkill-retained-restart','follower-snapshot-carried-token')


def run(output,names=CASES):
    need(type(names) in (list,tuple) and names and len(names)==len(set(names)),'remote qualification history set')
    for name in names:history.specification(name)
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False);initial=owned.source()
    result=dict(status='FAIL',scope='five-controller-branches' if tuple(names)==CASES else 'selected-history-probes',
                sourceBinding=initial,histories=list(names),completed=[],cases=[],qualifiedMeasurement=False,
                fullRemoteQualification=False,syntheticSelection=True,paidCloud=False)
    try:
        for name in names:
            need(owned.source()==initial,'remote history qualification source changed')
            print(json.dumps(dict(history=name,status='RUNNING')),flush=True)
            case=owned.run(root/name,history=name)
            need(owned.source()==initial and case['sourceBinding']==initial,'remote history qualification source changed')
            need(case['status']=='PASS' and case['submits']==1 and case['duplicateReceiptEqual'] and case['alternateCommandIdRejected'] and
                 case['qualifiedMeasurement'] is False and case['fullRemoteQualification'] is False and case['paidCloud'] is False,
                 'remote history qualification incomplete ownership')
            result['cases'].append(case);result['completed'].append(name);runtime.save(root/'receipt.json',result)
            print(json.dumps(dict(history=name,status='PASS',completed=len(result['completed']),total=len(names))),flush=True)
        result['status']='PASS';return result
    except BaseException as error:result['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:runtime.save(root/'receipt.json',result)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--history',action='append');a=p.parse_args()
    run(a.output,CASES if a.history is None else a.history)
