"""Untimed public-consumer integration. The frozen M01 windows are not run here."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
import uuid
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from scripts.v51 import public_trace
from scripts.v51 import performance_bundle as bundle
from scripts.v51 import public_qualification_harness as q
from scripts.v51.performance_model import strict_json
from . import controls,measurement_model as model,measurement_trace as trace
from . import measurement_runtime_evidence as evidence
from . import measurement_load as load
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


def save(path,value):path.write_bytes(encoded(value)+b'\n')


class Worker:
    def __init__(self,root,node,cp,mode,history,generation=1):
        self.root,self.node,self.history,self.generation=root,node,history,generation
        self.lock=threading.Lock();self.pending={};self.serial=0;self.startup=queue.Queue(1);self.error=None
        self.log=(root/(node+'-stderr.log')).open('ab');self.output=(root/(node+'-stdout.jsonl')).open('ab')
        self.proc=subprocess.Popen(['java','-cp',cp,q.PACKAGE+'replication.V52MeasurementWorker',str(root),node[-1],mode,str(generation)],
                                   stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log)
        self.reader=threading.Thread(target=self.receive,daemon=True);self.reader.start()
        try:
            self.identity=self.startup.get(timeout=30)
            need(self.identity and self.identity['status']=='STARTED' and self.identity['pid']==self.proc.pid and
                 self.identity['node']==node and self.identity['mode']==mode,'measurement consumer startup')
        except BaseException:self.stop(kill=True);raise

    def receive(self):
        try:
            while True:
                line=self.proc.stdout.readline(65537)
                if not line:break
                need(len(line)<=65536 and line.endswith(b'\n'),'measurement worker response bound')
                self.output.write(line);self.output.flush();value=strict_json(line);now=time.monotonic_ns()
                if 'opId' not in value:self.startup.put_nowait(value);continue
                with self.lock:
                    future,record=self.pending.pop(value['opId']);record.update(endNanos=now,outcome=value['outcome'],response=value)
                    future.set_result(value)
        except BaseException as error:self.error=repr(error)
        finally:
            with self.lock:
                for future,record in self.pending.values():record['disconnectNanos']=time.monotonic_ns();future.set_result(None)
                self.pending.clear()
            if self.startup.empty():
                try:self.startup.put_nowait(None)
                except queue.Full:pass

    def submit(self,kind,**values):
        with self.lock:
            need(self.error is None and self.proc.poll() is None,'measurement worker unavailable: '+str(self.error))
            self.serial+=1;identity=f'{self.node}-g{self.generation}-{self.serial}'
            command=dict(opId=identity,kind=kind,**values);record=dict(command,node=self.node,pid=self.proc.pid,generation=self.generation,
                        startNanos=time.monotonic_ns(),endNanos=None,outcome='PENDING')
            future=concurrent.futures.Future();self.pending[identity]=future,record;self.history.append(record)
            self.proc.stdin.write(encoded(command)+b'\n');self.proc.stdin.flush();return identity,future

    def send(self,kind,**values):return self.submit(kind,**values)[1]

    def call(self,kind,**values):
        result=self.send(kind,**values).result(timeout=35)
        need(result is not None and result['outcome']=='SUCCESS','measurement public call failed: '+str(result));return result

    def stop(self,kill=False):
        try:
            if self.proc.poll() is None:
                if kill:self.proc.kill()
                else:self.proc.stdin.write(b'{"kind":"close"}\n');self.proc.stdin.flush();self.proc.stdin.close()
            code=self.proc.wait(timeout=35);self.reader.join(timeout=5)
            need(not self.reader.is_alive() and self.error is None,'measurement response reader failed: '+str(self.error))
            if not kill:need(code==0,'measurement close failed: '+str(code))
        finally:
            if self.proc.poll() is None:self.proc.kill();self.proc.wait(timeout=10)
            self.log.close();self.output.close();self.proc.stdout.close()
            public_trace.finish(self.root,self.node,self.proc,self.generation)


def prepare(root,mode,*,exercise_load=False,m01_repetition=None):
    need(mode in model.MODES,'measurement unknown preparation mode')
    if m01_repetition is not None:
        from .measurement_m01 import profile
        need(not exercise_load,'measurement smoke and M01 profiles are exclusive')
        measured_profile=profile(mode,m01_repetition)
    root.mkdir(parents=True,exist_ok=False);model.load();published=controls.resolve(ROOT/'target/v52-controls')
    save(root/'corpus.json',model.corpus());(root/'group-id.txt').write_text(str(uuid.uuid4())+'\n')
    artifacts=root/'artifacts';artifacts.mkdir();version='5.1.0' if mode.startswith('published') else current()
    jars=[]
    for artifact in ('general-search-engine','general-search-engine-replication'):
        source=(ROOT/'target/v52-controls' if version=='5.1.0' else ROOT/('target' if artifact=='general-search-engine' else artifact+'/target'))/(artifact+'-'+version+'.jar')
        target=artifacts/source.name;shutil.copyfile(source,target);jars.append(target)
    control=artifacts/'general-search-engine-4.4.0.jar';shutil.copyfile(ROOT/'target/v52-controls'/control.name,control)
    classes=root/'consumer';classes.mkdir();observer=root/'observer';observer.mkdir();control_classes=root/'control-classes';control_classes.mkdir()
    java=ROOT/'scripts/v52/java';json_source=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
    common=[json_source,java/'V52ReadQueries.java',java/'V52MeasurementQueries.java']
    cp=os.pathsep.join(map(str,(*jars,classes,observer)));control_cp=os.pathsep.join(map(str,(control,control_classes)))
    consumer=[*common,java/'V52MeasurementConsumer.java',java/'V52MeasurementSampler.java']
    if version!='5.1.0':consumer.append(java/'V52MeasuredExplicitReads.java')
    q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',classes,*consumer],root,'compile-consumer')
    q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',observer,ROOT/'scripts/v51/java/PublicRuntimeConsumer.java',
               ROOT/'scripts/v51/java/V51PublicWorker.java',java/'V52MeasurementTrace.java',java/'V52MeasurementWorker.java'],root,'compile-observer')
    q.command(['javac','--release','21','-proc:none','-cp',control_cp,'-d',control_classes,*common,java/'V52MeasurementSeed.java',java/'V52MeasurementOracle.java'],root,'compile-control')
    seed=q.command(['java','-cp',control_cp,PACKAGE+'V52MeasurementSeed',root/'control',root/'corpus.json'],root,'seed')
    need(seed.stderr.strip()=='coreSource='+str(control),'measurement seed loaded wrong control')
    need(json.loads(seed.stdout)==dict(status='PASS',documents=64,sequence=1),'measurement seed result')
    q.command(['java','-cp',cp,PACKAGE+'V52MeasurementConsumer',root,'setup'],root,'bootstrap')
    binding=dict(build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()),mode=mode,
                 origin=str(root),driverExercise=exercise_load,smokeInitialization='read-write-targets-confirmed-updates-v1',publicationAuthority='forced-generation-v1',programSha256=model.PLAN_SHA,run=os.environ.get('GITHUB_RUN_ID','local'),attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1')),
                 artifacts={p.name:digest(p.read_bytes()) for p in artifacts.iterdir()},classes={p.relative_to(root).as_posix():digest(p.read_bytes())
                 for directory in (classes,observer,control_classes) for p in sorted(directory.rglob('*.class'))})
    if m01_repetition is not None:
        binding.pop('smokeInitialization');binding.pop('driverExercise')
        binding['measurementProfile']=measured_profile
    elif exercise_load:binding['driverMarkerSchedule']=list(evidence.DRIVER_MARKERS)
    save(root/'binding.json',binding);return binding,cp,control_cp


def await_publication(workers,index,sequence,*,clock=time.monotonic,sleep=time.sleep):
    """Observe prepared state on the required read/write targets; never retry a business operation."""
    deadline=clock()+40
    while clock()<deadline:
        states={node:w.call('status') for node,w in workers.items()}
        need(all(v['state']!='FAILED' for v in states.values()),'measurement prepared voter failed')
        if all(v['state'] in ('FOLLOWER','LEADER_READY') and v['publishedIndex']>=index and v['sequence']==sequence for v in states.values()):return states
        sleep(.05)
    raise ValueError('measurement prepared publication unavailable')


def smoke(root,mode,*,exercise_load=False):
    binding,cp,control_cp=prepare(root,mode,exercise_load=exercise_load);workers={};history=[];processes=[];result=None
    try:
        for i in (1,2,3):
            node=f'node-{i}';worker=Worker(root,node,cp,mode,history);workers[node]=worker
            for component in ('core','replication'):
                path=Path(worker.identity[component+'Source']);need(path.parent==root/'artifacts' and digest(path.read_bytes())==binding['artifacts'][path.name],'measurement loaded artifact')
        deadline=time.monotonic()+40;leader=None
        while time.monotonic()<deadline:
            states={node:w.call('status') for node,w in workers.items()};need(all(s['state']!='FAILED' for s in states.values()),'measurement voter failed')
            ready=[node for node,s in states.items() if s['state']=='LEADER_READY']
            if len(ready)==1:leader=ready[0];break
            time.sleep(.05)
        need(leader is not None,'measurement smoke activation timeout');active=workers[leader]
        initial=active.call('read',query=model.query(0),setupToken=True)
        updates=[r['document'] for r in model.program() if r['kind']=='update'][:3]
        for doc in updates:active.call('update',document=doc)
        prepared=active.call('status');need(prepared['sequence']==4,'measurement confirmed setup sequence')
        target=leader if mode.endswith('strong') else sorted(set(workers)-{leader})[-1]
        baseline=await_publication({node:workers[node] for node in sorted({leader,target})},prepared['publishedIndex'],4)
        if target!=leader:
            from . import token
            index=token.decode(__import__('base64').b64decode(initial['token']))['index'];until=time.monotonic()+25
            while time.monotonic()<until:
                status=workers[target].call('status')
                if status['state']=='FOLLOWER' and status['publishedIndex']>=index:break
                time.sleep(.02)
            else:raise ValueError('measurement target did not publish initial bound')
        parameters=dict(minimum=initial['token']) if mode=='candidate-minimum' else {}
        if exercise_load:
            # Three-second driver integration only; never an abbreviated M01 run.
            for worker in workers.values():worker.call('sample-start')
            calls=[dict(kind='read',ordinal=i,offsetNanos=i*100_000_000,window='driver-smoke',query=model.query(i)) for i in range(10)]
            def submit(call):return workers[target].submit(call['kind'],query=call['query'],**parameters)
            def mark(name):
                for worker in workers.values():yield worker.submit('sample-mark',marker=name)
            offered,pending=load.dispatch(calls,3_000_000_000,submit,markers=evidence.DRIVER_MARKERS,mark=mark)
            save(root/'offered.json',load.drain(offered,pending,35))
            for worker in workers.values():worker.call('sample-stop')
            checked=load.validate(offered,calls,3_000_000_000,history)
            need(checked['outcomes']=={'SUCCESS':10},'measurement driver smoke outcome')
            load.validate_markers(offered,evidence.DRIVER_MARKERS,history,workers)
            save(root/'load-validation.json',checked)
        else:
            for i in range(5):workers[target].call('read',query=model.query(i),**parameters)
            pending=[workers[target].send('read',query=model.query(i),**parameters) for i in range(5,10)]
            for future in pending:
                response=future.result(timeout=35);need(response is not None and response['outcome']=='SUCCESS','measurement concurrent consumer failure: '+str(response))
        probes={node:worker.call('probe') for node,worker in workers.items()}
        need(all(v['queues']['admissionAvailable']==64 and v['queues'].get('readsOwned',0)==0 for v in probes.values()),'measurement consumer ownership leak')
        save(root/'scenario.json',dict(mode=mode,leader=leader,readTarget=target,initialRead=initial['opId'],updates=updates,readCount=11,probes=probes,baseline=baseline,baselineIndex=prepared['publishedIndex']))
        result=dict(status='PASS',execution='untimed-measurement-consumer-smoke-only',mode=mode,leader=leader,readTarget=target,reads=11,updates=3,qualifiedMeasurement=False)
    finally:
        errors=[]
        for node,worker in workers.items():
            try:worker.stop()
            except BaseException as error:errors.append(str(error))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode,identity=worker.identity))
        save(root/'history.json',history);save(root/'processes.json',processes)
        if errors:save(root/'close-errors.json',errors);raise ValueError('measurement worker close failures: '+str(errors))
    result['traces']={node:trace.Trace(root/(node+'-trace.jsonl'),node=node).verify() for node in workers}
    save(root/'receipt.json',result);return result


def run(output,only=None,*,exercise_load=False):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    need(only is None or only in model.MODES,'unknown measurement smoke mode')
    receipt=dict(schema='gse-v52-measurement-consumer-smoke-v1',status='FAIL',measured=False,paidCloud=False,qualifiedMeasurement=False,cases=[])
    try:
        for mode in model.MODES:
            if only and mode!=only:continue
            case=root/mode;result=smoke(case,mode,exercise_load=exercise_load);binding=strict_json((case/'binding.json').read_bytes())
            save(case/'bundle-members.json',bundle.members(case))
            original=evidence.replay(case,binding,root/(mode+'-validation'))
            archive=root/(mode+'.tar.gz');bundle.pack(case,archive);relocated=root/(mode+'-relocated');bundle.unpack(archive,relocated)
            portable=evidence.replay(relocated,binding,root/(mode+'-portable-validation'))
            need(original==portable,'measurement smoke relocated physical/query replay drift')
            result['validation']=original;receipt['cases'].append(result);print(json.dumps({k:result[k] for k in ('mode','status','reads','updates')}),flush=True)
        if only is None and exercise_load:
            from . import measurement_bundle_foundation
            receipt['largePackage']=measurement_bundle_foundation.run(root/'candidate-minimum',root/'large-package')
        receipt['status']='PARTIAL' if only else 'PASS'
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:save(root/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--only');parser.add_argument('--exercise-load',action='store_true');args=parser.parse_args();run(args.output,args.only,exercise_load=args.exercise_load)
