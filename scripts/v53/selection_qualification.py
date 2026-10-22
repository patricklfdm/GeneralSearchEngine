"""Source/JAR-bound frozen-source byte qualification; runtime remains disabled."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from . import selection_evidence as e
from . import selection_negatives as n
from .context_evidence import sha
from .foundation import ROOT,JARS,binding,jar,need,save


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-selection-qualification-v1',status='RUNNING',runtimeEnabled=False,authorityEvidence=False)
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();receipt['source']=binding(ROOT,source)
        receipt['jars']=[jar(ROOT/path,role) for path,role in zip(JARS,('core','replication'))]
        classes=ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        receipt['classes']={path.name:sha(path.read_bytes()) for path in sorted(classes.glob('V53*.class'))}
        for name in ('V53SelectionWorker','V53SelectionFixture','V53CapsuleWorker','V53CapsuleFixture','V53ContextWorker','V53ContextFixture','V53DeclarationsTest'):
            path=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(path.stat().st_mtime_ns <= (classes/(name+'.class')).stat().st_mtime_ns,'stale selection fixture')
        cp=os.pathsep.join(str(ROOT/path) for path in (*JARS,'general-search-engine-replication/target/test-classes'))
        result=subprocess.run(['java','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V53SelectionWorker',str(output/'physical')],cwd=ROOT,capture_output=True,text=True,timeout=120)
        (output/'worker.stdout').write_text(result.stdout);(output/'worker.stderr').write_text(result.stderr)
        need(result.returncode==0,'selection fixture: '+result.stderr[-3000:])
        validation=e.validate(output/'physical');save(output/'validation.json',validation)
        negatives=n.run(output/'physical');save(output/'negatives.json',negatives)
        need(binding(ROOT,source)==receipt['source'],'source changed during selection qualification')
        need([jar(ROOT/path,role) for path,role in zip(JARS,('core','replication'))]==receipt['jars'],'JAR changed during selection qualification')
        receipt.update(status='PASS',selections=validation['selections'],sources=validation['sources'],negativeCases=len(negatives),relocatedReplay='PASS',
                       files={path.relative_to(output).as_posix():sha(path.read_bytes()) for path in sorted(output.rglob('*')) if path.is_file()})
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source','jars','classes','files')},sort_keys=True));return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
