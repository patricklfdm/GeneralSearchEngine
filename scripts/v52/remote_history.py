"""Whole declared histories over receiver-local pipes. Local qualification only."""
import json
import os
from pathlib import Path
import shutil
import socket
import uuid
from scripts.v51 import public_qualification_harness as q
from . import cloud_suite as suite,remote_topology as topology
from . import measurement_runtime as runtime,measurement_bundle as bundle
from . import measurement_options as options,measurement_m01 as m01,measurement_minimum as minimum
from . import measurement_recovery as recovery,measurement_cohort as cohort
from .evidence import need,digest

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


class Worker(runtime.Worker):
    ENTRY=q.PACKAGE+'replication.V52RemoteMeasurementWorker'


def specification(name):
    plan=suite.load()
    need(type(name) is str and name in plan['histories'],'remote undeclared history')
    return plan['histories'][name]


def member_for(name):
    specification(name)
    matches=[member for member,row in suite.load()['members'].items() if name in row['histories']]
    need(len(matches)==1,'remote history member ambiguity');return matches[0]


def original_counts(result,spec):
    if spec['family']=='UNTIMED':return result['reads'],result['updates']
    return tuple(sum(result['ledger']['outcomes'][kind].values()) for kind in ('read','update'))


class Receivers:
    """One owner for preparation, every process generation and stopped collection."""
    def __init__(self,root,name,expected,*,worker_factory=None):
        self.root=Path(root).resolve();self.name=name;self.spec=specification(name);self.expected=expected
        self.root.mkdir(parents=True,exist_ok=False)
        self.producer=self.root/'producer';self.collected=self.root/'evidence';self.collected.mkdir()
        self.roots={};self.classpath={};self.workers={};self.history=[];self.processes=[];self.sockets=[]
        self.binding=None;self.generations={};self.prepared=False;self.finished=False
        self.worker_factory=worker_factory

    def prepare(self):
        spec=self.spec;family=spec['family'];mode=spec['mode']
        if family=='UNTIMED':original,_,_=runtime.prepare(self.producer,mode,exercise_load=True)
        elif family=='M01':original,_,_=runtime.prepare(self.producer,mode,m01_repetition=spec['profile']['repetition'])
        elif family in ('M02','M03'):original,_,_=minimum.prepare(self.producer,self.name)
        else:original,_,_=recovery.prepare(self.producer,self.name)
        need({k:original[k] for k in self.expected}==self.expected,'remote preparation source changed')
        cp=self.paths(self.producer,original);java=ROOT/'scripts/v52/java'
        q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',self.producer/'consumer',java/'V52RemoteTopology.java',java/'V52RemoteBootstrap.java'],self.producer,'compile-remote-consumer')
        q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',self.producer/'observer',java/'V52RemoteMeasurementWorker.java'],self.producer,'compile-remote-worker')
        captured={directory+'/'+p.relative_to(self.producer/directory).as_posix():digest(p.read_bytes())
                  for directory in ('consumer','observer','control-classes') for p in sorted((self.producer/directory).rglob('*.class'))}
        self.binding=dict(original,origin=str(self.collected),classes=captured)
        for directory in ('artifacts','consumer','observer','control-classes'):
            shutil.copytree(self.producer/directory,self.collected/directory)
        for name in (options.FILE,recovery.FILE):
            if (self.producer/name).exists():shutil.copyfile(self.producer/name,self.collected/name)
        plan=self.topology_plan()
        topology.validate(plan);self.binding['remoteTopology']=plan;runtime.save(self.collected/topology.FILE,plan)
        receivers={}
        for node in topology.NODES:
            own=self.receiver_root(node);self.roots[node]=own
            answer=self.prepare_receiver(node,own,plan,original)
            need(answer['status']=='PREPARED_NOT_STARTED' and answer['node']==node and answer['topology']==plan and
                 answer['originalRoot']==str(own),'remote prepared receiver identity')
            receivers[node]={k:answer[k] for k in ('originalRoot','manifestSha256','genesisSha256')}
        self.binding['remoteReceivers']=receivers;runtime.save(self.collected/'binding.json',self.binding)
        self.release_ports();self.prepared=True

    def topology_plan(self):
        for _ in topology.NODES:
            sock=socket.socket();self.sockets.append(sock);sock.bind(('127.0.0.1',0))
        return dict(schema=topology.SCHEMA,placement='local-no-gcp',groupId=str(uuid.uuid4()),
            members=[dict(node=node,host='127.0.0.1',port=sock.getsockname()[1]) for node,sock in zip(topology.NODES,self.sockets)])

    def receiver_root(self,node):return self.root/'receivers'/node

    def prepare_receiver(self,node,own,plan,original):
        own.mkdir(mode=0o700,parents=True)
        runtime.save(own/topology.FILE,plan)
        for directory in ('artifacts','consumer','observer'):shutil.copytree(self.producer/directory,own/directory)
        for name in (options.FILE,recovery.FILE):
            if (self.producer/name).exists():shutil.copyfile(self.producer/name,own/name)
        shutil.copytree(self.producer/'control/seed',own/'control/seed')
        self.classpath[node]=self.paths(own,original)
        return json.loads(q.command(['java','-cp',self.classpath[node],PACKAGE+'V52RemoteBootstrap',own,node],own,'bootstrap').stdout)

    @staticmethod
    def paths(root,binding):
        return os.pathsep.join(map(str,(*[root/'artifacts'/n for n in binding['artifacts'] if not n.endswith('-4.4.0.jar')],root/'consumer',root/'observer')))

    def release_ports(self):
        for sock in self.sockets:sock.close()
        self.sockets.clear()

    def start(self,node,generation=1):
        need(self.prepared and not self.finished and node in self.roots and node not in self.workers,
             'remote voter start ownership')
        need(type(generation) is int and (generation==1 and node not in self.generations or
             generation==2 and self.name==recovery.CASES[0] and self.generations.get(node)==1 and
             any(p['node']==node and p['exitCode']==-9 for p in self.processes)), 'remote undeclared voter generation')
        own=self.roots[node];worker=(self.worker_factory or Worker)(own,node,self.classpath[node],self.spec['mode'],self.history,generation)
        self.workers[node]=worker;self.generations[node]=generation
        self.verify_worker(worker,own)

    def verify_worker(self,worker,own):
        for component in ('core','replication'):
            path=Path(worker.identity[component+'Source'])
            need(path.parent==own/'artifacts' and path.name in self.binding['artifacts'] and
                 bundle.sha_file(path)==self.binding['artifacts'][path.name],'remote loaded artifact')
        need(worker.identity['readParameters']==self.binding['readParameters'],'remote observed read parameters')

    def record(self,worker):
        self.processes.append(dict(node=worker.node,pid=worker.proc.pid,generation=worker.generation,
                                   exitCode=worker.proc.returncode,identity=worker.identity))

    def crash(self,node):
        need(self.name==recovery.CASES[0] and node in self.workers and self.generations[node]==1 and
             not any(p['exitCode']==-9 for p in self.processes),'remote undeclared crash')
        worker=self.workers[node];worker.proc.kill()
        try:
            need(worker.proc.wait(timeout=10)==-9,'remote unexpected abrupt exit')
            worker.stop(kill=True)
        finally:
            # Keep ownership on cleanup failure so finish can still reap it.
            if worker.proc.poll() is not None and not worker.reader.is_alive():
                self.record(worker);self.workers.pop(node)
        before=self.collected/'pre-reopen'/node
        shutil.copytree(self.roots[node]/node,before,symlinks=True)
        return dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode,preReopen=bundle.members(before))

    def partition(self,node=None):
        need(self.name==recovery.CASES[1] and (node is None or node in topology.NODES),'remote undeclared partition')
        # Each receiver sees the same closed cut, atomically per file. The shared
        # controller records the completed cut before offering the fault workload.
        for own in self.roots.values():recovery.partition(own,node)
        recovery.partition(self.collected,node)

    def observe(self):
        for node in topology.NODES:self.start(node)
        spec=self.spec;family=spec['family']
        if family=='UNTIMED':return runtime.observe_smoke(self.collected,self.workers,self.history,spec['mode'],exercise_load=True)
        if family=='M01':return m01.observe(self.collected,self.workers,self.history,spec['mode'],spec['profile']['repetition'])
        if family in ('M02','M03'):return minimum.observe(self.collected,self.workers,self.history,self.name)
        return recovery.observe(self.collected,self.workers,self.history,self.name,self.crash,lambda node:self.start(node,2),
                                partition_control=self.partition)

    def finish(self,failure):
        need(not self.finished,'remote receiver owner already finished');self.finished=True;errors=[]
        def retain(node,action):
            try:action()
            except BaseException as error:errors.append(dict(node=node,type=type(error).__name__,message=str(error)))
        retain('reserved-ports',self.release_ports)
        if self.name==recovery.CASES[1]:
            self.cleanup_partition(retain)
        for node,worker in self.workers.items():
            retain(node,worker.stop);self.record(worker)
        for node,own in self.roots.items():
            retain(node,lambda node=node,own=own:self.collect_receiver(node,own))
        runtime.save(self.collected/'history.json',self.history);runtime.save(self.collected/'processes.json',self.processes)
        runtime.save(self.collected/'execution.json',dict(status='STOPPED' if failure is None and not errors else 'FAIL',
            failure=failure,closeErrors=errors,qualifiedMeasurement=False,paidCloud=False))
        if errors and failure is None:raise ValueError('remote receiver cleanup failed: '+json.dumps(errors))

    def cleanup_partition(self,retain):
        # Independently heal all prepared roots even if one cleanup write fails.
        for node,own in self.roots.items():retain(node,lambda own=own:recovery.partition(own))
        retain('collected-network-controls',lambda:recovery.partition(self.collected))

    def collect_receiver(self,node,own):
        need(all(p['exitCode'] is not None for p in self.processes if p['node']==node),'remote collecting active process')
        worker=self.workers.get(node)
        need(worker is None or worker.proc.poll() is not None,'remote collecting live voter')
        for path in own.iterdir():
            if path.name==node or path.name.startswith(node+'-'):
                need(not path.is_symlink(),'remote collected symlink')
                if path.is_dir():shutil.copytree(path,self.collected/path.name,symlinks=True)
                else:shutil.copyfile(path,self.collected/path.name)
        if self.prepared:
            need(all(bundle.sha_file(own/'artifacts'/n)==sha for n,sha in self.binding['artifacts'].items()),'remote artifact changed')
            need(all(bundle.sha_file(own/n)==sha for n,sha in self.binding['classes'].items() if not n.startswith('control-classes/')),
                 'remote classes changed')
            for name in (options.FILE,recovery.FILE):
                source=self.producer/name;target=own/name
                need(source.exists()==target.exists() and (not source.exists() or source.read_bytes()==target.read_bytes()),'remote receiver parameters changed')
            if self.name==recovery.CASES[1]:need((own/'network-blocks.txt').read_bytes()==b'','remote receiver not healed')


