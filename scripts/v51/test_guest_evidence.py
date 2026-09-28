"""Synthetic replay fixtures; these tests never claim to execute a workload JVM."""
from copy import deepcopy
import gzip
from pathlib import Path
import tempfile
import unittest
from . import guest_evidence as e, cloud_package as package, cloud_workload_contract as contract
from . import remote_command as c, remote_collection as parts, remote_schedule as schedule
from . import remote_schedule_evidence as scheduling, performance_plan as plan, performance_model as m
from .test_guest_service import config


class Fixture:
    def __init__(self, root, mode=package.MODES[2], active=True):
        self.root, self.active = root, active; self.config = config(root/'remote-cell'); self.config['mode'] = mode
        if not active: self.config['binding']['node'] = 'node-2'
        self.node = 'local' if mode == package.MODES[0] else self.config['binding']['node']
        self.base = '/remote/verified-package'; env = contract.load()['environment']
        jars = ['artifacts/core.jar'] if self.node == 'local' else ['artifacts/core.jar','artifacts/replication.jar']
        local = 'source-inputs/docs/v5x/v5.1/phase6-plan.json'
        self.manifest = m.canonical(dict(source=self.config['binding']['source'],jvmArguments=env['jvmArguments'],
            modes={mode:dict(jars=jars,classes='classes-'+mode,main=package.MAINS[mode])},
            files=[dict(path=local,sha256=m.sha(plan.PLAN.read_bytes())),*[dict(path=n,sha256='a'*64) for n in jars]]))
        self.config['packageManifestSha256'] = m.sha(self.manifest)
        self.service = dict(pid=101,bootId='11111111-1111-4111-8111-111111111111',startTicks='100')
        args = [self.base+'/runtime/bin/java',*env['jvmArguments'],'-cp',
            ':'.join(self.base+'/'+n for n in [*jars,'classes-'+mode]),package.PACKAGE+package.MAINS[mode],
            self.config['root'],'run' if self.node == 'local' else self.node[-1],self.base+'/'+local,self.config['root']+'/source']
        self.os = dict(pid=102,bootId=self.service['bootId'],startTicks='101',args=args)
        identity = dict(pid=102,node=self.node,mode=mode,generation=1,javaMajor=21,processors=2,
            jvmArguments=env['jvmArguments'],javaVendor=env['javaVendor'],javaRuntime=env['javaRuntime'],
            host={'os':'Linux'},observedClockResolutionNanos=1,planFileSha256=m.sha(plan.PLAN.read_bytes()))
        for kind,name in zip(('core','replication'),jars): identity.update({kind+'Source':self.base+'/'+name,kind+'Sha256':'a'*64})
        self.transcript=[]; self.exchanges=[]; self.results=[]; self.files={}
        self.control('start-voter',{},dict(status='STARTED',identity=identity),1_000_000_000,1_050_000_000)
        status = self.exchange('status',{},1_060_000_005,1_060_000_015)
        status['status'] = dict(state='LEADER_READY' if active else 'FOLLOWER')
        self.control('fault',{'action':'status'},status,1_060_000_000,1_070_000_000)
        self.events=[]; self.spec=schedule.windows('healthy','experiment')[0]
        self.state=m.initial(plan.load())
        if active:
            self.exchange('configure',{'window':'warmup'},1_200_000_000,1_300_000_000)
            window=schedule.WindowState(self.spec,2_000_000_000,self.events.append)
            for call in self.spec['calls']:
                now=window.start+call['dueMillis']*10**6
                window.offer(call,now); window.invoke(call['ordinal'],now)
                response=self.exchange('call',call,now+5,now+15)
                before=self.state.sequence; answer=None
                if call['operation'] in m.OP_IDS: self.state.apply(m.OP_IDS[call['operation']],bytes.fromhex(call['payload']))
                else: answer=self.state.answer(call['operation'],call['cycle'])
                response['call']=dict({k:call[k] for k in ('ordinal','window','cycle','operation','keys','lane')},
                    outcome='SUCCESS',payloadSha256=m.sha(bytes.fromhex(call['payload'])),answer=answer,
                    answerSha256=m.sha(m.canonical(answer)),beforeSequence=before,afterSequence=self.state.sequence,
                    apiStartNanos=now+7,apiEndNanos=now+13)
                window.complete(call['ordinal'],now+20,dict(outcome='SUCCESS',opId=response['opId'],resultSha256=m.sha(m.canonical(response))))
            self.window=window.finish(window.start+self.spec['durationNanos'])
            result=dict(window='warmup',calls=len(self.spec['calls']),validation=scheduling.validate(self.spec,self.events,self.window))
            self.control('window',dict(cell='healthy',preset='experiment',window='warmup'),result,1_100_000_000,12_100_000_000)
            negative=self.control('collect',{},None,12_200_000_000,12_300_000_000)
            negative.pop('result');negative.update(state='FAILED',error=dict(type='ValueError',message='guest collection requires stopped JVM'))
        self.exchange('close',{},13_010_000_000,13_020_000_000)
        self.control('stop-voter',{'forced':False},{'stopped':True},13_000_000_000,14_000_000_000)
        self.control('collect',{},None,15_000_000_000,16_000_000_000)
        self.stopped=dict(self.os,exitCode=0,forced=False,readerReaped=True)
        self.samples=[]
        for i,when in enumerate(range(14)):
            boundary='start' if i==0 else 'closed' if i==13 else 'periodic'
            self.samples.append(self.sample(i+1,when*10**9,boundary))
        if active:
            self.samples.insert(2,self.sample(0,1_500_000_000,'window-start'))
            for i,row in enumerate(self.samples,1):row['order']=i
        self.trace=[dict(order=1,node=self.node,pid=102,localNanos=1,event='FIXTURE',generation=1,groupId=self.config['groupId'])]

    def sample(self, order, when, boundary):
        queues = dict(admissionAvailable=4,inboundAvailable=8,outboundAvailable={'peer':2},pinsBytes=0,stagingBytes=0,
            queuedBytes=0,authorityDiskBytes=0,transferDiskBytes=0,maintenancePending=0,
            **{k:0 for k in ('orderedQueue','deadlinesQueue','inputsQueue','completionsQueue','networkQueue','appQueue','clientsQueue')})
        return dict(order=order,node=self.node,pid=102,mode=self.config['mode'],boundary=boundary,window='warmup',
            localNanos=when,samplingStartNanos=when,heapUsedBytes=1,heapMaxBytes=2,VmRSSBytes=1,VmHWMBytes=2,
            threads=1,gcCount=0,gcMillis=0,cpuNanos=0,retainedBytes=0,processIo={},queues=queues,
            evidenceWriter=dict(queuedBytes=0,peakBytes=0,queuedRecords=0,peakRecords=0))

    def control(self, name, payload, result, start, end):
        request=c.request(self.config['binding'],f'{len(self.transcript)+1:032x}',name,payload)
        receipt=dict(schema='gse-v51-command-receipt-v1',bindingSha256=request['bindingSha256'],
            commandId=request['commandId'],requestSha256=m.sha(m.canonical(request)),state='SUCCEEDED',
            process=deepcopy(self.service),startedNanos=start,endedNanos=end,result=result)
        self.transcript.append(dict(request=request,receipt=receipt));return receipt

    def exchange(self, name, fields, start, end):
        request=dict(command=name,opId=f'{self.node}-g1-{len(self.exchanges)+1}',**fields)
        response=dict(command=name,opId=request['opId'],node=self.node,pid=102,mode=self.config['mode'],
            outcome='SUCCESS',workerStartNanos=start+1,workerEndNanos=end-1)
        self.exchanges.append(dict(request=request,response=response,startNanos=start,endNanos=end,outcome='SUCCESS'))
        self.results.append(response);return response

    def render(self):
        self.root.mkdir()
        def save(name,value):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(m.canonical(value)+b'\n')
        save('store/binding.json',self.config['binding'])
        for row in self.transcript[:-1]:
            receipt=row['receipt']; folder='store/commands/'+row['request']['commandId']+'/'
            save(folder+'request.json',row['request']);save(folder+'terminal.json',receipt)
            started={k:v for k,v in receipt.items() if k not in ('result','error','endedNanos')};started['state']='RUNNING'
            save(folder+'started.json',started)
        for suffix,value in [('jvm',self.os),('exchanges',self.exchanges),('stop',self.stopped)]: save(self.node+'-'+suffix+'.json',value)
        (self.root/(self.node+'-stderr.log')).write_bytes(b'')
        for kind,rows in [('results',self.results),('samples',self.samples),*([('trace',self.trace)] if self.node!='local' else [])]:
            (self.root/(self.node+'-'+kind+'.jsonl.gz')).write_bytes(gzip.compress(b''.join(m.canonical(r)+b'\n' for r in rows)))
        if self.active:
            save('window-healthy-warmup/spec.json',self.spec);save('window-healthy-warmup/result.json',self.window)
            (self.root/'window-healthy-warmup/arrivals.jsonl').write_bytes(b''.join(m.canonical(r)+b'\n' for r in self.events))
        for name,data in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        self.reseal()

    def reseal(self):
        index=self.root/parts.INDEX
        if index.exists():index.unlink()
        index.write_bytes(m.canonical(parts.inventory(self.root))+b'\n')
        self.transcript[-1]['receipt']['result']=dict(schema='gse-v51-binary-evidence-v1',bindingSha256=m.sha(m.canonical(self.config['binding'])),
            workloadSha256=contract.PLAN_SHA256,memberIndexSha256=m.sha(index.read_bytes()),compressedBytes=1,
            parts=[dict(name='part-0000.bin',bytes=1,sha256=m.sha(b'x'))])

    def validate(self):return e.validate(self.root,self.config,self.manifest,self.base,self.transcript,active=self.active)


class GuestEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.serial=0
    def fixture(self, **kwargs):
        self.serial+=1;return Fixture(self.root/str(self.serial),**kwargs)
    def test_three_modes_and_passive_voter_independently_replay(self):
        for mode,active in [(m,True) for m in package.MODES]+[(m,False) for m in package.MODES[1:]]:
            with self.subTest(mode=mode,active=active):
                f=self.fixture(mode=mode,active=active);f.render();result=f.validate()
                self.assertEqual(result['calls'],10 if active else 0);self.assertEqual(result['status'],'PASS')
                self.assertFalse(result['physicalHistoryQualified']);self.assertFalse(result['fullRemoteQualification'])
    def reject(self, mutate, message=None, **kwargs):
        f=self.fixture(**kwargs);mutate(f);f.render()
        with self.assertRaisesRegex((ValueError,KeyError),message or '.') : f.validate()
    def test_resealed_semantically_wrong_read_rejected(self):
        def change(f):
            response=f.results[-2];response['call'].update(answer=[],answerSha256=m.sha(m.canonical([])))
            for row in [*f.events,*f.window['calls']]:
                if 'result' in row and row['result']['opId']==response['opId']:row['result']['resultSha256']=m.sha(m.canonical(response))
        self.reject(change,'logical answer')
    def test_resealed_changed_frozen_request_rejected(self):
        self.reject(lambda f:f.exchanges[2]['request'].update(payload='00'),'frozen JVM request')
    def test_original_journal_cannot_disagree_with_pipe_response(self):
        def change(f):f.results[2]=dict(f.results[2],pid=999)
        self.reject(change,'request/result binding')
    def test_duplicate_missing_or_extra_jvm_results_rejected(self):
        for mutation in (lambda f:f.results.pop(),lambda f:f.results.append(f.results[0]),lambda f:f.results.__setitem__(1,f.results[0])):
            with self.subTest(mutation=mutation):self.reject(mutation)
    def test_issuer_and_window_scope_not_inferred_from_guest(self):
        f=self.fixture();f.render();f.active=False
        with self.assertRaisesRegex(ValueError,'issuer coverage'):f.validate()
        self.reject(lambda f:f.spec.update(preset='canonical'),'frozen warmup')
    def test_unplanned_jvm_command_rejected(self):
        def change(f):
            row=f.exchanges[0];row['request']['command']='backup';row['response']['command']='backup'
            f.transcript[1]['request']['payload']['action']='backup'
            f.transcript[1]['receipt']['requestSha256']=m.sha(m.canonical(f.transcript[1]['request']))
        self.reject(change,'control/JVM binding')
    def test_controller_and_guest_terminal_receipts_must_match(self):
        f=self.fixture();f.render();f.transcript[0]['receipt']=dict(f.transcript[0]['receipt'],endedNanos=1_050_000_001)
        with self.assertRaisesRegex(ValueError,'retained/controller'):f.validate()
    def test_package_source_and_loaded_artifact_drift_rejected(self):
        self.reject(lambda f:f.config.update(packageManifestSha256='0'*64),'package binding')
        self.reject(lambda f:f.transcript[0]['receipt']['result']['identity'].update(coreSha256='0'*64),'artifact identity')
        self.reject(lambda f:f.transcript[0]['receipt']['result']['identity'].update(javaRuntime='22'),'JVM configuration')
    def test_boot_pid_args_and_stop_drift_rejected(self):
        for change in (lambda f:f.os.update(bootId='22222222-2222-4222-8222-222222222222'),
                       lambda f:f.os.update(pid=101),lambda f:f.os['args'].append('--extra'),lambda f:f.stopped.update(forced=True)):
            with self.subTest(change=change):self.reject(change)
    def test_resealed_sequence_hash_and_arrival_result_drift_rejected(self):
        for change in (lambda f:f.exchanges[2]['response']['call'].update(beforeSequence=999),
                       lambda f:f.exchanges[2]['response']['call'].update(afterSequence=999),
                       lambda f:f.exchanges[2]['response']['call'].update(payloadSha256='0'*64),
                       lambda f:f.window['calls'][0]['result'].update(resultSha256='0'*64)):
            with self.subTest(change=change):self.reject(change)
    def test_resealed_extra_passive_command_and_extra_window_rejected(self):
        def change(f):
            row=f.exchanges[0];row['request']['command']='configure';row['response']['command']='configure'
        self.reject(change,active=False)
        self.reject(lambda f:f.samples[3].update(boundary='window-start'),active=False)
    def test_resealed_receipt_reorder_and_failure_upgrade_rejected(self):
        self.reject(lambda f:f.transcript[2]['receipt'].update(startedNanos=0),'lifetime/order')
        def change(f):
            row=next(r for r in f.transcript if r['receipt']['state']=='FAILED')
            row['receipt']['error']['message']='some other failure'
        self.reject(change,'unexpected failed command')
        def upgrade(f):next(r for r in f.transcript if r['receipt']['state']=='FAILED')['receipt']['state']='SUCCEEDED'
        self.reject(upgrade,'unexpected failed command')
    def test_resource_trace_and_sampling_bounds_rejected(self):
        for change in (lambda f:f.samples[-1]['queues'].update(maintenancePending=1),
                       lambda f:f.samples.pop(4),lambda f:f.samples[0].update(pid=999),
                       lambda f:f.samples[-1]['evidenceWriter'].update(peakRecords=257),
                       lambda f:f.trace[0].update(groupId='22222222-2222-4222-8222-222222222222')):
            with self.subTest(change=change):self.reject(change)
    def test_resealed_unexpected_files_and_journal_segment_gap_rejected(self):
        self.reject(lambda f:f.files.update({'node-3-secret':b'other member'}),'closed inventory')
        self.reject(lambda f:f.files.update({f.node+'-results-part0002.jsonl.gz':gzip.compress(b'{}\n')}),'segment identity')
    def test_changed_inventory_and_truncated_gzip_rejected(self):
        f=self.fixture();f.render();path=f.root/(f.node+'-results.jsonl.gz');path.write_bytes(path.read_bytes()[:-4])
        with self.assertRaisesRegex(ValueError,'inventory changed'):f.validate()
        f.reseal()
        with self.assertRaises((ValueError,EOFError)):f.validate()
    def test_symlink_and_missing_terminal_cannot_be_replayed(self):
        f=self.fixture();f.render();(f.root/'link').symlink_to('/tmp')
        with self.assertRaisesRegex(ValueError,'file type'):f.validate()
        f=self.fixture();f.render();p=f.root/'store/commands'/f.transcript[0]['request']['commandId']/'terminal.json';p.unlink()
        with self.assertRaisesRegex(ValueError,'inventory changed'):f.validate()


if __name__ == '__main__':unittest.main()
