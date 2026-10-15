"""Real Java writer, SIGKILL append recovery and portable independent decoding."""
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import zipfile
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from scripts.v51 import public_trace
from scripts.v51 import public_qualification_harness as q
from . import controls,measurement_trace as trace
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v52-measurement-trace-foundation-v1',status='FAIL',measured=False,paidCloud=False,
                 execution='observer-encoding-only',checks=[])
    try:
        receipt['binding']=build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        controls.resolve(ROOT/'target/v52-controls')
        versions={'candidate':current(),'published-v51':'5.1.0'}
        for mode,version in versions.items():
            own=root/mode;own.mkdir();classes=own/'classes';classes.mkdir();artifacts=own/'artifacts';artifacts.mkdir()
            jars=[]
            for artifact in ('general-search-engine','general-search-engine-replication'):
                source=(ROOT/'target/v52-controls' if mode=='published-v51' else ROOT/('target' if artifact=='general-search-engine' else artifact+'/target'))/(artifact+'-'+version+'.jar')
                jar=artifacts/source.name;shutil.copyfile(source,jar);jars.append(jar)
            receipt[mode]=dict(artifacts={j.name:digest(j.read_bytes()) for j in jars})
            cp=os.pathsep.join(map(str,(*jars,classes)))
            sources=[ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java',
                     ROOT/'scripts/v51/java/PublicRuntimeConsumer.java',ROOT/'scripts/v51/java/V51PublicWorker.java',
                     ROOT/'scripts/v51/java/V51PublicTraceProbe.java',ROOT/'scripts/v52/java/V52MeasurementTrace.java',ROOT/'scripts/v52/java/V52MeasurementTraceProbe.java']
            q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,*sources],own,'compile')
            receipt[mode]['classes']={p.relative_to(classes).as_posix():digest(p.read_bytes()) for p in sorted(classes.rglob('*.class'))}
            limits=q.command(['java','-cp',cp,q.PACKAGE+'replication.V52MeasurementTraceProbe',own,'limits','1'],own,'limits')
            need(json.loads(limits.stdout)==dict(vars(trace.Limits()),chunk_size=trace.CHUNK,inline=trace.INLINE),'measurement writer/decoder budget drift')
            # Existing normal trace and interrupted-append behavior must also hold.
            legacy=own/'legacy';legacy.mkdir();receipt[mode]['legacyTrace']=public_trace.verify_writer(legacy,cp)
            for boundary in ('before','partial','complete'):
                case=own/boundary;case.mkdir()
                command=['java','-cp',cp,q.PACKAGE+'replication.V52MeasurementTraceProbe',str(case)]
                with (case/'stderr.log').open('wb') as stderr:
                    process=subprocess.Popen([*command,boundary,'1'],stdout=subprocess.PIPE,stderr=stderr)
                    try:
                        need(select.select([process.stdout],[],[],20)[0] and process.stdout.readline()==b'READY\n','measurement trace probe boundary')
                        process.kill();need(process.wait(timeout=10)==-9,'measurement trace SIGKILL')
                        public_trace.finish(case,'node-1',process)
                    finally:
                        if process.poll() is None:process.kill();process.wait(timeout=10)
                        process.stdout.close()
                q.command([*command,'normal','2'],case,'restart')
                reader=trace.Trace(case/'node-1-trace.jsonl',node='node-1')
                expected=(case/'expected.jsonl').read_bytes();need(b''.join(reader.raw_rows())==expected,'measurement original bytes differ')
                need(reader.stats['rows']==24 and reader.stats['processGenerations']==2,'measurement trace process/row count')
                need(reader.stats['encodedBytes']+reader.stats['chunkBytes']<len(expected)//2,'measurement repeated chunks not shared')
                archive=case/'trace.zip'
                with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as packed:
                    for p in [reader.path,*sorted(reader.directory.iterdir())]:packed.write(p,p.relative_to(case))
                relocated=case/'relocated';relocated.mkdir()
                with zipfile.ZipFile(archive) as packed:packed.extractall(relocated)
                portable=trace.Trace(relocated/reader.path.name,node='node-1')
                need(b''.join(portable.raw_rows())==expected and portable.stats==reader.stats,'measurement relocated bytes differ')
                receipt['checks'].append(dict(mode=mode,boundary=boundary,status='PASS',**reader.stats))
            bounded=own/'bounds';bounded.mkdir()
            q.command(['java','-cp',cp,q.PACKAGE+'replication.V52MeasurementTraceProbe',bounded,'bounds','1'],bounded,'bounds')
            cumulative=own/'restart-bound';cumulative.mkdir()
            q.command(['java','-cp',cp,q.PACKAGE+'replication.V52MeasurementTraceProbe',cumulative,'restart-bound','2'],cumulative,'restart-bound')
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(root/'receipt.json').write_bytes(encoded(receipt)+b'\n')
    print(json.dumps(dict(status='PASS',execution=receipt['execution'],checks=len(receipt['checks']))),flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
