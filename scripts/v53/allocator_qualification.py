"""Fresh-JVM filesystem qualification; no public bootstrap, protocol or cloud execution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from . import allocator_evidence as e
from . import allocator_negatives as n
from .foundation import ROOT, JARS, binding, jar, need, save

WORKER='io.github.patricklfdm.generalsearch.replication.V53BallotAllocatorWorker'


class Probe:
    def __init__(self, directory, case, cp):
        self.directory=directory;self.case=case;self.cp=cp;self.processes={}

    def command(self, command, *args):
        return ['java','-cp',self.cp,WORKER,command,str(self.directory/'authority'),str(self.case['size']),*map(str,args)]

    def launch(self, name, command, *args):
        # Real files avoid PIPE buffering/deadlock, and retain even a timed-out probe's output.
        with (self.directory/(name+'.stdout')).open('xb') as out, (self.directory/(name+'.stderr')).open('xb') as err:
            return subprocess.Popen(self.command(command,*args),cwd=ROOT,stdin=subprocess.PIPE,stdout=out,stderr=err)

    def finish(self, name, proc, code):
        try: proc.wait(timeout=30)
        except BaseException:
            if proc.poll() is None:proc.kill()
            proc.wait();raise
        finally:
            if proc.stdin:proc.stdin.close()
            self.processes[name]=dict(exitCode=proc.returncode)
        need(proc.returncode==code,f'allocator probe {name}: expected {code}, got {proc.returncode}')

    def call(self, name, command, *args, code=0):
        self.finish(name,self.launch(name,command,*args),code)

    def marker(self, name, proc, expected):
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            data=(self.directory/(name+'.stdout')).read_bytes()
            need(len(data)<=65536,'allocator handshake output bound')
            # Only consume complete lines: a filesystem read can observe a split JSON write.
            rows=[json.loads(line) for line in data.split(b'\n')[:-1]]
            if rows and rows[-1]==expected:return
            need(proc.poll() is None,'allocator probe exited before handshake')
            time.sleep(.02)
        raise ValueError('allocator probe handshake deadline')

    def kill(self, name, proc):
        if proc.poll() is None:proc.kill()
        self.finish(name,proc,-9)

    def snapshot(self, name):shutil.copytree(self.directory/'authority',self.directory/name)

    def run(self):
        c=self.case;mode,cut=c['mode'],c['cut']
        try:
            self.call('init','init');self.snapshot('initial')
            if mode=='clean':
                self.call('first','reserve',9);self.call('second','reserve',0);self.call('inspect','inspect')
            elif mode=='lock':
                proc=self.launch('holder','hold')
                try:
                    self.marker('holder',proc,dict(event='HELD'))
                    self.call('contender','inspect',code=2);self.snapshot('blocked')
                finally:self.kill('holder',proc)
                self.call('inspect','inspect')
            else:
                if mode=='halt':self.call('fault','reserve',9,cut,mode,code=73)
                else:
                    proc=self.launch('fault','reserve',9,cut,mode)
                    try:self.marker('fault',proc,dict(event='AWAITING_KILL',cut=cut))
                    finally:self.kill('fault',proc)
                self.snapshot('crash')
                self.call('resume','inspect',code=2 if cut=='ALLOCATOR_CREATED' else 0)
                if cut!='ALLOCATOR_CREATED':self.call('next','reserve',0)
            self.snapshot('final')
        finally:
            save(self.directory/'case.json',dict(case=c,execution='private-storage-process',runtimeEnabled=False,processes=self.processes))
        return e.validate_case(self.directory,c)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-allocator-qualification-v1',status='RUNNING',execution='private-storage-process',
                 runtimeEnabled=False,publicBootstrap=False,powerLossTested=False)
    started=time.monotonic()
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['source']=binding(ROOT,source)
        receipt['jars']=[jar(ROOT/path,role) for path,role in zip(JARS,('core','replication'))]
        classes=ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        names=('V53BallotAllocatorWorker','V53ContextFixture','V53DeclarationsTest')
        for name in names:
            src=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(src.stat().st_mtime_ns<=(classes/(name+'.class')).stat().st_mtime_ns,'stale allocator fixture')
        receipt['classes']={p.name:sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}
        cp=os.pathsep.join(str(ROOT/p) for p in (*JARS,'general-search-engine-replication/target/test-classes'))
        physical=output/'physical';physical.mkdir()
        for case in e.cases():
            directory=physical/case['name'];directory.mkdir()
            result=Probe(directory,case,cp).run();print(json.dumps(result,sort_keys=True),flush=True)
        validation=e.validate(physical);save(output/'validation.json',validation)
        negatives=n.run(physical);save(output/'negatives.json',negatives)
        with tempfile.TemporaryDirectory(prefix='v53-allocator-replay-') as temp:
            copied=Path(temp)/'physical';shutil.copytree(physical,copied)
            need(e.validate(copied)==validation,'allocator relocated replay')
        need(binding(ROOT,source)==receipt['source'],'source changed during allocator qualification')
        need([jar(ROOT/p,r) for p,r in zip(JARS,('core','replication'))]==receipt['jars'],'allocator JAR changed')
        need({p.name:sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}==receipt['classes'],'allocator fixture changed')
        receipt.update(status='PASS',cases=len(validation['cases']),negativeCases=len(negatives),relocatedReplay='PASS',
                       elapsedSeconds=round(time.monotonic()-started,3),
                       files={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','jars','classes','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
