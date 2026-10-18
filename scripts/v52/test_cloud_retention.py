"""Modeled workload inputs through actual native storage/wire/cleanup code."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch
from . import cloud_retention as r,cloud_evidence_parts as parts,cloud_control as c,cloud_wire_policy as wire
from . import test_cloud_native_runner as native_fixture,test_cloud_wire_policy as fixture
from .test_cloud_authority import completion


class OriginalCaptureTest(unittest.TestCase):
    """Collection tests with synthetic history bytes; no workload acceptance."""
    def setUp(self):
        from .test_cloud_member import CorrelationTest
        self.case=CorrelationTest();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root.parent;self.member=self.root/'member';self.member.mkdir()
        self.case.root.rename(self.member/self.case.name);self.case.root=self.member/self.case.name
        self.output=self.root/'retention';self.output.mkdir();self.proof={'source':self.case.source}
        self.claim={'original':'claim'};self.row=self.case.check()
        self.selection={'member':{'histories':[self.case.name]}}
        self.receipt=dict(selection=self.selection,status='MEMBER_EXECUTED_NOT_QUALIFIED',
            resourceClaimSha256=r.digest(r.encoded(self.claim)),histories=[self.row])
        r.artifacts.save(self.member/'receipt.json',self.receipt)
        r.artifacts.save(self.case.root/'result.json',self.case.result)
        self.session=SimpleNamespace(owner=SimpleNamespace(request={'selection':self.selection}),
            output=self.root/'native',package=self.root/'original-package',
            guests=SimpleNamespace(closed=True,failure=None),guest_identity={'original':'guests'},
            checkpoint=Mock(return_value=self.claim),
            staged=SimpleNamespace(check=Mock(return_value=self.proof),files=self.case.files),
            storage=SimpleNamespace(java=self.case.java,records={},installations={}),
            api=SimpleNamespace(admission=SimpleNamespace(proof=self.proof,build={'original':'build'},
                observations={'completedAt':100},cfg={},plan={},approval={},clean={})))
        self.session.member_capture=r.member.Captured(self.session,self.member,self.receipt,
            {self.case.name:dict(result=self.case.result,placement=self.case.placement.binding)},r.member._CAPTURE)
        for path in [self.session.package,
            *[self.session.output/'build-provenance'/name for name in r.BUILD_FILES],
            *[self.session.output/'recent-cleanup'/name for name in ('observation.json','cleanup.zip','receipt.json')]]:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original modeled provenance')
        (self.member/'private-key').write_bytes(b'NEVER RETAIN THIS')
        self.build=patch.object(r.artifacts,'replay',return_value={'original':'build'}).start()
        self.package=patch.object(r.inputs,'inspect',return_value=self.proof).start();self.addCleanup(patch.stopall)

    def test_original_correlated_inventory_excludes_unselected_files_and_keeps_admission_clock(self):
        files=r.capture_files(self.session,self.output)
        self.assertEqual(22,len(files));self.assertNotIn('private-key',str(files))
        self.assertTrue(all(path.is_file() for path in files.values()))
        self.assertEqual(100,self.build.call_args.kwargs['now'])
        authority=r.artifacts.read(files['authority.json'])
        self.assertEqual(self.claim,authority['claim']);self.assertEqual(self.case.placement.binding,authority['placements'][self.case.name])
        self.assertEqual(self.session.package,files['inputs.tar.gz'])

    def test_copied_capture_running_guest_and_guest_close_failure_are_rejected(self):
        captured=self.session.member_capture
        for change in (lambda:setattr(captured,'session',object()),
                       lambda:setattr(self.session.guests,'closed',False),
                       lambda:setattr(self.session.guests,'failure','original close failed')):
            change()
            with self.assertRaisesRegex(ValueError,'closed member capture'):r.capture_files(self.session,self.output)
            captured.session=self.session;self.session.guests.closed=True;self.session.guests.failure=None

    def test_changed_receipt_history_bytes_build_package_or_claim_cannot_be_retained(self):
        original=(self.member/'receipt.json').read_bytes();(self.member/'receipt.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'member receipt changed'):r.capture_files(self.session,self.output)
        (self.member/'receipt.json').write_bytes(original)
        original=(self.case.root/'result.json').read_bytes();(self.case.root/'result.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'history replay result changed'):r.capture_files(self.session,self.output)
        (self.case.root/'result.json').write_bytes(original)
        for mocked,wrong,reason in ((self.build,{},'build changed'),(self.package,{},'package changed'),
                                   (self.session.checkpoint,{},'member receipt changed'),
                                   (self.session.staged.check,{},'inputs changed')):
            value=mocked.return_value;mocked.return_value=wrong
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):r.capture_files(self.session,self.output)
            mocked.return_value=value
        (self.case.root/'history.tar.gz').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'archive changed'):r.capture_files(self.session,self.output)


class EvidenceWireTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.LifecycleTest.setUpClass()
    def setUp(self):
        self.case=fixture.LifecycleTest();self.case.setUp();self.addCleanup(self.case.doCleanups)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        path=self.root/'original';path.write_bytes(b'original fixture bytes');self.manifest=parts.scan({'original':path},self.case.req)
        self.chunks=dict(parts.chunks({'original':path},self.manifest));self.store=self.case.store;self.key=r.prefix(self.case.req)
    def test_original_manifest_then_chunks_are_immutable_and_cannot_grant_pass(self):
        c.put(self.store,self.key+'manifest.json',self.manifest,0)
        c.put(self.store,r.chunk_key(self.case.req,0),self.chunks[0],0)
        with self.assertRaises(Exception):self.store.put(self.key+'manifest.json',self.manifest,1)
        self.assertIsNone(self.case.api.policy.retained)
        with self.assertRaises(ValueError):self.store.put(c.attempt_key(self.case.req)+'completion.json',completion(self.case.req),0)
    def test_missing_manifest_wrong_part_and_wrong_request_reject_before_post(self):
        with self.assertRaisesRegex(ValueError,'manifest missing'):self.store.put(r.chunk_key(self.case.req,0),self.chunks[0],0)
        c.put(self.store,self.key+'manifest.json',self.manifest,0)
        value=deepcopy(self.chunks[0]);value['data']='A'*len(value['data'])
        with self.assertRaisesRegex(ValueError,'bytes changed'):self.store.put(r.chunk_key(self.case.req,0),value,0)
        value=deepcopy(self.manifest);value['requestSha256']='a'*64
        with self.assertRaisesRegex(ValueError,'manifest request'):self.store.put(self.key+'manifest.json',value,0)
    def test_cleanup_role_cannot_create_manifest_or_chunks(self):
        self.case.api.policy.role='cleanup'
        with self.assertRaisesRegex(ValueError,'cannot publish'):self.store.put(self.key+'manifest.json',self.manifest,0)
    def test_cross_request_and_unbounded_object_indices_are_outside_wire_scope(self):
        scope=self.case.api.policy
        for key in (self.key+'chunk-99999.json',self.key+'chunk-0.json',self.key+'another.json',self.key.replace('attempts/','other/')):
            with self.assertRaises(ValueError):scope.object(key)


class NativeRetentionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):native_fixture.NativeRunnerTest.setUpClass()
    def setUp(self):
        self.base=native_fixture.NativeRunnerTest();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.session=self.base.open();self.root=self.base.root;self.session.staged=Mock()
        self.paths={}
        for name in ('authority.json','histories/original.tar.gz'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(('synthetic '+name).encode());self.paths[name]=path
    def publish(self):
        # Only the workload collection is modeled. Native authority, wire policy,
        # JSON transfers, original-result queries and cleanup all execute.
        with patch.object(r,'capture_files',return_value=self.paths):return self.session.retain_member(self.root/'retained')
    def test_exact_readback_then_cleanup_is_required_before_pass_completion(self):
        with self.assertRaisesRegex(ValueError,'original closed member capture'):r.capture_files(self.session,self.root)
        posted=[];lost=False
        def lose_reply(stage,row):
            nonlocal lost
            if row['method']=='POST':
                value=r.strict(row['body'])
                if value.get('schema')==parts.CHUNK:
                    if stage=='before':posted.append(value['ordinal'])
                    elif not lost:lost=True;raise ConnectionError('lost original upload response')
        self.base.case.server.fault=lose_reply
        result=self.publish();self.assertEqual('EVIDENCE_RETAINED_AWAITING_CLEANUP',result['status'])
        self.assertTrue(lost);self.assertEqual([0,1],posted)
        self.assertFalse(result['fullRemoteQualification']);self.assertIsNone(self.base.case.get(c.attempt_key(self.session.owner.request)+'completion.json'))
        with self.assertRaisesRegex(ValueError,'already consumed'):self.session.retain_member(self.root/'again')
        self.session.close()
        self.assertEqual({},self.base.case.server.resources);self.assertIsNone(self.base.case.get(c.a.LEASE))
        ledger=self.base.state();self.assertEqual({'PASS'},{row['status'] for row in ledger['attempts'].values()})
        completed=self.base.case.get(c.attempt_key(self.session.owner.request)+'completion.json')
        self.assertEqual(result['manifestSha256'],completed['evidenceSha256'])
        self.assertEqual(4_000_000,ledger['reservedCostMicrousd'])
    def test_partial_or_uncertain_upload_never_grants_pass_and_is_not_resubmitted(self):
        posted=[]
        def fault(stage,row):
            if row['method']=='POST' and '/upload/' in row['url']:
                value=r.strict(row['body'])
                if value.get('schema')==parts.CHUNK:
                    if stage=='before':posted.append(value['ordinal']);raise ValueError('original upload rejected')
        self.base.case.server.fault=fault
        with self.assertRaisesRegex(ValueError,'original upload rejected'):self.publish()
        self.assertEqual([0],posted);self.assertIsNone(self.session.api.retained)
        with self.assertRaisesRegex(ValueError,'already consumed'):self.session.retain_member(self.root/'again')
        self.base.case.server.fault=lambda *args:None;self.session.close()
        self.assertEqual({'FAIL'},{row['status'] for row in self.base.state()['attempts'].values()})
        self.assertEqual({},self.base.case.server.resources)

    def test_completed_upload_with_failed_cleanup_remains_failed_after_reconciliation(self):
        self.publish();self.session.heartbeat.close()
        def reject_delete(stage,row):
            if stage=='before' and row['method']=='DELETE' and 'compute.googleapis.com' in row['url']:
                return 403,b'fixture denial'
        self.base.case.server.fault=reject_delete
        result=self.session.owner.close();self.assertEqual('FAIL',result['status'])
        key=c.attempt_key(self.session.owner.request)+'completion.json';original=self.base.case.get(key)
        self.assertEqual('FAIL',original['status']);self.assertIsNone(original['evidenceSha256'])
        self.assertIsNotNone(self.base.case.get(c.a.LEASE));self.assertTrue(self.base.case.server.resources)
        self.base.case.server.fault=lambda *args:None
        self.session.api.retained=self.session.api.policy.retained=None
        result=c.reconcile(self.session.owner.store,self.session.owner.provider,trigger='workflow_dispatch',now=10**10)
        self.assertEqual('PASS',result['status']);self.assertEqual(original,self.base.case.get(key))
        self.assertEqual({'FAIL'},{row['status'] for row in self.base.state()['attempts'].values()})
        self.assertEqual({},self.base.case.server.resources)
        self.session.owner.cleanup_result=result;self.session.close()

    def test_retained_manifest_generation_change_cannot_grant_pass(self):
        self.publish();self.session.heartbeat.close();req=self.session.owner.request
        key=r.prefix(req)+'manifest.json';self.base.case.put(key,self.base.case.get(key))
        with self.assertRaisesRegex(ValueError,'retained manifest changed'):self.session.owner.close()
        self.assertIsNone(self.base.case.get(c.attempt_key(req)+'completion.json'))
        self.session.api.retained=self.session.api.policy.retained=None
        result=c.reconcile(self.session.owner.store,self.session.owner.provider,trigger='workflow_dispatch',now=10**10)
        self.assertEqual('PASS',result['status'])
        self.assertEqual({'FAIL'},{row['status'] for row in self.base.state()['attempts'].values()})
        self.session.owner.cleanup_result=result;self.session.close()

    def test_interrupted_ledger_append_reconciles_only_the_original_completion(self):
        self.publish();self.session.heartbeat.close();req=self.session.owner.request
        def reject_terminal(stage,row):
            if stage=='before' and row['method']=='POST':
                body=r.strict(row['body'])
                if body.get('schema')=='gse-v52-owned-ledger-v1' and len(body['entries'])>1:
                    raise ValueError('ledger unavailable')
        self.base.case.server.fault=reject_terminal
        with self.assertRaisesRegex(ValueError,'ledger unavailable'):self.session.owner.close()
        key=c.attempt_key(req)+'completion.json';original=self.base.case.get(key)
        self.assertEqual('PASS',original['status']);self.assertIsNotNone(self.base.case.get(c.a.LEASE))
        self.assertEqual({'PENDING'},{row['status'] for row in self.base.state()['attempts'].values()})
        self.base.case.server.fault=lambda *args:None
        self.session.api.retained=self.session.api.policy.retained=None
        result=c.reconcile(self.session.owner.store,self.session.owner.provider,trigger='workflow_dispatch',now=10**10)
        self.assertEqual('PASS',result['status']);self.assertEqual(original,self.base.case.get(key))
        self.assertEqual({'PASS'},{row['status'] for row in self.base.state()['attempts'].values()})
        self.assertEqual(4_000_000,self.base.state()['reservedCostMicrousd'])
        self.assertIsNone(self.base.case.get(c.a.LEASE));self.session.owner.cleanup_result=result;self.session.close()


if __name__=='__main__':unittest.main()
