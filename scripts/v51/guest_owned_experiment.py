"""One modeled owned lease and package pool for the complete frozen experiment.

This qualifies real guest workload/SSH execution, not native cloud admission.
"""
from pathlib import Path
from types import SimpleNamespace
import time
from . import cloud_authority as a, cloud_package as package, performance_model as m, remote_command as c
from . import guest_owned_three_mode as healthy, guest_owned_faults as faults, guest_owned_services as owned
from . import remote_collection as parts
from .guest_fault_service import CASES as FAULTS

MODE='complete-experiment'
SCOPE='owned-complete-experiment'
CELLS=('healthy',*FAULTS)


class Services(healthy.Services):
    mode=MODE
    def prepare(self, req, facts, targets, startup, output, deadline, *, recheck, readiness):
        result=super().prepare(req,facts,targets,startup,output,deadline,recheck=recheck,readiness=readiness)
        groups=dict(self.groups)
        self.healthy=SimpleNamespace(offline=True,mode=healthy.MODE,groups=groups,root=self.root,source=self.source,
            provider=self.provider,archive=self.archive,clients=[v for g in groups.values() for v in g.clients])
        receipt=dict(status='FAIL',requestSha256=a.validate_request(req),healthy=result,cells=[])
        try:
            for case in FAULTS:
                group=owned.Services(self.provider,self.archive,self.pool.endpoint,fault_cell=case,deliver=self.pool.deliver,
                    clock=self.clock,sleep=self.sleep,**self.options)
                self.groups[case]=group
                answer=group.prepare(req,facts,targets,startup,self.root/case,deadline,recheck=recheck,readiness=readiness)
                receipt['cells'].append(dict(case=case,receipt=answer))
            receipt['status']='PASS';return receipt
        finally:c.write_once(self.root/'experiment-services.json',receipt,maximum=262144)
    def retention_files(self):
        yield from super().retention_files()
        if self.root is not None and (self.root/'experiment-services.json').exists():
            yield 'experiment-services.json',(self.root/'experiment-services.json').read_bytes()


class Probe:
    execution=a.EXECUTION;scope=SCOPE;mode=MODE;require_physical=True;require_backup=True
    def __init__(self, services, output, *, clock=time.monotonic, sleep=time.sleep):
        m.need(services.offline and services.mode==MODE,'owned experiment services scope')
        self.services=services;self.root=Path(output);self.root.mkdir(mode=0o700,parents=True);self.raw=self.root/'raw';self.raw.mkdir()
        self.clock=clock;self.sleep=sleep;self.cells=[];self.programs={};self.stopped=False;self.healthy=None;self.timeline=[]
        self.binding=m.sha(m.canonical(dict(scope=SCOPE,requestSha256=a.validate_request(services.provider.req))))
    @property
    def engineWorkloadExecuted(self):return bool(self.healthy and self.healthy.engineWorkloadExecuted) or any(v.attempted for v in self.programs.values())
    def prepare(self, req, deadline):
        m.need(self.healthy is None and not self.programs and req==self.services.provider.req and req['member']=='experiment' and
               list(self.services.groups)==[*package.MODES,*FAULTS],'owned experiment preparation/order')
        c.write_once(self.raw/'plan.json',dict(scope=SCOPE,request=req,services=c.read(self.services.root/'experiment-services.json')))
        self.healthy=healthy.Probe(self.services.healthy,self.root/'healthy',clock=self.clock,sleep=self.sleep)
        self.healthy.prepare(req,deadline)
        for case in FAULTS:
            program=faults.Cell(self.services.groups[case],self.raw/case,case,clock=self.clock,sleep=self.sleep)
            self.programs[case]=program;program.prepare(req,deadline/1e9)
    def cell(self, name, deadline):
        m.need(len(self.timeline)==len(self.cells) and len(self.cells)<len(CELLS) and name==CELLS[len(self.cells)],'owned experiment consumed/order')
        row=dict(cell=name,status='FAIL',startNanos=int(self.clock()*1e9));self.timeline.append(row)
        try:
            if name=='healthy':self.healthy.cell(name,deadline)
            else:self.programs[name].run(deadline)
            row['status']='PASS';self.cells.append(name)
        finally:
            row['endNanos']=int(self.clock()*1e9)
            c.write_once(self.raw/(name+'-timeline.json'),row)
    def stop(self):
        self.stopped=True
        if self.healthy:self.healthy.stop()
    def collect_validate(self, output, deadline):
        m.need(self.stopped,'owned experiment collection before stop');errors=[];reports=[]
        if self.healthy:
            try:reports.append(self.healthy.collect_validate(output,deadline))
            except BaseException as error:errors.append(dict(cell='healthy',message=str(error)[:2000]))
            finally:
                self.healthy.raw.rename(self.raw/'healthy');self.healthy.raw=self.raw/'healthy'
        for name,program in self.programs.items():errors.extend(dict(case=name,**v) for v in program.collect(deadline/1e9))
        result=dict(status='FAIL',scope=SCOPE,mode=MODE,execution=a.EXECUTION,paidCloud=False,fullRemoteQualification=False,
            engineWorkloadExecuted=self.engineWorkloadExecuted,physicalHistoryQualified=False,backupRestoreQualified=False,
            cells=self.cells,errors=errors)
        try:
            from .guest_experiment_evidence import validate
            result['aggregate']=validate(self.raw,self.root/'replay')
            m.need(not errors and reports and reports[0]['status']=='PASS' and self.cells==list(CELLS) and self.clock()<deadline/1e9,'owned experiment incomplete/deadline')
            result.update(status='PASS',physicalHistoryQualified=True,backupRestoreQualified=True)
        except BaseException as error:errors.append(dict(phase='validation',message=str(error)[:2000]))
        c.write_once(self.raw/'validation.json',result,maximum=262144);return result
    def retention_files(self):
        parts.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()
