"""Internal private-method mailbox boundaries, not public admission schedules."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
from . import backpressure_evidence as evidence, storage_inspector as s
from . import public_qualification_harness as q
from .storage_harness import ROOT,need,save
from scripts.v50.offline_harness import CORE,REPLICATION


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='internal-runtime-mailbox',publicRuntime=False,paidCloud=False,cases=[])
    try:
        need(all(p.is_file() for p in (CORE,REPLICATION)),'package current candidates first')
        need(all(p.stat().st_mtime_ns<=REPLICATION.stat().st_mtime_ns for p in
                 (ROOT/'general-search-engine-replication/src/main').rglob('*.java')),'package current runtime first')
        receipt['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
        inventory={p:s.sha((ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT/p).is_file()}
        save(root/'source-inventory.json',inventory);receipt['sourceInventorySha256']=s.sha(s.canonical(inventory))
        receipt['jars']={p.name:s.sha(p.read_bytes()) for p in (CORE,REPLICATION)}
        classes=root/'classes';classes.mkdir();module=ROOT/'general-search-engine-replication'
        cp=os.pathsep.join(map(str,(CORE,REPLICATION,module/'target/test-classes')))
        q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,ROOT/'scripts/v51/java/V51MailboxWorker.java'],root,'compile',60)
        cp+=os.pathsep+str(classes)
        for name in ('inputs','completions'):
            case=root/name;case.mkdir()
            args=['java','-Xmx512m','-cp',cp,q.PACKAGE+'replication.V51MailboxWorker',case]
            q.command([*args,name],case,'run',60)
            with tarfile.open(case/'before-reopen.tar.gz','w:gz') as tar:tar.add(case/'node-1',arcname='node-1')
            q.command([*args,'reopen'],case,'reopen',60)
            validated=evidence.internal(case);save(case/'validation.json',validated)
            receipt['cases'].append(dict(case=name,status='PASS'));print(json.dumps(receipt['cases'][-1]),flush=True)
        receipt['status']='PASS'
    finally:save(root/'receipt.json',receipt)
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');run(p.parse_args().output)
