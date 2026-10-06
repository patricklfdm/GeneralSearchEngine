"""Failure continuation with native records and synthetic HTTP only."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from . import cloud_runner_failure as f, cloud_runner_resource_qualification as q
from . import cloud_native_authority as n, cloud_native_cleanup as cleanup, cloud_http as h
from . import cloud_gcp as g, performance_model as m
from .cloud_http_fake import delay_instance_deletes
from .remote_command import read


class RunnerFailureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = f.workload.load()
        loader = patch.object(f.workload, 'load', side_effect=lambda: deepcopy(frozen))
        loader.start(); cls.addClassCleanup(loader.stop)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.input = q.fixture(self.root/'inputs', self.root/'private')
        self.api = None

    def run_failure(self, fault='iap-denied', before=None):
        self.input['probe'].fault = fault
        original = q.resources.inject(fault, self.input['clock'], self.input['http'],
            preparation_seconds=q.r.timing.PREPARATION_SECONDS)
        def recover(api, root, receipt):
            self.api = api
            # The lost response is a one-time injection. It must not turn a
            # different cleanup CAS into another simulated preparation failure.
            self.input['http'].send = original
            if before: before(api)
            return f.recover(api, root, receipt)
        return q.prepare(self.input, self.root/'evidence', on_failure=recover)

    def store(self):
        api = h.Api(transport=self.input['http'], tokens=lambda _: 'offline', clock=self.input['clock'].seconds)
        return g.Store(self.input['cfg']['provider'], api, authority=n)

    def mutations(self):
        return [v for v in self.input['http'].requests if v['method'] != 'GET']

    def assert_finished(self, result, *, cost=q.q.COST):
        self.assertEqual('FAIL', result['status'], result)
        recovered = result['ownerRecovery']
        self.assertEqual('PASS', recovered['status'], recovered)
        self.assertEqual('PASS', recovered['cleanup']['status'])
        self.assertEqual('VERIFIED', recovered['retention']); self.assertTrue(recovered['leaseReleased'])
        self.assertFalse(recovered['paidCloud']); self.assertFalse(recovered['engineWorkloadExecuted'])
        self.assertEqual({}, self.input['http'].resources)
        self.assertIsNone(self.store().get(n.LEASE))
        charged, entries = n.inspect_ledger(self.store().get(n.LEDGER)[1])
        self.assertEqual(cost, charged)
        self.assertEqual('FAIL', entries[n.validate_request(self.api.req)]['status'])

    def test_active_iap_failure_deletes_exact_ids_retains_originals_and_never_refunds(self):
        result = self.run_failure(); self.assert_finished(result)
        self.assertEqual(13, self.input['http'].inserts)
        deletes = [v for v in self.mutations() if v['method']=='DELETE' and v['path'].startswith('/compute/')]
        self.assertEqual(13, len(deletes))
        self.assertEqual({row['id'] for row in self.api.lease['resources']}, {v['path'].rsplit('/',1)[1] for v in deletes})
        self.assertLess(self.input['clock'].wall(), self.api.lease['expiresAt'])
        prefix = n.PREFIX+'attempts/'+n.validate_request(self.api.req)+'/'
        manifest = m.strict_json(self.store().get(prefix+'preparation-failure/manifest.json')[1])
        for row in manifest['files']:
            data = self.store().get(prefix+'preparation-failure/'+row['path'])[1]
            self.assertEqual((row['bytes'], row['sha256']), (len(data), m.sha(data)))
        self.assertEqual((self.root/'evidence/receipt.json').read_bytes(),
                         self.store().get(prefix+'preparation-failure/receipt.json')[1])
        self.assertNotIn('identity', [row['path'] for row in manifest['files']])

    def test_lost_insert_and_identity_replies_resolve_original_operation_without_replay(self):
        for fault in ('lost-insert-1','lost-insert-11','lost-insert-13','lost-identity-13'):
            with self.subTest(fault=fault):
                self.input = q.fixture(self.root/fault, self.root/(fault+'-key'))
                out = self.root/'evidence'
                if out.exists(): out.rename(self.root/('previous-'+fault))
                result = self.run_failure(fault); self.assert_finished(result)
                inserts = [v for v in self.mutations() if v['method']=='POST' and v['path'].startswith('/compute/')]
                self.assertEqual(len(inserts), len({v['query']['requestId'] for v in inserts}))

    def test_slow_vm_deletes_complete_native_owner_recovery_without_detached_disk_leaks(self):
        def slow(api):
            delay_instance_deletes(self.input['http'], self.input['clock'], {1:85.5, 2:56.5, 3:50})
        # Cleanup reconstructs its own provider from retained bytes, with the
        # same synthetic monotonic clock as creation and credentials.
        with patch.dict(g.Compute.__init__.__kwdefaults__, sleep=self.input['clock'].sleep):
            result = self.run_failure(before=slow)
        self.assert_finished(result)
        self.assertEqual(192, result['ownerRecovery']['elapsedSeconds'])
        deletes = [v for v in self.mutations() if v['method']=='DELETE' and v['path'].startswith('/compute/')]
        self.assertEqual(13, len(deletes)); self.assertEqual(13, len({v['query']['requestId'] for v in deletes}))

    def test_lost_ledger_context_or_plan_keeps_charge_and_finishes_failure(self):
        for fault in ('lost-ledger','lost-context','lost-plan'):
            with self.subTest(fault=fault):
                self.input = q.fixture(self.root/fault, self.root/(fault+'-key'))
                out = self.root/'evidence'
                if out.exists(): out.rename(self.root/('previous-'+fault))
                self.assert_finished(self.run_failure(fault))
                self.assertEqual(0,self.input['http'].inserts)

    def test_lost_initial_lease_reply_is_reconciled_without_inventing_a_charge(self):
        result = self.run_failure('lost-lease')
        self.assertEqual('PASS',result['ownerRecovery']['status'],result)
        self.assertEqual(0,self.input['http'].inserts); self.assertIsNone(self.store().get(n.LEASE))
        before = self.input['value']['resourcePlan']['baseline']
        self.assertEqual(None if before is None else (before[0],before[1]),self.store().get(n.LEDGER))

    def test_unresolved_insert_keeps_lease_and_manual_still_waits_for_expiry(self):
        result = self.run_failure('pending-operation')
        self.assertEqual('FAIL',result['ownerRecovery']['cleanup']['status'],result)
        self.assertFalse(result['ownerRecovery']['leaseReleased'])
        self.assertEqual('VERIFIED',result['ownerRecovery']['retention'])
        lease = self.store().get(n.LEASE)[1]
        saved = q.q.cleanup.snapshot(self.input['http'])
        active, after, _ = q.resources.replay(self.input['cfg']['provider'],q.q.pq.SOURCE,saved,
            self.root/'manual-active',lease['startedAt'])
        self.assertEqual('WAITING',active['status']);self.assertEqual(saved,after)
        self.assertEqual(11,self.input['http'].inserts)

    def test_lost_intent_with_no_operation_is_not_mistaken_for_final_absence(self):
        result = self.run_failure('lost-intent')
        self.assertEqual('FAIL',result['ownerRecovery']['cleanup']['status'])
        self.assertIsNotNone(self.store().get(n.LEASE));self.assertEqual(0,self.input['http'].inserts)
        self.assertEqual('VERIFIED',result['ownerRecovery']['retention'])

    def test_preparation_deadline_has_separate_bounded_cleanup_not_new_lease(self):
        result = self.run_failure('deadline'); self.assert_finished(result)
        self.assertGreater(self.input['clock'].seconds(),self.api.deadline)
        self.assertLess(self.input['clock'].seconds(),self.api.owner_deadline)

    def test_guest_stage_failure_enters_same_recovery(self):
        original = q.r._run
        def run(*args,**kwargs):
            def guest(*args): raise ValueError('private diagnostic must not escape')
            return original(*args,**dict(kwargs,guest_stage=guest))
        with patch.object(q.r,'_run',side_effect=run): result = self.run_failure('complete')
        self.assert_finished(result)
        self.assertEqual(dict(phase='guest-setup',type='ValueError'),{k:result['failure'][k] for k in ('phase','type')})
        self.assertEqual('PREPARATION_REJECTED',result['failure']['code'])
        self.assertNotIn('private diagnostic',str(result))

    def test_guest_deadline_retains_node_and_part_without_exception_text(self):
        original=q.r._run
        operation=dict(node='node-3',kind='package',action='part',index=5)
        def run(*args,**kwargs):
            def guest(api,*_):
                api.guest_operation=operation
                self.input['clock'].sleep(api.deadline-api.clock())
                raise ValueError('sensitive-token-and-provider-body')
            return original(*args,**dict(kwargs,guest_stage=guest))
        with patch.object(q.r,'_run',side_effect=run):result=self.run_failure('complete')
        self.assert_finished(result);failure=result['failure']
        self.assertEqual('PREPARATION_DEADLINE',failure['code']);self.assertEqual(operation,failure['operation'])
        self.assertEqual(failure['deadlineNanos'],failure['observedNanos'])
        self.assertNotIn('sensitive-token',str(result))
        key=n.PREFIX+'attempts/'+n.validate_request(self.api.req)+'/preparation-failure/receipt.json'
        retained=m.strict_json(self.store().get(key)[1]);self.assertEqual(failure,retained['failure'])

    def test_original_api_consumed_once_and_copy_or_offline_resource_api_cannot_authorize(self):
        self.run_failure()
        for source in (self.api,deepcopy(self.api.value),q.resources.fixture()[-1]):
            with self.subTest(source=type(source).__name__),self.assertRaises(ValueError): f._Api(source)

    def test_complete_preparation_remains_partial_and_is_not_cleaned(self):
        result = self.run_failure('complete')
        self.assertEqual('PARTIAL',result['status']); self.assertNotIn('ownerRecovery',result)
        self.assertEqual(13,len(self.input['http'].resources)); self.assertIsNotNone(self.store().get(n.LEASE))

    def test_failed_admission_never_constructs_recovery(self):
        self.input['approved']['confirmed']=False
        result = self.run_failure()
        self.assertEqual('FAIL',result['status']); self.assertNotIn('ownerRecovery',result); self.assertIsNone(self.api)
        self.assertEqual([],self.mutations())

    def test_replaced_lease_blocks_before_any_recovery_mutation(self):
        count=[]
        def change(api):
            lease=deepcopy(api.lease);lease['startedAt']+=1;lease['expiresAt']+=1
            self.store().put(n.LEASE,lease,api.generation);count.append(len(self.mutations()))
        result=self.run_failure(before=change)
        self.assertEqual('FAIL',result['ownerRecovery']['status']);self.assertIsNone(result['ownerRecovery']['cleanup'])
        self.assertEqual(count[0],len(self.mutations()))

    def test_missing_charge_or_context_blocks_resource_cleanup(self):
        for name in ('ledger','context'):
            with self.subTest(name=name):
                self.input=q.fixture(self.root/name,self.root/(name+'-key'))
                out=self.root/'evidence'
                if out.exists():out.rename(self.root/('previous-'+name))
                count=[]
                def change(api):
                    key=n.LEDGER if name=='ledger' else n.PREFIX+'attempts/'+n.validate_request(api.req)+'/cleanup-context.json'
                    current=self.store().get(key);self.store().delete(key,current[0]);count.append(len(self.mutations()))
                result=self.run_failure(before=change)
                self.assertIsNone(result['ownerRecovery']['cleanup'])
                self.assertEqual(count[0],len(self.mutations()));self.assertEqual(13,len(self.input['http'].resources))

    def test_replaced_resource_id_is_never_deleted_or_released(self):
        def change(api):
            next(v for v in self.input['http'].resources.values() if 'machineType' in v)['id']='999999999'
        result=self.run_failure(before=change)
        self.assertEqual('FAIL',result['ownerRecovery']['cleanup']['status']);self.assertIsNotNone(self.store().get(n.LEASE))
        self.assertFalse(any(v['method']=='DELETE' and v['path'].endswith('/999999999') for v in self.mutations()))

    def test_denied_deletion_keeps_lease_but_attempts_other_resources(self):
        result=self.run_failure(before=lambda _:setattr(self.input['http'],'fault','delete-denied'))
        self.assertEqual('FAIL',result['ownerRecovery']['cleanup']['status']);self.assertIsNotNone(self.store().get(n.LEASE))
        self.assertTrue(any(v['method']=='DELETE' and v['path'].startswith('/compute/') for v in self.mutations()))

    def test_retention_failure_does_not_prevent_cleanup_or_release_lease(self):
        def change(api):
            send=self.input['http'].send
            def denied(method,url,*args):
                if method=='POST' and 'preparation-failure' in url: return 403,b''
                return send(method,url,*args)
            self.input['http'].send=denied
        result=self.run_failure(before=change)
        self.assertEqual('PASS',result['ownerRecovery']['cleanup']['status']);self.assertEqual({},self.input['http'].resources)
        self.assertEqual('INCOMPLETE',result['ownerRecovery']['retention']);self.assertIsNotNone(self.store().get(n.LEASE))
        _,attempts=n.inspect_ledger(self.store().get(n.LEDGER)[1])
        self.assertEqual('PENDING',attempts[n.validate_request(self.api.req)]['status'])

    def test_changed_original_receipt_cannot_be_retained_as_this_attempt(self):
        def change(api):
            path=self.root/'evidence/receipt.json';value=read(path)
            value['requestSha256']='f'*64;path.write_bytes(m.canonical(value))
        result=self.run_failure(before=change)
        self.assertEqual('PASS',result['ownerRecovery']['cleanup']['status'])
        self.assertEqual('INCOMPLETE',result['ownerRecovery']['retention'])
        self.assertIsNotNone(self.store().get(n.LEASE));self.assertEqual({},self.input['http'].resources)

    def test_local_evidence_write_failure_still_attempts_cleanup_and_keeps_lease(self):
        write=q.r.write_once
        def fail(path,*args,**kwargs):
            if path.name=='admission-http.json':raise OSError('private local IO diagnostic')
            return write(path,*args,**kwargs)
        with patch.object(q.r,'write_once',side_effect=fail):result=self.run_failure()
        self.assertEqual('PASS',result['ownerRecovery']['cleanup']['status'],result)
        self.assertEqual({},self.input['http'].resources);self.assertIsNotNone(self.store().get(n.LEASE))
        self.assertNotIn('private local IO diagnostic',str(result))

    def test_expired_owner_cannot_begin_fresh_cleanup_or_retention_budget(self):
        count=[]
        def expired(api):
            self.input['clock'].sleep(5401);count.append(len(self.mutations()))
        result=self.run_failure(before=expired)
        self.assertIsNone(result['ownerRecovery']['cleanup']);self.assertEqual(count[0],len(self.mutations()))
        self.assertEqual(13,len(self.input['http'].resources))

    def test_lost_completion_reply_keeps_lease_and_expired_reconciler_preserves_failure(self):
        def change(api):
            send=self.input['http'].send
            def lost(method,url,*args):
                result=send(method,url,*args)
                if method=='POST' and parse_qs(urlsplit(url).query).get('name',[''])[0].endswith('/completion.json'):
                    raise ConnectionError('lost completion')
                return result
            self.input['http'].send=lost
        result=self.run_failure(before=change); self.assertFalse(result['ownerRecovery']['leaseReleased'])
        lease=self.store().get(n.LEASE)[1];saved=q.q.cleanup.snapshot(self.input['http'])
        prefix=n.PREFIX+'attempts/'+n.validate_request(lease['request'])+'/'
        original=self.store().get(prefix+'completion.json')
        clean,after,_=q.resources.replay(self.input['cfg']['provider'],q.q.pq.SOURCE,saved,
            self.root/'expired',lease['expiresAt']+lease['graceSeconds'])
        self.assertEqual('PASS',clean['status'],clean)
        _,model,raw,_=q.q.cleanup.restore(after)
        self.assertEqual(original,g.Store(self.input['cfg']['provider'],raw,authority=n).get(prefix+'completion.json'))
        self.assertNotIn(n.LEASE,model.objects)

    def test_closed_inventory_rejects_symlinks_and_excludes_unrelated_private_files(self):
        root=self.root/'files';root.mkdir();(root/'receipt.json').write_text('{"status":"FAIL"}')
        (root/'private-key').write_text('secret');self.assertEqual({'receipt.json'},set(f.evidence(root)))
        (root/'http.json').symlink_to(root/'private-key')
        with self.assertRaisesRegex(ValueError,'symlink'):f.evidence(root)

    def test_policy_rejects_create_foreign_reads_unretained_completion_and_name_delete(self):
        checked=[]
        def inspect(source):
            api=f._Api(source);store=api.admit();provider=api.provider
            spec=next(row['spec'] for row in api.lease['resources'] if row['attempted'])
            forbidden=[('POST',provider.url(spec).rsplit('/',1)[0],provider.body(spec)),
                ('DELETE',provider.url(spec),None), ('GET',store.url(n.PREFIX+'foreign.json'),None),
                ('POST',api.upload+'?uploadType=media&name='+api.attempt+'completion.json&ifGenerationMatch=0',{})]
            count=len(self.mutations())
            for method,url,body in forbidden:
                with self.assertRaises(ValueError):h.Api.call(api,method,url,body,deadline=api.clock()+30)
            self.assertEqual(count,len(self.mutations()));checked.append(True)
        result=self.run_failure(before=inspect)
        self.assertEqual([True],checked)
        # The test consumed the one-shot continuation; it cannot run twice.
        self.assertEqual('FAIL',result['ownerRecovery']['status'])

    def test_cleanup_and_whole_lease_deadlines_cannot_be_reset_by_base_api_calls(self):
        def inspect(source):
            api=f._Api(source);store=api.admit()
            self.input['clock'].sleep(601)
            with self.assertRaisesRegex(ValueError,'deadline'):
                h.Api.call(api,'GET',store.url(n.LEASE),deadline=api.clock()+600)
            api.retention({'receipt.json':b'original'})
            self.assertLessEqual(api.deadline,source.owner_deadline)
            spec=next(row['spec'] for row in api.lease['resources'] if row['attempted'])
            with self.assertRaisesRegex(ValueError,'retention cannot reopen'):
                h.Api.call(api,'GET',api.provider.url(spec),deadline=api.clock()+30)
            self.input['clock'].sleep(5400)
            with self.assertRaisesRegex(ValueError,'deadline'):
                h.Api.call(api,'GET',store.url(n.LEASE),deadline=api.clock()+600)
        result=self.run_failure(before=inspect)
        self.assertEqual('FAIL',result['ownerRecovery']['status'])
        self.assertEqual(13,len(self.input['http'].resources))

    def test_lost_delete_reply_is_not_replayed_and_lease_is_kept(self):
        lost=[]
        def change(api):
            send=self.input['http'].send
            def lose(method,url,*args):
                result=send(method,url,*args)
                if method=='DELETE' and '/compute/' in url and not lost:
                    lost.append(url);raise ConnectionError('lost delete')
                return result
            self.input['http'].send=lose
        result=self.run_failure(before=change)
        self.assertEqual('FAIL',result['ownerRecovery']['cleanup']['status']);self.assertIsNotNone(self.store().get(n.LEASE))
        deletes=[v['path'] for v in self.mutations() if v['method']=='DELETE' and '/compute/' in v['path']]
        self.assertEqual(len(deletes),len(set(deletes)));self.assertEqual(1,len(lost))

    def test_native_entry_invokes_cleanup_with_original_credentials_after_iap_failure(self):
        value=self.input;r=q.r;a=r.admission;original_read=a.artifacts.c.read
        value['probe'].fault='iap-denied'
        class Wire:
            offline=False
            def send(self,method,url,*args):
                return (q.q.auth.Provider(value['http']) if urlsplit(url).netloc in ('storage.googleapis.com','compute.googleapis.com')
                        else value['issuer']).send(method,url,*args)
        pins=a.ci.ROOT/'docs/v5x/v5.1/published-controls.json'
        with patch.object(a.ci,'github',side_effect=lambda p:deepcopy(value['data'][p])),\
             patch.object(a.build,'binding',return_value=value['binding']),\
             patch.object(a.entry,'credential_file',return_value=value['descriptor']),patch.object(h,'Network',Wire),\
             patch.object(r.time,'time',side_effect=value['clock'].wall),patch.object(r.time,'monotonic',side_effect=value['clock'].seconds),\
             patch.dict(a.credentials._Exchange.__init__.__kwdefaults__,clock=value['clock'].seconds,wall=value['clock'].wall),\
             patch.object(a.artifacts.c,'read',side_effect=lambda p:value['controls'] if p==pins else original_read(p)),\
             patch.object(r.iap,'_network_probe',side_effect=lambda api,target,deadline:value['probe'].identity(target,deadline)):
            result=r.prepare_native(value['cfg'],value['env'],q.q.pq.SOURCE,q.q.pq.SOURCE,value['preflight'],value['root'],value['value'],
                value['approved'],value['originals'],value['key'],self.root/'native')
        self.assertEqual('FAIL',result['status'],result);self.assertEqual('PASS',result['ownerRecovery']['status'])
        self.assertTrue(result['ownerRecovery']['paidCloud']);self.assertEqual({},value['http'].resources)
        self.assertIsNone(self.store().get(n.LEASE))


if __name__=='__main__':unittest.main()