def source():
    from . import remote_python_context
    installed=remote_python_context.source()
    if installed is not None:return installed
    need(Path(runtime.subprocess.check_output(['git','rev-parse','--show-toplevel'],cwd=ROOT,text=True).strip())==ROOT,
         'remote source requires checkout root or explicit installed context')
    return runtime.build.binding(ROOT,runtime.subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())


def run(root,name,expected,*,progress=lambda stage:None,receiver_factory=None):
    owner=(receiver_factory or Receivers)(root,name,expected);failure=None
    try:
        progress('preparation');owner.prepare()
        need(source()==expected,'remote source changed before execution')
        progress('original-workload');owner.observe()
    except BaseException as error:failure=dict(type=type(error).__name__,message=str(error));raise
    finally:owner.finish(failure)
    need(source()==expected,'remote source changed during history')
    collected=owner.collected;binding=owner.binding
    need(runtime.evidence.reads.read(collected/'binding.json')==binding,'remote binding changed during original execution')
    runtime.save(collected/bundle.INDEX,bundle.members(collected));progress('physical-replay')
    if owner.spec['family']=='UNTIMED':
        original=runtime.evidence.replay(collected,binding,owner.root/'original-validation',package=bundle)
        archive=owner.root/'history.tar.gz';bundle.pack(collected,archive);relocated=bundle.unpack(archive,owner.root/'relocated')
        portable=runtime.evidence.replay(relocated,binding,owner.root/'relocated-validation',package=bundle)
        need(original==portable,'remote receiver relocated replay drift');sha=bundle.sha_file(archive)
    else:
        portable=cohort.replay_member(collected,binding,owner.spec,owner.root/'portable')
        original=portable['result'];sha=portable['archiveSha256']
        need(original['negatives']==suite.load()['formalNegativeRules'][name],'remote incomplete formal negatives')
    need(source()==expected,'remote source changed during replay');progress('complete')
    reads,updates=original_counts(original,owner.spec)
    return dict(status='PASS',history=name,family=owner.spec['family'],mode=owner.spec['mode'],binding=binding,
                result=original,archiveSha256=sha,originalReads=reads,originalUpdates=updates,
                qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
