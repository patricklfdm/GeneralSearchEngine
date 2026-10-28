from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import contextlib
import io
import runpy
import sys
import tempfile
import unittest
import warnings
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit
from . import cloud_native_cleanup as n, cloud_preflight as f, cloud_preflight_read as r
from . import cloud_credentials as credentials, cloud_credentials_offline as auth
from . import cloud_authority as a, cloud_provider as p, cloud_control as c, cloud_wire_policy as w
from .cloud_provider_offline import Server
from .cloud_preflight_offline import Server as Observations
from .test_cloud_preflight import configuration, SOURCE
from .test_cloud_authority import fixture
from .evidence import encoded, strict, digest


class NativeCleanupTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=configuration();self.original=deepcopy(self.cfg['provider']);self.role='manual';self.count=0
        self.make();self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(n.os.environ,self.env,clear=True))
        self.source=self.stack.enter_context(patch.object(r,'source_configuration',side_effect=lambda source:deepcopy(self.cfg)))
        self.stack.enter_context(patch.object(credentials,'checkout',return_value=SOURCE))
        self.stack.enter_context(patch.object(credentials,'github',side_effect=lambda path,end,clock:self.invocation.get(path,end)))
        self.stack.enter_context(patch.object(credentials,'credential_file',side_effect=lambda *args:self.descriptor))
        self.stack.enter_context(patch.object(n.time,'monotonic',side_effect=lambda:self.clock.seconds()))
        self.stack.enter_context(patch.object(n.time,'time',side_effect=lambda:self.clock.wall()))
        self.stack.enter_context(patch.object(n.h.Network,'send',new=lambda _,*args:self.send(*args)))
        self.captured=[];original=n.NativeCleanupApi.__init__
        def capture(api,*args):original(api,*args);self.captured.append(api)
        self.stack.enter_context(patch.object(n.NativeCleanupApi,'__init__',new=capture))
        self.change=lambda method,url,body:None;self.response=None

    def make(self):
        self.project,self.env,self.descriptor,self.invocation,self.issuer=auth.fixture(self.cfg['provider'],self.role,SOURCE)
        self.clock=self.invocation.clock;self.observations=Observations(self.cfg,self.role,self.clock)
        self.server=Server(self.original);self.calls=[]

    def send(self,method,url,headers,body,timeout,maximum):
        self.calls.append(dict(method=method,url=url,body=body))
        self.change(method,url,body)
        if self.response is not None:return self.response
        if url in self.observations.routes:
            return self.observations.send(method,url,headers,body,timeout,maximum)
        if url.startswith(('https://compute.googleapis.com/','https://storage.googleapis.com/')):
            parts=urlsplit(url)
            if parts.query.startswith('fields='):url=urlunsplit(parts._replace(query=''))
            # Test-only network boundary. Real NativeCleanupApi/NetworkCredentials
            # run unchanged; the old fixture receives its own synthetic bearer.
            return self.server.send(method,url,dict(headers,Authorization='Bearer offline-not-a-credential'),body,timeout,maximum)
        return self.issuer.send(method,url,headers,body,timeout,maximum)

    def put(self,key,value):
        self.server.serial+=1;self.server.objects[key]=(self.server.serial,encoded(value),'application/json')

    def get(self,key):
        row=self.server.objects.get(key);return strict(row[1]) if row else None

    def prepared(self,*,active=False,resources=True,member='experiment'):
        self.req=fixture(member,domain='native');self.req['configurationSha256']=p.config(self.original)
        # The old workload source differs from this cleanup workflow source.
        self.req['selection']['binding']['source']='b'*40
        plan=p.Plan(self.original,self.req);lease=a.lease(self.req,self.clock.wall()-(0 if active else 90));lease['phase']='ACTIVE'
        if resources:
            for row in lease['resources']:
                spec=row['spec'];endpoint=p.query(plan.endpoint(spec).rsplit('/',1)[0],requestId=plan.operation_id(spec))
                _,raw=self.server.handle('POST',endpoint,{},encoded(plan.body(spec)))
                row.update(attempted=True,id=strict(raw)['targetId'])
        self.put(a.LEASE,lease);self.put(a.LEDGER,a.reserve(a.empty_ledger(domain='native'),self.req,previous_cost=0,cost=1))
        self.put(p.context_key(self.req),p.context(self.original,self.req,domain='native'));return lease

    def execute(self):
        self.count+=1;self.output=self.root/str(self.count)
        return n.reconcile_native(SOURCE,self.output,role=self.role)

    def mutations(self):return [r for r in self.calls if r['method']!='GET' and not r['url'].endswith(':testIamPermissions') and 'iamcredentials.googleapis.com' not in r['url'] and 'sts.googleapis.com' not in r['url']]

    def cli(self):
        self.count+=1;self.output=self.root/f'cli-{self.count}';stdout=io.StringIO()
        # Match the workflow's python -m entry: execute under __main__, while
        # the strict provider guard imports the module by its canonical name.
        with patch.object(sys,'argv',['cloud_native_cleanup','--source',SOURCE,'--role',self.role,'--output',str(self.output)]), \
             contextlib.redirect_stdout(stdout),warnings.catch_warnings():
            warnings.filterwarnings('ignore',message=".*scripts.v52.cloud_native_cleanup.*found in sys.modules.*",category=RuntimeWarning)
            with self.assertRaises(SystemExit) as stopped:runpy.run_module('scripts.v52.cloud_native_cleanup',run_name='__main__')
        return stopped.exception.code,stdout.getvalue()

    def test_module_cli_expired_lease_reaches_exact_id_cleanup(self):
        self.prepared();code,output=self.cli()
        self.assertEqual(0,code,output)
        result=strict((self.output/'receipt.json').read_bytes())
        self.assertEqual('PASS',result['status']);self.assertEqual(13,result['resourceDeletesSubmitted'])
        self.assertTrue(result['leaseReleased']);self.assertIsNone(self.get(a.LEASE))
        self.assertEqual({},self.server.resources);self.assertFalse(result['fullRemoteQualification'])

    def test_module_cli_cleaning_failure_preserves_original_terminal_ledger(self):
        lease=self.prepared();lease['phase']='CLEANING';self.put(a.LEASE,lease)
        first=next(row for row in lease['resources'] if row['spec']['kind']=='instance')
        name=first['spec']['name'];first['id']=None;self.put(a.LEASE,lease)
        op=next(v for v in self.server.operations.values() if v['targetLink'].endswith('/'+name))
        op['error']=dict(errors=[dict(code='ZONE_RESOURCE_POOL_EXHAUSTED')])
        self.server.resources.clear()
        sha=a.validate_request(self.req,domain='native');key=c.attempt_key(self.req)+'completion.json'
        completion=dict(schema='gse-v52-owned-completion-v1',execution=self.req['execution'],
            requestSha256=sha,status='FAIL',evidenceSha256=None,cleanupSha256='c'*64)
        self.put(key,completion);self.put(a.LEDGER,a.finish(self.get(a.LEDGER),self.req,completion))
        ledger=deepcopy(self.server.objects[a.LEDGER]);original=deepcopy(self.server.objects[key])
        code,output=self.cli();self.assertEqual(0,code,output)
        result=strict((self.output/'receipt.json').read_bytes())
        self.assertEqual('PASS',result['status']);self.assertIsNone(self.get(a.LEASE))
        self.assertEqual(0,result['resourceDeletesSubmitted'])
        self.assertEqual(ledger,self.server.objects[a.LEDGER]);self.assertEqual(original,self.server.objects[key])

    def test_module_cli_active_lease_waits_without_mutations(self):
        self.prepared(active=True);code,output=self.cli()
        self.assertEqual(0,code,output);self.assertEqual('WAITING',strict((self.output/'receipt.json').read_bytes())['status'])
        self.assertEqual([],self.mutations());self.assertEqual(13,len(self.server.resources))

    def test_module_cli_missing_original_context_rejects_without_mutations(self):
        self.prepared();self.server.objects.pop(p.context_key(self.req));code,output=self.cli()
        self.assertEqual(2,code,output);self.assertIn('V52_CLEANUP_REJECTED',output)
        self.assertFalse((self.output/'receipt.json').exists());self.assertIsNotNone(self.get(a.LEASE))
        self.assertEqual([],self.mutations());self.assertEqual(13,len(self.server.resources))

    def test_expired_native_resources_use_original_ids_and_finish_original_failed_charge(self):
        lease=self.prepared();result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(13,result['resourceDeletesSubmitted'])
        self.assertTrue(result['deletionPathExercised']);self.assertTrue(result['paidCloud'])
        self.assertFalse(result['paidAdmission']);self.assertFalse(result['fullRemoteQualification'])
        self.assertEqual({},self.server.resources);self.assertIsNone(self.get(a.LEASE))
        self.assertEqual('b'*40,result['controlBefore']['lease']['value']['request']['selection']['binding']['source'])
        self.assertEqual(SOURCE,result['source']);self.assertEqual(2,result['credentials']['context']['runAttempt'])
        ledger=a.inspect_ledger(self.get(a.LEDGER),domain='native')
        self.assertEqual('FAIL',ledger['attempts'][a.validate_request(self.req,domain='native')]['status'])
        self.assertEqual(1,ledger['reservedCostMicrousd'])
        deletes=[row['url'].split('?')[0].rsplit('/',1)[1] for row in self.calls if row['method']=='DELETE' and 'compute.googleapis.com' in row['url']]
        self.assertEqual({row['id'] for row in lease['resources']},set(deletes))
        self.assertTrue(self.captured[-1].closed);self.assertTrue(self.captured[-1].reader.closed)
        self.assertTrue(self.captured[-1].tokens.closed);self.assertIsNone(self.captured[-1].token)

    def test_original_v1_lease_cleans_all_thirteen_ids_after_shard_migration(self):
        suite=a.suite;old=suite.read(suite.LEGACY_PLAN)
        with patch.object(suite,'PLAN_SHA',suite.LEGACY_SHA),patch.object(suite,'load',return_value=old):
            lease=self.prepared()
        result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(13,result['resourceDeletesSubmitted'])
        self.assertIsNone(self.get(a.LEASE));self.assertEqual({},self.server.resources)
        view=a.inspect_ledger(self.get(a.LEDGER),domain='native')
        self.assertEqual(1,view['reservedCostMicrousd'])
        self.assertEqual('FAIL',view['attempts'][a.validate_request(self.req,domain='native')]['status'])
        deletes=[row['url'].split('?')[0].rsplit('/',1)[1] for row in self.calls
                 if row['method']=='DELETE' and 'compute.googleapis.com' in row['url']]
        self.assertEqual({row['id'] for row in lease['resources']},set(deletes))

    def test_failed_original_insert_with_target_id_releases_stranded_lease_preserving_failure(self):
        lease=self.prepared();lease['phase']='CLEANING'
        instances=[row for row in lease['resources'] if row['spec']['kind']=='instance']
        instances[0]['id']=None
        for row in instances[1:]:row.update(attempted=False,id=None)
        name=instances[0]['spec']['name']
        op=next(v for v in self.server.operations.values() if v['targetLink'].endswith('/'+name))
        op['error']=dict(errors=[dict(code='ZONE_RESOURCE_POOL_EXHAUSTED',message='never-public')])
        self.server.resources.clear();self.put(a.LEASE,lease)
        sha=a.validate_request(self.req,domain='native');key=c.attempt_key(self.req)+'completion.json'
        completion=dict(schema='gse-v52-owned-completion-v1',execution=self.req['execution'],
            requestSha256=sha,status='FAIL',evidenceSha256=None,cleanupSha256='c'*64)
        self.put(key,completion);self.put(a.LEDGER,a.finish(self.get(a.LEDGER),self.req,completion))
        original_ledger=deepcopy(self.server.objects[a.LEDGER]);original_completion=deepcopy(self.server.objects[key])
        result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(0,result['resourceDeletesSubmitted'])
        self.assertIsNone(self.get(a.LEASE));self.assertEqual({},self.server.resources)
        self.assertEqual(original_ledger,self.server.objects[a.LEDGER])
        self.assertEqual(original_completion,self.server.objects[key])
        self.assertEqual('FAIL',a.inspect_ledger(self.get(a.LEDGER),domain='native')['attempts'][sha]['status'])
        self.assertFalse(result['fullRemoteQualification'])

    def test_original_v2_lease_cleans_all_thirteen_ids_after_canonical_migration(self):
        suite=a.suite;old=suite.read(suite.LEGACY_V2_PLAN)
        with patch.object(suite,'PLAN_SHA',suite.LEGACY_V2_SHA),patch.object(suite,'load',return_value=old), \
             patch.object(suite,'MEMBERS',tuple(old['members'])):
            lease=self.prepared(member='canonical-1')
        result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(13,result['resourceDeletesSubmitted'])
        self.assertIsNone(self.get(a.LEASE));self.assertEqual({},self.server.resources)
        view=a.inspect_ledger(self.get(a.LEDGER),domain='native')
        self.assertEqual(1,view['reservedCostMicrousd'])
        self.assertEqual('FAIL',view['attempts'][a.validate_request(self.req,domain='native')]['status'])
        deletes=[row['url'].split('?')[0].rsplit('/',1)[1] for row in self.calls
                 if row['method']=='DELETE' and 'compute.googleapis.com' in row['url']]
        self.assertEqual({row['id'] for row in lease['resources']},set(deletes))

    def test_empty_control_pass_is_observation_only_and_does_not_certify_delete_path(self):
        result=self.execute();self.assertEqual('PASS',result['status'])
        self.assertFalse(result['deletionPathExercised']);self.assertEqual(0,result['providerWrites'])
        self.assertEqual([],self.mutations());self.assertEqual([],self.captured)

    def test_activity_and_grace_wait_without_loading_context_or_writing(self):
        lease=self.prepared(active=True);del self.server.objects[p.context_key(self.req)]
        for offset in (0,60,89):
            self.clock.now=10+offset;result=self.execute()
            self.assertEqual('WAITING',result['status']);self.assertEqual(0,result['providerWrites'])
            self.assertEqual(lease,self.get(a.LEASE));self.assertEqual([],self.mutations())
        self.clock.now=100
        with self.assertRaisesRegex(ValueError,'context missing'):self.execute()
        self.assertEqual([],self.mutations())

    def test_cleaning_phase_can_resume_before_old_expiry(self):
        lease=self.prepared(active=True);lease['phase']='CLEANING';self.put(a.LEASE,lease)
        self.assertEqual('PASS',self.execute()['status'])

    def test_schedule_uses_same_reconciliation_and_dedicated_identity(self):
        self.role='schedule';self.make();n.os.environ.clear();n.os.environ.update(self.env);self.prepared()
        result=self.execute();self.assertEqual('schedule',result['trigger'])
        self.assertEqual('schedule',result['credentials']['context']['role']);self.assertEqual(13,result['resourceDeletesSubmitted'])

    def test_no_lease_with_pending_charge_is_failure_without_writes(self):
        self.prepared(resources=False);del self.server.objects[a.LEASE]
        with self.assertRaisesRegex(ValueError,'orphan pending'):self.execute()
        self.assertEqual([],self.mutations());self.assertFalse((self.output/'receipt.json').exists())
        self.assertEqual('V52_CLEANUP_CONTROL_REJECTED',strict((self.output/'failure.json').read_bytes())['code'])

    def test_completed_ledger_is_preserved_in_empty_observation(self):
        self.prepared();self.execute();previous=deepcopy(self.server.objects);result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(0,result['providerWrites']);self.assertEqual(previous,self.server.objects)

    def test_no_attempted_resource_releases_lease_without_claiming_delete_path(self):
        self.prepared(resources=False);result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertFalse(result['deletionPathExercised']);self.assertIsNone(self.get(a.LEASE))

    def test_old_image_zone_layout_do_not_need_to_match_current_configuration(self):
        self.original.update(zone='us-west4-b',imageName='old-image',imageId='321')
        self.server=Server(self.original);self.prepared()
        result=self.execute();self.assertEqual('PASS',result['status'])
        self.assertNotEqual(self.req['configurationSha256'],p.config(self.cfg['provider']))
        self.assertFalse(any('/images/' in row['url'] for row in self.calls))
        self.assertTrue(any('/zones/us-west4-b/' in row['url'] for row in self.calls))

    def test_missing_or_wrong_original_context_fails_before_mutation(self):
        self.prepared();key=p.context_key(self.req);original=self.get(key)
        for change in (None,dict(original,requestSha256='f'*64),dict(original,configuration=self.cfg),dict(original,extra=True)):
            if change is None:self.server.objects.pop(key,None)
            else:self.put(key,change)
            with self.assertRaises((ValueError,KeyError)):self.execute()
            self.assertEqual([],self.mutations())

    def test_foreign_bucket_and_project_are_not_authorized_by_current_credentials(self):
        for field in ('project','bucket'):
            self.make();self.original=deepcopy(self.cfg['provider']);self.original[field]='other-location'
            self.server=Server(self.cfg['provider']);self.prepared(resources=False)
            with self.assertRaisesRegex(ValueError,'location changed'):self.execute()
            self.assertEqual([],self.mutations())

    def test_control_generation_change_even_same_value_fences_before_mutation(self):
        self.prepared()
        def change(method,url,body):
            if url==f.plan(self.cfg,self.role)['bucket']['url']:self.put(a.LEASE,self.get(a.LEASE))
        self.change=change
        with self.assertRaisesRegex(ValueError,'generation changed'):self.execute()
        self.assertEqual([],self.mutations())

    def test_permission_denial_and_source_drift_fail_before_mutation(self):
        self.prepared();self.observations.rows['projectPermissions']['permissions']=[]
        with self.assertRaisesRegex(ValueError,'missing/forbidden'):self.execute()
        self.assertEqual([],self.mutations())
        self.observations=Observations(self.cfg,self.role,self.clock)
        self.source.side_effect=[self.cfg,dict(self.cfg,projectNumber='999')]
        with self.assertRaisesRegex(ValueError,'source/configuration changed'):self.execute()
        self.assertEqual([],self.mutations())

    def test_credential_attempt_drift_rejects_without_provider_mutations(self):
        self.prepared();self.invocation.value['run_attempt']=3
        with self.assertRaises(ValueError):self.execute()
        self.assertEqual([],self.mutations())

    def test_permission_http_error_body_is_not_retained(self):
        def change(method,url,body):
            if url.endswith(':testIamPermissions'):self.response=(403,b'PRIVATE_PROVIDER_ERROR')
        self.change=change
        with self.assertRaises(n.h.ApiError):self.execute()
        failure=strict((self.output/'failure.json').read_bytes());self.assertEqual(403,failure['httpStatus'])
        self.assertFalse((self.output/'receipt.json').exists())
        for path in self.output.rglob('*'):
            if path.is_file():self.assertNotIn(b'PRIVATE_PROVIDER_ERROR',path.read_bytes())

    def test_missing_ledger_cannot_delete_attempted_resources(self):
        self.prepared();del self.server.objects[a.LEDGER]
        with self.assertRaisesRegex(ValueError,'reservation missing'):self.execute()
        self.assertEqual([],self.mutations())

    def test_renewed_lease_after_preflight_blocks_original_cleanup(self):
        self.prepared();once=True
        def change(method,url,body):
            nonlocal once
            if once and 'provider-context.json' in url:
                once=False;lease=self.get(a.LEASE);lease['renewedAt']=self.clock.wall();lease['expiresAt']=self.clock.wall()+60
                self.put(a.LEASE,lease)
        self.change=change
        with self.assertRaisesRegex(ValueError,'lease changed'):self.execute()
        self.assertEqual([],self.mutations())

    def test_uncertain_delete_is_not_replayed_and_can_be_reconciled_later(self):
        self.prepared();lost=False
        def fault(stage,row):
            nonlocal lost
            if stage=='after' and row['method']=='DELETE' and 'compute.googleapis.com' in row['url'] and not lost:
                lost=True;raise ConnectionError('PRIVATE_UNCERTAIN_ERROR')
        self.server.fault=fault;result=self.execute()
        self.assertEqual('FAIL',result['status']);self.assertIsNotNone(self.get(a.LEASE))
        self.assertEqual(13,result['resourceDeletesSubmitted'])
        self.server.fault=lambda *args:None;result=self.execute()
        self.assertEqual('PASS',result['status']);self.assertEqual(0,result['resourceDeletesSubmitted'])
        self.assertIsNone(self.get(a.LEASE))
        for path in self.root.rglob('*'):
            if path.is_file():self.assertNotIn(b'PRIVATE_UNCERTAIN_ERROR',path.read_bytes())

    def test_unknown_submission_remains_unresolved_and_keeps_lease(self):
        lease=self.prepared(resources=False);row=lease['resources'][0];row.update(attempted=True)
        self.put(a.LEASE,lease)
        key=c.attempt_key(self.req)+'operations/'+row['spec']['operationId']+'-submitted.json'
        self.put(key,dict(schema='gse-v52-provider-submission-v1',spec=row['spec']))
        result=self.execute();self.assertEqual('FAIL',result['status']);self.assertIsNotNone(self.get(a.LEASE))
        self.assertEqual(0,result['resourceDeletesSubmitted']);self.assertFalse(result['deletionPathExercised'])

    def test_foreign_same_name_resource_is_never_deleted(self):
        self.prepared();key=next(iter(self.server.resources));self.server.resources[key]['id']='999999'
        result=self.execute();self.assertEqual('FAIL',result['status'])
        self.assertIn(key,self.server.resources);self.assertIsNotNone(self.get(a.LEASE))
        self.assertFalse(any('/999999?' in row['url'] and row['method']=='DELETE' for row in self.calls))

    def test_native_factory_has_no_force_token_transport_request_or_runner_entry(self):
        for arguments in (dict(force=True),dict(tokens=lambda _:''),dict(transport=self.server),dict(request=fixture(domain='native'))):
            with self.assertRaises(TypeError):n.reconcile_native(SOURCE,self.root/'injected',**arguments)
        with self.assertRaises(ValueError):n.reconcile_native(SOURCE,self.root/'runner',role='runner')
        with self.assertRaises(ValueError):n.NativeCleanupApi(None,{},None,object())
        with self.assertRaises(ValueError):p.Provider(p.Store(self.original,p.OfflineApi(self.server)),fixture(domain='native'))
        class Lookalike(n.NativeCleanupApi):pass
        with self.assertRaises(ValueError):p.api_guard(object.__new__(Lookalike))
        self.assertEqual([],self.calls)

    def test_native_scope_cannot_insert_reserve_renew_or_claim_workload_pass(self):
        self.prepared();checks=[]
        original=n.NativeCleanupApi.bind_store
        def bound(api,store):
            original(api,store);plan=api.policy.plan;spec=next(iter(plan.specs.values()))
            with self.assertRaises(ValueError):
                api.call('POST',p.query(plan.endpoint(spec).rsplit('/',1)[0],requestId=plan.operation_id(spec)),plan.body(spec),deadline=self.clock.seconds()+30)
            with self.assertRaises(ValueError):c.OfflineOwner(store,p.Provider(store,api.policy.req),api.policy.req)
            before=self.get(a.LEASE);renewed=deepcopy(before);renewed['renewedAt']+=1;renewed['expiresAt']+=1
            with self.assertRaises(ValueError):store.put(a.LEASE,renewed,self.server.objects[a.LEASE][0])
            completion=dict(schema='gse-v52-owned-completion-v1',execution=a.DOMAINS['native'],requestSha256=a.validate_request(self.req,domain='native'),status='PASS',evidenceSha256='a'*64,cleanupSha256='b'*64)
            with self.assertRaises(ValueError):store.put(c.attempt_key(self.req)+'completion.json',completion,0)
            checks.append(True)
        with patch.object(n.NativeCleanupApi,'bind_store',new=bound):result=self.execute()
        self.assertEqual([True],checks);self.assertEqual('PASS',result['status'])

    def test_renewal_during_credential_refresh_fences_the_first_cleanup_write(self):
        self.prepared(resources=False);original=n.NativeCleanupApi.authorize;armed=False
        def authorize(api,method,url,body):
            nonlocal armed
            original(api,method,url,body)
            if method=='POST' and body is not None and body.get('phase')=='CLEANING' and not armed:
                armed=True;api.token=None;recheck=api.tokens.recheck
                def refresh(end):
                    recheck(end);lease=self.get(a.LEASE)
                    lease['renewedAt']=self.clock.wall();lease['expiresAt']=self.clock.wall()+60
                    self.put(a.LEASE,lease)
                api.tokens.recheck=refresh
        with patch.object(n.NativeCleanupApi,'authorize',new=authorize):
            with self.assertRaisesRegex(ValueError,'generation/owner changed'):self.execute()
        self.assertTrue(armed);self.assertEqual([],self.mutations())
        self.assertEqual('ACTIVE',self.get(a.LEASE)['phase'])

    def test_configuration_drift_during_refresh_cannot_send_the_write(self):
        self.prepared(resources=False);original=n.NativeCleanupApi.authorize;armed=False
        def authorize(api,method,url,body):
            nonlocal armed
            original(api,method,url,body)
            if method=='POST' and not armed:
                armed=True;api.token=None;recheck=api.tokens.recheck
                def refresh(end):
                    recheck(end);api.reader.configuration['provider']['bucket']='foreign-bucket'
                api.tokens.recheck=refresh
        with patch.object(n.NativeCleanupApi,'authorize',new=authorize):
            with self.assertRaisesRegex(ValueError,'configuration changed'):self.execute()
        self.assertTrue(armed);self.assertEqual([],self.mutations())

    def test_lost_cleanup_lease_cas_reply_only_observes_the_original_write(self):
        self.prepared(resources=False);lost=False
        def fault(stage,row):
            nonlocal lost
            if stage=='after' and row['method']=='POST' and strict(row['body']).get('phase')=='CLEANING' and not lost:
                lost=True;raise ConnectionError('lost original lease reply')
        self.server.fault=fault;result=self.execute();self.assertEqual('PASS',result['status'])
        writes=[row for row in self.mutations() if row['method']=='POST' and row['body'] and strict(row['body']).get('phase')=='CLEANING']
        self.assertEqual(1,len(writes));self.assertTrue(lost)

    def test_401_mutation_is_sent_once_and_leaves_original_lease_for_later_reconciliation(self):
        before=self.prepared(resources=False)
        def fault(stage,row):
            if stage=='before' and row['method']=='POST':return 401,b'PRIVATE_AUTH_ERROR'
        self.server.fault=fault
        with self.assertRaises(n.h.ApiError):self.execute()
        self.assertEqual(1,len(self.mutations()));self.assertEqual(before,self.get(a.LEASE))
        self.assertFalse((self.output/'receipt.json').exists())
        self.assertNotIn('PRIVATE_AUTH_ERROR',(self.output/'exchanges.jsonl').read_text())

    def test_named_object_403_is_never_empty_success(self):
        self.server.fault=lambda stage,row:(403,b'PRIVATE') if stage=='before' else None
        with self.assertRaises(n.h.ApiError):self.execute()
        self.assertEqual([],self.mutations());self.assertFalse((self.output/'receipt.json').exists())

    def test_final_source_change_preserves_cleanup_result_but_cannot_publish_success(self):
        self.prepared(resources=False)
        self.source.side_effect=[self.cfg,self.cfg,dict(self.cfg,projectNumber='999')]
        with self.assertRaisesRegex(ValueError,'source/configuration changed'):self.execute()
        self.assertEqual('PASS',strict((self.output/'reconciliation.json').read_bytes())['status'])
        self.assertFalse((self.output/'receipt.json').exists());self.assertTrue(self.captured[-1].tokens.closed)

    def test_memory_reconciliation_also_rejects_an_orphan_pending_reservation(self):
        from . import cloud_offline as offline
        store=offline.Store();provider=offline.Provider(store);req=fixture()
        store.put(a.LEDGER,a.reserve(a.empty_ledger(domain='offline'),req,previous_cost=0,cost=1),0)
        with self.assertRaisesRegex(ValueError,'orphan pending'):
            c.reconcile(store,provider,trigger='workflow_dispatch',now=1000)
        self.assertEqual([],provider.events)

    def test_output_symlink_or_reuse_never_obtains_credentials(self):
        self.execute();self.calls.clear()
        with self.assertRaises(FileExistsError):n.reconcile_native(SOURCE,self.output)
        linked=self.root/'linked';linked.symlink_to(self.output,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlink'):n.reconcile_native(SOURCE,linked)
        self.assertEqual([],self.calls)


if __name__=='__main__':unittest.main()
