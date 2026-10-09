"""One complete frozen tape on already admitted services.

Offline qualification only: provider/block facts remain fixtures. Physical replay
supports both replicated modes. Canonical tapes are explicit offline components;
they do not admit full presets or paid execution.
"""
from pathlib import Path
import os
import time
import uuid
from . import cloud_authority as a, cloud_package as package, performance_model as m
from . import remote_command as c, remote_collection as collection, remote_schedule as schedule
from . import guest_evidence
from . import native_experiment_timing as timing
from . import guest_workload_spec as workload

SCOPE='owned-automatic-healthy-experiment'
CONFIGURED_SCOPE='owned-configured-healthy-experiment'
LOCAL_SCOPE='owned-v44-healthy-experiment'
SCOPES={package.MODES[0]:LOCAL_SCOPE,package.MODES[1]:CONFIGURED_SCOPE,package.MODES[2]:SCOPE}


class Probe:
    execution=a.EXECUTION
    authority=a
    scope=SCOPE
    def __init__(self, services, output, *, physical=False, backup=False, clock=time.monotonic, sleep=time.sleep):
        m.need(services.offline is True and services.mode in SCOPES and services.bootstrap is not None,
               'owned workload requires offline mode/bootstrap')
        self._initialize(services,output,physical=physical,backup=backup,clock=clock,sleep=sleep)

    def _initialize(self, services, output, *, physical=False, backup=False, clock=time.monotonic, sleep=time.sleep):
        self.mode=services.mode;self.scope=SCOPES[self.mode]
        self.cell_name=getattr(services,'canonical_cell',None) or 'healthy'
        self.preset='canonical' if getattr(services,'canonical_cell',None) else 'experiment'
        if self.preset=='canonical':
            m.need(services.offline is True or self.authority.PAID_CLOUD and services.authority is self.authority,'owned canonical workload domain')
            m.need(self.mode==package.MODES[0] or physical and backup,'canonical replicated tape requires physical history and backup')
            self.scope=workload.scope(self.mode,self.cell_name)
        self.repetition=getattr(services,'canonical_repetition',None)
        selection=dict(mode=self.mode)
        if self.repetition:selection.update(execution='local-guest-service-only',workload=dict(cell=self.cell_name,preset=self.preset,repetition=self.repetition))
        self.nodes=package.service_nodes(selection)
        self.control_node=package.control_node(selection)
        m.need(type(physical) is bool and (not physical or self.mode in package.MODES[1:]),'owned physical scope');self.require_physical=physical
        m.need(type(backup) is bool and (not backup or physical), 'owned backup requires physical scope');self.require_backup=backup
        self.services,self.root,self.clock,self.sleep=services,Path(output),clock,sleep
        self.root.mkdir(parents=True,mode=0o700); self.raw=self.root/'raw';self.raw.mkdir(mode=0o700)
        self.clients=[];self.started=[];self.transcripts={};self.active=None;self.cells=[]
        self.attempted=False;self.engineWorkloadExecuted=False;self.stopped=False;self.prepared=False
        self.command_count=0;self.stop_attempted=set();self.stop_errors=[]
        self.binding=m.sha(m.canonical(dict(scope=self.scope,requestSha256=self.authority.validate_request(services.provider.req))))

    def execute(self, member, name, payload, deadline):
        node,client,cfg=member
        m.need(self.command_count<2000 and self.clock()<deadline,'owned workload command count/deadline')
        self.command_count+=1
        request=c.request(cfg['binding'],uuid.uuid4().hex,name,payload)
        folder=self.raw/'commands'/str(node)/request['commandId'];folder.mkdir(parents=True,mode=0o700)
        c.write_once(folder/'request.json',dict(config=cfg,request=request))
        start=int(self.clock()*10**9)
        try:
            options={}
            if timing.selected(self.services.provider.req):
                deadline=min(deadline,self.clock()+timing.COMMAND_SECONDS)
                options['limits']=dict(failures=timing.MAX_TRANSIENT_FAILURES,
                    uncertain=timing.MAX_UNCERTAIN_REPLIES,queries=timing.MAX_QUERIES)
            receipt=c.submit_and_observe(client,request,deadline,clock=self.clock,sleep=self.sleep,**options)
            c.write_once(folder/'receipt.json',receipt)
            self.transcripts.setdefault(node,[]).append(dict(request=request,receipt=receipt))
            return receipt
        except (Exception,KeyboardInterrupt) as error:
            c.write_once(folder/'failure.json',dict(type=type(error).__name__,message=str(error)[:2000]));raise
        finally:
            c.write_once(folder/'observation.json',dict(startNanos=start,endNanos=int(self.clock()*10**9)))

    def succeeded(self, member, name, payload, deadline):
        result=self.execute(member,name,payload,deadline)
        m.need(result['state']=='SUCCEEDED','owned guest command failed: '+str(result))
        return result

    def prepare(self, req, deadline):
        m.need(not self.prepared and req==self.services.provider.req and (req['member']=='experiment' or self.authority.PAID_CLOUD and req['member'].startswith('canonical-')), 'owned workload request/scope')
        complete=c.read(self.services.root/'receipt.json')
        m.need(complete['status']=='PASS' and complete['requestSha256']==self.authority.validate_request(req) and
               complete['bootstrap']['status']=='PASS' and complete['bootstrap']['publicBootstrapVerified'] is True,
               'owned workload before admitted services/bootstrap')
        self.clients=list(self.services.clients)
        m.need([n for n,_,_ in self.clients]==list(self.nodes) and
               [row['node'] for row in complete['members']]==list(self.nodes),'owned workload member set')
        self.manifest=(self.services.archive.parent/'package/manifest.json').read_bytes()
        package.verify(self.services.archive.parent/'package',req['source'])
        for (node,client,cfg),member in zip(self.clients,complete['members']):
            m.need(client.config==cfg and cfg['mode']==self.mode and
                   workload.selection(cfg)==(self.cell_name,self.preset) and
                   cfg.get('workload',{}).get('repetition')==self.repetition and
                   cfg['binding']==c.binding(req['source'],req['bundleSha256'],req['attempt'],'node-'+str(node)) and
                   m.sha(self.manifest)==cfg['packageManifestSha256'] and member['node']==node and
                   member['configSha256']==m.sha(m.canonical(cfg)), 'owned workload client identity')
        c.write_once(self.raw/'plan.json',dict(scope=self.scope,mode=self.mode,request=req,configs=[cfg for _,_,cfg in self.clients]))
        with (self.raw/'package-manifest.json').open('xb') as out:
            out.write(self.manifest);out.flush();os.fsync(out.fileno())
        c.sync_directory(self.raw)
        self.prepared=True
        m.need(self.clock()<deadline/10**9,'owned workload preparation deadline')

    def cell(self, name, deadline):
        m.need(self.prepared and not self.attempted and name==self.cell_name,'owned workload cell consumed/scope')
        limit=300 if name=='healthy' else timing.cell(self.services.provider.req,name)
        self.attempted=True;end=min(deadline/10**9,self.clock()+timing.control(self.services.provider.req,'mode',limit))
        record=dict(scope=self.scope,mode=self.mode,status='FAIL',startedNanos=int(self.clock()*10**9),windows=[])
        try:
            for member in self.clients:
                self.started.append(member);self.engineWorkloadExecuted=True
                self.succeeded(member,'start-voter',{},end)
            activation=min(end,self.clock()+timing.control(self.services.provider.req,'activation',30))
            if self.mode==package.MODES[0]:self.active=self.clients[0]
            if self.mode==package.MODES[1]:
                self.active=next(member for member in self.clients if 'node-'+str(member[0])==self.control_node)
                self.succeeded(self.active,'fault',dict(action='activate'),activation)
            while self.active is None:
                for member in self.clients:
                    answer=self.succeeded(member,'fault',dict(action='status'),activation)
                    state=answer['result']['status']['state'];m.need(state!='FAILED','owned voter failed')
                    if state=='LEADER_READY':self.active=member;break
                m.need(self.clock()<activation,'owned activation deadline')
                if self.active is None:self.sleep(.05)
            for spec in schedule.windows(self.cell_name,self.preset):
                for member in self.clients:
                    if member[0]!=self.active[0]:self.succeeded(member,'fault',dict(action='configure',window=spec['window']),end)
                result=self.succeeded(self.active,'window',dict(cell=self.cell_name,preset=self.preset,window=spec['window']),end)
                m.need(result['result']['calls']==len(spec['calls']),'owned frozen window count')
                record['windows'].append(spec['window'])
            negative=self.execute(self.active,'collect',{},end)
            m.need(negative['state']=='FAILED' and negative['error']==dict(type='ValueError',message='guest collection requires stopped JVM'),
                   'owned live collection negative')
            if self.require_physical:
                if self.require_backup:self.succeeded(self.active,'backup',{},end)
                from .guest_physical_evidence import converge
                converge(self.clients,self.active,lambda member,until:self.succeeded(member,'fault',dict(action='status'),until)['result']['status'],
                         end,mode=self.mode,clock=self.clock,sleep=self.sleep,
                         seconds=timing.control(self.services.provider.req,'convergence',30))
            self.cells.append(name);record['status']='EXECUTED'
        finally:
            record['endedNanos']=int(self.clock()*10**9)
            c.write_once(self.raw/'cell.json',record)
        m.need(self.clock()<=end,'owned healthy mode ceiling')

    def stop(self):
        # No background dispatcher: all windows above have their original receipts.
        # Close the JVMs under Runner's validation-retention deadline below.
        self.stopped=True

    def close_voters(self, deadline):
        # Final convergence precedes shutdown. Keep the observed issuer alive
        # while followers stop: a slow remote stop of the leader first leaves
        # a quorum that can elect and force a new cut behind the stopped voter.
        # Preserve start order for collection and partially attempted startup.
        leader=self.active[0] if self.active is not None else None
        closing=sorted(self.started,key=lambda member:member[0]==leader)
        # Reuse the original result, including failure. Never retry a stop mutation.
        for member in closing:
            if member[0] in self.stop_attempted:continue
            self.stop_attempted.add(member[0])
            try:self.succeeded(member,'stop-voter',dict(forced=False),deadline)
            except (Exception,KeyboardInterrupt) as error:
                self.stop_errors.append(dict(node=member[0],phase='stop',message=str(error)[:2000]))
        return list(self.stop_errors)

    def collect(self, deadline):
        """Retain original bytes for replay; collection alone never qualifies a tape."""
        m.need(self.stopped,'owned workload collection before stop')
        m.need(not getattr(self,'collection_attempted',False),'owned workload collection consumed')
        self.collection_attempted=True
        end=deadline/10**9;errors=list(self.close_voters(end));collected=[]
        if self.require_backup and self.active is not None and self.cells==[self.cell_name] and not errors:
            try:self.succeeded(self.active,'restore-backup',{},end)
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(node=self.active[0],phase='restore',message=str(error)[:2000]))
        for member in self.started:
            node,client,cfg=member
            try:
                backup=self.require_backup and self.active is not None and node==self.active[0]
                payload=dict(physical=True,backup=True) if backup else ({'physical':True} if self.require_physical else {})
                receipt=self.succeeded(member,'collect',payload,end);manifest=receipt['result']
                binding=m.sha(m.canonical(cfg['binding']));collection.validate_manifest(manifest,binding)
                folder=self.raw/('node-'+str(node));folder.mkdir(mode=0o700)
                download=folder/'parts';download.mkdir(mode=0o700)
                c.write_once(download/'parts.json',manifest)
                for part in manifest['parts']:
                    raw=client.part(part['name'],part['bytes'],end)
                    # Archive parts can be 8 MiB; receiver input blocks are at
                    # most 1 MiB. Preserve the original part length and digest.
                    collection.receive_part(download,part,(raw[p:p+(1<<20)] for p in range(0,len(raw),1<<20)))
                    m.need(self.clock()<end,'owned collection deadline')
                controller=dict(config=cfg,packageRoot=str(client.base),active=self.active is not None and node==self.active[0],
                                transcript=self.transcripts[node])
                c.write_once(folder/'controller.json',controller)
                collected.append(dict(node=node,folder=folder,controller=controller,backup=backup))
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(node=node,phase='collection-validation',message=str(error)[:2000]))
        return errors,collected

    def collect_validate(self, output, deadline):
        errors,collected=self.collect(deadline);end=deadline/10**9
        members=[];physical_members=[];physical=None
        for item in collected:
            node,folder,controller,backup=(item[k] for k in ('node','folder','controller','backup'))
            cfg=controller['config']
            try:
                replay=self.root/('replay-node-'+str(node))
                collection.unpack(folder/'parts',replay,m.sha(m.canonical(cfg['binding'])))
                validated=guest_evidence.validate(replay,cfg,self.manifest,controller['packageRoot'],controller['transcript'],active=controller['active'],healthy=True,physical=self.require_physical,backup=backup)
                c.write_once(folder/'validation.json',validated);members.append(validated)
                physical_members.append(dict(root=replay,controller=controller))
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(node=node,phase='collection-validation',message=str(error)[:2000]))
        if self.require_physical and self.prepared:
            try:
                from . import guest_physical_evidence
                physical=guest_physical_evidence.validate(physical_members,self.manifest,backup=self.require_backup)
                c.write_once(self.raw/'physical.json',physical)
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(phase='physical-validation',message=str(error)[:2000]))
        m.need(self.clock()<end,'owned validation deadline')
        valid=(self.prepared and self.cells==[self.cell_name] and [n for n,_,_ in self.started]==list(self.nodes) and
               len(members)==len(self.nodes) and sum(v['calls'] for v in members)==sum(len(s['calls']) for s in schedule.windows(self.cell_name,self.preset)) and not errors)
        result=dict(status='PASS' if valid else 'FAIL',execution=self.execution,scope=self.scope,mode=self.mode,paidCloud=self.authority.PAID_CLOUD,
            engineWorkloadExecuted=self.engineWorkloadExecuted,fullRemoteQualification=False,physicalHistoryQualified=physical is not None,
            backupRestoreQualified=physical is not None and physical.get('backupRestoreQualified',False),
            cells=list(self.cells),members=members,errors=errors)
        c.write_once(self.raw/'validation.json',result);return result

    def retention_files(self):
        # All originals, including unresolved requests and partial downloads, fit
        # the existing complete binary inventory/part budgets. Never publish replay
        # scratch directories as a replacement for the original collected bytes.
        collection.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()
