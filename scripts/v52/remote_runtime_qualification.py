"""Real local receiver pipes using one unchanged public smoke program; no GCP."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import uuid
from scripts.v51 import public_qualification_harness as q
from . import measurement_runtime as runtime,measurement_model as model,measurement_bundle as bundle
from . import measurement_runtime_evidence as evidence,remote_topology as topology
from .evidence import need,encoded,digest

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=q.PACKAGE+'admission.'


class Worker(runtime.Worker):
    ENTRY=q.PACKAGE+'replication.V52RemoteMeasurementWorker'


def smoke(root,mode,expected):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=False)
    producer=root/'producer';original,_,_=runtime.prepare(producer,mode,exercise_load=True)
    need({k:original[k] for k in expected}==expected,'remote preparation source changed')
    cp=os.pathsep.join(map(str,(*[producer/'artifacts'/n for n in original['artifacts'] if not n.endswith('-4.4.0.jar')],producer/'consumer',producer/'observer')))
    java=ROOT/'scripts/v52/java'
    q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',producer/'consumer',java/'V52RemoteTopology.java',java/'V52RemoteBootstrap.java'],producer,'compile-remote-consumer')
    q.command(['javac','--release','21','-proc:none','-cp',cp,'-d',producer/'observer',java/'V52RemoteMeasurementWorker.java'],producer,'compile-remote-worker')
    captured={directory+'/'+p.relative_to(producer/directory).as_posix():digest(p.read_bytes()) for directory in ('consumer','observer','control-classes')
              for p in sorted((producer/directory).rglob('*.class'))}
    collected=root/'evidence';collected.mkdir();binding=dict(original,origin=str(collected),classes=captured)
    for directory in ('artifacts','consumer','observer','control-classes'):shutil.copytree(producer/directory,collected/directory)
    sockets=[];receivers={};classpath={};workers={};history=[];processes=[];close_errors=[];failure=None
    try:
        for _ in topology.NODES:
            sock=socket.socket();sock.bind(('127.0.0.1',0));sockets.append(sock)
        plan=dict(schema=topology.SCHEMA,placement='local-no-gcp',groupId=str(uuid.uuid4()),
                  members=[dict(node=node,host='127.0.0.1',port=sock.getsockname()[1]) for node,sock in zip(topology.NODES,sockets)])
        topology.validate(plan);binding['remoteTopology']=plan;runtime.save(collected/topology.FILE,plan)
        for node in topology.NODES:
            own=root/'receivers'/node;own.mkdir(parents=True);runtime.save(own/topology.FILE,plan)
            for directory in ('artifacts','consumer','observer'):shutil.copytree(producer/directory,own/directory)
            shutil.copytree(producer/'control/seed',own/'control/seed')
            classpath[node]=os.pathsep.join(map(str,(*[own/'artifacts'/n for n in original['artifacts'] if not n.endswith('-4.4.0.jar')],own/'consumer',own/'observer')))
            answer=json.loads(q.command(['java','-cp',classpath[node],PACKAGE+'V52RemoteBootstrap',own,node],own,'bootstrap').stdout)
            need(answer['status']=='PREPARED_NOT_STARTED' and answer['node']==node and answer['topology']==plan,'remote prepared receiver identity')
            receivers[node]={k:answer[k] for k in ('originalRoot','manifestSha256','genesisSha256')}
        binding['remoteReceivers']=receivers;runtime.save(collected/'binding.json',binding)
        for sock in sockets:sock.close()
        sockets.clear()
        for node in topology.NODES:
            own=Path(receivers[node]['originalRoot']);worker=Worker(own,node,classpath[node],mode,history);workers[node]=worker
            for component in ('core','replication'):
                path=Path(worker.identity[component+'Source']);need(path.parent==own/'artifacts' and bundle.sha_file(path)==binding['artifacts'][path.name],'remote loaded artifact')
            need(worker.identity['readParameters']==binding['readParameters'],'remote observed read parameters')
        runtime.observe_smoke(collected,workers,history,mode,exercise_load=True)
    except BaseException as error:failure=dict(type=type(error).__name__,message=str(error));raise
    finally:
        for sock in sockets:sock.close()
        for node,worker in workers.items():
            try:worker.stop()
            except BaseException as error:close_errors.append(dict(node=node,type=type(error).__name__,message=str(error)))
            processes.append(dict(node=node,pid=worker.proc.pid,generation=worker.generation,exitCode=worker.proc.returncode,identity=worker.identity))
        runtime.save(collected/'history.json',history);runtime.save(collected/'processes.json',processes)
        runtime.save(collected/'execution.json',dict(status='STOPPED' if failure is None and not close_errors else 'FAIL',failure=failure,closeErrors=close_errors,
                     qualifiedMeasurement=False,paidCloud=False))
        # Collection is only from reaped workers. Retain each original root too.
        for node in receivers:
            own=Path(receivers[node]['originalRoot'])
            for path in own.iterdir():
                if path.name==node or path.name.startswith(node+'-'):
                    need(not path.is_symlink(),'remote collected symlink')
                    if path.is_dir():shutil.copytree(path,collected/path.name)
                    else:shutil.copyfile(path,collected/path.name)
        if close_errors and failure is None:raise ValueError('remote worker close failed: '+str(close_errors))
    # Reconcile expected source and loaded class bytes even after all workers exit.
    for value in receivers.values():
        own=Path(value['originalRoot'])
        need(all(bundle.sha_file(own/'artifacts'/name)==sha for name,sha in binding['artifacts'].items()),'remote artifact changed')
        need(all(bundle.sha_file(own/name)==sha for name,sha in captured.items() if not name.startswith('control-classes/')),'remote classes changed')
    need(runtime.evidence.reads.read(collected/'binding.json')==binding,'remote binding changed during original execution')
    runtime.save(collected/bundle.INDEX,bundle.members(collected))
    original=evidence.replay(collected,binding,root/'original-validation',package=bundle)
    archive=root/'history.tar.gz';bundle.pack(collected,archive);relocated=bundle.unpack(archive,root/'relocated')
    portable=evidence.replay(relocated,binding,root/'relocated-validation',package=bundle)
    need(original==portable,'remote receiver relocated replay drift')
    return dict(status='PASS',mode=mode,binding=binding,result=original,archiveSha256=bundle.sha_file(archive))


def run(output,only=None):
    need(only is None or only in model.MODES,'remote qualification mode')
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    def source():return runtime.build.binding(ROOT,runtime.subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
    frozen=source()
    receipt=dict(status='FAIL',execution='local-receiver-runtime-pipes-only',binding=frozen,qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False,cases=[])
    try:
        for mode in model.MODES:
            if only and mode!=only:continue
            need(source()==frozen,'remote source changed between histories')
            value=smoke(root/mode,mode,frozen)
            need(source()==frozen,'remote source changed during history')
            receipt['cases'].append(value);print(json.dumps(dict(mode=mode,status='PASS')),flush=True)
        need(source()==frozen,'remote final source changed')
        receipt['status']='PARTIAL' if only else 'PASS';return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:runtime.save(root/'receipt.json',receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
