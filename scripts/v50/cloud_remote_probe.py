"""Full public workload over bounded guest commands and owned persistent JVM streams."""
import json
import os
import re
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import time
import zipfile
from .cloud_common import ROOT, canonical, read, require, save
from .cloud_workload_io import inventory, pack, unpack, sha_file, relative
from .cloud_workload_plan import PLAN, PLAN_SHA256, arithmetic, read_plan
from .cloud_presets import preset
from .cloud_remote_guest import SCHEMA, EXECUTION
from .cloud_guest import BASE, ROOT as GUEST_ROOT


def now(): return time.monotonic_ns()


def collection_member(node,name):
    """Each guest may supply only its own process/authority namespace."""
    parts=relative(name).parts
    if parts[0] in (f'volume-{node}',f'lost-node-{node}'):
        return parts[0].startswith('lost-') or len(parts)>2 and parts[1]==f'node-{node}'
    if parts[0] in ('workers','stops','streams'):
        return len(parts)>1 and re.fullmatch(f'node-{node}-[1-9][0-9]*(\\.json)?',parts[1]) is not None
    if parts[0]=='cuts':return len(parts)>3 and parts[1] in ('entry-cut','proof-cut') and parts[2]==f'node-{node}'
    return node==1 and parts[0] in ('source','export','published-after-cut','operation','capacity-sources',
        'control-streams','restore-streams','control-measure','control-restore')


class RemoteWorker:
    def __init__(self, probe, node, generation):
        self.probe, self.node, self.generation = probe, node, generation
        self.path = probe.root / 'members' / f'node-{node}-{generation}.json'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt = dict(schema='gse-v50-cloud-workload-member-v1', node=f'node-{node}', generation=generation,
            streams=f'streams/node-{node}-{generation}', startedNanos=now(), exchanges=[], instanceId=probe.nodes[node]['id'])
        self.buffer = b''; self.stderr = self.path.with_suffix('.stderr').open('wb')
        self.process = probe.backend.worker(probe.nodes[node], probe.guest_args('worker', node, generation=generation), self.stderr)
        probe.all_workers.append(self); save(self.path, self.receipt)
        ready = self.receive(40)
        require(ready['ready'] and ready['node'] == f'node-{node}', 'remote worker readiness')
        retained = probe.guest(node, 'receipt', generation=generation)
        require(ready['identity']['pid'] == retained['pid'], 'remote ready/receipt PID')
        self.receipt.update(ready=ready, readyNanos=now(), pid=retained['pid'], args=retained['args'],
                            linuxStartTicks=retained['startTicks'], bootId=retained['bootId'])
        save(self.path, self.receipt)

    def receive(self, maximum=40):
        deadline = min(time.monotonic() + maximum, self.probe.deadline)
        while b'\n' not in self.buffer:
            wait = deadline-time.monotonic()
            require(wait > 0 and select.select([self.process.stdout], [], [], wait)[0], 'remote response deadline')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            require(chunk, 'remote JVM/SSH stream exited'); self.buffer += chunk
            require(len(self.buffer) <= 4 << 20, 'remote response bound')
        line, self.buffer = self.buffer.split(b'\n', 1)
        from .cloud_workload_io import parse_json
        return parse_json(line)

    def send(self, name, **values):
        request = dict(command=name, **values)
        exchange = dict(request=request, sentNanos=now(), outcome='indeterminate')
        self.receipt['exchanges'].append(exchange); save(self.path, self.receipt)
        self.process.stdin.write(canonical(request)+b'\n'); self.process.stdin.flush()
        return exchange

    def command(self, name, accepted=True, response_timeout=None, **values):
        exchange = self.send(name, **values)
        maximum = values['calls']*values['intervalNanos']/1e9+30 if name == 'measure' else 40
        if response_timeout is not None: maximum=min(maximum,response_timeout)
        result = self.receive(maximum)
        exchange.update(response=result, receivedNanos=now()); exchange.pop('outcome')
        save(self.path, self.receipt)
        require(result['command'] == name and (accepted is None or result['accepted'] is accepted),
                'remote public command failed: '+json.dumps(result))
        return result

    def close(self, *, killed=False, already_closed=False, barrier=None):
        if 'finishedNanos' in self.receipt: return
        try:
            if killed:
                stop = self.probe.guest(self.node, 'stop', generation=self.generation, barrier=barrier)
                require(stop['pid'] == self.receipt['pid'] and stop['startTicks'] == self.receipt['linuxStartTicks'], 'remote kill ownership')
            elif not already_closed: self.command('close')
            self.process.wait(timeout=15)
            if not killed: require(self.process.returncode == 0, 'remote normal exit')
            stop = self.probe.guest(self.node, 'stop', generation=self.generation)
            require(stop['status'] == 'EXITED', 'remote JVM was not reaped')
            self.receipt.update(finishedNanos=now(), exitCode=-9 if killed else 0, transportExitCode=self.process.returncode,
                cleanup='reaped', forced=killed)
        finally:
            if self.process.poll() is None:
                # Killing the SSH client is insufficient: stop the checked guest PID first.
                try: self.probe.guest(self.node, 'stop', generation=self.generation)
                finally: self.process.kill(); self.process.wait(timeout=10)
            save(self.path, self.receipt)
            self.process.stdin.close(); self.process.stdout.close(); self.stderr.close()


