"""Fresh-process original pending ACCEPT, recovery and source capture; no public service."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from . import allocator_qualification as base
from . import pending_accept_evidence as e
from . import pending_accept_negatives as n
from .foundation import ROOT,JARS,binding,jar,need,save


class Probe(base.Probe):
    def command(self,command,*args):
        return ['java','-XX:-UsePerfData','-cp',self.cp,'io.github.patricklfdm.generalsearch.replication.V53PendingAcceptWorker',
                command,str(self.directory/'authority'),str(self.case['size']),str(self.case['tail']).lower(),*map(str,args)]

    def crash(self,label,cut,mode):
        if mode=='halt':self.call(label,'accept',cut,mode,code=73)
        else:
            proc=self.launch(label,'accept',cut,mode)
            try:self.marker(label,proc,dict(event='AWAITING_KILL',cut=cut))
            finally:self.kill(label,proc)

    def run(self):
        mode,cut=self.case['mode'],self.case['cut']
        try:
            self.call('init','init');self.snapshot('provisioned');self.call('install','install');self.snapshot('initial')
            if mode=='clean':
                self.call('first','accept');self.snapshot('original');self.call('duplicate','accept');self.snapshot('duplicate')
            else:
                repeat=mode.startswith('repeat-');mode=mode.removeprefix('repeat-')
                self.crash('fault','ACCEPT_CANDIDATE_WRITTEN' if repeat else cut,'halt' if repeat else mode);self.snapshot('crash')
                if repeat:self.crash('recovery-fault',cut,mode);self.snapshot('recovery-crash')
                self.call('resume','accept');self.snapshot('resumed')
            self.call('capture','capture');self.call('inspect','inspect');self.snapshot('final')
        finally:
            save(self.directory/'case.json',dict(case=self.case,execution='private-pending-accept',runtimeEnabled=False,
                                                remoteOwnershipVerified=False,networkAck=False,processes=self.processes))
        return e.validate_case(self.directory,self.case)


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-pending-accept-qualification-v1',status='RUNNING',execution='private-pending-accept',
                 runtimeEnabled=False,remoteOwnershipVerified=False,networkAck=False,publicBootstrap=False,powerLossTested=False)
    start=time.monotonic()
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['source']=binding(ROOT,source)
        receipt['jars']=[jar(ROOT/p,r) for p,r in zip(JARS,('core','replication'))]
        classes=ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        names=('V53PendingAcceptWorker','V53PendingAcceptFixture','V53GenerationInstallFixture','V53BallotAllocatorWorker','V53ContextFixture','V53DeclarationsTest','V53CapsuleFixture','V53SelectionFixture','V53CurrentGenerationFixture')
        for name in names:
            src=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(src.stat().st_mtime_ns<=(classes/(name+'.class')).stat().st_mtime_ns,'stale pending ACCEPT fixture')
        receipt['classes']={p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}
        cp=os.pathsep.join(str(ROOT/p) for p in (*JARS,'general-search-engine-replication/target/test-classes'))
        physical=output/'physical';physical.mkdir()
        for case in e.cases():
            directory=physical/case['name'];directory.mkdir();print(json.dumps(Probe(directory,case,cp).run(),sort_keys=True),flush=True)
        result=e.validate(physical);save(output/'validation.json',result)
        negatives=n.run(physical);save(output/'negatives.json',negatives)
        with tempfile.TemporaryDirectory(prefix='v53-pending-accept-replay-') as temp:
            copy=Path(temp)/'physical';shutil.copytree(physical,copy);need(e.validate(copy)==result,'pending ACCEPT portable replay')
        need(binding(ROOT,source)==receipt['source'],'source changed during pending ACCEPT qualification')
        need([jar(ROOT/p,r) for p,r in zip(JARS,('core','replication'))]==receipt['jars'],'pending ACCEPT JAR changed')
        need({p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}==receipt['classes'],'pending ACCEPT fixture changed')
        receipt.update(status='PASS',cases=len(result['cases']),negativeCases=len(negatives),relocatedReplay='PASS',elapsedSeconds=round(time.monotonic()-start,3),
                       files={p.relative_to(output).as_posix():base.sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','jars','classes','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
