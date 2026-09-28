"""One complete automatic experiment healthy tape on already admitted services.

Offline qualification only: provider/block facts remain fixtures. Physical replay
is explicit; other modes/faults and paid acceptance stay open.
"""
from pathlib import Path
import os
import time
import uuid
from . import cloud_authority as a, cloud_package as package, performance_model as m
from . import remote_command as c, remote_collection as collection, remote_schedule as schedule
from . import guest_evidence

SCOPE='owned-automatic-healthy-experiment'


class Probe:
    execution=a.EXECUTION
    scope=SCOPE
    def __init__(self, services, output, *, physical=False, clock=time.monotonic, sleep=time.sleep):
        m.need(services.offline is True and services.mode==package.MODES[2] and services.bootstrap is not None,
               'owned workload requires offline automatic bootstrap')
        self.services,self.root,self.clock,self.sleep=services,Path(output),clock,sleep
        self.root.mkdir(parents=True,mode=0o700); self.raw=self.root/'raw';self.raw.mkdir(mode=0o700)
        self.clients=[];self.started=[];self.transcripts={};self.active=None;self.cells=[]
        self.attempted=False;self.engineWorkloadExecuted=False;self.stopped=False;self.prepared=False
        self.command_count=0;self.stop_attempted=set()
        m.need(type(physical) is bool,'owned physical scope');self.require_physical=physical
        self.binding=m.sha(m.canonical(dict(scope=SCOPE,requestSha256=a.validate_request(services.provider.req))))

    def execute(self, member, name, payload, deadline):
        node,client,cfg=member
        m.need(self.command_count<2000 and self.clock()<deadline,'owned workload command count/deadline')
        self.command_count+=1
        request=c.request(cfg['binding'],uuid.uuid4().hex,name,payload)
        folder=self.raw/'commands'/str(node)/request['commandId'];folder.mkdir(parents=True,mode=0o700)
        c.write_once(folder/'request.json',dict(config=cfg,request=request))
        try:
            receipt=c.submit_and_observe(client,request,deadline,clock=self.clock,sleep=self.sleep)
            c.write_once(folder/'receipt.json',receipt)
            self.transcripts.setdefault(node,[]).append(dict(request=request,receipt=receipt))
            return receipt
        except (Exception,KeyboardInterrupt) as error:
            c.write_once(folder/'failure.json',dict(type=type(error).__name__,message=str(error)[:2000]));raise

    def succeeded(self, member, name, payload, deadline):
        result=self.execute(member,name,payload,deadline)
        m.need(result['state']=='SUCCEEDED','owned guest command failed: '+str(result))
        return result

    def prepare(self, req, deadline):
        m.need(not self.prepared and req==self.services.provider.req and req['member']=='experiment', 'owned workload request/scope')
        complete=c.read(self.services.root/'receipt.json')
        m.need(complete['status']=='PASS' and complete['requestSha256']==a.validate_request(req) and
               complete['bootstrap']['status']=='PASS' and complete['bootstrap']['publicBootstrapVerified'] is True,
               'owned workload before admitted services/bootstrap')
        self.clients=list(self.services.clients)
        m.need([n for n,_,_ in self.clients]==[1,2,3] and len(complete['members'])==3,'owned workload member set')
        self.manifest=(self.services.archive.parent/'package/manifest.json').read_bytes()
        package.verify(self.services.archive.parent/'package',req['source'])
        for (node,client,cfg),member in zip(self.clients,complete['members']):
            m.need(client.config==cfg and cfg['mode']==package.MODES[2] and
                   cfg['binding']==c.binding(req['source'],req['bundleSha256'],req['attempt'],'node-'+str(node)) and
                   m.sha(self.manifest)==cfg['packageManifestSha256'] and member['node']==node and
                   member['configSha256']==m.sha(m.canonical(cfg)), 'owned workload client identity')
        c.write_once(self.raw/'plan.json',dict(scope=SCOPE,request=req,configs=[cfg for _,_,cfg in self.clients]))
        with (self.raw/'package-manifest.json').open('xb') as out:
            out.write(self.manifest);out.flush();os.fsync(out.fileno())
        c.sync_directory(self.raw)
        self.prepared=True
        m.need(self.clock()<deadline/10**9,'owned workload preparation deadline')

    def cell(self, name, deadline):
        m.need(self.prepared and not self.attempted and name=='healthy','owned workload cell consumed/scope')
        self.attempted=True;end=min(deadline/10**9,self.clock()+300)
        record=dict(scope=SCOPE,status='FAIL',startedNanos=int(self.clock()*10**9),windows=[])
        try:
            for member in self.clients:
                self.started.append(member);self.engineWorkloadExecuted=True
                self.succeeded(member,'start-voter',{},end)
            activation=min(end,self.clock()+30)
            while self.active is None:
                for member in self.clients:
                    answer=self.succeeded(member,'fault',dict(action='status'),activation)
                    state=answer['result']['status']['state'];m.need(state!='FAILED','owned voter failed')
                    if state=='LEADER_READY':self.active=member;break
                m.need(self.clock()<activation,'owned activation deadline')
                if self.active is None:self.sleep(.05)
            for spec in schedule.windows('healthy','experiment'):
                for member in self.clients:
                    if member[0]!=self.active[0]:self.succeeded(member,'fault',dict(action='configure',window=spec['window']),end)
                result=self.succeeded(self.active,'window',dict(cell='healthy',preset='experiment',window=spec['window']),end)
                m.need(result['result']['calls']==len(spec['calls']),'owned frozen window count')
                record['windows'].append(spec['window'])
            negative=self.execute(self.active,'collect',{},end)
            m.need(negative['state']=='FAILED' and negative['error']==dict(type='ValueError',message='guest collection requires stopped JVM'),
                   'owned live collection negative')
            if self.require_physical:
                from .guest_physical_evidence import converge
                converge(self.clients,self.active,lambda member,until:self.succeeded(member,'fault',dict(action='status'),until)['result']['status'],
                         end,clock=self.clock,sleep=self.sleep)
            self.cells.append(name);record['status']='EXECUTED'
        finally:
            record['endedNanos']=int(self.clock()*10**9)
            c.write_once(self.raw/'cell.json',record)
        m.need(self.clock()<=end,'owned healthy mode ceiling')

    def stop(self):
        # No background dispatcher: all windows above have their original receipts.
        # Close the JVMs under Runner's validation-retention deadline below.
        self.stopped=True

    def collect_validate(self, output, deadline):
        m.need(self.stopped,'owned workload collection before stop')
        end=deadline/10**9;errors=[];members=[];physical_members=[];physical=None
        for member in self.started:
            try:
                m.need(member[0] not in self.stop_attempted,'owned voter stop consumed')
                self.stop_attempted.add(member[0])
                self.succeeded(member,'stop-voter',dict(forced=False),end)
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(node=member[0],phase='stop',message=str(error)[:2000]))
        for member in self.started:
            node,client,cfg=member
            try:
                receipt=self.succeeded(member,'collect',{'physical':True} if self.require_physical else {},end);manifest=receipt['result']
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
                replay=self.root/('replay-node-'+str(node));collection.unpack(download,replay,binding)
                controller=dict(config=cfg,packageRoot=str(client.base),active=self.active is not None and node==self.active[0],
                                transcript=self.transcripts[node])
                c.write_once(folder/'controller.json',controller)
                validated=guest_evidence.validate(replay,cfg,self.manifest,client.base,controller['transcript'],active=controller['active'],healthy=True,physical=self.require_physical)
                c.write_once(folder/'validation.json',validated);members.append(validated)
                physical_members.append(dict(root=replay,controller=controller))
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(node=node,phase='collection-validation',message=str(error)[:2000]))
        if self.require_physical:
            try:
                from . import guest_physical_evidence
                physical=guest_physical_evidence.validate(physical_members,self.manifest)
                c.write_once(self.raw/'physical.json',physical)
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(phase='physical-validation',message=str(error)[:2000]))
        m.need(self.clock()<end,'owned validation deadline')
        valid=(self.cells==['healthy'] and len(members)==3 and sum(v['calls'] for v in members)==90 and not errors)
        result=dict(status='PASS' if valid else 'FAIL',execution=a.EXECUTION,scope=SCOPE,paidCloud=False,
            engineWorkloadExecuted=self.engineWorkloadExecuted,fullRemoteQualification=False,physicalHistoryQualified=physical is not None,
            cells=list(self.cells),members=members,errors=errors)
        c.write_once(self.raw/'validation.json',result);return result

    def retention_files(self):
        # All originals, including unresolved requests and partial downloads, fit
        # the existing complete binary inventory/part budgets. Never publish replay
        # scratch directories as a replacement for the original collected bytes.
        collection.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()
