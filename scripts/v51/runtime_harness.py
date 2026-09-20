"""Real three-process TCP execution; no public bootstrap or paid environment."""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import tarfile
import threading
import time
import sys
import xml.etree.ElementTree as ET
from . import runtime_evidence as oracle, storage_inspector as storage
from .storage_harness import ROOT,need,save


class Worker:
    def __init__(self,root,node,cp):
        self.log=(root/(node+'-stderr.log')).open('ab')
        self.process=subprocess.Popen(['java','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V51RuntimeWorker',str(root),node[-1]],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True)
        self.lines=queue.Queue(4)
        def read():
            for line in self.process.stdout:self.lines.put(line)
        self.reader=threading.Thread(target=read,daemon=True);self.reader.start()
        try:self.first=self.receive();need(self.first['status']=='STARTED','runtime startup')
        except BaseException:
            self.process.kill();self.process.wait(timeout=10);self.process.stdin.close();self.log.close();raise
    def receive(self):return json.loads(self.lines.get(timeout=35))
    def command(self,name,**values):
        self.process.stdin.write(json.dumps(dict(command=name,**values))+'\n');self.process.stdin.flush();result=self.receive()
        need(result['command']==name and result['accepted'],'runtime command: '+json.dumps(result));return result
    def kill(self):self.process.kill();self.process.wait(timeout=10);self.process.stdin.close();self.log.close()
    def close(self):
        if self.process.poll() is None:
            try:self.command('close');self.process.stdin.close();self.process.wait(timeout=15)
            finally:
                if self.process.poll() is None:self.process.kill();self.process.wait(timeout=10)
        self.log.close()


def run(output):
    from scripts.v50.offline_harness import CORE,REPLICATION
    root=Path(output).resolve();need(not root.exists(),'fresh runtime evidence');root.mkdir(parents=True)
    cp=os.pathsep.join(map(str,[CORE,REPLICATION,ROOT/'general-search-engine-replication/target/test-classes']))
    need(all(p.is_file() for p in (CORE,REPLICATION)),'package current reactor first')
    module=ROOT/'general-search-engine-replication'
    need(all(p.stat().st_mtime_ns<=REPLICATION.stat().st_mtime_ns for p in (module/'src/main').rglob('*.java')),'runtime JAR predates sources')
    result=subprocess.run(['java','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V51RuntimeWorker',str(root),'setup'],cwd=ROOT,capture_output=True,timeout=30)
    (root/'setup.stderr').write_bytes(result.stderr);need(result.returncode==0,'runtime fixture setup: '+result.stderr.decode(errors='replace'))
    workers={};receipt=dict(status='RUNNING',execution='internal-runtime-real-tcp',publicRuntime=False,pids=[],cases=[],jars={p.name:storage.sha(p.read_bytes()) for p in (CORE,REPLICATION)})
    files=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    receipt['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    receipt['sourceInventorySha256']=storage.sha(storage.canonical({p:storage.sha((ROOT/p).read_bytes()) for p in sorted(set(files)) if p and (ROOT/p).is_file()}))
    receipt['javaReports']={}
    for name,minimum in [('V51AutomaticRuntimeTest',4),('V51AutomaticWireTest',3),('V51AutomaticProtocolTest',21)]:
        report=module/'target/surefire-reports'/('TEST-io.github.patricklfdm.generalsearch.replication.'+name+'.xml');suite=ET.parse(report).getroot()
        need(int(suite.attrib['tests'])>=minimum and all(int(suite.attrib.get(k,0))==0 for k in ('failures','errors','skipped')),'runtime regression prerequisite: '+name)
        receipt['javaReports'][name]=dict(tests=int(suite.attrib['tests']),sha256=storage.sha(report.read_bytes()))
    def leader():
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            for node,worker in workers.items():
                status=worker.command('status');need(status['failure'] is None,'runtime dispatcher failed: '+json.dumps(status))
                if status['state']=='LEADER_READY':return node,worker
            time.sleep(.1)
        raise ValueError('no automatic leader')
    try:
        for i in range(1,4):
            node='node-'+str(i);workers[node]=Worker(root,node,cp);receipt['pids'].append(workers[node].process.pid)
        old,active=leader();large='chunked-'*1500
        active.command('add',id=1,value=large);need(active.command('query')['documents']==[dict(id=1,value=large)],'initial V4 query')
        receipt['cases'].append(dict(case='healthy',status='PASS',leader=old));print(json.dumps(receipt['cases'][-1]),flush=True)
        active.kill();del workers[old]
        with tarfile.open(root/'leader-before-reopen.tar.gz','w:gz') as archive:archive.add(root/old,arcname=old)
        new,active=leader();need(active.command('query')['documents']==[dict(id=1,value=large)],'recovered V4 query')
        active.command('update',id=1,value='updated');active.command('add',id=2,value='shared')
        need(sorted(active.command('query')['documents'],key=lambda d:d['id'])==[dict(id=1,value='updated'),dict(id=2,value='shared')],'survivor V4 mutations')
        receipt['cases'].append(dict(case='leader-sigkill',status='PASS',leader=new));print(json.dumps(receipt['cases'][-1]),flush=True)
        workers[old]=Worker(root,old,cp);receipt['pids'].append(workers[old].process.pid)
        restarted=workers[old].command('status');need(restarted['state']!='LEADER_READY','restart revived old readiness')
        receipt['cases'].append(dict(case='retained-restart',status='PASS',node=old))
    except BaseException as error:
        receipt.update(status='FAIL',failure=str(error));raise
    finally:
        cleanup=[]
        for worker in workers.values():
            try:worker.close()
            except Exception as error:cleanup.append(str(error))
        if cleanup:receipt.update(status='FAIL',cleanupErrors=cleanup)
        save(root/'receipt.json',receipt)
        if cleanup and sys.exc_info()[0] is None:raise ValueError('runtime cleanup failed: '+str(cleanup))
    try:
        receipt['validation']=oracle.validate(root);receipt['negatives']=oracle.negatives(root);receipt['status']='PASS'
    except BaseException as error:receipt.update(status='FAIL',failure=str(error));raise
    finally:save(root/'receipt.json',receipt)
    print(json.dumps(receipt['validation']),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');run(p.parse_args().output)