class RemoteProbe:
    def __init__(self, backend, archive, workspace, content, *, qualification=False):
        self.backend, self.archive, self.content = backend, Path(archive).resolve(), Path(content).resolve()
        self.root = Path(workspace).resolve() / 'runtime'; self.root.mkdir(parents=True)
        self.manifest = read(self.content / 'bundle.json', 16 << 20)
        require(self.manifest['schema'] == SCHEMA and self.manifest['execution'] == EXECUTION, 'remote bundle schema')
        self.plan = read_plan(); self.profile = 'local-qualification' if qualification else backend.request['profile']
        self.qualification = qualification; self.nodes = {}; self.hosts = {}; self.workers = {}; self.all_workers = []
        self.generations = {i: 0 for i in (1, 2, 3)}; self.cells = []; self.cycle = 0; self.revision = 10000
        self.endpoints = ''; self.completed = False; self.started = now(); self.runner = None
        maximum = self.plan['localQualification']['maximumRunSeconds'] if qualification else preset(self.profile)['plannedMaximumSeconds']
        self.deadline = time.monotonic()+maximum-30 if qualification else time.monotonic()+maximum-300
        self.guest_base = self.content if qualification else BASE
        self.guest_root = backend.guest_root if qualification else GUEST_ROOT
        shutil.copyfile(PLAN, self.root / 'plan.json')
        for name in ('classes-candidate', 'classes-control'): shutil.copytree(self.content / name, self.root / name)
        (self.root / 'artifacts').mkdir()
        for name in ('core', 'replication', 'control'): shutil.copyfile(self.content / (name+'.jar'), self.root / 'artifacts' / (name+'.jar'))
        with zipfile.ZipFile(self.root / 'source-inputs.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name in self.manifest['inputs']: archive.write(self.content / 'source-inputs' / name, name)
        save(self.root / 'remote-bundle.json', self.manifest)
        self.metadata = dict(head=backend.request['source'], dirty=self.manifest['dirty'], inputs=self.manifest['inputs'],
            execution='local-remote-workload-only' if qualification else 'gcp-cloud-workload', volumeLayout=True,
            javaExecutable=str(self.guest_base / 'jre/bin/java'), java=self.manifest['java'], arithmetic=arithmetic(self.plan),
            jars={n: dict(path=str(self.guest_base / (n+'.jar')), sha256=self.manifest['jars'][n]) for n in ('core','replication','control')})

    def guest_args(self, action, node, **values):
        args = ['python3', str(self.guest_base / 'guest.py'), action, '--node', str(node), '--owner', self.backend.request['owner'],
                '--endpoints', self.endpoints, '--profile', self.profile]
        if self.qualification: args += ['--qualification', '--base', str(self.guest_base), '--root', str(self.guest_root)]
        for name, value in values.items():
            if value is not None: args += ['--'+name.replace('_','-')] + ([] if value is True else [str(value)])
        return args

    def guest(self, node, action, **values):
        timeout = 930 if action == 'measure' else 150 if action in ('restore','bootstrap','replace','collect') else 40
        return self.backend.ssh(self.nodes[node], self.guest_args(action, node, **values), timeout=timeout)

    def prepare(self, instance):
        node = instance['node']; self.nodes[node] = instance
        if not self.qualification:
            deadline = time.monotonic()+120
            while True:
                try: self.backend.ssh(instance, ['python3','-c','print("{}")'], timeout=15); break
                except Exception:
                    if time.monotonic() >= deadline: raise
                    time.sleep(2)
            self.backend.copy(instance, self.archive, '/tmp/gse-v50-bundle.tar.gz')
            self.backend.copy(instance, self.content / 'install.py', '/tmp/gse-v50-install.py')
            distribution = self.backend.ssh(instance, ['sudo','python3','/tmp/gse-v50-install.py','install',
                '--archive','/tmp/gse-v50-bundle.tar.gz','--sha256',self.backend.request['bundleSha256'],'--remote-workload'])
            require(distribution['manifest'] == self.manifest, 'remote distribution manifest')
        else: distribution = dict(installed=True, manifest=self.manifest, bundleSha256=sha_file(self.archive), qualification=True)
        self.hosts[node] = dict(instance=instance, distribution=distribution, facts=self.guest(node,'facts'))

    def control(self, role):
        started = now(); receipt = self.guest(1, role)
        receipt['process'].update(startedNanos=started, finishedNanos=now())
        save(self.root / 'processes' / ('control-'+role+'.json'), receipt['process'])
        save(self.root / 'processes' / ('control-'+role+'.stdout'), receipt['result'])
        save(self.root / ('control.json' if role=='measure' else 'restore.json'), receipt)
        return receipt

    def bootstrap(self, instance):
        self.endpoints = self.backend.endpoints if self.qualification else ','.join(
            self.nodes[i]['observation']['networkInterfaces'][0]['networkIP']+':9700' for i in (1,2,3))
        self.control_result = self.control('measure'); self.metadata['sourceBackup'] = self.control_result['sourceBackup']
        for node in (1,2,3):
            self.hosts[node]['initialMount'] = self.mount(1, node, fresh=True)
        self.guest(1, 'bootstrap')

    def mount(self, host, node, fresh=False):
        if self.qualification:
            (self.guest_root / f'volume-{node}').mkdir(exist_ok=True)
            return dict(qualification=True, filesystems=[dict(target=str(self.guest_root / f'volume-{node}'), fstype='local-directory')])
        mounted=self.backend.ssh(self.nodes[host], self.guest_args('mount', node, fresh=fresh or None))
        disk=next(r for r in reversed(self.runner.rows('disks')) if r['purpose']=='data' and r['node']==node)
        observation=self.backend.describe(self.nodes[host])
        attachments=[d for d in observation['disks'] if d.get('deviceName')==f'gse-data-{node}']
        require(len(attachments)==1 and attachments[0]['source'].endswith('/disks/'+disk['name']) and
                attachments[0]['autoDelete'] is True,'owned volume attachment read-back')
        return dict(mounted,diskId=disk['id'],diskName=disk['name'],instanceId=self.nodes[host]['id'],attachment=attachments[0])

    def unmount(self, instance, disk):
        if not self.qualification: self.backend.ssh(instance, self.guest_args('unmount', disk['node']))

    def start(self, instance):
        node = instance['node']; require(node not in self.workers, 'worker already active')
        if self.generations[node] == 0 and node != 1: self.hosts[node]['runtimeMount'] = self.mount(node, node)
        self.generations[node] += 1
        self.workers[node] = RemoteWorker(self, node, self.generations[node])

    def start_all(self):
        for node in (1,2,3): self.start(self.nodes[node])

    def stop_node(self, node, **values):
        worker = self.workers.pop(node, None)
        if worker: worker.close(**values)

    def quiesce(self):
        for node in list(self.workers): self.stop_node(node)

    def command(self, name, **values): return self.workers[1].command(name, **values)
    def configure(self, name, enabled=False):
        for worker in self.workers.values(): worker.command('configure', window=name, enabled=enabled)
    def update(self):
        self.revision += 1; return self.command('update', id=5, revision=self.revision)

    def catchup(self, node):
        # A peer can finish a durable recovery batch after its RPC caller times out.
        # Resume through public catchUp only while the leader remains writable;
        # no safety rejection, cell deadline or run deadline may be bypassed.
        deadline=min(self.deadline,getattr(self,'cell_deadline',None) or self.deadline)
        result=None
        def diagnostic(message): return f'remote catchup node-{node} {message}; last response: '+json.dumps(result,sort_keys=True)
        for attempt in range(1,21):
            remaining=deadline-time.monotonic()
            require(remaining>0,diagnostic('deadline exhausted'))
            result = self.command('catchup', accepted=None, peer=f'node-{node}',response_timeout=remaining)
            require(time.monotonic()<=deadline,diagnostic('deadline exhausted'))
            if result['accepted']: return result
            require(result['reason'] in ('CAPACITY_EXCEEDED','QUORUM_UNAVAILABLE') and
                    result['status']['state']=='READY' and result['status']['writeQuorum'],diagnostic('rejected'))
            if attempt==20: raise ValueError(diagnostic('exhausted 20 attempts'))
            require(time.monotonic()+.05<deadline,diagnostic('deadline exhausted'))
            time.sleep(.05)

    def restart(self):
        self.quiesce(); self.start_all(); return self.command('activate')

    def kill_at(self, barrier, name, **values):
        worker = self.workers[1]; worker.command('arm', barrier=barrier); worker.send(name, **values)
        self.stop_node(1, killed=True, barrier=barrier)
        return dict(barrier=barrier, killedPid=worker.receipt['pid'], member=worker.path.relative_to(self.root).as_posix())

    def measure(self, name):
        local = self.plan['localQualification']; workload = self.plan['workload']
        sustained = name=='sustained'
        cycles = local['warmupCycles'] if name=='warmup' else local['cyclesPerWindow']
        if not self.qualification: cycles = workload['warmupSeconds'] if name=='warmup' else (120 if self.profile=='canonical' else 30)
        calls = (local['sustainedCalls'] if self.qualification else 6000) if sustained else cycles*10
        interval = (local if self.qualification else workload)['sustainedIntervalNanos' if sustained else 'healthyIntervalNanos']
        self.configure(name, name.startswith('instrumented') or sustained)
        result = self.command('measure', profile=self.profile, window=name, firstCycle=self.cycle, calls=calls,
            intervalNanos=interval, sustained=sustained)['measurement']
        if not sustained: self.cycle += cycles
        return result

    def preserve_disk(self, instance, disk): return self.guest(instance['node'], 'capture', label='lost')
    def initialize_replacement(self, source, disk):
        mounted = self.mount(source['node'], disk['node'], fresh=True)
        result = self.backend.ssh(source, self.guest_args('replace', disk['node'], source=source['node']), timeout=150)
        return dict(diskId=disk['id'], sourceNode=source['node'], mount=mounted, publicReceipt=result)
    def mount_replacement(self, instance, disk): return self.mount(instance['node'], disk['node'])
    def resume_replacement(self, target):
        if target==3:
            self.start_all(); self.command('activate'); before=self.workers[3].command('status')
            self.replacement = dict(before=before, recovered=self.catchup(3))
        else:
            self.start(self.nodes[1]); self.start(self.nodes[2]); refused=self.command('reconstruct', accepted=False)
            require(refused['reason']=='QUORUM_UNAVAILABLE', 'one-survivor reconstruction accepted')
            self.start(self.nodes[3]); self.replacement=dict(oneSurvivor=refused,recovered=self.command('reconstruct'))

    def fault_cell(self, name):
        if name in ('unavailable','incremental','slow','snapshot'):
            before=self.workers[3].command('status')['status']; slow=name=='slow'
            if slow: self.workers[3].command('fault',mode='slow')
            else: self.command('fault',mode='block-node-3')
            count=10 if name=='snapshot' or not self.qualification else 2
            for i in range(count):
                dispatched=time.monotonic()
                self.update()
                if not self.qualification:
                    due=dispatched+1
                    while time.monotonic()<due: time.sleep(min(.1,due-time.monotonic()))
                elif slow: time.sleep(.3)
            during=self.workers[3].command('status')['status']
            checkpoint=self.command('checkpoint') if name=='snapshot' else None
            self.command('fault',mode='none'); self.workers[3].command('fault',mode='none')
            if name=='snapshot': self.workers[3].command('fault',mode='lose-snapshot-ack')
            recovered=self.catchup(3);self.workers[3].command('fault',mode='none')
            if not slow: require(before['commitIndex']==during['commitIndex'],'isolated follower advanced')
            if checkpoint: require(checkpoint['status']['checkpointSequence']>before['sequence'],'snapshot path not selected')
            return dict(before=before,during=during,recovered=recovered,checkpoint=checkpoint)
        if name in ('entry-cut','proof-cut'):
            barrier='AFTER_ENTRY_QUORUM' if name=='entry-cut' else 'AFTER_PROOF_QUORUM'
            self.revision+=1; cut=self.kill_at(barrier,'update',id=5,revision=self.revision);self.quiesce()
            captured=[self.guest(i,'capture',label=name) for i in (1,2,3)]
            self.start_all();recovered=self.command('activate')
            require(recovered['status']['sequence']==max(v['report']['sequence'] for v in captured),'recovery lost proven prefix')
            return dict(cut, recovered=recovered)
        if name in ('restart','fencing'):
            before=self.command('status')['status'];after=self.restart()['status']
            require(after['epoch']>before['epoch'],'restart did not fence')
            return dict(before=before,after=after,**self.guest(1,'replay'))
        if name in ('follower-replacement','leader-replacement'):
            for node in (2,3): self.catchup(node)
            target,source=(3,1) if name=='follower-replacement' else (1,2)
            self.runner.replace_data_disk(target,source)
            return self.replacement
        if name=='maintenance':
            self.update();exported=self.command('backup',target='export')
            cut=self.kill_at('AFTER_PUBLIC_BACKUP','backup',target='published-after-cut')
            self.quiesce();self.start_all();self.command('activate')
            cancelled=self.command('backup-cancel',target='cancelled-backup');self.stop_node(1,already_closed=True)
            self.quiesce();self.start_all();self.command('activate')
            return dict(exported=exported,cut=cut,cancelled=cancelled)
        if name=='capacity':
            attempts=[]
            for attempt in range(3):
                self.update();before=self.guest(1,'capture',label=f'capacity-before-{attempt}')
                result=self.command('checkpoint',accepted=None);attempts.append(result)
                if not result['accepted']:
                    require(result['reason']=='CAPACITY_EXCEEDED','unexpected checkpoint rejection')
                    after=self.guest(1,'capture',label='capacity-after-rejection')
                    require(before['files']==after['files'],'capacity changed protected sources')
                    return dict(attempts=attempts,beforePath=before['path'],afterPath=after['path'],sourceBefore=before['files'],sourceAfter=after['files'])
            raise ValueError('capacity remained unbounded')
        if name=='no-quorum':
            before=self.command('state',label='before-no-quorum')['semantic'];self.stop_node(2);self.stop_node(3)
            failure=self.command('update',accepted=False,id=5,revision=20000)
            after=self.command('state',label='after-no-quorum')['semantic']
            require(all(before[k]==after[k] for k in ('sequence','count','documentsSha256','indexCount')),'unproven write became visible')
            # Keep the committed leader available until the end of the measured cell.
            return dict(before=before,after=after,failure=failure)
        raise ValueError('unknown workload cell: '+name)

    def exercise(self):
        warmup_started=now()
        self.command('activate')
        if not self.qualification: self.measure('warmup')
        warmup_finished=now();control_overhead=0;previous=warmup_finished
        save(self.root/'timing.json',dict(warmupStartedNanos=warmup_started,warmupFinishedNanos=warmup_finished))
        selected=[dict(name=n,seconds=0) for n in self.plan['localQualification']['cells']] if self.qualification else preset(self.profile)['cells']
        for spec in selected:
            name=spec['name'];self.configure(name)
            record=dict(name=name,startedNanos=now(),status='RUNNING');self.cells.append(record);save(self.root/'cells.json',self.cells)
            self.cell_deadline=None if self.qualification else record['startedNanos']/1e9+spec['seconds']
            control_overhead+=record['startedNanos']-previous
            try:
                if name=='healthy':
                    names=(['warmup'] if self.qualification else [])+self.plan['workload']['windows']
                    details=dict(windows=[self.measure(n) for n in names])
                elif name=='sustained': details=dict(window=self.measure(name))
                else: details=self.fault_cell(name)
                record['details']=details
                if name in ('healthy','sustained'):
                    self.command('state',label='paired-steady' if name==('sustained' if self.qualification or self.profile=='canonical' else 'healthy') else 'healthy-steady')
                if not self.qualification:
                    measured=details.get('windows',[details['window']] if 'window' in details else [])
                    if measured:
                        active=sum(w['calls']*w['intervalNanos'] for w in measured)
                        require(active==spec['seconds']*10**9,'frozen measurement allocation')
                        # SSH and ABBA transitions are separately charged to the existing
                        # candidate warmup/control allowance, never subtracted from samples.
                        record['measurementNanos']=active
                        record['controlOverheadNanos']=now()-record['startedNanos']-active
                        require(record['controlOverheadNanos']>=0,'measurement controller coverage')
                        control_overhead+=record['controlOverheadNanos']
                        allowance=self.plan['profiles'][self.profile]['reservationsSeconds'][2]*10**9
                        require(warmup_finished-warmup_started+control_overhead<=allowance,'candidate setup/control budget')
                    else:
                        budget=spec['seconds']*10**9;elapsed=now()-record['startedNanos']
                        record.update(workNanos=elapsed,budgetNanos=budget)
                        deadline=record['startedNanos']+budget
                        require(elapsed<=budget,f'cloud cell overrun: {name}; elapsed={elapsed/1e9:.3f}s, limit={spec["seconds"]}s')
                        while now()<deadline: time.sleep(max(0,min(.25,(deadline-now())/1e9)))
                record['status']='PASS'
            except Exception as error:
                record.update(status='FAIL',error=dict(type=type(error).__name__,message=str(error)[:2000]))
                raise
            finally:
                record['finishedNanos']=now();save(self.root/'cells.json',self.cells)
                self.cell_deadline=None
            previous=record['finishedNanos']
            if not self.qualification:
                require(warmup_finished-warmup_started+control_overhead<=self.plan['profiles'][self.profile]['reservationsSeconds'][2]*10**9,
                        'candidate setup/control budget')
            print(json.dumps(dict(cell=name,status=record['status'])),flush=True)
        self.quiesce();self.control('restore');self.completed=True

    def stop(self, instance):
        node=instance['node']
        if node in self.workers:self.stop_node(node,killed=not self.completed)
        for worker in self.all_workers:
            if worker.node==node and 'finishedNanos' not in worker.receipt: worker.close(killed=True)

    def collect(self, instance, target):
        node=instance['node'];receipt=self.guest(node,'collect')
        target=Path(target);chunks=target.with_name(target.name+'-chunks');chunks.mkdir(parents=True)
        manifest=receipt['manifest'];require(manifest['bytes']<=4<<30 and len(manifest['files'])<=2000,'guest collection budget')
        require(receipt['directory']==str(self.guest_root/f'collection-{node}') and
                all(collection_member(node,name) for name in manifest['files']),'guest collection namespace')
        raw=canonical(manifest);require(len(raw)<=16<<20,'collection manifest bound')
        self.backend.copy(instance, receipt['directory']+'/parts.json', chunks/'parts.json', download=True)
        require(sha_file(chunks/'parts.json')==receipt['manifestSha256'] and read(chunks/'parts.json',16<<20)==manifest,'collection manifest transfer')
        seen=set();total=0
        for item in manifest['files'].values():
            for part in item['parts']:
                require(re.fullmatch('chunk-[0-9]{4}\\.bin',part['path']) and part['path'] not in seen and
                        0<part['bytes']<=32<<20,'collection part identity/bound')
                seen.add(part['path']);total+=part['bytes'];require(total<=4<<30 and len(seen)<2000,'collection aggregate bound')
                self.backend.copy(instance,receipt['directory']+'/'+part['path'],chunks/part['path'],download=True)
                require((chunks/part['path']).stat().st_size==part['bytes'] and sha_file(chunks/part['path'])==part['sha256'],'collection part transfer')
        unpack(chunks,target);shutil.rmtree(chunks)
        for path in sorted(target.rglob('*')):
            if not path.is_file():continue
            name=path.relative_to(target);relative(name.as_posix());dest=self.root/name
            require(not dest.exists(),'duplicate guest evidence member');dest.parent.mkdir(parents=True,exist_ok=True);shutil.move(path,dest)
        shutil.rmtree(target)
        authority=self.root/f'volume-{node}/node-{node}'
        if authority.exists():shutil.copytree(authority,self.root/f'node-{node}')
        self.hosts[node]['collection']=receipt

    def validate(self, workspace):
        require(self.completed and len(self.hosts)==3,'incomplete remote workload')
        self.metadata.update(bootId=self.hosts[1]['facts']['bootId'],filesystem=self.hosts[1]['initialMount'])
        save(self.root/'metadata.json',self.metadata)
        save(self.root/'hosts.json',dict(schema='gse-v50-remote-workload-hosts-v1',qualification=self.qualification,
            request=self.backend.request,plan=self.backend.plan,endpoints=self.endpoints,hosts=[self.hosts[i] for i in (1,2,3)]))
        for cell in self.cells:
            if cell['name']=='maintenance':cell['details']['exportInventory']=inventory(self.root/'export')
        save(self.root/'cells.json',self.cells)
        from .cloud_workload_evidence import measurements
        save(self.root/'measurements.json',measurements(self.root))
        save(self.root/'set.json',dict(schema='gse-v50-remote-workload-evidence-v1',execution=self.metadata['execution'],
            preset=self.profile,planSha256=PLAN_SHA256,startedNanos=self.started,finishedNanos=now(),members=['node-1','node-2','node-3'],
            files=inventory(self.root,exclude=('set.json',),logical=True)))
        from .cloud_remote_evidence import validate_raw
        result=validate_raw(self.root,qualification=self.qualification)
        pack(self.root,Path(workspace)/'workload-evidence')
        save(Path(workspace)/'workload-validation.json',result)
        return result

    def retention_files(self, workspace):
        workspace=Path(workspace);bundle=workspace/'workload-evidence'
        if not bundle.exists():pack(self.root,bundle)  # Retain incomplete runs as failure evidence too.
        result={'workload-evidence/'+name:value for name,value in inventory(bundle).items()}
        for name in ('lifecycle.json','workload-validation.json','request.json','preflight.json','fresh-preflight.json','approval.json'):
            path=workspace/name
            if path.exists():
                require(path.stat().st_size<=16<<20,'retention receipt bound')
                result[name]=dict(bytes=path.stat().st_size,sha256=sha_file(path))
        require(sum(v['bytes'] for v in result.values())<=4<<30 and len(result)<=2000,'remote retained evidence budget')
        return result
