"""Synthetic backup lifecycle/replay fixtures; never Linux engine qualification."""
from copy import deepcopy
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from scripts.v43 import derived_format_v12 as fmt
from . import guest_backup as backup, guest_backup_evidence as evidence, guest_evidence as logical
from . import cloud_package as package, cloud_workload_contract as contract, remote_command as c
from . import performance_model as m, remote_schedule as schedule
from .test_guest_healthy_evidence import HealthyFixture


def payloads(state):
    """Encode real checksummed V4 backup bytes for the synthetic final model."""
    pack=struct.pack;lp=fmt.lp;history=(123,456);profile=fmt.profile_bytes();digest=fmt.profile_digest()
    identity=('performance-store','semantic-schema','semantic-codec')
    descriptors=b''.join(pack('>B',{'equality':1,'range':2,'prefix':3,'text':4}[v['kind']])+lp(v['field'])+lp(v['analyzer'])
                         for v in [m.INDEXES[i] for i in (3,1,2,0)])
    meta=fmt.checked(pack('>QhhQQ',fmt.METADATA_MAGIC,1,2,*history)+lp('gse-durable')+pack('>I',len(profile))+profile+digest+
        b''.join(lp(v) for v in identity)+pack('>iiiiiqqqi',1,1024,4096,16,1024,32<<20,128<<20,4<<20,4)+descriptors)
    documents=b''
    for key,doc in state.documents.items():
        raw=m.encode_document(doc);documents+=pack('>Biii',1,4,key,len(raw))+raw
    count=len(state.documents)
    checkpoint=fmt.checked(pack('>QhhQQ',fmt.CHECKPOINT_MAGIC,1,2,*history)+digest+
        pack('>qiii',state.sequence,count,count,4)+descriptors+pack('>i',count)+documents)
    result={'gse-backup-checkpoint':checkpoint,'gse-backup-metadata':meta}
    preimage=fmt._backup_preimage(result,digest,history,state.sequence,*identity,1)
    manifest=pack('>Qhh',fmt.BACKUP_MAGIC,1,2)+lp('gse-backup')+lp('gse-durable')+pack('>hh',1,2)+digest
    manifest+=pack('>QQq',*history,state.sequence)+b''.join(lp(v) for v in identity)+pack('>iI',1,2)
    manifest+=b''.join(lp(name)+pack('>Q',len(raw))+bytes.fromhex(m.sha(raw)) for name,raw in result.items())
    result['gse-backup-manifest']=fmt.checked(manifest+bytes.fromhex(m.sha(preimage))+pack('>q',0)+lp('synthetic'))
    return result


class BackupFixture(HealthyFixture):
    def __init__(self,root):
        super().__init__(root)
        manifest=m.strict_json(self.manifest)
        manifest['modes'][package.MODES[0]]=dict(jars=['artifacts/published.jar'],classes='classes-'+package.MODES[0],main=package.MAINS[package.MODES[0]])
        manifest['files'].append(dict(path='artifacts/published.jar',sha256='b'*64))
        self.manifest=m.canonical(manifest);self.config['packageManifestSha256']=m.sha(self.manifest)
        self.transcript=self.transcript[:-2];self.exchanges.pop();self.results.pop()
        now=self.transcript[-1]['receipt']['endedNanos']+100
        response=self.exchange('backup',{},now+10,now+90);response['sequence']=self.state.sequence
        raw=payloads(self.state);files={n:dict(bytes=len(b),sha256=m.sha(b)) for n,b in raw.items()}
        self.backed=dict(response=response,files=files)
        self.control('backup',{},self.backed,now,now+100)
        self.exchange('close',{},now+210,now+290)
        self.control('stop-voter',dict(forced=False),dict(stopped=True),now+200,now+300)
        agent=Path(self.config['root'])/'agents'/self.node
        spec=manifest['modes'][package.MODES[0]]
        args=[self.base+'/runtime/bin/java',*contract.load()['environment']['jvmArguments'],'-cp',
              ':'.join(self.base+'/'+v for v in [*spec['jars'],spec['classes']]),package.PACKAGE+spec['main'],
              str(agent/'restored-check'),'restore',self.base+'/source-inputs/docs/v5x/v5.1/phase6-plan.json',self.config['root']+'/export']
        self.restored=dict(files=files,process=dict(args=args,pid=103,exitCode=0,startedNanos=now+410,endedNanos=now+490))
        self.control('restore-backup',{},self.restored,now+400,now+500)
        self.control('collect',dict(physical=True,backup=True),None,now+600,now+700)
        self.files.update({'backup/export/'+n:b for n,b in raw.items()})
        self.files['authority/'+self.node+'/fixture']=b'logical-only fixture'
        self.files['backup/restore.stdout']=m.canonical(dict(sequence=self.state.sequence,indexCount=4,documents=list(self.state.documents.values())))
        self.files['backup/restore.stderr']=b''
    def render(self):
        for name,value in [('backup-claim',dict(config=self.config)),('backup-result',self.backed),
                           ('restore-claim',dict(config=self.config,backupSha256=m.sha(m.canonical(self.backed)))),('restore-result',self.restored)]:
            self.files['backup/'+name+'.json']=m.canonical(value)
        super().render()
    def validate(self):
        return logical.validate(self.root,self.config,self.manifest,self.base,self.transcript,active=True,healthy=True,physical=True,backup=True)


class BackupEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
    def test_bytes_and_public_restore_replay_without_claiming_physical_qualification(self):
        f=BackupFixture(self.root/'raw');f.render();value=f.validate()
        self.assertEqual(value['backupRestore']['status'],'PASS');self.assertEqual(value['calls'],90)
        self.assertEqual(value['backupRestore']['sequence'],f.state.sequence)
        self.assertFalse(value['physicalHistoryQualified']);self.assertFalse(value['fullRemoteQualification'])
    def test_resealed_backup_bytes_must_decode_not_just_match_inventory(self):
        f=BackupFixture(self.root/'raw');name='gse-backup-checkpoint'
        f.files['backup/export/'+name]=b'corrupt'
        f.backed['files'][name]=dict(bytes=7,sha256=m.sha(b'corrupt'));f.render()
        with self.assertRaises(ValueError):f.validate()
    def test_original_response_and_backup_cannot_move_to_another_sequence(self):
        f=BackupFixture(self.root/'raw');f.backed['response']['sequence']+=1;f.render()
        with self.assertRaisesRegex(ValueError,'binding/cut'):f.validate()
    def test_resealed_restore_must_match_actual_documents(self):
        f=BackupFixture(self.root/'raw');f.files['backup/restore.stdout']=m.canonical(dict(sequence=f.state.sequence,indexCount=4,documents=[]));f.render()
        with self.assertRaisesRegex(ValueError,'application differs'):f.validate()
    def test_restore_requires_separate_pid_published_classpath_and_success(self):
        for key,value in [('pid',102),('exitCode',1),('args',['java','changed']),('startedNanos',0)]:
            with self.subTest(key=key):
                f=BackupFixture(self.root/key);f.restored['process'][key]=value;f.render()
                with self.assertRaisesRegex(ValueError,'restore process'):f.validate()
    def test_controller_backup_response_cannot_disagree_with_collected_record(self):
        f=BackupFixture(self.root/'raw');f.render();row=next(v for v in f.transcript if v['request']['command']=='backup')
        row['receipt']=deepcopy(row['receipt']);row['receipt']['result']['response']['sequence']+=1
        with self.assertRaisesRegex(ValueError,'retained/controller'):f.validate()
    def test_service_pid_and_boolean_exit_code_cannot_claim_a_restore_jvm(self):
        for key,value in [('pid',101),('exitCode',False)]:
            f=BackupFixture(self.root/key);f.restored['process'][key]=value;f.render()
            with self.assertRaisesRegex(ValueError,'restore process'):f.validate()
    def test_backup_scope_is_explicit(self):
        f=BackupFixture(self.root/'raw');f.render()
        with self.assertRaisesRegex(ValueError,'collection receipt'):
            logical.validate(f.root,f.config,f.manifest,f.base,f.transcript,active=True,healthy=True,physical=True)
    def test_trace_requires_original_backup_response_owner_and_exact_cardinality(self):
        response=dict(command='backup',opId='op',pid=102,sequence=7,outcome='SUCCESS')
        original={'node-1':[dict(event='CLIENT_INVOKE',order=1,**response),dict(event='CLIENT_RESULT',order=2,**response)],'node-2':[]}
        evidence.trace_binding(original,'node-1',response)
        cases=[]
        changed=deepcopy(original);changed['node-1'][1]['sequence']=8;cases.append(changed)
        changed=deepcopy(original);changed['node-2']=changed.pop('node-1');cases.append(changed)
        changed=deepcopy(original);changed['node-1'].pop();cases.append(changed)
        changed=deepcopy(original);changed['node-1']*=2;cases.append(changed)
        for traces in cases:
            with self.assertRaisesRegex(ValueError,'backup trace'):evidence.trace_binding(traces,'node-1',response)


class BackupLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.service=SimpleNamespace(root=self.root/'agent',cell=self.root/'cell',config=dict(mode=package.MODES[2]),
            jvm=Mock(closed=False),plan=self.root/'plan',java=Mock(return_value=['java','restore']),oneshot=Mock(return_value={'exitCode':0}))
        self.service.root.mkdir();self.service.cell.mkdir()
        for spec in schedule.windows('healthy','experiment'):
            folder=self.service.root/('window-healthy-'+spec['window']);folder.mkdir()
            c.write_once(folder/'result.json',dict(status='PASS',calls=spec['calls']))
        def create(_):
            folder=self.service.cell/'export';folder.mkdir()
            for name in backup.bootstrap.SOURCE:(folder/name).write_bytes(name.encode())
            return dict(outcome='SUCCESS')
        self.service.jvm.command.side_effect=create
    def test_once_only_backup_and_restore_claims_survive_repeated_invocation(self):
        backup.create(self.service)
        with self.assertRaises(FileExistsError):backup.create(self.service)
        self.service.jvm.command.assert_called_once_with('backup')
        self.service.jvm.closed=True;backup.restore(self.service)
        with self.assertRaises(FileExistsError):backup.restore(self.service)
        self.service.oneshot.assert_called_once()
    def test_failed_backup_consumes_claim_and_is_never_reexecuted(self):
        self.service.jvm.command.side_effect=ValueError('failed original')
        with self.assertRaisesRegex(ValueError,'failed original'):backup.create(self.service)
        with self.assertRaises(FileExistsError):backup.create(self.service)
        self.service.jvm.command.assert_called_once()
    def test_incomplete_tape_prevents_backup_and_live_voter_prevents_restore(self):
        (self.service.root/'window-healthy-warmup/result.json').unlink()
        with self.assertRaises(FileNotFoundError):backup.create(self.service)
        self.service.jvm.command.assert_not_called()
        with self.assertRaisesRegex(ValueError,'stopped automatic'):backup.restore(self.service)
    def test_changed_export_prevents_restore(self):
        backup.create(self.service);self.service.jvm.closed=True
        (self.service.cell/'export'/backup.bootstrap.SOURCE[0]).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'backup changed'):backup.restore(self.service)
        self.service.oneshot.assert_not_called()
    def test_restore_failure_cannot_be_rearmed(self):
        backup.create(self.service);self.service.jvm.closed=True
        self.service.oneshot.side_effect=ValueError('restore failed')
        with self.assertRaisesRegex(ValueError,'restore failed'):backup.restore(self.service)
        with self.assertRaises(FileExistsError):backup.restore(self.service)
        self.service.oneshot.assert_called_once()
    def test_failed_restore_stdout_and_original_claims_remain_collectable(self):
        backup.create(self.service);self.service.jvm.closed=True
        def failed(*_):
            (self.service.root/'restore.stderr').write_bytes(b'original failure')
            raise ValueError('failed')
        self.service.oneshot.side_effect=failed
        with self.assertRaises(ValueError):backup.restore(self.service)
        backup.capture(self.service,self.root/'retained')
        self.assertEqual((self.root/'retained/restore.stderr').read_bytes(),b'original failure')
        self.assertTrue((self.root/'retained/restore-claim.json').is_file())
        self.assertFalse((self.root/'retained/restore-result.json').exists())
        self.assertEqual(backup.authority.inventory(self.root/'retained/export'),backup.exported(self.service.cell))
    def test_empty_or_partial_failed_export_is_retained_but_not_a_success_inventory(self):
        export=self.service.cell/'export';export.mkdir()
        backup.capture(self.service,self.root/'empty')
        self.assertTrue((self.root/'empty/export').is_dir())
        (export/'partial.tmp').write_bytes(b'partial original')
        backup.capture(self.service,self.root/'partial')
        self.assertEqual((self.root/'partial/export/partial.tmp').read_bytes(),b'partial original')
        with self.assertRaisesRegex(ValueError,'closed inventory'):backup.exported(self.service.cell)


