"""Fresh-process adoption fence; no prefix installation, vote or service."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from . import allocator_qualification as base
from . import adoption_fence_evidence as e
from . import adoption_fence_negatives as n
from .foundation import ROOT,JARS,binding,jar,need,save


class Probe(base.Probe):
    def command(self,command,*args):
        # Concurrent PID namespaces can share /tmp/hsperfdata but reuse a PID.
        # These short crash probes need no JVM monitoring file; keep stdout exact JSON.
        return ['java','-XX:-UsePerfData','-cp',self.cp,'io.github.patricklfdm.generalsearch.replication.V53AdoptionFenceWorker',
                command,str(self.directory/'authority'),str(self.case['size']),str(self.case['through']),*map(str,args)]

    def run(self):
        mode,cut=self.case['mode'],self.case['cut']
        try:
            self.call('init','init');self.snapshot('initial')
            if mode=='clean':
                self.call('first','adopt');self.snapshot('original')
                self.call('duplicate','adopt');self.snapshot('duplicate')
            else:
                if mode=='halt':self.call('fault','adopt',cut,mode,code=73)
                else:
                    proc=self.launch('fault','adopt',cut,mode)
                    try:self.marker('fault',proc,dict(event='AWAITING_KILL',cut=cut))
                    finally:self.kill('fault',proc)
                self.snapshot('crash');self.call('resume','adopt');self.snapshot('resumed')
            self.call('same','same',code=2);self.snapshot('same')
            self.call('old','old',code=2);self.snapshot('final')
        finally:
            save(self.directory/'case.json',dict(case=self.case,execution='private-adoption-fence',runtimeEnabled=False,
                                                remoteOwnershipVerified=False,prefixInstalled=False,processes=self.processes))
        return e.validate_case(self.directory,self.case)


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-adoption-fence-qualification-v1',status='RUNNING',execution='private-adoption-fence',
                 runtimeEnabled=False,remoteOwnershipVerified=False,prefixInstalled=False,publicBootstrap=False,powerLossTested=False)
    start=time.monotonic()
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['source']=binding(ROOT,source)
        receipt['jars']=[jar(ROOT/p,r) for p,r in zip(JARS,('core','replication'))]
        classes=ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        names=('V53AdoptionFenceWorker','V53BallotAllocatorWorker','V53ContextFixture','V53DeclarationsTest','V53CapsuleFixture','V53SelectionFixture','V53CurrentGenerationFixture','V53AdoptionFenceFixture')
        for name in names:
            src=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(src.stat().st_mtime_ns<=(classes/(name+'.class')).stat().st_mtime_ns,'stale adoption fixture')
        receipt['classes']={p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}
        cp=os.pathsep.join(str(ROOT/p) for p in (*JARS,'general-search-engine-replication/target/test-classes'))
        physical=output/'physical';physical.mkdir()
        for case in e.cases():
            directory=physical/case['name'];directory.mkdir();print(json.dumps(Probe(directory,case,cp).run(),sort_keys=True),flush=True)
        result=e.validate(physical);save(output/'validation.json',result)
        negatives=n.run(physical);save(output/'negatives.json',negatives)
        with tempfile.TemporaryDirectory(prefix='v53-adoption-replay-') as temp:
            copy=Path(temp)/'physical';shutil.copytree(physical,copy);need(e.validate(copy)==result,'adoption portable replay')
        need(binding(ROOT,source)==receipt['source'],'source changed during adoption qualification')
        need([jar(ROOT/p,r) for p,r in zip(JARS,('core','replication'))]==receipt['jars'],'adoption JAR changed')
        need({p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}==receipt['classes'],'adoption fixture changed')
        receipt.update(status='PASS',cases=len(result['cases']),negativeCases=len(negatives),relocatedReplay='PASS',elapsedSeconds=round(time.monotonic()-start,3),
                       files={p.relative_to(output).as_posix():base.sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','jars','classes','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
