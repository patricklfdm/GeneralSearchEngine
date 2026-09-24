"""Fault execution, independent rejection checks and relocated binary replay; no GCP."""
import argparse
import copy
from pathlib import Path
import signal
import tempfile
from . import remote_faults as workload, remote_fault_evidence as evidence, remote_collection as collection
from . import performance_model as m, public_qualification_evidence as physical
from .performance_harness import save


def negatives(root):
    root=Path(root);execution=evidence.read(root/'execution.json');results=[]
    def rejected(label,fn):
        try:fn()
        except (ValueError,KeyError,StopIteration,FileNotFoundError):results.append(label);return
        raise ValueError('fault evidence mutation accepted: '+label)
    for c in execution['cases']:
        name=c['case'];directory=root/name;receipt=evidence.read(directory/'receipt.json');history=evidence.read(directory/'history.json')
        traces=physical.traces_at(directory);retained=evidence.archives(directory,receipt,None)
        changed=copy.deepcopy(traces);bad_receipt=copy.deepcopy(receipt);bad_files=copy.deepcopy(retained)
        if name in ('leader-loss','entry-chosen','proof-quorum','interrupted-transfer'):
            next(s for s in bad_receipt['stops'] if s['kill'])['kill']=False
        elif name=='group-restart':bad_receipt['starts'].pop()
        elif name=='slow-follower':
            changed={n:[r for r in rows if r['event']!='SLOW_FORCE_END'] for n,rows in changed.items()}
        elif name=='maintenance':
            changed={n:[r for r in rows if r['event']!='REJOIN_INSTALLED'] for n,rows in changed.items()}
        elif name=='minority-capacity':bad_receipt['rejection']['requested']=0
        else:changed={n:[r for r in rows if r['event']!='NETWORK_DROP'] for n,rows in changed.items()}
        rejected(name+':missing-physical-fault',lambda:evidence.fault_facts(directory,bad_receipt,history,changed,bad_files))
        changed_history=copy.deepcopy(history);changed_history[0]['documents'][0]['value']+='x'
        rejected(name+':changed-seed',lambda:evidence.schedule(changed_history,receipt))
        bad_receipt=copy.deepcopy(receipt);bad_receipt['progress'][-1]['endNanos']=receipt['faultStartNanos']+61*10**9
        # Every retained progress end is bounded, even if an earlier pair succeeded.
        rejected(name+':extended-progress',lambda:evidence.schedule(history,bad_receipt))
    directory=root/'leader-loss';history=evidence.read(directory/'history.json');receipt=evidence.read(directory/'receipt.json')
    mapping={(s['node'],s['pid']):s['generation'] for s in receipt['starts']}
    results.extend('physical:'+v['case'] for v in physical.negatives(directory,history,process_generations=mapping))
    return results


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='local-guest-faults-only',paidCloud=False,fullRemoteQualification=False)
    try:
        execution=workload.run(root/'raw')
        result=evidence.validate(root/'raw');save(root/'raw/validation.json',result)
        rejected=negatives(root/'raw');save(root/'raw/negatives.json',rejected)
        binding=m.sha(m.canonical(execution));parts=collection.pack(root/'raw',root/'parts',binding)
        with tempfile.TemporaryDirectory(prefix='v51-fault-replay-') as temp:
            retained=collection.unpack(root/'parts',Path(temp)/'raw',binding)
            replay=evidence.validate(Path(temp)/'raw');m.need(result==replay,'relocated fault validation differs')
        receipt.update(status='PASS',cases=len(result['cases']),calls=sum(c['calls'] for c in result['cases']),negativeCases=len(rejected),
                       bindingSha256=binding,collection=retained,parts=len(parts['parts']))
        return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root/'receipt.json',receipt);print(m.canonical(receipt).decode(),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args()
    def terminate(*_):raise SystemExit('remote fault qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(a.output)
