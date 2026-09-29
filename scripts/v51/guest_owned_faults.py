"""Two owned experiment fault cells under one lease; full preset remains open."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from . import cloud_authority as a, cloud_package as package, remote_command as c, performance_model as m
from . import guest_owned_services as owned, guest_owned_three_mode as shared, guest_owned_workload as healthy
from . import guest_package_delivery as delivery, remote_collection as parts
from .guest_fault_service import QUICK_CASES as CASES
from .remote_faults import documents, availability

MODE='experiment-faults'
SCOPE='owned-experiment-leader-loss-no-quorum'


class Services(shared.Services):
    mode=MODE
    cases=CASES
    def retention_files(self):
        for name,data in super().retention_files():
            yield ('fault-services.json' if name=='three-mode-services.json' else name),data
    def prepare(self, req, facts, targets, startup, output, deadline, *, recheck, readiness):
        m.need(self.root is None,'owned fault services consumed')
        self.root=Path(output);self.root.mkdir(mode=0o700)
        result=dict(status='FAIL',requestSha256=a.validate_request(req),cells=[])
        try:
            for case in self.cases:
                group=owned.Services(self.provider,self.archive,self.pool.endpoint,fault_cell=case,deliver=self.pool.deliver,
                    clock=self.clock,sleep=self.sleep,**self.options)
                self.groups[case]=group
                answer=group.prepare(req,facts,targets,startup,self.root/case,deadline,recheck=recheck,readiness=readiness)
                result['cells'].append(dict(case=case,receipt=answer))
            result['status']='PASS';return result
        finally:c.write_once(self.root/'receipt.json',result,maximum=262144)


class Cell:
    execute=healthy.Probe.execute
    succeeded=healthy.Probe.succeeded
    def __init__(self, services, root, case, *, clock=time.monotonic, sleep=time.sleep):
        self.services=services;self.raw=Path(root);self.raw.mkdir(mode=0o700)
        self.clients=services.clients;self.case=case;self.clock=clock;self.sleep=sleep;self.command_count=0;self.transcripts={}
        self.running={};self.stopped=set();self.history=[];self.progress_count=0;self.final_count=0;self.attempted=False
        self.record=dict(case=case,status='FAIL',seconds=240 if case=='maintenance' else 120,events=[],progress=[],finalReads=[],rejoins=[],cleanupErrors=[])
    def parallel(self, fn, members=None):
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(fn,v) for v in (self.clients if members is None else members)]
            results=[];errors=[]
            for future in futures:
                try:results.append(future.result())
                except BaseException as error:errors.append(error)
            if errors:raise errors[0]
            return results
    def prepare(self, req, deadline):
        c.write_once(self.raw/'plan.json',dict(scope=SCOPE,request=req,case=self.case,configs=[v[2] for v in self.clients]))
        (self.raw/'package-manifest.json').write_bytes((self.services.archive.parent/'package/manifest.json').read_bytes())
        prepared=self.parallel(lambda member:self.succeeded(member,'prepare-cell',{},deadline)['result'])
        m.need(len({(v['manifestSha256'],v['genesisSha256']) for v in prepared})==1 and all(v['source']=='EMPTY' for v in prepared),'fault bootstrap agreement')
    def member(self, node):return next(v for v in self.clients if 'node-'+str(v[0])==node)
    def event(self, name, **values):
        row=dict(event=name,controllerNanos=int(self.clock()*10**9),**values);self.record['events'].append(row);return row
    def start(self, member, restart=False):
        node='node-'+str(member[0]);self.running[node]=None
        answer=self.succeeded(member,'fault' if restart else 'start-voter',dict(action='restart') if restart else {},self.end)['result']
        self.running[node]=answer['identity'];self.stopped.discard(node)
    def stop_node(self, node, forced=False):
        if node in self.stopped:return
        self.stopped.add(node)  # Failed/uncertain stop is never submitted twice.
        return self.succeeded(self.member(node),'stop-voter',dict(forced=forced),self.end)['result']
    def status(self, node, deadline=None):
        value=self.succeeded(self.member(node),'fault',dict(action='status'),deadline or self.end)['result']['response']
        m.need(value['outcome']=='SUCCESS' and value['state']!='FAILED','owned fault status failed');return value
    def wait(self, fn, deadline, label):
        while self.clock()<min(deadline,self.end):
            result=fn()
            if result:return result
            self.sleep(.05)
        raise ValueError(label)
    def leader(self, deadline, exclude=()):
        def choose():
            for node in self.running:
                if node not in self.stopped and node not in exclude and self.status(node,deadline)['state']=='LEADER_READY':return node
        return self.wait(choose,deadline,'owned fault activation deadline')
    def call(self, node, kind, **values):
        m.need(len(self.history)<24,'owned fault operation cap')
        intent=f'call-{len(self.history)+1:02d}'
        record=dict(kind=kind,intentId=intent,node=node,startNanos=int(self.clock()*10**9),endNanos=None,outcome='PENDING',**values)
        self.history.append(record)
        answer=self.succeeded(self.member(node),'fault',dict(action='call',kind=kind,intentId=intent,**values),self.end)['result']
        response=answer['response'];identity=answer['identity']
        record.update(endNanos=int(self.clock()*10**9),outcome=response['outcome'],opId=response['opId'],pid=identity['pid'],generation=identity['generation'],response=response)
        for key in ('documents','reason','reasonCode'):
            if key in response:record[key]=response[key]
        availability(response,kind);return response
    def progress(self, deadline, exclude=()):
        while self.progress_count<4:
            tag=100+10*self.progress_count;self.progress_count+=1;node=self.leader(deadline,exclude)
            row=dict(node=node,tag=tag,startNanos=int(self.clock()*10**9));self.record['progress'].append(row)
            row['write']=self.call(node,'addAll',documents=documents(tag));row['read']=self.call(node,'read')
            row['endNanos']=int(self.clock()*10**9);m.need(self.clock()<=deadline,'owned fault progress deadline')
            if all(row[k]['outcome']=='SUCCESS' for k in ('write','read')):return node
        raise ValueError('owned fault progress attempts exhausted')
    def rejoin(self, node, through):
        start=self.clock();end=min(self.end,start+60)
        def caught():
            result=self.status(node,end);return result if result['provenIndex']>=through else None
        observed=self.wait(caught,end,'owned fault durable rejoin deadline')
        self.record['rejoins'].append(dict(node=node,through=through,startNanos=int(start*1e9),endNanos=int(self.clock()*1e9),observed=observed))
    def run(self, deadline):
        m.need(not self.attempted,'owned fault cell consumed');self.attempted=True
        self.end=min(deadline/1e9,self.clock()+self.record['seconds']);self.record['startNanos']=int(self.clock()*1e9)
        healer=None
        try:
            self.parallel(self.start);leader=self.leader(min(self.end,self.clock()+30))
            for tag in (10,20,30):m.need(self.call(leader,'addAll',documents=documents(tag))['outcome']=='SUCCESS','owned fault seed failed')
            seed=self.call(leader,'read');m.need(seed['outcome']=='SUCCESS','owned fault seed read failed')
            self.record.update(seedRead=seed,seedLeader=leader)
            start=self.event('fault-request',node=leader)['controllerNanos'];self.record['faultStartNanos']=start
            progress_end=min(self.end,start/1e9+60)
            if self.case=='leader-loss':
                self.stop_node(leader,True);active=self.progress(progress_end);through=self.status(active)['provenIndex']
                self.start(self.member(leader),True);self.rejoin(leader,through)
            elif self.case=='maintenance':
                self.maintenance(leader,progress_end)
            else:
                import threading
                self.parallel(lambda member:self.succeeded(member,'fault',dict(action='isolate'),self.end))
                self.event('isolated-all');errors=[]
                def release():
                    self.event('heal-request')
                    try:self.parallel(lambda member:self.succeeded(member,'fault',dict(action='heal'),self.end))
                    except BaseException as error:errors.append(str(error))
                healer=threading.Timer(15,release);healer.start()
                self.sleep(2)
                self.record['refusals']=[self.call(leader,'addAll',documents=documents(90)),self.call(leader,'read')]
                m.need(all(v['outcome']!='SUCCESS' for v in self.record['refusals']),'isolated voter served a public call')
                healer.join(max(.001,self.end-self.clock()));m.need(not healer.is_alive() and not errors,'owned network heal failed: '+str(errors))
                active=self.progress(progress_end)
                through=self.status(active)['provenIndex']
                for node in self.running:self.rejoin(node,through)
            while self.final_count<4:
                self.final_count+=1;active=self.leader(self.end);result=self.call(active,'read');self.record['finalReads'].append(result)
                if result['outcome']=='SUCCESS':break
            m.need(self.record['finalReads'][-1]['outcome']=='SUCCESS','owned fault final read failed')
            self.record['status']='EXECUTED'
        finally:
            if healer is not None:
                healer.cancel();healer.join(timeout=max(.001,min(5,self.end-self.clock())))
                if healer.is_alive():self.record['cleanupErrors'].append('heal thread remains active')
            def stop(member):
                node='node-'+str(member[0])
                if node in self.running:
                    try:self.stop_node(node)
                    except BaseException as error:self.record['cleanupErrors'].append(str(error))
            self.parallel(stop)
            if self.case=='maintenance' and self.record['status']=='EXECUTED' and not self.record['cleanupErrors']:
                try:self.record['restore']=self.succeeded(self.member(self.backup_node),'restore-backup',{},self.end)['result']
                except BaseException as error:self.record['cleanupErrors'].append('restore: '+str(error))
            self.record['endNanos']=int(self.clock()*1e9)
            c.write_once(self.raw/'receipt.json',self.record);c.write_once(self.raw/'history.json',self.history)
        m.need(not self.record['cleanupErrors'] and self.clock()<=self.end,'owned fault close/budget failed')
    def maintenance(self, leader, progress_end):
        intent=f'call-{len(self.history)+1:02d}'
        h=dict(kind='read',intentId=intent,node=leader,startNanos=int(self.clock()*1e9),endNanos=None,outcome='PENDING')
        self.history.append(h)
        member=self.member(leader)
        pending=self.succeeded(member,'fault',dict(action='pin',intentId=intent),self.end)['result']
        identity=pending['identity'];h.update(opId=pending['opId'],pid=identity['pid'],generation=identity['generation'])
        def state():return self.succeeded(member,'fault',dict(action='pin-state'),self.end)['result']
        self.record['cut']=self.wait(lambda:state()['cut'],progress_end,'owned maintenance pin not reached')
        self.parallel(lambda peer:self.succeeded(peer,'fault',dict(action='isolate',node=leader),self.end))
        active=self.progress(progress_end,exclude=(leader,));through=self.status(active)['provenIndex']
        self.parallel(lambda peer:self.succeeded(peer,'fault',dict(action='heal'),self.end))
        def installed():
            value=state();return value if value['installed'] else None
        observed=self.wait(installed,progress_end,'owned maintenance pin did not cross rejoin')
        m.need(observed['pending'],'owned maintenance pin completed early')
        self.event('release-pin',node=leader)
        released=self.succeeded(member,'fault',dict(action='release-pin'),self.end)['result']['response']
        h.update(endNanos=int(self.clock()*1e9),outcome=released['outcome'],response=released,documents=released.get('documents'))
        m.need(released['outcome']=='SUCCESS' and released['documents']==self.record['seedRead']['documents'],'owned maintenance captured view changed')
        self.record['pinnedRead']=released;self.rejoin(leader,through)
        self.wait(lambda:state()['unpinned'],self.end,'owned maintenance pin still retained')
        self.backup_node=self.leader(self.end)
        for kind in ('checkpoint','backup'):
            result=self.call(self.backup_node,kind);m.need(result['outcome']=='SUCCESS','owned maintenance failed: '+kind)
            self.record[kind]=result

    def collect(self, deadline):
        errors=[]
        for node,client,cfg in self.clients:
            try:
                result=self.succeeded((node,client,cfg),'collect',dict(physical=True),deadline)['result']
                binding=m.sha(m.canonical(cfg['binding']));parts.validate_manifest(result,binding)
                folder=self.raw/f'node-{node}';folder.mkdir();download=folder/'parts';download.mkdir()
                c.write_once(download/'parts.json',result)
                for part in result['parts']:
                    raw=client.part(part['name'],part['bytes'],deadline)
                    parts.receive_part(download,part,(raw[p:p+(1<<20)] for p in range(0,len(raw),1<<20)))
                c.write_once(folder/'controller.json',dict(config=cfg,packageRoot=str(client.base),transcript=self.transcripts[node]))
            except BaseException as error:errors.append(dict(node=node,message=str(error)[:2000]))
        return errors


class Probe:
    execution=a.EXECUTION;scope=SCOPE;mode=MODE;cases=CASES;require_physical=True;require_backup=False
    def __init__(self, services, output, *, clock=time.monotonic, sleep=time.sleep):
        m.need(services.offline and services.mode==self.mode,'owned fault services scope')
        self.services=services;self.root=Path(output);self.root.mkdir(mode=0o700,parents=True);self.raw=self.root/'raw';self.raw.mkdir()
        self.clock=clock;self.sleep=sleep;self.cells=[];self.programs={};self.stopped=False
        self.binding=m.sha(m.canonical(dict(scope=self.scope,requestSha256=a.validate_request(services.provider.req))))
    @property
    def engineWorkloadExecuted(self):return any(v.attempted for v in self.programs.values())
    def prepare(self, req, deadline):
        m.need(not self.programs and req==self.services.provider.req and req['member']=='experiment' and list(self.services.groups)==list(self.cases),'owned fault preparation scope/order')
        c.write_once(self.raw/'plan.json',dict(scope=self.scope,request=req))
        for case,group in self.services.groups.items():
            program=Cell(group,self.raw/case,case,clock=self.clock,sleep=self.sleep);self.programs[case]=program;program.prepare(req,deadline/1e9)
    def cell(self, name, deadline):
        m.need(len(self.cells)<len(self.cases) and name==self.cases[len(self.cells)],'owned fault cell order')
        self.programs[name].run(deadline);self.cells.append(name)
    def stop(self):self.stopped=True
    def collect_validate(self, output, deadline):
        m.need(self.stopped,'owned fault collection before stop');errors=[]
        for name,program in self.programs.items():errors.extend(dict(case=name,**v) for v in program.collect(deadline/1e9))
        result=dict(status='FAIL',scope=self.scope,mode=self.mode,execution=a.EXECUTION,paidCloud=False,fullRemoteQualification=False,
            engineWorkloadExecuted=self.engineWorkloadExecuted,physicalHistoryQualified=False,cells=self.cells,errors=errors)
        try:
            from .guest_fault_evidence import validate
            result['aggregate']=validate(self.raw,self.root/'replay',cases=self.cases,scope=self.scope)
            m.need(not errors and self.cells==list(self.cases) and self.clock()<deadline/1e9,'owned fault incomplete/deadline')
            result.update(status='PASS',physicalHistoryQualified=True)
        except BaseException as error:errors.append(dict(phase='validation',message=str(error)[:2000]))
        c.write_once(self.raw/'validation.json',result,maximum=262144);return result
    def retention_files(self):
        parts.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()


class MaintenanceServices(Services):
    mode='experiment-maintenance'
    cases=('maintenance',)


class MaintenanceProbe(Probe):
    mode=MaintenanceServices.mode
    scope='owned-maintenance-experiment'
    cases=MaintenanceServices.cases
