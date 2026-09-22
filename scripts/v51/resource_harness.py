"""Own separate JVMs for fixed storage/protocol resource limits."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
from . import resource_evidence as evidence,storage_inspector as s
from .storage_harness import ROOT,need,save
from scripts.v50.offline_harness import CORE,REPLICATION

CASES=('promise-count','retained-bytes','transfer-staging','entry-count','ancestry-count','epoch-overflow')


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    need(all(p.is_file() for p in (CORE,REPLICATION)),'package current candidate JARs first')
    need(all(p.stat().st_mtime_ns<=REPLICATION.stat().st_mtime_ns for p in
             (ROOT/'general-search-engine-replication/src/main').rglob('*.java')),'package current runtime first')
    classes=root/'classes';classes.mkdir()
    cp=os.pathsep.join(map(str,(CORE,REPLICATION,ROOT/'general-search-engine-replication/target/test-classes')))
    worker=ROOT/'scripts/v51/java/V51ResourceWorker.java'
    compilation=subprocess.run(['javac','--release','21','-proc:none','-cp',cp,'-d',str(classes),str(worker)],capture_output=True,timeout=60)
    (root/'compile.stderr').write_bytes(compilation.stderr)
    need(compilation.returncode==0,'resource worker compilation: '+compilation.stderr.decode(errors='replace'))
    cp+=os.pathsep+str(classes);receipt=dict(status='FAIL',execution='internal-resource-boundary',publicRuntime=False,paidCloud=False,cases=[],jars={p.name:s.sha(p.read_bytes()) for p in (CORE,REPLICATION)})
    receipt['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    inventory={p:s.sha((ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT/p).is_file()}
    save(root/'source-inventory.json',inventory);receipt['sourceInventorySha256']=s.sha(s.canonical(inventory))
    def invoke(case,action):
        proc=subprocess.run(['java','-Xmx512m','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V51ResourceWorker',str(case),action],capture_output=True,timeout=180)
        (case/(action+'.stdout')).write_bytes(proc.stdout);(case/(action+'.stderr')).write_bytes(proc.stderr)
        need(proc.returncode==0,'resource worker '+action+': '+proc.stderr.decode(errors='replace')[-4000:])
    try:
        for name in CASES:
            case=root/name;case.mkdir()
            invoke(case,name)
            before=s.inventory(case/'node-1')
            with tarfile.open(case/'before-reopen.tar.gz','w:gz') as tar:tar.add(case/'node-1',arcname='node-1')
            invoke(case,'reopen');need(before==s.inventory(case/'node-1'),'resource reopen mutated authority')
            validated=evidence.internal(case);validated['archiveSha256']=s.sha((case/'before-reopen.tar.gz').read_bytes());save(case/'validation.json',validated)
            receipt['cases'].append(dict(case=name,status='PASS'));print(json.dumps(receipt['cases'][-1]),flush=True)
        receipt['status']='PASS'
    finally:save(root/'receipt.json',receipt)
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');run(p.parse_args().output)
