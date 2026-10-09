"""One offline lease, immutable rich seed and complete fifteen-cell canonical run."""
from copy import deepcopy
from pathlib import Path
import time
from . import cloud_authority as a, cloud_package as package, cloud_workload_contract as contract
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import guest_owned_three_mode as shared, guest_shared_source, guest_bootstrap
from . import guest_owned_workload as rich, guest_owned_drill as drill

MODE='complete-canonical'
SCOPE='owned-complete-canonical'
CELLS=tuple(contract.load()['presets']['canonical']['cells'])
TAPES=package.CANONICAL_WORKLOADS


def validate_repetition(value):
    m.need(type(value) is int and value in (1,2,3),'owned canonical repetition')
    return value


def key(mode,cell):
    m.need((mode,cell) in TAPES,'owned canonical tape')
    return cell+'--'+mode


class Source(guest_shared_source.SharedSource):
    def __init__(self, output, member, **options):
        super().__init__(output,**options);self.repetition=validate_repetition(member)
    def selection(self, config):
        cell,preset=package.workload_selection(config)
        m.need(preset=='canonical' and config['workload'].get('repetition')==self.repetition,'shared canonical repetition')
        return key(config['mode'],cell),[key(mode,cell) for mode,cell in TAPES]
    def normalized(self, config):
        value=super().normalized(config)
        value['binding']['node']=self.config['binding']['node']
        value['workload']=deepcopy(self.config['workload'])
        return value


class Services(shared.Services):
    mode=MODE
    def __init__(self,*args,repetition,**kwargs):
        self.repetition=validate_repetition(repetition)
        super().__init__(*args,**kwargs)
    def prepare(self,req,facts,targets,startup,output,deadline,*,recheck,readiness):
        m.need(self.root is None and self.offline and req['member']=='experiment','owned canonical services scope/consumed')
        self.root=Path(output);self.root.mkdir(mode=0o700)
        self.source=Source(self.root/'shared-source',self.repetition,clock=self.clock,sleep=self.sleep)
        result=dict(status='FAIL',scope=SCOPE,repetition=self.repetition,requestSha256=a.validate_request(req),tapes=[],faults=[])
        try:
            for mode,cell in TAPES:
                name=key(mode,cell)
                group=self.group(mode=mode,canonical_cell=cell,canonical_repetition=self.repetition,bootstrap=self.seed())
                self.groups[name]=group
                answer=group.prepare(req,facts,targets,startup,self.root/name,deadline,recheck=recheck,readiness=readiness)
                result['tapes'].append(dict(mode=mode,cell=cell,receipt=answer))
            seeds={v['receipt']['bootstrap']['identity']['sourceSha256'] for v in result['tapes']}
            m.need(len(seeds)==1,'owned canonical shared seed disagreement')
            result['sourceSha256']=next(iter(seeds))
            for case in drill.CASES:
                group=self.group(fault_cell=case);self.groups[case]=group
                answer=group.prepare(req,facts,targets,startup,self.root/case,deadline,recheck=recheck,readiness=readiness)
                result['faults'].append(dict(case=case,receipt=answer))
            result['status']='PASS';return result
        finally:c.write_once(self.root/'receipt.json',result,maximum=262144)

    def retention_files(self):
        for name,raw in super().retention_files():
            yield ('canonical-services.json' if name=='three-mode-services.json' else name),raw