class OwnedBackupTest(unittest.TestCase):
    def setUp(self):
        from . import test_guest_owned_workload as fixture
        self.fixture=fixture.OwnedWorkloadTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.probe=self.fixture.probe;self.probe.require_physical=True;self.probe.require_backup=True
        # Only command-store OS metadata is synthetic; run the real submit/query
        # and lifecycle logic, including durable claims and lost replies.
        read=Path.read_text
        def metadata(path,*args,**kwargs):
            if str(path)=='/proc/sys/kernel/random/boot_id':return '11111111-1111-4111-8111-111111111111'
            if str(path)=='/proc/self/stat':return '1 (synthetic) '+' '.join(['0']*20)
            return read(path,*args,**kwargs)
        self.patch=patch.object(Path,'read_text',metadata);self.patch.start();self.addCleanup(self.patch.stop)
        self.order=[]
        for n,client,_ in self.probe.clients:
            original=client.submit
            def submit(value,end,original=original,n=n):
                self.order.append((n,value['command']));return original(value,end)
            client.submit=submit
        self.convergence=patch('scripts.v51.guest_physical_evidence.converge');self.convergence.start();self.addCleanup(self.convergence.stop)
    def run_tape(self):self.probe.cell('healthy',self.fixture.clock.nanos()+300*10**9)
    def collect(self):
        self.probe.stop();return self.probe.collect_validate(self.fixture.root,self.fixture.clock.nanos()+600*10**9)
    def test_once_only_lost_backup_restore_replies_and_all_voters_stopped_first(self):
        self.probe.clients[1][1].lost=True;self.run_tape();self.collect()
        commands=[name for _,name in self.order]
        self.assertEqual(commands.count('backup'),1);self.assertEqual(commands.count('restore-backup'),1)
        self.assertLess(max(i for i,n in enumerate(commands) if n=='window'),commands.index('backup'))
        self.assertLess(max(i for i,n in enumerate(commands) if n=='stop-voter'),commands.index('restore-backup'))
        cl=self.probe.clients[1][1]
        for name in ('backup','restore-backup'):
            originals=[q for q in cl.calls if q['command']==name];queries=[q for q in cl.queries if q['command']==name]
            self.assertEqual(originals,queries);self.assertEqual(len(originals),1)
    def test_failed_backup_is_retained_and_does_not_run_restore(self):
        self.probe.clients[1][1].failure='backup'
        with self.assertRaisesRegex(ValueError,'injected backup'):self.run_tape()
        result=self.collect();self.assertEqual(result['status'],'FAIL')
        self.assertEqual([n for n,c in self.order if c=='stop-voter'],[1,2,3])
        self.assertNotIn('restore-backup',[c for _,c in self.order])
        self.assertEqual(c.read(self.probe.raw/'cell.json')['status'],'FAIL')
    def test_failed_stop_prevents_restore_without_skipping_other_stops(self):
        self.run_tape();self.probe.clients[0][1].failure='stop-voter'
        result=self.collect();self.assertEqual(result['status'],'FAIL')
        self.assertEqual([n for n,c in self.order if c=='stop-voter'],[1,2,3])
        self.assertNotIn('restore-backup',[c for _,c in self.order])


if __name__=='__main__':unittest.main()
