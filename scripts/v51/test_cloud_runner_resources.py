from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from . import cloud_runner_resource_qualification as q, cloud_runner_resources as r
from . import cloud_http as h, cloud_native_authority as n, performance_model as m
from .remote_command import read


class RunnerResourcesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        frozen = r.admission.workload.load()
        loader = patch.object(r.admission.workload,'load',side_effect=lambda:deepcopy(frozen))
        loader.start();cls.addClassCleanup(loader.stop)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.f=q.fixture(self.root/'inputs',self.root/'private')

    def prepare(self): return q.prepare(self.f,self.root/'evidence')
    def mutations(self): return [v for v in self.f['http'].requests if v['method'] != 'GET']

    def test_complete_stage_is_partial_with_one_insert_per_resource_and_pending_charge(self):
        result=self.prepare();self.assertEqual('PARTIAL',result['status'])
        self.assertEqual('RESOURCES_AND_IAP_READY',result['stage']);self.assertEqual(3,len(result['guests']))
        inserts=[v for v in self.mutations() if v['path'].startswith('/compute/')]
        self.assertEqual(13,len(inserts));self.assertEqual(13,len({v['query']['requestId'] for v in inserts}))
        self.assertEqual(3,len(self.f['probe'].calls))
        _,model,raw,_=q.q.cleanup.restore(q.q.cleanup.snapshot(self.f['http']))
        ledger=q.g.Store(self.f['cfg']['provider'],raw,authority=n).get(n.LEDGER)[1]
        cost,entries=n.inspect_ledger(ledger)
        self.assertEqual(q.q.COST,cost);self.assertEqual({'PENDING'},{v['status'] for v in entries.values()})
        self.assertIn(n.LEASE,model.objects)
        for key in ('paidCloud','paidAdmission','engineWorkloadExecuted','fullRemoteQualification'):self.assertIs(result[key],False)
        self.assertEqual([],list((self.root/'evidence').rglob('identity')))

    def test_second_invocation_cannot_reuse_receipt_or_active_lease(self):
        self.assertEqual('PARTIAL',self.prepare()['status']);count=len(self.mutations())
        result=q.prepare(self.f,self.root/'again')
        self.assertEqual('FAIL',result['status']);self.assertEqual('admission',result['failure']['phase'])
        self.assertEqual(count,len(self.mutations()))

    def test_unapproved_or_corrupt_original_blocks_before_credentials(self):
        self.f['approved']['confirmed']=False
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.mutations())
        self.assertEqual([],self.f['issuer'].calls)

    def test_wrong_private_key_blocks_before_credentials(self):
        q.guest_setup.generate(self.root/'wrong-key','f'*32);self.f['key']=self.root/'wrong-key/identity'
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.f['issuer'].calls)
        self.assertEqual([],self.mutations())

    def test_master_moving_during_resource_name_scan_blocks_first_cas(self):
        http=self.f['http'];original=http.send;changed=False
        def send(method,url,*args):
            nonlocal changed
            if method=='GET' and '/compute/v1/projects/' in url and not changed:
                changed=True;self.f['data']['branches/master']['commit']['sha']='e'*40
            return original(method,url,*args)
        http.send=send
        self.assertEqual('FAIL',self.prepare()['status']);self.assertTrue(changed);self.assertEqual([],self.mutations())
        self.assertEqual('admission-recheck',read(self.root/'evidence/resources/receipt.json')['failure']['phase'])

    def test_artifact_replaced_during_resource_scan_blocks_first_cas(self):
        http=self.f['http'];original=http.send;changed=False
        def send(method,url,*args):
            nonlocal changed
            if method=='GET' and '/compute/v1/projects/' in url and not changed:
                changed=True;(self.f['originals']/'package.zip').write_bytes(b'changed')
            return original(method,url,*args)
        http.send=send
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.mutations())

    def test_original_deadline_cannot_be_renewed_by_reinspection(self):
        http=self.f['http'];original=http.send;delayed=False
        def send(method,url,*args):
            nonlocal delayed
            if method=='GET' and '/compute/v1/projects/' in url and not delayed:
                delayed=True;self.f['clock'].sleep(181)
            return original(method,url,*args)
        http.send=send
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.mutations())

    def test_insert_401_is_submitted_once_without_credential_retry(self):
        http=self.f['http'];original=http.send;calls=0
        def send(method,url,*args):
            nonlocal calls
            if method=='POST' and '/compute/v1/' in url:
                calls+=1;return 401,b''
            return original(method,url,*args)
        http.send=send
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual(1,calls)
        stage=read(self.root/'evidence/resources/receipt.json')
        self.assertEqual(dict(phase='insert',type='ApiError',httpStatus=401),stage['failure'])
        self.assertEqual(3,len(self.f['issuer'].calls));self.assertEqual([],self.f['probe'].calls)

    def test_lost_create_reply_does_not_replay_or_attempt_iap(self):
        q.resources.inject('lost-insert-11',self.f['clock'],self.f['http'])
        result=self.prepare();self.assertEqual('FAIL',result['status'])
        self.assertEqual(11,self.f['http'].inserts);self.assertEqual([],self.f['probe'].calls)
        self.assertEqual((10,1),(result['confirmedResourceCount'],result['unresolvedIntentCount']))
        self.assertTrue(result['resourcesCreated']);self.assertEqual(self.f['approved']['requestSha256'],result['requestSha256'])
        stage=read(self.root/'evidence/resources/receipt.json')
        self.assertEqual(dict(phase='insert',type='ConnectionError'),stage['failure'])

    def test_lost_first_insert_is_unknown_rather_than_no_resources_created(self):
        q.resources.inject('lost-insert-1',self.f['clock'],self.f['http'])
        result=self.prepare();self.assertEqual('FAIL',result['status'])
        self.assertEqual((0,1),(result['confirmedResourceCount'],result['unresolvedIntentCount']))
        self.assertIsNone(result['resourcesCreated'])

    def test_guest_identity_drift_stops_without_replaying_probe(self):
        self.f['probe'].fault='guest-id-drift'
        result=self.prepare();self.assertEqual(dict(phase='iap',type='ValueError'),{k:result['failure'][k] for k in ('phase','type')})
        self.assertEqual(1,len(self.f['probe'].calls));self.assertEqual(13,self.f['http'].inserts)
        self.assertEqual('SUBMITTING',read(self.root/'evidence/iap/node-1-probe.json')['status'])
        self.assertFalse((self.root/'evidence/iap/node-1.json').exists())
        self.assertFalse((self.root/'evidence/iap/node-2-probe.json').exists())

    def test_provider_replacement_after_probe_is_not_accepted(self):
        probe=self.f['probe'];original=probe.identity
        def identity(target,deadline):
            result=original(target,deadline)
            next(v for v in self.f['http'].resources.values() if v['id']==target['instanceId'])['id']='999999'
            return result
        probe.identity=identity
        result=self.prepare();self.assertEqual('FAIL',result['status']);self.assertEqual('iap',result['failure']['phase'])
        self.assertEqual(1,len(probe.calls))

    def test_guest_agent_host_key_readiness_polls_only_reads_under_original_deadline(self):
        http=self.f['http'];hook=http.hook;calls=0
        def pending(method,path,query,body):
            nonlocal calls
            if path.path.endswith('/getGuestAttributes'):
                calls+=1
                if calls<=2:return http.reply(dict(queryPath='hostkeys/',queryValue=dict(items=[])))
            return hook(method,path,query,body)
        http.hook=pending
        result=self.prepare();self.assertEqual('PARTIAL',result['status'])
        self.assertEqual(2,result['elapsedSeconds']);self.assertEqual(13,http.inserts)
        self.assertEqual(3,len(self.f['probe'].calls))

    def test_persistent_missing_host_key_exhausts_original_budget_without_iap(self):
        http=self.f['http'];hook=http.hook
        def pending(method,path,query,body):
            if path.path.endswith('/getGuestAttributes'):
                self.f['clock'].sleep(29)
                return http.reply(dict(queryPath='hostkeys/',queryValue=dict(items=[])))
            return hook(method,path,query,body)
        http.hook=pending
        self.assertEqual('FAIL',self.prepare()['status']);self.assertEqual([],self.f['probe'].calls)
        self.assertEqual(13,http.inserts)

    def test_host_key_404_then_ready_polls_same_instance_without_recreating(self):
        http=self.f['http'];hook=http.hook;calls=0
        def pending(method,path,query,body):
            nonlocal calls
            if path.path.endswith('-n3/getGuestAttributes'):
                calls+=1
                if calls<=2:return 404,b''
            return hook(method,path,query,body)
        http.hook=pending
        result=self.prepare();self.assertEqual('PARTIAL',result['status'],result)
        self.assertEqual(2,result['elapsedSeconds']);self.assertEqual(13,http.inserts)
        self.assertEqual(3,len(self.f['probe'].calls))

    def test_persistent_host_key_404_stops_at_original_deadline_without_iap(self):
        http=self.f['http'];hook=http.hook;calls=0
        def pending(method,path,query,body):
            nonlocal calls
            if path.path.endswith('/getGuestAttributes'):
                calls+=1;self.f['clock'].sleep(29)
                return 404,b''
            return hook(method,path,query,body)
        http.hook=pending
        result=self.prepare()
        self.assertEqual(dict(phase='iap',type='ValueError'),{k:result['failure'][k] for k in ('phase','type')})
        self.assertEqual(600,result['elapsedSeconds']);self.assertEqual(20,calls)
        self.assertEqual([],self.f['probe'].calls);self.assertEqual(13,http.inserts)

    def test_denied_host_key_query_is_not_readiness_retry(self):
        http=self.f['http'];hook=http.hook;calls=0
        def denied(method,path,query,body):
            nonlocal calls
            if path.path.endswith('/getGuestAttributes'):calls+=1;return 403,b''
            return hook(method,path,query,body)
        http.hook=denied
        result=self.prepare();self.assertEqual(dict(phase='iap',type='ApiError',httpStatus=403),{k:result['failure'][k] for k in ('phase','type','httpStatus')})
        self.assertEqual(1,calls);self.assertEqual([],self.f['probe'].calls)

    def test_resource_policy_blocks_mutations_until_gate_and_host_queries_before_completion(self):
        inspected=q.q.inspect(self.f);api=r._Api(inspected,now=self.f['clock'].wall(),deadline=self.f['clock'].seconds()+600)
        with self.assertRaisesRegex(ValueError,'gate closed'):api.upload()
        api.failed=False
        spec=next(v['spec'] for v in api.lease['resources'] if v['spec']['kind']=='instance')
        with self.assertRaises(ValueError):
            h.Api.call(api,'GET',api.provider().url(spec)+'/getGuestAttributes?queryPath=hostkeys%2F',deadline=api.deadline)
        self.assertEqual([],self.mutations())

    def test_host_key_scope_and_read_deadline_remain_closed_through_base_api(self):
        captured=[];original=r._Api.__init__
        def initialize(api,*args,**kw):original(api,*args,**kw);captured.append(api)
        with patch.object(r._Api,'__init__',initialize):self.assertEqual('PARTIAL',self.prepare()['status'])
        api=captured[0];spec=next(v['spec'] for v in api.lease['resources'] if v['spec']['kind']=='instance')
        url=api.provider().url(spec)+'/getGuestAttributes'
        for tail in ('?queryPath=foreign','?queryPath=hostkeys%2F&queryPath=hostkeys%2F',''):
            with self.assertRaises(ValueError):h.Api.call(api,'GET',url+tail,deadline=api.deadline)
        self.f['clock'].sleep(601)
        with self.assertRaisesRegex(ValueError,'deadline'):
            h.Api.call(api,'GET',api.provider().url(spec),deadline=api.clock()+100)

    def test_native_constructor_owns_network_checkout_credential_and_probe_boundaries(self):
        f=self.f;get=lambda path:deepcopy(f['data'][path]);original_read=r.admission.artifacts.c.read
        class Wire:
            offline=False
            def send(self,method,url,*args):
                return (q.q.auth.Provider(f['http']) if urlsplit(url).netloc in ('storage.googleapis.com','compute.googleapis.com')
                        else f['issuer']).send(method,url,*args)
        pins=r.admission.ci.ROOT/'docs/v5x/v5.1/published-controls.json'
        with patch.object(r.admission.ci,'github',side_effect=get),\
             patch.object(r.admission.build,'binding',return_value=f['binding']) as binding,\
             patch.object(r.admission.entry,'credential_file',return_value=f['descriptor']),patch.object(h,'Network',Wire),\
             patch.object(r.time,'time',side_effect=f['clock'].wall),patch.object(r.time,'monotonic',side_effect=f['clock'].seconds),\
             patch.dict(r.admission.credentials._Exchange.__init__.__kwdefaults__,clock=f['clock'].seconds,wall=f['clock'].wall),\
             patch.object(r.admission.artifacts.c,'read',side_effect=lambda p:f['controls'] if p==pins else original_read(p)),\
             patch.object(r.iap,'_network_probe',side_effect=lambda api,target,deadline:f['probe'].identity(target,deadline)) as probe:
            result=r.prepare_native(f['cfg'],f['env'],q.q.pq.SOURCE,q.q.pq.SOURCE,f['preflight'],f['root'],f['value'],
                f['approved'],f['originals'],f['key'],self.root/'evidence')
        self.assertEqual('PARTIAL',result['status']);self.assertEqual('native-runner-resource-entry',result['execution'])
        self.assertTrue(result['paidAdmission']);self.assertTrue(result['paidCloud'])
        self.assertFalse(result['fullRemoteQualification']);self.assertEqual(2,binding.call_count);self.assertEqual(3,probe.call_count)
        with self.assertRaises(TypeError):r.prepare_native(transport=Wire())


if __name__=='__main__':unittest.main()