class Probe:
    execution=a.EXECUTION;scope=SCOPE;mode=MODE;require_physical=True;require_backup=True
    def __init__(self,services,output,*,clock=time.monotonic,sleep=time.sleep):
        m.need(services.offline is True and services.mode==MODE,'owned canonical services scope')
        self.services,self.clock,self.sleep=services,clock,sleep;self.repetition=validate_repetition(services.repetition)
        self.root=Path(output);self.root.mkdir(parents=True,mode=0o700);self.raw=self.root/'raw';self.raw.mkdir(mode=0o700)
        self.probes={};self.programs={};self.cells=[];self.attempted=[];self.prepared=False;self.stopped=False
        self.binding=m.sha(m.canonical(dict(scope=SCOPE,repetition=self.repetition,requestSha256=a.validate_request(services.provider.req))))
    @property
    def engineWorkloadExecuted(self):
        return any(p.engineWorkloadExecuted for p in self.probes.values()) or any(p.attempted for p in self.programs.values())
    def prepare(self,req,deadline):
        names=[key(mode,cell) for mode,cell in TAPES]+list(drill.CASES)
        m.need(not self.prepared and not self.probes and not self.programs and req==self.services.provider.req and
               req['member']=='experiment' and list(self.services.groups)==names,'owned canonical preparation/order')
        receipt=c.read(self.services.root/'receipt.json')
        m.need(receipt['status']=='PASS' and receipt['requestSha256']==a.validate_request(req) and
               receipt['repetition']==self.repetition,'owned canonical service admission')
        c.write_once(self.raw/'plan.json',dict(scope=SCOPE,repetition=self.repetition,request=req,services=receipt))
        (self.raw/'source').mkdir(mode=0o700)
        for name in guest_bootstrap.SOURCE:
            (self.raw/'source'/name).write_bytes((self.services.source.root/'seed/source'/name).read_bytes())
        for mode,cell in TAPES:
            name=key(mode,cell);group=self.services.groups[name]
            probe=rich.Probe(group,self.root/name,physical=mode in package.MODES[1:],backup=mode in package.MODES[1:],clock=self.clock,sleep=self.sleep)
            self.probes[name]=probe;probe.prepare(req,deadline)
        for case in drill.CASES:
            program=drill.Cell(self.services.groups[case],self.raw/case,case,clock=self.clock,sleep=self.sleep)
            self.programs[case]=program;program.prepare(req,deadline/1e9)
        self.prepared=True
    def cell(self,name,deadline):
        m.need(self.prepared and len(self.attempted)==len(self.cells) and len(self.cells)<len(CELLS) and
               name==CELLS[len(self.cells)],'owned canonical cell consumed/order')
        self.attempted.append(name)
        row=dict(cell=name,status='FAIL',startNanos=int(self.clock()*1e9),tapes=[])
        print(m.canonical(dict(cell=name,repetition=self.repetition,status='START')).decode(),flush=True)
        try:
            if name in ('healthy','read-heavy','sustained'):
                for mode,cell in TAPES:
                    if cell!=name:continue
                    probe=self.probes[key(mode,cell)];span=dict(mode=mode,status='FAIL',startNanos=int(self.clock()*1e9));row['tapes'].append(span)
                    try:
                        ceiling=300 if cell=='healthy' else next(v['seconds'] for v in contract.load()['cells'] if v['name']==cell)
                        end=min(deadline/1e9,self.clock()+ceiling)
                        probe.cell(cell,int(end*1e9))
                        m.need(not probe.close_voters(end) and self.clock()<=end,'owned canonical mode close/deadline')
                        span['status']='PASS'
                    finally:span['endNanos']=int(self.clock()*1e9)
                    print(m.canonical(dict(cell=cell,mode=mode,status=span['status'])).decode(),flush=True)
            else:self.programs[name].run(deadline)
            m.need(self.clock()<=deadline/1e9,'owned canonical cell deadline')
            row['status']='PASS';self.cells.append(name)
        finally:
            row['endNanos']=int(self.clock()*1e9);c.write_once(self.raw/(name+'-timeline.json'),row)
            print(m.canonical(dict(cell=name,repetition=self.repetition,status=row['status'],
                elapsedSeconds=round((row['endNanos']-row['startNanos'])/1e9,3))).decode(),flush=True)
    def stop(self):
        self.stopped=True
        for probe in self.probes.values():probe.stop()
    def collect_validate(self,output,deadline):
        m.need(self.stopped,'owned canonical collection before stop');errors=[]
        for name,probe in self.probes.items():
            print(m.canonical(dict(phase='canonical-collection',tape=name,status='START')).decode(),flush=True)
            try:
                failures,collected=probe.collect(deadline)
                errors.extend(dict(tape=name,**v) for v in failures)
                m.need(len(collected)==len(probe.nodes),'owned canonical collected member coverage')
            except (Exception,KeyboardInterrupt) as error:errors.append(dict(tape=name,message=str(error)[:2000]))
            finally:probe.raw.rename(self.raw/name);probe.raw=self.raw/name
        for name,program in self.programs.items():
            print(m.canonical(dict(phase='canonical-collection',cell=name,status='START')).decode(),flush=True)
            errors.extend(dict(case=name,**v) for v in program.collect(deadline/1e9))
        result=dict(status='FAIL',scope=SCOPE,mode=MODE,repetition=self.repetition,execution=self.execution,paidCloud=False,
            fullRemoteQualification=False,engineWorkloadExecuted=self.engineWorkloadExecuted,physicalHistoryQualified=False,
            backupRestoreQualified=False,cells=list(self.cells),errors=errors)
        try:
            # Close all daemons before CPU-heavy replay. Runner subsequently
            # verifies these same terminal stop receipts, without another write.
            m.need(self.clock()<deadline/1e9,'owned canonical collection deadline')
            self.services.stop(deadline/1e9)
            m.need(self.prepared and not errors and len(self.probes)==5 and
                   self.cells==list(CELLS) and self.clock()<deadline/1e9,'owned canonical incomplete/deadline')
            from .guest_canonical_evidence import bounded_replay
            from .remote_budget import CANONICAL_RETENTION_RESERVE_SECONDS
            replay_end=deadline/1e9-CANONICAL_RETENTION_RESERVE_SECONDS
            print(m.canonical(dict(phase='canonical-replay-budget',remainingSeconds=round(max(0,replay_end-self.clock()),3),
                                  retentionReserveSeconds=CANONICAL_RETENTION_RESERVE_SECONDS)).decode(),flush=True)
            result['aggregate']=bounded_replay(self.raw,self.root/'replay',replay_end,clock=self.clock)
            result.update(status='PASS',physicalHistoryQualified=True,backupRestoreQualified=True)
        except (Exception,KeyboardInterrupt) as error:errors.append(dict(phase='aggregate',message=str(error)[:2000]))
        c.write_once(self.raw/'validation.json',result,maximum=262144);return result
    def retention_files(self):
        parts.pack(self.raw,self.root/'retained',self.binding)
        for path in sorted((self.root/'retained').iterdir()):yield path.name,path.read_bytes()
