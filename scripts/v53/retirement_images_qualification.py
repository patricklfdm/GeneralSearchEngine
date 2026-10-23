"""Bounded floor-image retirement in fresh JVMs, preserving every original snapshot."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
from . import allocator_qualification as base
from . import retirement_qualification as prior
from . import retirement_images_evidence as e
from .foundation import ROOT,JARS,binding,jar,need,save


class Probe(prior.Probe):
    def command(self,command,*args):
        values=super().command(command,*args);values[4]='io.github.patricklfdm.generalsearch.replication.V53RetirementImagesWorker';return values
    def run(self):
        mode,cut=self.case['mode'],self.case['cut']
        try:
            self.call('init','init');self.snapshot('initial')
            if mode=='clean':
                self.call('first','retire');self.snapshot('original');self.call('duplicate','retire');self.snapshot('duplicate')
            else:
                repeated=mode.startswith('repeat-');mode=mode.removeprefix('repeat-')
                self.crash('fault','RETIREMENT_FILE_DELETED@2' if repeated else cut,'halt' if repeated else mode);self.snapshot('crash')
                if repeated:self.crash('recovery-fault',cut,mode);self.snapshot('recovery-crash')
                self.call('resume','retire');self.snapshot('resumed')
            self.call('inspect','inspect');self.snapshot('final')
        finally:
            save(self.directory/'case.json',dict(case=self.case,execution='private-floor-image-retirement',runtimeEnabled=False,
                 historicalOwnershipVerified=False,networkAck=False,selectedSourceFrames=True,processes=self.processes))
        return e.validate_case(self.directory,self.case)


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    receipt=dict(schema='gse-v53-retirement-images-qualification-v1',status='RUNNING',runtimeEnabled=False,paidCloud=False,powerLoss=False,historicalOwnershipVerified=False)
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['source']=binding(ROOT,source)
        receipt['jars']=[jar(ROOT/path,role) for path,role in zip(JARS,('core','replication'))]
        classes=ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        names=('V53RetirementImagesWorker','V53RetirementWorker','V53FloorWorker','V53BallotAllocatorWorker','V53ContextFixture','V53DeclarationsTest','V53CapsuleFixture','V53SelectionFixture','V53CurrentGenerationFixture')
        for name in names:
            src=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(src.stat().st_mtime_ns<=(classes/(name+'.class')).stat().st_mtime_ns,'stale retirement image fixture')
        receipt['classes']={p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}
        cp=os.pathsep.join(str(ROOT/path) for path in (*JARS,'general-search-engine-replication/target/test-classes'));physical=output/'physical';physical.mkdir()
        for case in e.cases():
            directory=physical/case['name'];directory.mkdir();print(json.dumps(Probe(directory,case,cp).run(),sort_keys=True),flush=True)
        result=e.qualify(physical);save(output/'validation.json',result)
        need(binding(ROOT,source)==receipt['source'],'source changed during image retirement qualification')
        need([jar(ROOT/path,role) for path,role in zip(JARS,('core','replication'))]==receipt['jars'],'image retirement JAR changed')
        need({p.name:base.sha(p) for name in names for p in sorted(classes.glob(name+'*.class'))}==receipt['classes'],'image retirement fixture changed')
        receipt.update(status='PASS',cases=len(result['cases']),negativeCases=len(result['negatives']),portableReplay=result['portableReplay'],
                       freshProcesses=sum(len(json.loads((directory/'case.json').read_text())['processes']) for directory in physical.iterdir()),
                       elapsedSeconds=round(time.monotonic()-started,3),files={p.relative_to(output).as_posix():base.sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','jars','classes','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
