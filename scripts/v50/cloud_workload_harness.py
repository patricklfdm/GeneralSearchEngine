"""Owned local qualification of the full corpus, public workload and ordered faults. No cloud adapter."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import struct
import subprocess
import time
import zipfile
from .admission_format import check
from . import runtime_format
from .offline_harness import ROOT, CORE, REPLICATION, PACKAGE, save
from .performance_harness import Run, Worker as BaseWorker, now, source_inputs
from .leader_harness import ports
from .cloud_workload_plan import PLAN, read_plan, arithmetic
from .cloud_workload_io import inventory, sha_file, rows, pack


class Worker(BaseWorker):
    def send(self, command, **values):
        request = dict(command=command, **values)
        self.receipt['exchanges'].append(dict(sentNanos=now(), request=request, outcome='indeterminate'))
        save(self.path, self.receipt)
        self.process.stdin.write(json.dumps(request).encode()+b'\n'); self.process.stdin.flush()


class Group:
    def __init__(self, run, cp, java, plan, volume_layout=False):
        self.run, self.root, self.cp, self.java, self.plan = run, run.root, cp, java, plan
        self.volume_layout = volume_layout
        if volume_layout:
            for i in (1,2,3): (self.root/f'volume-{i}').mkdir()
        self.endpoints = ','.join('127.0.0.1:'+str(p) for p in ports())
        self.generations = {i: 0 for i in (1,2,3)}; self.workers = {}; self.cells = []; self.revision = 10000
    def args(self, ordinal): return [str(self.root), str(ordinal), self.endpoints, str(self.root/'plan.json')]
    def layout(self): return ['volumes'] if self.volume_layout else []
    def authority(self, ordinal):
        return (self.root/f'volume-{ordinal}' if self.volume_layout else self.root)/f'node-{ordinal}'
    def offline(self, command, *extra):
        return self.run.process('offline-'+command+'-'+ '-'.join(map(str, extra)),
            [*self.java, '-cp', self.cp, PACKAGE+'admission.V50CloudWorkloadConsumer', *self.args(0),command,*map(str,extra),*self.layout()],True)
    def start(self, ordinal):
        self.generations[ordinal] += 1; label=f'{ordinal}-{self.generations[ordinal]}'
        output=self.root/'streams'/('node-'+label)
        w=Worker(self.run,label,[*self.java,'-cp',self.cp,PACKAGE+'replication.V50CloudWorkloadWorker',*self.args(ordinal),str(output),*self.layout()])
        w.receipt.update(schema='gse-v50-cloud-workload-member-v1',node=f'node-{ordinal}',generation=self.generations[ordinal],streams=str(output.relative_to(self.root)))
        save(w.path,w.receipt); self.workers[ordinal]=w; return w
    def start_all(self):
        for i in (1,2,3): self.start(i)
    def stop(self, ordinal, kill=False, already_closed=False):
        w=self.workers.pop(ordinal,None)
        if w:
            if already_closed: w.process.wait(timeout=10)
            w.close(failed=kill)
    def close(self):
        for i in list(self.workers): self.stop(i)
    def command(self,name,**values): return self.workers[1].command(name,**values)
    def configure(self,name,enabled=False):
        for w in self.workers.values(): w.command('configure',window=name,enabled=enabled)
    def update(self,key=5):
        self.revision+=1; return self.command('update',id=key,revision=self.revision)
    def catchup(self,node):
        # Catch-up may contend with a bounded outgoing FIFO immediately after healing.
        for attempt in range(20):
            w=self.workers[1]; request=dict(command='catchup',peer=f'node-{node}')
            e=dict(sentNanos=now(),request=request);w.receipt['exchanges'].append(e);save(w.path,w.receipt)
            w.process.stdin.write(json.dumps(request).encode()+b'\n');w.process.stdin.flush();r=w.receive()
            e.update(receivedNanos=now(),response=r);save(w.path,w.receipt)
            if r['accepted']: return r
            check(r['reason']=='CAPACITY_EXCEEDED' and r['status']['writeQuorum'],'unexpected catchup failure')
            time.sleep(.05)
        raise ValueError('catchup capacity did not recover')
    def capture(self,label):
        check(not self.workers,'quiescent inspection required')
        path=self.root/'cuts'/label;path.mkdir(parents=True)
        reports=[]
        for i in (1,2,3):
            shutil.copytree(self.authority(i),path/f'node-{i}')
            reports.append(runtime_format.inspect(path/f'node-{i}',torn=True))
        save(path/'inspection.json',reports);return reports
    def restart(self):
        self.close();self.start_all();return self.command('activate')
    def kill_at(self,barrier,command,**values):
        w=self.workers[1];w.command('arm',barrier=barrier);w.send(command,**values)
        marker=self.root/w.receipt['streams']/'barrier'; deadline=time.monotonic()+20
        while not marker.exists() and w.process.poll() is None and time.monotonic()<deadline: time.sleep(.01)
        check(marker.exists() and marker.read_text().splitlines()==[str(w.process.pid),barrier],'owned fault barrier')
        self.stop(1,kill=True)
        return dict(barrier=barrier,killedPid=w.process.pid,member=w.path.relative_to(self.root).as_posix())
    def cell(self,name,action):
        started=now(); self.configure(name)
        record=dict(name=name,startedNanos=started,status='RUNNING');self.cells.append(record);save(self.root/'cells.json',self.cells)
        try:
            record['details']=action() or {};record['status']='PASS'
        finally:
            record['finishedNanos']=now();save(self.root/'cells.json',self.cells)
        print(json.dumps(dict(cell=name,status=record['status'],elapsedSeconds=round((now()-started)/1e9,2))),flush=True)


def run(root,control, *, volume_layout=False, bundle=None):
    root=root.resolve();control=control.resolve();check(not root.exists(),'fresh qualification directory');root.mkdir(parents=True)
    raw=root/'raw';raw.mkdir();plan=read_plan();local=plan['localQualification'];(raw/'plan.json').write_bytes(PLAN.read_bytes())
    adapted=dict(localSmoke=dict(maximumRunSeconds=local['maximumRunSeconds'],cleanupReserveSeconds=local['cleanupReserveSeconds']),evidenceBounds=plan['evidenceBounds'])
    runner=Run(raw,adapted);group=None;success=False
    try:
        check(sha_file(control)==plan['publishedControl']['sha256'],'published control checksum')
        inputs=source_inputs();inputs[str(PLAN.relative_to(ROOT))]=sha_file(PLAN)
        if bundle:
            from .cloud_common import inventory as bundle_inventory, read as bundle_read
            bundle=Path(bundle).resolve();manifest=bundle_read(bundle/'bundle.json',16<<20)
            actual=bundle_inventory(bundle);actual.pop('bundle.json')
            inputs['docs/v5x/v5.0/phase6-runner-plan.json']=sha_file(ROOT/'docs/v5x/v5.0/phase6-runner-plan.json')
            check(manifest['schema']=='gse-v50-cloud-workload-bundle-v1' and manifest['execution']=='offline-workload-bundle-only' and
                  manifest['files']==actual and manifest['inputs']==inputs and manifest['workloadPlanSha256']==sha_file(PLAN),'offline workload bundle identity')
        with zipfile.ZipFile(raw/'source-inputs.zip','w',zipfile.ZIP_DEFLATED) as z:
            for name in inputs: z.write(ROOT/name,name)
        artifacts=raw/'artifacts';artifacts.mkdir();jars={}
        for name,path in [('core',CORE),('replication',REPLICATION),('control',control)]:
            if bundle:
                check(sha_file(path)==manifest['jars'][name],'bundle artifact identity');path=bundle/(name+'.jar')
            target=artifacts/(name+'.jar');shutil.copyfile(path,target);jars[name]=dict(path=str(target),sha256=sha_file(target))
        java_executable=str(bundle/'jre/bin/java') if bundle else 'java'
        metadata=dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),inputs=inputs,jars=jars,
            execution=local['execution'],bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            javaExecutable=java_executable,volumeLayout=volume_layout,
            arithmetic=arithmetic(plan),java=runner.process('java-version',[java_executable,'--version']),
            filesystem=runner.process('filesystem',['findmnt','-J','-T',str(raw),'-o','TARGET,SOURCE,FSTYPE,OPTIONS,SIZE']))
        save(raw/'metadata.json',metadata)
        source=ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch'
        names=['AdmissionJson','AdmissionSemanticModel','PerformanceWorkload','PerformanceTelemetry','CloudWorkloadTelemetry','CloudWorkloadSchedule','CloudWorkload']
        common=[source/'admission'/(n+'.java') for n in names]
        classes=raw/'classes-candidate';oracle=raw/'classes-control'
        cp=os.pathsep.join(jars[n]['path'] for n in ('core','replication'))
        if bundle:
            shutil.copytree(bundle/'classes-candidate',classes);shutil.copytree(bundle/'classes-control',oracle)
            save(raw/'offline-bundle.json',manifest)
        else:
            classes.mkdir();oracle.mkdir()
            runner.process('compile-consumer',['javac','--release','21','-proc:none','-cp',cp,'-d',classes,*common,source/'admission/V50CloudWorkloadConsumer.java'])
        cp+=os.pathsep+str(classes)
        if not bundle:
            runner.process('compile-observer',['javac','--release','21','-proc:none','-cp',cp,'-d',classes,source/'replication/V50CloudWorkloadWorker.java'])
            runner.process('compile-control',['javac','--release','21','-proc:none','-cp',jars['control']['path'],'-d',oracle,*common,source/'admission/V50CloudWorkloadControl.java'])
        java=[java_executable,*plan['jvmArguments']]
        control_args=[*java,'-cp',jars['control']['path']+os.pathsep+str(oracle),PACKAGE+'admission.V50CloudWorkloadControl']
        measured=runner.process('control-measure',[*control_args,'measure',raw,raw/'plan.json'],True);save(raw/'control.json',measured)
        metadata['sourceBackup']=inventory(raw/'source');save(raw/'metadata.json',metadata)
        group=Group(runner,cp,java,plan,volume_layout);group.offline('bootstrap');group.start_all();group.command('activate')
        cycle=0
        def healthy():
            nonlocal cycle
            windows=[]
            for name in ['warmup',*plan['workload']['windows']]:
                group.configure(name,name.startswith('instrumented'))
                count=local['warmupCycles'] if name=='warmup' else local['cyclesPerWindow']
                windows.append(group.command('measure',profile='local-qualification',window=name,firstCycle=cycle,calls=count*10,intervalNanos=local['healthyIntervalNanos'],sustained=False)['measurement']);cycle+=count
            return dict(windows=windows)
        group.cell('healthy',healthy)
        group.cell('sustained',lambda:dict(window=group.command('measure',profile='local-qualification',window='sustained',firstCycle=cycle,calls=local['sustainedCalls'],intervalNanos=local['sustainedIntervalNanos'],sustained=True)['measurement'],semantic=group.command('state',label='paired-steady')['semantic']))
        def unavailable():
            before=group.workers[3].command('status')['status'];group.command('fault',mode='block-node-3')
            for _ in range(local['isolationUpdates']):group.update();time.sleep(.1)
            during=group.workers[3].command('status')['status'];group.command('fault',mode='none');recovered=group.catchup(3)
            check(before['commitIndex']==during['commitIndex'],'isolated follower advanced')
            return dict(before=before,during=during,recovered=recovered)
        group.cell('unavailable',unavailable)
        def slow():
            group.workers[3].command('fault',mode='slow')
            for _ in range(2):group.update();time.sleep(.3)
            group.workers[3].command('fault',mode='none');return dict(recovered=group.catchup(3))
        group.cell('slow',slow)
        group.cell('incremental',unavailable)
        def snapshot():
            group.command('fault',mode='block-node-3');before=group.workers[3].command('status')['status']
            for _ in range(10):group.update()
            checkpoint=group.command('checkpoint');group.command('fault',mode='none')
            group.workers[3].command('fault',mode='lose-snapshot-ack');recovered=group.catchup(3);group.workers[3].command('fault',mode='none')
            check(checkpoint['status']['checkpointSequence']>before['sequence'],'snapshot path not forced')
            return dict(before=before,checkpoint=checkpoint,recovered=recovered)
        group.cell('snapshot',snapshot)
        def cut(name,barrier):
            group.revision+=1; receipt=group.kill_at(barrier,'update',id=5,revision=group.revision);group.close()
            reports=group.capture(name);group.start_all();recovered=group.command('activate')
            check(recovered['status']['sequence']==max(r['sequence'] for r in reports),'recovery lost proven prefix')
            return dict(**receipt,recovered=recovered)
        group.cell('entry-cut',lambda:cut('entry-cut','AFTER_ENTRY_QUORUM'))
        group.cell('proof-cut',lambda:cut('proof-cut','AFTER_PROOF_QUORUM'))
        def restart():
            before=group.command('status')['status'];after=group.restart()['status']
            check(after['epoch']>before['epoch'],'restart did not fence')
            from .hardening_harness import exact_read
            from . import admission_format as f
            request=next(r['request'] for r in rows(raw/'streams/node-1-1/ledger') if r['type']=='APPEND')
            ordinal=int(request['recipient'].split('-')[1])
            with socket.create_connection(('127.0.0.1',int(group.endpoints.split(',')[ordinal-1].split(':')[1])),timeout=5) as connection:
                connection.sendall(f.framed(f.TYPES.index(request['type'])+1,f.canonical(request),magic=b'GSRP'))
                header=exact_read(connection,48);length=struct.unpack_from('>i',header,12)[0];check(0<length<1<<20,'replay response bound')
                raw_response=header+exact_read(connection,length)
            genesis=f.genesis((group.authority(1)/'genesis.gsr').read_bytes());manifest=f.manifest((group.authority(1)/'manifest.gsr').read_bytes(),genesis)
            f.wire(raw_response,manifest);result=f.json_value(raw_response[48:])
            check(result['type']=='REJECT' and result['payload']['reason']=='STALE_EPOCH','stale incarnation accepted')
            return dict(before=before,after=after,staleRequest=request,staleResponse=result)
        group.cell('restart',restart)
        def replace(target,source):
            for i in (2,3):group.catchup(i)
            group.close();authority=group.authority(target);authority.rename(raw/f'lost-node-{target}')
            materialization=authority.parent/f'materialization-node-{target}'
            if materialization.exists(): materialization.rename(raw/f'lost-materialization-node-{target}')
            group.offline('replace',target,source)
            if target==3:
                group.start_all();group.command('activate');before=group.workers[3].command('status');result=group.catchup(3)
                return dict(before=before,recovered=result)
            group.start(1);group.start(2);refused=group.command('reconstruct',accepted=False)
            check(refused['reason']=='QUORUM_UNAVAILABLE','one-survivor reconstruction')
            group.start(3);return dict(oneSurvivor=refused,recovered=group.command('reconstruct'))
        group.cell('follower-replacement',lambda:replace(3,1))
        group.cell('leader-replacement',lambda:replace(1,2))
        def maintenance():
            group.update();exported=group.command('backup',target='export');retained=inventory(raw/'export')
            receipt=group.kill_at('AFTER_PUBLIC_BACKUP','backup',target='published-after-cut');group.close();group.start_all();group.command('activate')
            cancelled=group.command('backup-cancel',target='cancelled-backup');group.stop(1,already_closed=True);group.close()
            check(inventory(raw/'export')==retained and (raw/'published-after-cut').is_dir(),'published backup lost')
            group.start_all();group.command('activate')
            return dict(exported=exported,cut=receipt,cancelled=cancelled,exportInventory=retained)
        group.cell('maintenance',maintenance)
        def capacity():
            attempts=[]
            for attempt in range(3):
                group.update()
                before_path=raw/'capacity-sources'/f'before-{attempt}'
                before_path.parent.mkdir(exist_ok=True)
                shutil.copytree(group.authority(1),before_path)
                check(sum(p.stat().st_size for p in before_path.parent.rglob('*') if p.is_file())<=128<<20,'capacity diagnostic budget')
                w=group.workers[1];q=dict(command='checkpoint');e=dict(sentNanos=now(),request=q)
                w.receipt['exchanges'].append(e);save(w.path,w.receipt);w.process.stdin.write(json.dumps(q).encode()+b'\n');w.process.stdin.flush()
                r=w.receive();e.update(receivedNanos=now(),response=r);save(w.path,w.receipt);attempts.append(r)
                if not r['accepted']:
                    check(r['reason']=='CAPACITY_EXCEEDED','unexpected checkpoint failure')
                    after_path=raw/'capacity-sources'/'after-rejection';shutil.copytree(group.authority(1),after_path)
                    before_files=inventory(before_path,logical=True);after_files=inventory(after_path,logical=True)
                    check(before_files==after_files,'capacity rejection changed valid recovery sources')
                    return dict(attempts=attempts,beforePath=str(before_path.relative_to(raw)),afterPath=str(after_path.relative_to(raw)),sourceBefore=before_files,sourceAfter=after_files)
            raise ValueError('protected generation was not bounded')
        group.cell('capacity',capacity)
        def no_quorum():
            before=group.command('state',label='before-no-quorum')['semantic'];group.stop(2);group.stop(3)
            failure=group.command('update',accepted=False,id=5,revision=20000)
            after=group.command('state',label='after-no-quorum')['semantic']
            check(all(before[k]==after[k] for k in ('sequence','count','documentsSha256','indexCount')),'unproven write became readable')
            group.close();return dict(before=before,after=after,failure=failure)
        group.cell('no-quorum',no_quorum)
        if volume_layout:
            for i in (1,2,3): shutil.copytree(group.authority(i),raw/f'node-{i}')
        restored=runner.process('control-restore',[*control_args,'restore',raw,raw/'plan.json'],True);save(raw/'restore.json',restored)
        check(inventory(raw/'source')==metadata['sourceBackup'],'immutable source changed')
        actual=source_inputs();actual[str(PLAN.relative_to(ROOT))]=sha_file(PLAN)
        if bundle: actual['docs/v5x/v5.0/phase6-runner-plan.json']=sha_file(ROOT/'docs/v5x/v5.0/phase6-runner-plan.json')
        check(actual==inputs,'inputs changed during qualification')
        from .cloud_workload_evidence import measurements
        save(raw/'measurements.json',measurements(raw))
        save(raw/'set.json',dict(schema=plan['evidenceSchema'],execution=local['execution'],preset=local['preset'],planSha256=sha_file(PLAN),
                                startedNanos=runner.start,finishedNanos=now(),members=['node-1','node-2','node-3'],files=inventory(raw,exclude=('set.json',),logical=True)))
        pack(raw,root/'bundle')
        from .cloud_workload_evidence import validate
        result=validate(root/'bundle');save(root/'validation.json',result);print(json.dumps(result),flush=True);success=True
    finally:
        errors=[]
        for w in runner.workers:
            try:w.close(failed=not success)
            except Exception as error:errors.append(str(error))
        if not success:save(root/'failure.json',dict(status='FAIL',cleanupErrors=errors,finishedNanos=now()))
        check(not errors,'owned cleanup failure: '+'; '.join(errors))


if __name__=='__main__':
    def interrupted(signum,frame):raise RuntimeError('qualification interrupted: '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('workspace',type=Path);p.add_argument('--control-jar',required=True,type=Path)
    p.add_argument('--volume-layout',action='store_true');p.add_argument('--bundle',type=Path)
    a=p.parse_args();run(a.workspace,a.control_jar,volume_layout=a.volume_layout,bundle=a.bundle)
