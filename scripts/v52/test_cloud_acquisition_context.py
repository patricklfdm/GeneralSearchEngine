from copy import deepcopy
import unittest
from unittest.mock import patch
from . import cloud_control as c, cloud_provider as p, cloud_wire_policy as w, cloud_authority as a
from .cloud_provider_offline import Server
from .test_cloud_provider import configuration
from .test_cloud_authority import fixture
from .evidence import encoded,strict


class PowerLoss(BaseException):pass


class AcquisitionContextTest(unittest.TestCase):
    def setUp(self):
        self.now=1000;self.cfg=configuration();self.req=fixture();self.req['configurationSha256']=p.config(self.cfg)
        self.server=Server(self.cfg);self.store,self.provider,self.owner=self.connect(self.req)
        self.stop=patch('scripts.v51.cloud_http.Network.send',side_effect=AssertionError('network forbidden'));self.stop.start();self.addCleanup(self.stop.stop)

    def connect(self,req,role='runner'):
        api=w.ScopedOfflineApi(self.server,req,role=role,previous_cost=None if role=='cleanup' else 0,cost=None if role=='cleanup' else 1,wall=lambda:self.now)
        store=p.Store(self.cfg,api);provider=p.Provider(store,req,wall=lambda:self.now,sleep=self.server.sleep)
        return store,provider,c.OfflineOwner(store,provider,req,wall=lambda:self.now) if role=='runner' else None

    def fail_at(self,cut):
        def fault(stage,row):
            if row['method']!='POST' or 'storage.googleapis.com' not in row['url']:return
            value=strict(row['body'])
            match=(cut=='before-context' and stage=='before' and value.get('schema')=='gse-v52-provider-context-v1' or
                   cut=='after-context' and stage=='after' and value.get('schema')=='gse-v52-provider-context-v1' or
                   cut=='after-lease' and stage=='after' and value.get('phase')=='ACQUIRING' or
                   cut=='after-reservation' and stage=='after' and value.get('schema')=='gse-v52-owned-ledger-v1' or
                   cut=='after-activation' and stage=='after' and value.get('phase')=='ACTIVE')
            if match:raise PowerLoss(cut)
        self.server.fault=fault

    def test_context_write_precedes_every_lease_or_ledger_write(self):
        self.owner.acquire(previous_cost=0,cost=1)
        writes=[strict(row['body']) for row in self.server.events if row['method']=='POST']
        self.assertEqual('gse-v52-provider-context-v1',writes[0]['schema'])
        self.assertEqual('ACQUIRING',writes[1]['phase']);self.assertEqual('ACTIVE',writes[-1]['phase'])
        self.assertEqual({},self.server.resources)

    def test_abrupt_loss_before_context_cannot_leave_a_lease_or_charge(self):
        self.fail_at('before-context')
        with self.assertRaises(PowerLoss):self.owner.acquire(previous_cost=0,cost=1)
        self.assertEqual({},self.server.objects);self.assertEqual({},self.server.resources)

    def test_abrupt_loss_after_context_does_not_reserve_or_create(self):
        self.fail_at('after-context')
        with self.assertRaises(PowerLoss):self.owner.acquire(previous_cost=0,cost=1)
        self.server.fault=lambda *args:None
        self.assertIsNotNone(self.store.get(p.context_key(self.req)))
        self.assertIsNone(self.store.get(a.LEASE));self.assertIsNone(self.store.get(a.LEDGER))
        self.assertEqual({},self.server.resources)

    def cold_cleanup(self,cut):
        self.fail_at(cut)
        with self.assertRaises(PowerLoss):self.owner.acquire(previous_cost=0,cost=1)
        self.server.fault=lambda *args:None
        self.assertIsNotNone(self.store.get(p.context_key(self.req)))
        lease=self.store.get(a.LEASE)[1];self.assertFalse(any(row['attempted'] for row in lease['resources']))
        self.now=1090;store,_,_=self.connect(self.req,'cleanup');provider=p.reconstruct(store,self.req)
        result=c.reconcile(store,provider,trigger='workflow_dispatch',now=self.now)
        self.assertEqual('PASS',result['status']);self.assertIsNone(store.get(a.LEASE));self.assertEqual({},self.server.resources)
        self.assertFalse(any(row['method']=='DELETE' and 'compute.googleapis.com' in row['url'] for row in self.server.events))
        ledger=store.get(a.LEDGER)
        if ledger:self.assertEqual('FAIL',next(iter(a.inspect_ledger(ledger[1],domain='offline')['attempts'].values()))['status'])

    def test_cold_cleanup_after_lease_before_charge_uses_retained_original_context(self):self.cold_cleanup('after-lease')
    def test_cold_cleanup_after_charge_before_activation_keeps_original_failed_cost(self):self.cold_cleanup('after-reservation')
    def test_cold_cleanup_after_activation_before_first_intent_releases_without_resources(self):self.cold_cleanup('after-activation')

    def test_initial_lease_cannot_be_created_without_retained_context(self):
        with self.assertRaisesRegex(ValueError,'retained context'):c.put(self.store,a.LEASE,a.lease(self.req,1000),0)
        self.assertEqual({},self.server.objects)

    def test_concurrent_contexts_do_not_bypass_the_single_lease_cas(self):
        other=fixture(attempt='d'*32);other['configurationSha256']=p.config(self.cfg)
        store,provider,owner=self.connect(other);raced=False
        def fault(stage,row):
            nonlocal raced
            if stage=='after' and row['method']=='POST' and not raced and strict(row['body']).get('schema')=='gse-v52-provider-context-v1':
                raced=True;owner.acquire(previous_cost=0,cost=1)
        self.server.fault=fault
        with self.assertRaises(ValueError):self.owner.acquire(previous_cost=0,cost=1)
        self.server.fault=lambda *args:None
        self.assertEqual(other,store.get(a.LEASE)[1]['request'])
        view=a.inspect_ledger(store.get(a.LEDGER)[1],domain='offline');self.assertEqual(1,len(view['attempts']));self.assertEqual(1,view['reservedCostMicrousd'])
        self.assertEqual({},self.server.resources)


if __name__=='__main__':unittest.main()
