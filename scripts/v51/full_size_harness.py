"""Actual 512-slot component boundary qualification; no election/performance/cloud claim."""
import argparse
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from . import performance_harness as h, performance_plan as plan, performance_model as m
from . import performance_semantics as semantics, remote_collection as collection
from .storage_inspector import inventory


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    raw=root/'raw';raw.mkdir();admitted=plan.load();h.save(raw/'plan.json',admitted)
    runner=h.Run(raw,admitted)
    execution=dict(schema='gse-v51-full-size-v1',execution='local-component-boundaries',paidCloud=False,
                   fullRemoteQualification=False,root=str(raw),status='FAIL')
    try:
        execution['source']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=h.ROOT,text=True,timeout=10).strip()
        paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=h.ROOT,timeout=10).decode().split('\0')
        h.save(raw/'source-inventory.json',{p:m.sha((h.ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (h.ROOT/p).is_file()})
        execution['sourceInventorySha256']=m.sha((raw/'source-inventory.json').read_bytes())
        execution['controls']=m.strict_json(runner.process([sys.executable,'-m','scripts.v51.controls',h.ROOT/'target/v51-controls'],'resolve-controls'))
        execution['adapters']=h.compile_adapters(runner,h.ROOT/'target/v51-controls')
        adapter=execution['adapters']['candidate-v5.1-automatic'];cp=adapter['cp']
        source=h.ROOT/'scripts/v51/java/V51FullSizeBoundary.java';classes=raw/'classes-candidate-v5.1-automatic'
        runner.process(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,source],'compile-full-size')
        adapter['classes']=inventory(classes);adapter['sources'][str(source.relative_to(h.ROOT))]=m.sha(source.read_bytes())
        runner.process(runner.java(execution['adapters']['published-v4.4-local']['cp'],'admission.V51MeasuredLocal',
                                  raw,'prepare',raw/'plan.json',raw/'source'),'prepare-source')
        execution['sourceBackup']=semantics.source_backup(raw/'source',m.initial(admitted))
        h.group_directory(raw/'group')
        runner.process(runner.java(cp,'admission.V51MeasuredAutomatic',raw/'group','setup',raw/'plan.json',raw/'source'),'bootstrap')
        runner.process(runner.java(cp,'replication.V51FullSizeBoundary',raw),'boundaries')
        execution['status']='EXECUTED';h.save(raw/'execution.json',execution)
        from . import full_size_evidence as evidence
        result=evidence.validate(raw);h.save(raw/'validation.json',result)
        rejected=evidence.negatives(raw);h.save(raw/'negatives.json',rejected)
        binding=m.sha(m.canonical(execution));parts=collection.pack(raw,root/'parts',binding)
        with tempfile.TemporaryDirectory(prefix='v51-full-size-replay-') as temp:
            target=Path(temp)/'raw';collection.unpack(root/'parts',target,binding)
            m.need(evidence.validate(target)==result,'relocated full-size validation')
            m.need(evidence.negatives(target)==rejected,'relocated full-size negatives')
        receipt=dict(status='PASS',execution=execution['execution'],paidCloud=False,fullRemoteQualification=False,
                     validation=result,negativeCases=len(rejected),bindingSha256=binding,parts=len(parts['parts']))
        h.save(root/'receipt.json',receipt);print(m.canonical(receipt).decode(),flush=True);return receipt
    except BaseException as error:
        execution.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
        h.save(raw/'execution.json',execution);raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args()
    def terminate(*_):raise SystemExit('full-size qualification terminated')
    signal.signal(signal.SIGTERM,terminate)
    run(a.output)
