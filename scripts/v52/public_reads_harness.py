"""External JAR-only replica reads, retained physical traces and published V4.4 replay."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from scripts.v51 import public_qualification_harness as q, performance_bundle as bundle
from . import controls, public_reads_evidence as evidence
from .evidence import need, digest, encoded

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


def save(path,value):Path(path).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def replay(root, traces, output):
    """Execute actual published code again; copied/claimed oracle output is not sufficient."""
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    cp=os.pathsep.join(map(str,(root/'control-classes',root/'artifacts/general-search-engine-4.4.0.jar')))
    results={}
    for key,value in evidence.oracle_inputs(root,traces).items():
        directory=output/key;directory.mkdir();save(directory/'input.json',value)
        result=q.command(['java','-cp',cp,PACKAGE+'V52ReadControl',directory,'oracle',directory/'input.json',root/'control/seed'],directory,'oracle')
        results[key]=json.loads(result.stdout)
        need(results[key]['documents']==value['documents'] and results[key]['sequence']==value['sequence'],'published query control projection')
    return results


def prepare(root, *, scenario=None):
    """One fresh public bootstrap, exact artifacts and separately compiled controls."""
    root=Path(root).resolve()
    (root/'replica-read-evidence').touch()
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    binding=dict(build.binding(ROOT,source),origin=str(root),run=os.environ.get('GITHUB_RUN_ID','local'),
                 attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1')),seed=52,codec='v52-read-codec/1')
    published=controls.resolve(ROOT/'target/v52-controls');artifacts=root/'artifacts';artifacts.mkdir()
    version=current();candidates=[ROOT/f'target/general-search-engine-{version}.jar',
            ROOT/f'general-search-engine-replication/target/general-search-engine-replication-{version}.jar']
    for path,module in zip(candidates,(ROOT,ROOT/'general-search-engine-replication')):
        need(path.is_file() and all(p.stat().st_mtime_ns<=path.stat().st_mtime_ns for p in (module/'src/main').rglob('*.java')),'stale public read artifact')
    for path in [*candidates,*[Path(a['path']) for a in published['artifacts']]]:shutil.copyfile(path,artifacts/path.name)
    binding['artifacts']={p.name:digest(p.read_bytes()) for p in sorted(artifacts.iterdir())};save(root/'binding.json',binding)
    candidate_cp=os.pathsep.join(str(artifacts/p.name) for p in candidates)
    classes=root/'consumer';classes.mkdir();observer=root/'observer';observer.mkdir();control=root/'control-classes';control.mkdir()
    java=ROOT/'scripts/v52/java';old=ROOT/'scripts/v51/java'
    json_source=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
    q.command(['javac','--release','21','-proc:none','-cp',candidate_cp,'-d',classes,json_source,
               old/'PublicRuntimeConsumer.java',java/'V52ReadQueries.java',java/'V52PublicReadConsumer.java'],root,'compile-consumer')
    q.command(['javac','--release','21','-proc:none','-cp',candidate_cp+os.pathsep+str(classes),'-d',observer,old/'V51PublicWorker.java'],root,'compile-observer')
    control_cp=os.pathsep.join(map(str,(control,artifacts/'general-search-engine-4.4.0.jar')))
    q.command(['javac','--release','21','-proc:none','-cp',artifacts/'general-search-engine-4.4.0.jar','-d',control,
               json_source,java/'V52ReadQueries.java',java/'V52ReadControl.java'],root,'compile-control')
    binding['classes']={p.relative_to(root).as_posix():digest(p.read_bytes()) for directory in (classes,observer,control)
                        for p in sorted(directory.rglob('*.class'))};save(root/'binding.json',binding)
    q.command(['java','-cp',control_cp,PACKAGE+'V52ReadControl',root/'control','seed'],root,'published-seed')
    cp=os.pathsep.join((candidate_cp,str(classes),str(observer)))
    q.command(['java','-cp',cp,PACKAGE+'V52PublicReadConsumer',root,'setup'],root,'bootstrap')
    if scenario is not None:binding['scenario']=scenario;save(root/'binding.json',binding)
    return binding,cp


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v52-public-read-v1',status='FAIL',paidCloud=False,execution='public-three-jvm-read-qualification')
    workers={};history=[];processes=[]
    try:
        binding,cp=prepare(root)
        def start(node):workers[node]=q.Worker(root,node,cp,history,consumer='replica-read');return workers[node]
        first=start('node-1');first.call('read',policy='STALE_ALLOWED') # imported genesis without a quorum
        start('node-2');start('node-3')
        deadline=time.monotonic()+40;active=None
        while time.monotonic()<deadline:
            states={n:w.call('status') for n,w in workers.items()}
            need(all(s['state']!='FAILED' for s in states.values()),'failed public read voter')
            leader=next((n for n,s in states.items() if s['state']=='LEADER_READY'),None)
            if leader is not None:active=workers[leader];break
            time.sleep(.02)
        need(active is not None,'public read election timeout')
        for start_id in (20,30,40):active.call('addAll',documents=[dict(id=i,value=f'java search query {i}') for i in (start_id,start_id+1)])
        strong=active.call('read',policy='LEADER_STRONG');index=evidence.token.decode(evidence.physical.raw(strong['token']))['index']
        for node,worker in workers.items():
            if worker is active:continue
            deadline=time.monotonic()+25
            while time.monotonic()<deadline:
                status=worker.call('status')
                if status['state']=='FOLLOWER' and status['publishedIndex']>=index:break
                time.sleep(.02)
            else:raise ValueError('follower did not publish the confirmed prefix')
            worker.call('read',policy='STALE_ALLOWED')
            worker.call('read',policy='AT_LEAST_INDEX',minimum=strong['token'],waitTimeoutMillis=5000)
        receipt['leader']=leader
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        errors=[]
        for node,worker in workers.items():
            try:worker.stop()
            except Exception as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=1,exitCode=worker.proc.returncode))
        save(root/'history.json',history);save(root/'processes.json',processes);receipt['cleanupErrors']=errors
        save(root.parent/(root.name+'-receipt.json'),receipt)
        need(not errors,'public read cleanup: '+str(errors))
    try:
        traces=evidence.traces_at(root);queries=replay(root,traces,root/'control-replay');save(root/'oracle-results.json',queries)
        save(root/'bundle-members.json',bundle.members(root))
        receipt['validation']=evidence.validate(root,binding,queries)
        receipt['negatives']=evidence.negatives(root,binding,queries)
        archive=root.parent/(root.name+'.tar.gz');bundle.pack(root,archive)
        relocated=root.parent/(root.name+'-relocated');bundle.unpack(archive,relocated)
        with tempfile.TemporaryDirectory(prefix='v52-oracle-') as temp:
            portable=replay(relocated,evidence.traces_at(relocated),Path(temp)/'replay')
            need(portable==queries,'published query replay changed after relocation')
            need(evidence.validate(relocated,binding,portable)==receipt['validation'],'relocated read validation differs')
            need(evidence.negatives(relocated,binding,portable)==receipt['negatives'],'relocated read negatives differ')
            receipt['portableReplay']=dict(status='PASS',queryCuts=len(portable),queryResultsSha256=digest(encoded(portable)))
        receipt['status']='PASS';receipt['bundleSha256']=digest(archive.read_bytes())
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root.parent/(root.name+'-receipt.json'),receipt)
    print(json.dumps(dict(status='PASS',reads=receipt['validation']['reads'],negatives=len(receipt['negatives']),paidCloud=False)))
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
