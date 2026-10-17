from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import unittest
from . import cloud_authority as a, cloud_control as c, cloud_offline as offline
from .test_cloud_authority import fixture


class ControlTest(unittest.TestCase):
    def setUp(self):
        self.store = offline.Store(); self.provider = offline.Provider(self.store)
        self.req = fixture(); self.now = 1000
        self.owner = c.OfflineOwner(self.store, self.provider, self.req, wall=lambda: self.now)

    def prepare(self, cost=1): return self.owner.prepare(previous_cost=0, cost=cost)
    def ledger(self): return a.inspect_ledger(self.store.get(a.LEDGER)[1], domain='offline')
    def cleanup(self, now=1090, trigger='workflow_dispatch'):
        return c.reconcile(self.store, self.provider, trigger=trigger, now=now)

    def test_real_control_path_retains_intent_before_all_thirteen_creates(self):
        result = self.prepare()
        self.assertEqual('RESOURCES_PREPARED_NOT_QUALIFIED', result['status'])
        self.assertFalse(result['fullRemoteQualification']); self.assertFalse(result['paidCloud'])
        creates = [r for r in self.provider.events if r['action']=='create']
        self.assertEqual(13, len(creates)); self.assertEqual(13, len(self.provider.objects))
        writes = [e['value'] for e in self.store.events if e['action']=='put' and e['key']==a.LEASE]
        for i in range(13):
            self.assertTrue(any(row['resources'][i]['attempted'] and row['resources'][i]['id'] is None for row in writes))
        result = self.owner.close(); self.assertEqual('PASS', result['status']); self.assertTrue(result['leaseReleased'])
        self.assertEqual({}, self.provider.objects); self.assertIsNone(self.store.get(a.LEASE))
        self.assertEqual(['instance']*3+['disk']*6+['firewall']*4,
            [r['spec']['kind'] for r in self.provider.events if r['action']=='delete'])
        self.assertEqual('FAIL', next(iter(self.ledger()['attempts'].values()))['status'])
        self.assertEqual(result, self.owner.close())

    def test_native_records_and_lookalike_adapters_cannot_enable_network_entry(self):
        with self.assertRaisesRegex(ValueError, 'request domain'):
            c.OfflineOwner(self.store, self.provider, fixture(domain='native'))
        class Lookalike(offline.Provider): pass
        for provider in (Lookalike(self.store), offline.Provider(offline.Store())):
            with self.assertRaisesRegex(ValueError, 'not admitted'): c.OfflineOwner(self.store, provider, self.req)
        self.assertEqual([], self.store.events)

    def test_existing_v51_control_objects_are_neither_read_nor_modified(self):
        from scripts.v51 import cloud_authority as old
        self.store.put(old.LEASE, {'old':'lease'}, 0); self.store.put(old.LEDGER, {'old':'ledger'}, 0)
        before = {k:self.store.get(k) for k in (old.LEASE,old.LEDGER)}
        def reject(action,key,value):
            if key in before:raise AssertionError('V5.1 object accessed')
        self.store.fault=reject;self.prepare();self.owner.close()
        self.store.fault=lambda *args:None
        self.assertEqual(before,{k:self.store.get(k) for k in before})

    def test_duplicate_preparation_does_not_clean_or_resubmit_original_resources(self):
        self.prepare();before=deepcopy(self.provider.events);original=self.store.get(a.LEASE)
        with self.assertRaisesRegex(ValueError,'already consumed'):self.prepare()
        self.assertEqual(original,self.store.get(a.LEASE));self.assertEqual(before,self.provider.events)
        self.owner.checkpoint();self.owner.close()

    def test_slow_original_insert_does_not_block_lease_renewal(self):
        entered=threading.Event();resume=threading.Event();first=True
        def fault(action,spec):
            nonlocal first
            if action=='before-create' and first:
                first=False;entered.set()
                if not resume.wait(5):raise TimeoutError('test insert not released')
        self.provider.fault=fault
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.prepare)
            try:
                self.assertTrue(entered.wait(5));self.now=1050
                self.assertEqual(1110,self.owner.renew()['expiresAt'])
            finally:resume.set()
            self.assertEqual('RESOURCES_PREPARED_NOT_QUALIFIED',future.result(timeout=10)['status'])
        self.assertEqual(13,sum(r['action']=='create' for r in self.provider.events));self.owner.close()

    def test_schedule_and_manual_wait_until_expiry_plus_grace_without_writes(self):
        self.prepare(); before = deepcopy(self.store.events); calls = deepcopy(self.provider.events)
        for event in ('schedule','workflow_dispatch'):
            self.assertEqual('WAITING', self.cleanup(now=1089, trigger=event)['status'])
        self.assertEqual(before, self.store.events); self.assertEqual(calls, self.provider.events)
        self.assertEqual('PASS', self.cleanup()['status']); self.assertEqual({}, self.provider.objects)
        before = deepcopy(self.store.events)
        self.assertEqual('PASS', self.cleanup()['status']); self.assertEqual(before, self.store.events)

    def test_renewal_preserves_resources_and_soft_budget_does_not_end_work(self):
        result = self.prepare(cost=300_000_000); self.assertTrue(result['warning']['exceeded'])
        ids = [r['id'] for r in self.owner.lease['resources']]
        for _ in range(4):
            self.now += 50; self.owner.renew()
        self.assertGreater(self.now, 1060); self.assertEqual(ids, [r['id'] for r in self.owner.checkpoint()['resources']])
        self.assertEqual('WAITING', self.cleanup(now=self.now+89)['status'])
        self.assertEqual('PASS', self.cleanup(now=self.now+90)['status'])
        self.assertEqual(300_000_000, self.ledger()['reservedCostMicrousd'])

    def test_expired_or_cleaning_owner_cannot_revive_or_create(self):
        self.owner.acquire(previous_cost=0, cost=1); self.now = 1060
        for action in (self.owner.checkpoint, self.owner.renew, self.owner.provision):
            with self.assertRaises(ValueError): action()
        self.assertEqual([], self.provider.events)
        self.cleanup(); self.now = 1001
        with self.assertRaises(ValueError): self.owner.renew()

    def test_resource_claim_stays_bound_to_original_ids_across_renewal(self):
        self.prepare();claim=self.owner.resource_claim()
        self.now=1050;self.owner.renew();self.assertEqual(claim,self.owner.resource_claim())
        changed=deepcopy(self.owner.lease);changed['resources'][-1]['id']='999999'
        self.assertNotEqual(claim,a.resource_claim(changed))
        self.owner.close()
        with self.assertRaises(ValueError):self.owner.resource_claim()

    def test_lost_original_cas_responses_are_observed_without_resubmission(self):
        seen = set()
        def fault(action, key, value):
            tag = (key, a.digest(a.encoded(value))) if value is not None else None
            if action == 'after-put' and tag not in seen:
                seen.add(tag); raise ConnectionError('lost original CAS reply')
        self.store.fault = fault
        self.prepare(); self.assertEqual('PASS', self.owner.close()['status'])
        ledger_events = [r['value'] for r in self.store.events if r['action']=='put' and r['key']==a.LEDGER]
        self.assertEqual([1,2], [len(v['entries']) for v in ledger_events])
        self.assertEqual(13, sum(v['action']=='create' for v in self.provider.events))

    def test_lost_cas_readback_recovers_original_write(self):
        armed = False; queries = 0
        def fault(action,key,value):
            nonlocal armed, queries
            if action == 'after-put': armed = True
            elif action == 'get' and armed:
                queries += 1; armed = False; raise TimeoutError('lost read-back')
        self.store.fault = fault
        self.owner.acquire(previous_cost=0,cost=1)
        self.assertEqual(3, queries); self.owner.close()

    def test_repeated_observation_failure_is_bounded_and_never_reissues_cas(self):
        calls = []; original = self.store.put
        def fault(action,key,value):
            calls.append(action)
            if action == 'before-put': raise ConnectionError('not submitted')
            if action == 'get': raise TimeoutError('cannot observe')
        self.store.fault = fault
        with self.assertRaisesRegex(ValueError, 'CAS outcome unresolved'): c.put(self.store, a.LEASE, {}, 0)
        self.assertEqual(['before-put','get','get','get'], calls); self.assertEqual({},self.store.objects)

    def test_original_insert_reply_loss_is_cleaned_by_operation_id_not_recreated(self):
        def fault(action,spec):
            if action == 'after-create' and spec['purpose']=='iap': raise ConnectionError('lost insert reply')
        self.provider.fault = fault
        with self.assertRaisesRegex(ConnectionError,'lost insert'): self.prepare()
        self.assertEqual(3, sum(r['action']=='create' for r in self.provider.events))
        self.assertEqual(3, sum(r['action']=='delete' for r in self.provider.events))
        self.assertEqual('PASS',self.owner.cleanup_result['status']); self.assertEqual({},self.provider.objects)
        self.assertIsNone(self.store.get(a.LEASE)); self.assertEqual(1,self.ledger()['reservedCostMicrousd'])
        self.assertEqual('ConnectionError',self.owner.preparation_failure['type'])

    def test_pending_create_remains_fenced_until_original_operation_finishes(self):
        def fault(action,spec):
            if action=='before-create' and spec['purpose']=='iap':
                self.provider.operations[spec['operationId']] = dict(spec=deepcopy(spec),state='PENDING',id=None)
                raise TimeoutError('original insertion pending')
        self.provider.fault = fault
        with self.assertRaises(TimeoutError): self.prepare()
        self.assertEqual('FAIL',self.owner.cleanup_result['status']); self.assertEqual('CLEANING',self.store.get(a.LEASE)[1]['phase'])
        self.assertEqual('FAIL',self.cleanup(now=1001)['status'])
        spec = a.resources(self.req)[2]; self.provider.operations[spec['operationId']].update(state='DONE',id=None)
        self.assertEqual('PASS',self.cleanup(now=1002)['status']); self.assertIsNone(self.store.get(a.LEASE))
        self.assertEqual(3,sum(r['action']=='create' for r in self.provider.events))

    def test_unknown_original_operation_is_not_treated_as_absence(self):
        self.owner.acquire(previous_cost=0,cost=1)
        value=deepcopy(self.owner.lease);value['resources'][0]['attempted']=True;self.owner.persist(value)
        self.assertEqual('FAIL',self.owner.close()['status'])
        self.assertIsNotNone(self.store.get(a.LEASE));self.assertEqual([],self.provider.events)

    def test_reused_numeric_id_is_never_deleted_but_other_owned_resources_are_cleaned(self):
        self.prepare(); row=self.owner.lease['resources'][-1];name=row['spec']['name']
        self.provider.objects[name]['id']='999999'
        outcome=self.owner.close()
        self.assertEqual('FAIL',outcome['status']);self.assertEqual({name},set(self.provider.objects))
        self.assertFalse(any(r['action']=='delete' and r['id']=='999999' for r in self.provider.events))
        del self.provider.objects[name]
        self.assertEqual('PASS',self.cleanup(now=1001)['status'])

    def test_foreign_name_without_an_original_intent_is_left_untouched(self):
        spec=a.resources(self.req)[0];foreign=dict(spec=dict(spec,owner='foreign'),id='999999')
        self.provider.objects[spec['name']]=deepcopy(foreign)
        with self.assertRaisesRegex(ValueError,'intent already consumed'):self.prepare()
        self.assertEqual(foreign,self.provider.objects[spec['name']]);self.assertEqual([],self.provider.events)

    def test_fenced_owner_does_not_advance_to_second_insert_or_reacquire(self):
        def fence(action,spec):
            if action=='after-create':
                generation,lease=self.store.get(a.LEASE);lease['phase']='CLEANING';self.store.put(a.LEASE,lease,generation)
        self.provider.fault=fence
        with self.assertRaisesRegex(ValueError,'active owner fenced'):self.prepare()
        self.assertEqual(1,sum(r['action']=='create' for r in self.provider.events))
        with self.assertRaises(ValueError):self.owner.renew()
        self.assertEqual('PASS',self.cleanup(now=1000)['status'])
        with self.assertRaisesRegex(ValueError,'already consumed'):self.owner.acquire(previous_cost=1,cost=1)

    def test_competing_acquisitions_allow_exactly_one_charged_owner(self):
        barrier=threading.Barrier(2)
        def fault(action,key,value):
            if action=='before-put' and key==a.LEASE and value['phase']=='ACQUIRING':barrier.wait(timeout=5)
        self.store.fault=fault
        other=c.OfflineOwner(self.store,self.provider,fixture(attempt='d'*32),wall=lambda:1000)
        def claim(owner):
            try:owner.acquire(previous_cost=0,cost=1);return owner
            except ValueError:return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            calls=[pool.submit(claim,o) for o in (self.owner,other)];results=[f.result(timeout=10) for f in calls]
        winners=[r for r in results if r is not None];self.assertEqual(1,len(winners));self.assertEqual(1,len(self.ledger()['attempts']))
        winners[0].close()

    def test_ledger_write_failure_before_reservation_releases_only_uncharged_empty_lease(self):
        def fault(action,key,value):
            if action=='before-put' and key==a.LEDGER:raise PermissionError('reservation denied')
        self.store.fault=fault
        with self.assertRaises(PermissionError):self.prepare()
        self.assertIsNone(self.store.get(a.LEASE));self.assertIsNone(self.store.get(a.LEDGER));self.assertEqual([],self.provider.events)
        self.assertEqual('PASS',self.owner.cleanup_result['status'])

    def test_missing_charge_on_attempted_inventory_blocks_before_any_deletion(self):
        self.prepare();version,_=self.store.get(a.LEDGER);self.store.delete(a.LEDGER,version)
        before=deepcopy(self.provider.events)
        with self.assertRaisesRegex(ValueError,'resource reservation'):self.cleanup()
        self.assertEqual(before,self.provider.events);self.assertEqual(13,len(self.provider.objects))

    def test_failed_completion_retention_keeps_lease_and_original_cleanup_recovers(self):
        self.prepare()
        def fault(action,key,value):
            if action=='before-put' and key.endswith('/completion.json'):raise PermissionError('retention denied')
        self.store.fault=fault
        with self.assertRaises(PermissionError):self.owner.close()
        self.assertEqual({},self.provider.objects);self.assertIsNotNone(self.store.get(a.LEASE))
        self.assertEqual('PENDING',next(iter(self.ledger()['attempts'].values()))['status'])
        self.store.fault=lambda *args:None
        self.assertEqual('PASS',self.cleanup(now=1001)['status']);self.assertIsNone(self.store.get(a.LEASE))

    def test_lost_release_reply_is_observed_without_deleting_a_new_owner(self):
        self.prepare();replacement=a.lease(fixture(attempt='d'*32),1000)
        def fault(action,key,value):
            if action=='after-delete' and key==a.LEASE:
                self.store.put(a.LEASE,replacement,0);raise ConnectionError('release reply lost')
        self.store.fault=fault
        result=self.owner.close();self.assertTrue(result['leaseReleased'])
        self.assertEqual(replacement,self.store.get(a.LEASE)[1])
        self.assertEqual(1,sum(r['action']=='delete' and r['key']==a.LEASE for r in self.store.events))

    def test_new_version_of_same_original_lease_is_not_reported_released(self):
        self.prepare()
        def fault(action,key,value):
            if action=='before-delete' and key==a.LEASE:
                version,current=self.store.get(a.LEASE)
                self.store.put(a.LEASE,current,version)
                raise TimeoutError('another reconciler advanced the same lease')
        self.store.fault=fault
        with self.assertRaisesRegex(ValueError,'original lease release unresolved'):self.owner.close()
        self.assertIsNotNone(self.store.get(a.LEASE))
        self.assertFalse(any(r['action']=='delete' for r in self.store.events))
        self.store.fault=lambda *args:None
        self.assertEqual('PASS',self.cleanup(now=1001)['status'])

    def test_delete_success_without_actual_absence_cannot_release_lease(self):
        self.prepare();self.provider.delete=lambda spec,identity:None
        result=self.owner.close();self.assertEqual('FAIL',result['status'])
        self.assertEqual(13,len(result['cleanup']['leftovers']));self.assertIsNotNone(self.store.get(a.LEASE))

    def test_original_failed_completion_is_not_rewritten_by_later_successful_cleanup(self):
        self.prepare();row=self.owner.lease['resources'][-1]
        def fault(action,spec):
            if action=='before-delete' and spec==row['spec']:raise PermissionError('delete denied')
        self.provider.fault=fault;self.assertEqual('FAIL',self.owner.close()['status'])
        key=c.attempt_key(self.req)+'completion.json';first=self.store.get(key)
        self.provider.fault=lambda *args:None
        self.assertEqual('PASS',self.cleanup(now=1001)['status']);self.assertEqual(first,self.store.get(key))
        self.assertEqual('FAIL',first[1]['status']);self.assertEqual(2,len(self.store.get(a.LEDGER)[1]['entries']))


if __name__=='__main__':unittest.main()
