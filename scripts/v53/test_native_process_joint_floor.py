"""Process record guards. Synthetic observations do not qualify a native run."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import native_process_joint_floor as m

CASE='4,FLOOR_MEMBER_FORCED,kill'


def sample(root,mode='kill'):
    side=root/'joint-floor-recovery';area=side/'process';area.mkdir(parents=True)
    for name in m.floor.FILES:
        if name in ('originals','interrupted','after-close','after-reopen','resumed-floor','after-maintenance'):(side/name).mkdir()
        else:(side/name).write_bytes(b'{}')
    case='4,FLOOR_MEMBER_FORCED,'+mode;m.h.save(side/'receipt.json',m.scope(case))
    (root/'original-plan.gsbp').write_bytes(b'synthetic-plan')
    captures=root/'source-retirement-captures';captures.mkdir();(captures/'prefix').write_bytes(b'synthetic-prefix')
    for name in ('before-open','at-cut','after-death','at-cut-scratch','after-death-scratch'):(area/name).mkdir()
    (area/'stderr').write_bytes(b'')
    lineage=dict(root='a'*64,node='node-2',replica='/original/replica',application='/original/application',cut={})
    m.h.save(side/'lineage.json',lineage);m.h.save(side/'maintenance.json',dict(startedNanos=123,originalDeadlineNanos=123+720_000_000_000))
    m.h.save(area/'spec.json',dict(schema=m.SCHEMA,root=dict(group='group',history='history',digest=lineage['root']),identity={},
        paths=dict(replica=lineage['replica'],application=lineage['application'],scratch='/original/scratch'),
        ordinal=4,point='FLOOR_MEMBER_FORCED',mode=mode,startedNanos=123,budgetNanos=720_000_000_000))
    m.h.save(area/'result.json',dict(schema=m.SCHEMA,status='PARTIAL',pid=101,parentPid=100,mode=mode,ordinal=4,point='FLOOR_MEMBER_FORCED',
        processDeathQualified=False,phase3Complete=False,liveLockRefused=True,lockReleased=True,exit=137 if mode=='kill' else 73))
    events=[dict(node='node-1',event='PARENT')];rows=[];controls=[];usage=[]
    def control(kind,value):
        rows.append(dict(kind=kind,value=value));controls.append(dict(kind=kind,value=value,eventCount=len(events)))
    def storage(event):
        value=dict(node='node-2',scope=m.SCOPE,event=event);events.append(value);rows.append(dict(kind='EVENT',value=value))
        value=dict(event=event,usage={});usage.append(value);rows.append(dict(kind='USAGE',value=value))
    control('STARTED',dict(mode=mode,pid=101))
    for event in ('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED',
                  'FUTURE_RETENTION_RECOVERY_FORCED','FUTURE_RETENTION_RECOVERY_PARENT_FORCED'):storage(event)
    control('OPENED',dict(pid=101,replica=lineage['replica'],application=lineage['application']))
    value=dict(node='node-2',scope=m.SCOPE,event='BEFORE_REQUEST_WRITE',request='request',kind='STATUS_PROBE',bytes='bytes')
    events.append(value);rows.append(dict(kind='EVENT',value=value))
    for event in ('FLOOR_COPY_BEFORE_RETURN','FLOOR_RESERVED','FLOOR_COPY_CREATED','FLOOR_MEMBER_FORCED'):storage(event)
    control('CUT',dict(mode=mode,pid=101,ordinal=4,point='FLOOR_MEMBER_FORCED'))
    events.append(dict(node='node-2',scope='joint-floor-reopened',event='CURRENT_VALIDATED'))
    m.h.save(root/'events.json',events);m.h.save(area/'controls.json',controls);m.h.save(side/'interrupted-usage.json',usage)
    (area/'stdout').write_bytes(b''.join(m.floor.f.canonical(v)+b'\n' for v in rows))
    return area,rows


class NativeProcessJointFloorTest(unittest.TestCase):
    def test_versioned_scratch_scope_requires_its_own_complete_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root);side=root/'joint-floor-recovery'
            self.assertNotIn('scratchRecovery',m.producer_scope(root,CASE))
            m.h.save(side/'receipt.json',m.scope(CASE,scratch_recovery=True))
            with self.assertRaisesRegex(ValueError,'complete sidecar'):m.collect(root,CASE)
            (side/'scratch-recovery').mkdir()
            self.assertTrue(m.producer_scope(root,CASE)['scratchRecovery']);self.assertEqual('PARTIAL',m.collect(root,CASE)['status'])
            row=m.scope(CASE,scratch_recovery=True);row['scratchRecovery']=False;m.h.save(side/'receipt.json',row)
            with self.assertRaisesRegex(ValueError,'exact producer cut'):m.collect(root,CASE)
            row['schema']='gse-v53-native-process-joint-floor-v3';m.h.save(side/'receipt.json',row)
            with self.assertRaisesRegex(ValueError,'known producer version'):m.collect(root,CASE)
            m.h.save(side/'receipt.json',m.scope(CASE))
            with self.assertRaisesRegex(ValueError,'complete sidecar'):m.collect(root,CASE)

    def test_original_identity_uses_checked_frame_digest_and_rejects_rebinding(self):
        catalog=m.floor.f.catalog();root=m.floor.f.sample(catalog['records']['ROOT']['schema'],catalog['types'])
        raw=m.floor.f.encode('records','ROOT',root);digest=raw[16:48].hex();identity=root['initial'][0]
        spec=dict(identity=identity,root=dict(group=root['groupId'],history=root['historyId'],digest=digest))
        self.assertNotEqual(m.h.digest(raw),digest)
        m.original_identity(spec,raw,identity,digest)
        for field in ('group','history','digest'):
            changed=copy.deepcopy(spec);changed['root'][field]='changed'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'original local identity'):
                m.original_identity(changed,raw,identity,digest)
        changed=copy.deepcopy(spec);changed['identity']['node']='other'
        with self.assertRaisesRegex(ValueError,'original local identity'):m.original_identity(changed,raw,identity,digest)
        with self.assertRaisesRegex(ValueError,'original local identity'):m.original_identity(spec,raw,identity,m.h.digest(raw))
        corrupted=bytearray(raw);corrupted[16]^=1
        with self.assertRaisesRegex(ValueError,'checksum'):m.original_identity(spec,bytes(corrupted),identity,digest)

    def test_exact_thirty_two_whole_history_commands(self):
        self.assertEqual(32,len(m.CASES));self.assertEqual(32,len(set(m.CASES)))
        for case in m.CASES:
            command=m.command(case);self.assertIn('-Dv53.native.process.joint='+case,command)
            self.assertIn('-Dtest='+m.CLASS.rsplit('.',1)[-1]+'#'+m.METHOD,command)
            self.assertFalse(any('retry' in v.lower() for v in command))
        for case in (None,False,'','01,FLOOR_MEMBER_FORCED,kill','4,FLOOR_MEMBER_FORCED,retry','4,FLOOR_MEMBER_FORCED,kill '):
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,'exact case'):m.command(case)

    def test_partial_or_complete_copy_readers_do_not_accept_process_scope(self):
        with self.assertRaisesRegex(ValueError,'bounded scope'):m.floor.writer_case(m.scope(CASE))

    def test_collection_never_upgrades_process_record_to_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root);before=m.h.inventory(root)
            with patch.object(m,'boundary') as replay:result=m.collect(root,CASE)
            replay.assert_not_called();self.assertEqual('PARTIAL',result['status'])
            for name in ('nativeHistoryQualified','processDeathQualified','phase3Complete'):self.assertIs(False,result[name])
            self.assertEqual(before,m.h.inventory(root));self.assertEqual(before,result['inventory'])
            with self.assertRaisesRegex(ValueError,'exact producer cut'):m.collect(root,CASE.replace('kill','halt'))

    def test_both_modes_bind_exact_pid_controls_and_exit(self):
        for mode in ('halt','kill'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sample(root,mode);spec,child=m.boundary(root,CASE.replace('kill',mode))
                self.assertEqual(mode,spec['mode']);self.assertEqual('FLOOR_MEMBER_FORCED',child[-1][1]['event'])

    def test_missing_or_extra_sidecar_member_prevents_complete_collection(self):
        for mode in ('missing','extra'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sample(root);side=root/'joint-floor-recovery'
                if mode=='missing':(side/'resumed-usage.json').unlink()
                else:(side/'unobserved').write_bytes(b'extra')
                with self.assertRaisesRegex(ValueError,'complete sidecar'):m.collect(root,CASE)

    def test_exit_lock_pid_and_success_upgrade_are_rejected(self):
        for field,value,reason in [('exit',0,'exact exit'),('liveLockRefused',False,'exact exit'),('lockReleased',False,'exact exit'),
                                  ('pid',True,'distinct live PID'),('pid',100,'distinct live PID'),
                                  ('processDeathQualified',True,'exact exit'),('status','PASS','exact exit')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);area,_=sample(root);path=area/'result.json';data=m.floor.read(path);data[field]=value;m.h.save(path,data)
                with self.assertRaisesRegex(ValueError,reason):m.boundary(root,CASE)

    def test_original_spec_roots_budget_and_cut_cannot_drift(self):
        for field,value,reason in [('ordinal',3,'unchanged budget'),('budgetNanos',720_000_000_001,'unchanged budget'),
                                  ('startedNanos',124,'unchanged original roots'),('mode','halt','unchanged budget')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);area,_=sample(root);path=area/'spec.json';data=m.floor.read(path);data[field]=value;m.h.save(path,data)
                with self.assertRaisesRegex(ValueError,reason):m.boundary(root,CASE)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);area,_=sample(root);path=area/'spec.json';data=m.floor.read(path)
            data['paths']['scratch']=data['paths']['replica']+'/nested';m.h.save(path,data)
            with self.assertRaisesRegex(ValueError,'disjoint original roots'):m.boundary(root,CASE)

    def test_missing_relabelled_or_extra_cold_callbacks_fail_projection(self):
        for change in ('remove','scope','extra'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);sample(root);path=root/'events.json';events=m.floor.read(path)
                if change=='remove':del events[1]
                elif change=='scope':events[1]['scope']='network-owner'
                else:events.insert(1,copy.deepcopy(events[1]))
                m.h.save(path,events)
                with self.assertRaisesRegex(ValueError,'complete original event projection'):m.boundary(root,CASE)

    def test_open_control_cannot_move_across_storage_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);area,_=sample(root);path=area/'controls.json';rows=m.floor.read(path);rows[1]['eventCount']-=1;m.h.save(path,rows)
            with self.assertRaisesRegex(ValueError,'exact open return boundary'):m.boundary(root,CASE)

    def test_resource_observations_cannot_drop_original_callback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root);path=root/'joint-floor-recovery/interrupted-usage.json';rows=m.floor.read(path);rows.pop();m.h.save(path,rows)
            with self.assertRaisesRegex(ValueError,'original resource observations'):m.boundary(root,CASE)

    def test_partial_duplicate_and_noncanonical_lines_fail_without_modifying_input(self):
        for raw in (b'{"kind":',b'{"kind":"CUT","kind":"CUT","value":{}}\n',b'{"value":{},"kind":"CUT"}\n',b'{"kind":"PASS","value":{}}\n'):
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'stdout';path.write_bytes(raw)
                with self.assertRaises(ValueError):m.messages(path)
                self.assertEqual(raw,path.read_bytes())

    def test_incomplete_wrong_or_retried_junit_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);suite=ET.Element('testsuite',dict(name=m.CLASS,tests='1',failures='0',errors='0',skipped='0'))
            ET.SubElement(suite,'testcase',dict(classname=m.CLASS,name=m.METHOD));path=root/'TEST-process.xml'
            ET.ElementTree(suite).write(path);self.assertEqual(m.CLASS,m.junit(root)['className'])
            with self.assertRaises(ValueError):m.base.junit(root)
            ET.SubElement(suite[0],'rerunFailure');ET.ElementTree(suite).write(path)
            with self.assertRaises(ValueError):m.junit(root)

    def test_inspection_cannot_return_green_if_original_boundary_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);area,_=sample(root);(area/'stdout').write_bytes(b'truncated')
            with patch.object(m.floor.c,'inventory') as physical:
                with self.assertRaisesRegex(ValueError,'incomplete original stdout'):m.inspect(root,CASE)
                physical.assert_not_called()

    def test_inspection_requires_the_exact_recorded_floor_prefix_before_disk_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root)
            with patch.object(m.floor.c,'inventory') as physical:
                with self.assertRaisesRegex(ValueError,'original recovered floor prefix'):m.inspect(root,CASE)
                physical.assert_not_called()

    def test_capture_uses_process_entry_and_retains_failures(self):
        from .test_process_toolchain import record
        def source_copy(repo,work):
            work.mkdir();(work/'source').write_bytes(b'original');return dict(head='a'*40,files={'source':m.h.digest(b'original')})
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.h,'source_copy',side_effect=source_copy),\
             patch.object(m.base,'reader_manifest',return_value=dict(files={},sha256='b'*64)),\
             patch.object(m.base.tc,'capture',return_value=record()),patch.object(m.h,'execute',return_value=dict(exit=1,elapsedSeconds=1)) as run,\
             patch.object(m,'collect') as collection:
            out=Path(tmp)/'failed'
            with self.assertRaisesRegex(ValueError,'execution failed'):m.capture(out,'mvn',CASE)
            value=m.floor.read(out/'receipt.json');self.assertEqual(m.EXECUTION_SCHEMA,value['schema']);self.assertEqual('FAIL',value['status'])
            self.assertEqual(['mvn',*m.command(CASE)],run.call_args.args[0]);collection.assert_not_called()
            self.assertEqual(b'original',(out/'workspace/source').read_bytes())

    def test_existing_output_or_bad_case_never_starts_process(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.h,'execute') as run:
            root=Path(tmp);(root/'keep').write_bytes(b'keep')
            with self.assertRaises(FileExistsError):m.capture(root,'mvn',CASE)
            with self.assertRaises(ValueError):m.capture(root/'bad','mvn','bad')
            self.assertEqual(b'keep',(root/'keep').read_bytes());run.assert_not_called()

    def test_collection_cli_writes_a_path_and_refuses_to_overwrite_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';sample(raw);output=root/'collection.json'
            args=['process','collect',str(output),'--case',CASE,'--raw',str(raw)]
            with patch.object(m.sys,'argv',args):m.main()
            saved=output.read_bytes();self.assertEqual(m.collect(raw,CASE),m.floor.read(output))
            with patch.object(m.sys,'argv',args),self.assertRaisesRegex(ValueError,'refuses overwrite'):m.main()
            self.assertEqual(saved,output.read_bytes())

    def test_other_inspection_cli_modes_persist_their_partial_results(self):
        for mode in ('inspect','qualify'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                output=Path(tmp)/'result.json';result=dict(status='PARTIAL',processDeathQualified=False)
                with patch.object(m,mode,return_value=result) as read,patch.object(m.sys,'argv',
                        ['process',mode,str(output),'--case',CASE,'--raw','original']):m.main()
                self.assertEqual(result,m.floor.read(output));read.assert_called_once_with('original',CASE)

    def test_negatives_need_valid_original_and_never_change_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root);before=m.h.inventory(root)
            with patch.object(m,'inspect',side_effect=ValueError('original failed')),patch.object(m,'mutate') as mutation:
                with self.assertRaisesRegex(ValueError,'original failed'):m.qualify(root,CASE)
                mutation.assert_not_called()
            with patch.object(m,'inspect',return_value=dict(status='PARTIAL')):
                result=m.qualify(root,CASE)
            self.assertEqual([dict(case=k,status='REJECTED',reason=v) for k,v in m.NEGATIVES.items()],result['negatives'])
            self.assertEqual(before,m.h.inventory(root));self.assertFalse(result['processDeathQualified'])

    def test_negative_cannot_pass_for_an_unrelated_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample(root)
            with patch.object(m,'inspect',return_value=dict(status='PARTIAL')),patch.object(m,'boundary',side_effect=ValueError('unrelated')):
                with self.assertRaisesRegex(ValueError,'unexpected negative reason'):m.qualify(root,CASE)


if __name__=='__main__':unittest.main()
