from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_preflight as f, cloud_preflight_read as r, cloud_credentials as credentials
from . import cloud_credentials_offline as auth, cloud_authority as a
from .cloud_preflight_offline import Server
from .test_cloud_provider import configuration as provider_configuration
from .test_cloud_authority import fixture as original_request
from .evidence import encoded, strict

SOURCE='a'*40


def configuration():
    return dict(schema='gse-v52-preflight-config-v1',provider=provider_configuration(),projectNumber='123456789',
                layout=dict(bootDiskGiB=30,dataDiskGiB=100),policy=dict(leaseSeconds=3600,operationGraceSeconds=300,budgetMicrousd=200000000))


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.no_network=patch.object(r.http.Network,'send',side_effect=AssertionError('real network forbidden'))
        self.no_network.start();self.addCleanup(self.no_network.stop);self.make()

    def make(self,role='runner'):
        self.cfg=configuration();self.role=role
        self.project,self.env,self.descriptor,self.invocation,self.issuer=auth.fixture(self.cfg['provider'],role,SOURCE)
        self.clock=self.invocation.clock;self.server=Server(self.cfg,role,self.clock)
        self.reader=r.OfflineReader(self.cfg,SOURCE,role,self.env,self.descriptor,self.invocation,self.issuer,self.server)
        self.addCleanup(self.reader.close)

    def collect(self):return r.collect(self.reader,wall=self.clock.wall)
    def evaluate(self,value=None):return f.evaluate(self.cfg,SOURCE,self.role,value or self.collect(),now=self.clock.wall())
    def blocked(self,name):self.assertEqual('BLOCKED',self.evaluate()['checks'][name]['status'])

    def request(self):
        req=original_request();req.update(execution=a.DOMAINS['native'],paidCloud=True,configurationSha256=f.p.config(self.cfg['provider']))
        return req

    def test_all_three_roles_are_read_only_diagnostics_without_admission(self):
        for role in credentials.ROLES:
            self.make(role);value=self.evaluate()
            self.assertEqual('PREFLIGHT_OBSERVED_NOT_ADMITTED',value['status'])
            self.assertTrue(all(value[k] is False for k in f.FLAGS))
            self.assertEqual(role,value['context']['credentialSelection']['role'])
            posts=[v for v in self.server.calls if v['method']=='POST']
            self.assertEqual(1,len(posts));self.assertTrue(posts[0]['url'].endswith(':testIamPermissions'))
            self.assertFalse(any(v['method']=='DELETE' for v in self.server.calls))

    def test_only_necessary_project_permissions_and_no_organization_or_image_list_probe(self):
        for role in credentials.ROLES:
            cfg=configuration();queries=f.plan(cfg,role);required,forbidden=f.permission_spec(role,'projectPermissions')
            self.assertNotIn('compute.images.useReadOnly',required);self.assertNotIn('compute.images.list',required)
            self.assertNotIn('compute.images.get',required)
            self.assertIn('compute.networks.updatePolicy',required)
            if role=='runner':self.assertIn('compute.disks.setLabels',required)
            else:self.assertIn('compute.disks.create',forbidden)
            for query in queries.values():
                self.assertNotIn('/organizations/',query['url']);self.assertNotIn('/folders/',query['url'])
                self.assertNotIn('getIamPolicy',query['url']);self.assertNotIn('/o/',query['url'])
            self.assertEqual(set(required)|set(forbidden),set(queries['projectPermissions']['body']['permissions']))

    def test_configuration_unknown_fields_numeric_aliases_and_role_reject(self):
        for change in (dict(schema='v51'),dict(projectNumber=123456789),dict(projectNumber='0'),dict(extra=True)):
            with self.assertRaises(ValueError):f.configuration(dict(self.cfg,**change))
        for role in ('observer','cleanup','',None):
            with self.assertRaises(ValueError):f.plan(self.cfg,role)

    def test_permissions_fail_fast_without_waiting_for_remaining_queries(self):
        self.server.rows['projectPermissions']['permissions'].remove('compute.disks.setLabels')
        with self.assertRaisesRegex(ValueError,'missing/forbidden'):self.collect()
        self.assertEqual(3,len(self.server.calls));self.assertNotIn('bucket',self.reader.phase)

    def test_excessive_permissions_and_malformed_probe_results_reject(self):
        for name,extra in (('projectPermissions','iam.serviceAccountKeys.create'),('bucketPermissions','storage.objects.create')):
            self.make();self.server.rows[name]['permissions'].append(extra)
            with self.assertRaisesRegex(ValueError,'missing/forbidden'):self.collect()
        for value in ({'permissions':['unknown']},{'permissions':[True]},{'permissions':['storage.buckets.get']*2},
                      {'permissions':[],'kind':'wrong'},{'permissions':[],'hidden':True}):
            with self.assertRaises(ValueError):f.permissions(value,'runner','bucketPermissions')

    def test_project_compute_id_is_distinct_from_bucket_project_number(self):
        value=self.evaluate();self.assertEqual('100',value['checks']['provider']['detail']['resources']['project'])
        self.server.rows['bucket']['projectNumber']='100';self.blocked('storage')

    def test_every_provider_resource_name_link_and_numeric_id_is_checked(self):
        for name in ('project','region','zone','machine','diskType','network','subnetwork','image'):
            for field,bad in (('name','foreign'),('selfLink','https://evil.invalid/x'),('id',True)):
                self.make();self.server.rows[name][field]=bad;self.blocked('provider')

    def test_private_subnet_region_zone_and_boot_image_size(self):
        cases=[('subnetwork','privateIpGoogleAccess',False),('subnetwork','ipCidrRange','8.8.8.0/24'),
               ('subnetwork','ipCidrRange','10.52.0.1/24'),('subnetwork','network','foreign'),
               ('subnetwork','region','foreign'),('zone','region','foreign'),('zone','status','DOWN'),
               ('region','status','DOWN'),('image','diskSizeGb','31')]
        for name,key,value in cases:
            self.make();self.server.rows[name][key]=value;self.blocked('provider')

    def test_pinned_deprecated_image_warns_without_following_replacement(self):
        self.server.rows['image']['deprecated']=dict(state='DEPRECATED',replacement='https://evil.invalid/other')
        result=self.evaluate();self.assertEqual('PREFLIGHT_OBSERVED_NOT_ADMITTED',result['status'])
        self.assertEqual([f.images.WARNING],result['checks']['provider']['detail']['warnings'])
        self.assertFalse(any('evil.invalid' in v['url'] for v in self.server.calls))
        for change in (dict(deprecated=dict(state='OBSOLETE')),dict(deprecated=dict(state='DELETED')),
                       dict(status='DELETING'),dict(id='999'),dict(architecture='ARM64')):
            self.make();self.server.rows['image'].update(change);self.blocked('provider')

    def test_cpu_quota_is_family_specific_and_based_on_actual_machine_shape(self):
        value=self.evaluate()['checks']['provider']['detail']
        self.assertEqual(12,value['regionalQuota']['CPUS']['required']);self.assertEqual(390,value['machine']['diskGiB'])
        self.cfg['provider']['machineType']='n2-standard-8'
        self.project,self.env,self.descriptor,self.invocation,self.issuer=auth.fixture(self.cfg['provider'],'runner',SOURCE)
        self.clock=self.invocation.clock;self.server=Server(self.cfg,'runner',self.clock)
        self.server.rows['machine'].update(guestCpus=8,memoryMb=32768)
        self.server.rows['region']['quotas']=[v for v in self.server.rows['region']['quotas'] if v['metric']!='CPUS']
        self.reader=r.OfflineReader(self.cfg,SOURCE,'runner',self.env,self.descriptor,self.invocation,self.issuer,self.server)
        self.addCleanup(self.reader.close)
        value=self.evaluate()['checks']['provider']['detail']
        self.assertEqual(24,value['regionalQuota']['N2_CPUS']['required']);self.assertNotIn('CPUS',value['regionalQuota'])

    def test_quota_headroom_and_invalid_or_duplicate_metrics_reject(self):
        for field,bad in (('limit',0),('usage',999999),('limit',True)):
            self.make();self.server.rows['region']['quotas'][0][field]=bad;self.blocked('provider')
        self.make();self.server.rows['region']['quotas'].append(deepcopy(self.server.rows['region']['quotas'][0]));self.blocked('provider')
        for number in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):f.quota([dict(metric='CPUS',limit=number,usage=0)],{'CPUS':1})

    def test_negative_ssd_usage_is_observed_with_warning_without_paid_admission(self):
        row=next(v for v in self.server.rows['region']['quotas'] if v['metric']=='SSD_TOTAL_GB')
        row.update(limit=1000,usage=-100)
        result=self.evaluate();detail=result['checks']['provider']['detail']
        self.assertEqual('PREFLIGHT_OBSERVED_NOT_ADMITTED',result['status'])
        self.assertTrue(all(result[k] is False for k in f.FLAGS))
        self.assertFalse(detail['allocationGuaranteed'])
        self.assertEqual(1000,detail['regionalQuota']['SSD_TOTAL_GB']['available'])
        self.assertEqual(-100,detail['regionalQuota']['SSD_TOTAL_GB']['reportedUsage'])
        self.assertTrue(any('NEGATIVE_QUOTA_USAGE_NORMALIZED: regional SSD_TOTAL_GB' in w for w in detail['warnings']))
        self.assertEqual(-100,row['usage'])

    def test_negative_ssd_usage_does_not_hide_insufficient_limit(self):
        row=next(v for v in self.server.rows['region']['quotas'] if v['metric']=='SSD_TOTAL_GB')
        row.update(limit=389,usage=-100)
        self.blocked('provider')

    def test_negative_quota_and_image_warnings_are_both_preserved(self):
        row=next(v for v in self.server.rows['region']['quotas'] if v['metric']=='SSD_TOTAL_GB')
        row.update(limit=1000,usage=-100)
        self.server.rows['image']['deprecated']=dict(state='DEPRECATED',replacement='https://evil.invalid/other')
        warnings=self.evaluate()['checks']['provider']['detail']['warnings']
        self.assertIn(f.images.WARNING,warnings)
        self.assertTrue(any('NEGATIVE_QUOTA_USAGE_NORMALIZED' in w for w in warnings))

    def test_storage_retention_cannot_freeze_control_or_delete_its_history(self):
        for change in (dict(retentionPolicy=dict(retentionPeriod='60')),dict(defaultEventBasedHold=True),
                       dict(iamConfiguration=dict(uniformBucketLevelAccess=dict(enabled=False)))):
            self.make();self.server.rows['bucket'].update(change);self.blocked('storage')
        for prefixes in (None,[''],['v5.2-'],[a.PREFIX],[a.PREFIX+'active.json']):
            self.make();condition=dict(age=9999)
            if prefixes is not None:condition['matchesPrefix']=prefixes
            self.server.rows['bucket']['lifecycle']=dict(rule=[dict(action=dict(type='Delete'),condition=condition)])
            self.blocked('storage')

    def test_other_namespaces_can_expire_and_evidence_keeps_minimum_retention(self):
        for prefix,age,status in (('old-v51/',1,'PASS'),(f.EVIDENCE_PREFIX,30,'PASS'),(f.EVIDENCE_PREFIX,29,'BLOCKED')):
            self.make();self.server.rows['bucket']['lifecycle']=dict(rule=[dict(action=dict(type='Delete'),
                condition=dict(matchesPrefix=[prefix],age=age))])
            self.assertEqual(status,self.evaluate()['checks']['storage']['status'])

    def test_existing_native_lease_blocks_runner_even_when_expired_but_cleanup_can_inspect_older_source(self):
        for role in ('runner','manual','schedule'):
            self.make(role);req=self.request();req['selection']['binding']['source']='b'*40
            lease=a.lease(req,1000);self.server.objects[a.LEASE]=(5,lease)
            value=self.evaluate();self.assertEqual('BLOCKED' if role=='runner' else 'PASS',value['checks']['control']['status'])
            self.assertFalse(value['cleanupReady']);self.assertEqual('b'*40,self.server.objects[a.LEASE][1]['request']['selection']['binding']['source'])

    def test_cost_is_soft_failed_cost_is_preserved_and_pending_attempt_is_blocked(self):
        req=self.request();ledger=a.reserve(a.empty_ledger(domain='native'),req,previous_cost=0,cost=999999999)
        self.server.objects[a.LEDGER]=(3,ledger);self.blocked('control')
        completion=dict(schema='gse-v52-owned-completion-v1',execution=req['execution'],requestSha256=a.validate_request(req,domain='native'),
                        status='FAIL',evidenceSha256=None,cleanupSha256='c'*64)
        self.server.objects[a.LEDGER]=(4,a.finish(ledger,req,completion));value=self.evaluate()
        self.assertEqual('PREFLIGHT_OBSERVED_NOT_ADMITTED',value['status']);self.assertTrue(value['checks']['control']['budgetExceeded'])
        self.assertEqual(999999999,value['checks']['control']['previousCostMicrousd'])

    def test_source_domain_query_inventory_and_freshness_cannot_be_relabelled(self):
        original=self.collect()
        for change in (lambda v:v['context'].update(source='b'*40),lambda v:v.update(execution='native-v52-provider-observations'),
                       lambda v:v.update(startedAt=self.clock.wall()-901),lambda v:v.update(completedAt=self.clock.wall()+1),
                       lambda v:v['observations'].pop('image'),lambda v:v.update(planSha256='f'*64),
                       lambda v:v['credentials'].update(completedExchanges=True)):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):self.evaluate(value)

    def test_credential_run_observation_must_match_its_exact_context(self):
        original=self.collect()
        for change in (lambda v:v['credentials']['runObservation'].update(runAttempt=99),
                       lambda v:v['credentials']['context'].update(runId=True),
                       lambda v:v['credentials'].update(paidAdmission=True),
                       lambda v:v['credentials'].update(schema='old-schema')):
            value=deepcopy(original);change(value)
            with self.assertRaises(ValueError):self.evaluate(value)

    def test_loopback_and_link_local_are_not_admitted_as_private_peer_subnets(self):
        for address in ('127.0.0.0/24','169.254.1.0/24','0.0.0.0/24'):
            self.make();self.server.rows['subnetwork']['ipCidrRange']=address
            self.blocked('provider')

    def test_generation_change_even_with_identical_ledger_bytes_invalidates_observation(self):
        self.server.objects[a.LEDGER]=(1,a.empty_ledger(domain='native'))
        def change(server,call):
            if call['url']==f.plan(self.cfg,'runner')['image']['url']:server.objects[a.LEDGER]=(2,a.empty_ledger(domain='native'))
        self.server.change=change;value=self.collect()
        with self.assertRaisesRegex(ValueError,'generation changed'):self.evaluate(value)

    def test_changed_metadata_within_one_object_read_rejects(self):
        self.server.objects[a.LEDGER]=(1,a.empty_ledger(domain='native'))
        def change(server,call):
            if len(server.calls)==3:server.objects[a.LEDGER]=(2,a.empty_ledger(domain='native'))
        self.server.change=change
        with self.assertRaisesRegex(ValueError,'metadata changed'):self.reader.object('ledger')

    def test_permission_denial_is_not_object_absence(self):
        self.server.reply=(403,b'private failure detail')
        with self.assertRaises(r.http.ApiError):self.reader.object('ledger')
        self.assertEqual(1,len(self.server.calls))

    def test_no_foreign_query_mutation_or_encoded_generation_reaches_provider(self):
        for name in ('https://evil.invalid','instances.insert','organization','objectPermissions'):
            with self.assertRaises(ValueError):self.reader.read(name)
        with self.assertRaises(ValueError):self.reader.read('ledger',generation='1&other=2')
        with self.assertRaises(ValueError):self.reader.read('bucket',generation='1')
        self.assertEqual([],self.server.calls);self.assertEqual([],self.issuer.calls)

    def test_credentials_refresh_cannot_open_changed_configuration(self):
        original=self.reader.tokens.recheck
        def changed(end):original(end);self.reader.configuration['provider']['bucket']='other-bucket'
        self.reader.tokens.recheck=changed
        with self.assertRaisesRegex(ValueError,'configuration changed'):self.reader.read('bucket')
        self.assertEqual([],self.server.calls)

    def test_401_refresh_and_transient_read_retries_are_bounded(self):
        self.server.change=lambda server,call:setattr(server,'reply',(401,b'') if len(server.calls)==1 else None)
        self.reader.read('bucket');self.assertEqual(2,len(self.server.calls));self.assertEqual(2,self.reader.tokens.exchanges)
        self.server.reply=(500,b'');self.server.change=lambda s,c:None
        with self.assertRaises(r.cloud_read_retry.ReadError) as error:self.reader.read('bucket')
        self.assertEqual(3,error.exception.detail['attempts']);self.assertEqual(5,len(self.server.calls))
        self.server.reply=(401,b'')
        with self.assertRaises(r.http.ApiError):self.reader.read('bucket')
        self.assertEqual(7,len(self.server.calls))

    def test_read_deadline_bytes_and_post_refresh_expiry_fail_before_any_retry(self):
        self.server.change=lambda s,c:self.clock.sleep(31)
        with self.assertRaisesRegex(ValueError,'read deadline'):self.reader.read('bucket')
        self.assertEqual(1,len(self.server.calls))
        self.make();self.server.reply=(200,b'x'*(65536+1))
        with self.assertRaisesRegex(ValueError,'bound/type'):self.reader.read('bucketPermissions')
        self.reader.close()
        with self.assertRaisesRegex(ValueError,'closed'):self.reader.read('bucket')

    def test_fixed_permission_post_retries_and_rechecks_scope(self):
        self.server.change=lambda server,call:setattr(server,'reply',(503,b'') if len(server.calls)==1 else None)
        self.reader.read('bucketPermissions');self.assertEqual(2,len(self.server.calls))
        self.assertEqual(self.server.calls[0],self.server.calls[1])
        self.make()
        def change(server,call):
            self.reader.configuration['provider']['bucket']='other-bucket'
            raise ConnectionError('lost')
        self.server.change=change
        with self.assertRaisesRegex(ValueError,'configuration changed'):self.reader.read('bucketPermissions')
        self.assertEqual(1,len(self.server.calls))

    def test_native_factory_has_no_injection_and_retains_no_error_body(self):
        def send(_,method,url,headers,body,timeout,maximum):
            if url.startswith(('https://compute.googleapis.com/','https://storage.googleapis.com/','https://cloudresourcemanager.googleapis.com/')):
                return self.server.send(method,url,headers,body,timeout,maximum)
            return self.issuer.send(method,url,headers,body,timeout,maximum)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(r.os.environ,self.env,clear=True))
            config=stack.enter_context(patch.object(r,'source_configuration',return_value=self.cfg))
            stack.enter_context(patch.object(credentials,'checkout',return_value=SOURCE))
            stack.enter_context(patch.object(credentials,'github',side_effect=lambda path,end,clock:self.invocation.get(path,end)))
            stack.enter_context(patch.object(credentials,'credential_file',return_value=self.descriptor))
            stack.enter_context(patch.object(r.time,'monotonic',side_effect=self.clock.seconds))
            stack.enter_context(patch.object(r.time,'time',side_effect=self.clock.wall))
            stack.enter_context(patch.object(r.http.Network,'send',new=send))
            output=self.root/'native';result=r.collect_native(SOURCE,output)
            self.assertEqual('PREFLIGHT_OBSERVED_NOT_ADMITTED',result['status']);self.assertEqual(2,config.call_count)
            observed=strict((output/'observations.json').read_bytes());self.assertEqual('native-v52-provider-observations',observed['execution'])
            self.assertFalse(result['paidAdmission']);self.assertTrue(list((output/'reads').glob('*-body.json')))
            self.server.reply=(403,b'PRIVATE_PROVIDER_ERROR');self.server.closed=False
            output=self.root/'failed'
            with self.assertRaises(r.http.ApiError):r.collect_native(SOURCE,output)
            failure=strict((output/'failure.json').read_bytes());self.assertEqual(403,failure['httpStatus'])
            self.assertEqual('V52_PREFLIGHT_LEDGER_REJECTED',failure['code']);self.assertFalse((output/'receipt.json').exists())
            for file in output.rglob('*.json'):self.assertNotIn('PRIVATE_PROVIDER_ERROR',file.read_text())
            self.server.reply=None;config.side_effect=[self.cfg,dict(self.cfg,policy=dict(self.cfg['policy'],budgetMicrousd=1))]
            output=self.root/'source-drift'
            with self.assertRaisesRegex(ValueError,'configuration changed'):r.collect_native(SOURCE,output)
            self.assertEqual('V52_PREFLIGHT_FINAL_SOURCE_REJECTED',strict((output/'failure.json').read_bytes())['code'])
            self.assertFalse((output/'receipt.json').exists())
        with self.assertRaises(TypeError):r.collect_native(SOURCE,self.root/'injected',transport=self.server)

    def test_missing_source_configuration_never_opens_credentials(self):
        with patch.object(r,'source_configuration',side_effect=ValueError('private detail')),patch.object(r,'NetworkReader') as native:
            with self.assertRaises(ValueError):r.collect_native(SOURCE,self.root/'source-failure')
        native.assert_not_called();raw=(self.root/'source-failure/failure.json').read_text()
        self.assertNotIn('private detail',raw);self.assertIn('V52_PREFLIGHT_SOURCE_REJECTED',raw)

    def test_source_configuration_uses_fixed_tracked_bytes_and_rejects_symlinks(self):
        path=self.root/f.CONFIG_PATH;path.parent.mkdir(parents=True);raw=encoded(self.cfg);path.write_bytes(raw)
        with patch.object(r,'ROOT',self.root),patch.object(credentials,'checkout',return_value=SOURCE), \
             patch.object(r.inputs.build,'git',return_value=raw) as git:
            self.assertEqual(self.cfg,r.source_configuration(SOURCE))
            git.assert_called_once_with(self.root,'show',SOURCE+':'+f.CONFIG_PATH)
            git.return_value=raw+b'\n'
            with self.assertRaisesRegex(ValueError,'not in source'):r.source_configuration(SOURCE)
            original=self.root/'original';path.rename(original);path.symlink_to(original)
            with self.assertRaisesRegex(ValueError,'file type'):r.source_configuration(SOURCE)


if __name__=='__main__':unittest.main()
