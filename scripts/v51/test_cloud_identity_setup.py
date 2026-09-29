"""Staging cannot activate a runner or serve as cleanup/paid admission evidence."""
from copy import deepcopy
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_identity_setup as s, cloud_identity_audit as a, cloud_identity_qualification as q
from . import cloud_authority, cloud_fake, cloud_preflight as p, remote_command as c


class IdentitySetupTest(unittest.TestCase):
    def setUp(self):self.cfg=c.read(p.CONFIG);self.v=s.proposal(self.cfg)
    def test_three_separate_pools_and_accounts_disabled(self):
        ids=list(self.v['identities'].values())
        self.assertEqual(3,len({i['pool'] for i in ids}));self.assertEqual(3,len({i['serviceAccount'] for i in ids}))
        for i in ids:
            for key in ('serviceAccountDisabled','poolDisabled','providerDisabled'):self.assertIs(i[key],True)
            for key in ('repository','repository_id','repository_owner_id','ref','event_name','environment','workflow_ref'):
                self.assertIn('assertion.'+key+" == '",i['attributeCondition'])
            self.assertNotIn('observer',i['principal']);self.assertNotIn('v50',i['principal'])
        self.assertEqual('schedule',ids[1]['claims']['event_name'])
        self.assertEqual('workflow_dispatch',ids[2]['claims']['event_name'])
    def test_cleanup_has_no_allocation_guest_or_iap_permissions(self):
        permissions=set(self.v['roles']['gseV51CleanupCompute']['includedPermissions'])
        self.assertEqual({'compute.instances.delete','compute.disks.delete','compute.firewalls.delete'}, {v for v in permissions if v.endswith('.delete')})
        self.assertTrue(all(v.endswith(('.get','.list','.delete')) or v=='compute.networks.updatePolicy' for v in permissions))
        bindings=self.v['projectBindings']
        for trigger in ('schedule','manual'):
            who='serviceAccount:'+self.v['identities'][trigger]['serviceAccount']
            self.assertEqual(['projects/gse-benchmark/roles/gseV51CleanupCompute'],[b['role'] for b in bindings if who in b['members']])
    def test_insert_field_permissions_and_no_attached_service_account(self):
        permissions=set(self.v['roles']['gseV51RunnerCompute']['includedPermissions'])
        self.assertTrue({'compute.disks.setLabels','compute.instances.setLabels','compute.instances.setMetadata','compute.instances.setTags','compute.disks.use','compute.subnetworks.use'}<=permissions)
        self.assertFalse(any(v.startswith('iam.') or v.endswith('ExternalIp') for v in permissions))
        self.assertNotIn('compute.projects.setCommonInstanceMetadata',permissions)
    def test_storage_read_create_and_delete_are_separate_scopes(self):
        for b in self.v['bucketBindings']:
            if b['role'].endswith('CloudBucketRead'):self.assertNotIn('condition',b);continue
            expression=b['condition']['expression']
            self.assertIn('v5.1-automatic-leadership/control/',expression);self.assertNotIn('v5.0',expression)
            if b['role'].endswith('CloudControlDelete'):
                self.assertIn(cloud_authority.LEASE,expression);self.assertIn(cloud_authority.LEDGER,expression)
                self.assertNotIn('startsWith',expression);self.assertNotIn('attempts/',expression)
        self.assertFalse(any('storage.objects.list' in r['includedPermissions'] for r in self.v['roles'].values()))
    def test_generated_commands_never_execute_and_disable_before_grants(self):
        with tempfile.TemporaryDirectory() as tmp,patch('subprocess.run',side_effect=AssertionError('unexpected execution')):
            root=Path(tmp)/'proposal';s.write(root,self.cfg);commands=c.read(root/'commands.json');text=(root/'APPLY.md').read_text()
            with self.assertRaises(FileExistsError):s.write(root,self.cfg)
        for identity in self.v['identities'].values():
            disable=next(i for i,v in enumerate(commands) if v[:4]==['gcloud','iam','service-accounts','disable'] and v[4]==identity['serviceAccount'])
            for i,v in enumerate(commands):
                if 'add-iam-policy-binding' in v and (identity['serviceAccount'] in v or '--member=serviceAccount:'+identity['serviceAccount'] in v):self.assertGreater(i,disable)
        for args in commands:
            self.assertNotIn('enable',args);self.assertNotIn('update-oidc',args)
            if 'create-oidc' in args or args[:4]==['gcloud','iam','workload-identity-pools','create']:self.assertIn('--disabled',args)
        self.assertFalse(any('repos/'+s.ci.REPOSITORY+'/environments/'+cloud_authority.ENVIRONMENT in v for v in commands))
        subprocess.run(['bash','-n'],input=text.split('```bash\n')[1].split('```')[0],text=True,check=True)
    def test_generated_proposal_cannot_authorize_paid_or_cleanup(self):
        req,_,approval=cloud_fake.fixture()
        with self.assertRaises(ValueError):cloud_authority.admit(req,self.v,approval,q.NOW)
        for key in ('paidAdmission','cleanupReady','fullRemoteQualification'):self.assertIs(self.v[key],False)


class IdentityAuditTest(unittest.TestCase):
    def setUp(self):self.cfg=c.read(p.CONFIG);self.value=q.fixture(self.cfg)
    def result(self,mode='staged',now=q.NOW):return a.evaluate(self.cfg,mode,self.value,now=now)
    def test_staged_match_is_not_authentication_or_admission(self):
        r=self.result();self.assertEqual('STAGED_MATCH',r['status'])
        for key in ('paidAdmission','cleanupReady','fullRemoteQualification','effectiveIamQualified','activationAllowed'):self.assertIs(r[key],False)
    def test_all_retained_negative_cases_reject(self):
        original=deepcopy(self.value)
        for name,mutation in q.mutations().items():
            with self.subTest(name=name):
                self.value=deepcopy(original);mutation(self.value['observations']);self.assertEqual('BLOCKED',self.result()['status'])
    def test_disabled_flags_cannot_be_missing_or_truthy(self):
        original=deepcopy(self.value)
        for trigger in ('runner','schedule','manual'):
            for entity in ('account','pool','providers'):
                for state in (None,False,1,'true'):
                    with self.subTest(trigger=trigger,entity=entity,state=state):
                        self.value=deepcopy(original);value=self.value['observations'][trigger+':'+entity]
                        if entity=='providers':value=value[0]
                        value['disabled']=state;self.assertEqual('BLOCKED',self.result()['status'])
    def test_exact_provider_mapping_and_audience(self):
        for change in ({'oidc':{'issuerUri':'https://example.com'}},{'oidc':{'issuerUri':'https://token.actions.githubusercontent.com','allowedAudiences':['other']}},
                       {'attributeMapping':{'google.subject':'assertion.sub'}}):
            self.setUp();self.value['observations']['runner:providers'][0].update(change);self.assertEqual('BLOCKED',self.result()['status'])
        self.setUp();self.value['observations']['schedule:providers'].append(self.value['observations']['schedule:providers'][0]);self.assertEqual('BLOCKED',self.result()['status'])
    def test_missing_observation_role_permission_and_stale_snapshot(self):
        for key in list(self.value['observations']):
            with self.subTest(key=key):
                self.setUp();del self.value['observations'][key];self.assertEqual('BLOCKED',self.result()['status'])
        self.setUp();self.value['observations']['role:gseV51CleanupCompute']['includedPermissions'].pop();self.assertEqual('BLOCKED',self.result()['status'])
        self.setUp();self.assertEqual('BLOCKED',self.result(now=q.NOW+901)['status'])
        self.value['completedAt']=q.NOW+1;self.assertEqual('BLOCKED',self.result()['status'])
    def test_unrelated_bindings_preserved_but_extra_new_role_grant_rejected(self):
        rows=self.value['observations']['project-policy']['bindings']
        rows.append(dict(role='roles/viewer',members=['user:other@example.com']))
        self.assertEqual('STAGED_MATCH',self.result()['status'])
        rows.append(dict(role='projects/gse-benchmark/roles/gseV51CleanupCompute',members=['user:other@example.com']))
        self.assertEqual('BLOCKED',self.result()['status'])
    def test_api_merging_and_reordering_does_not_change_grants(self):
        rows=self.value['observations']['bucket-policy']['bindings'];merged={}
        for row in rows:
            key=json.dumps([row['role'],row.get('condition')],sort_keys=True)
            target=merged.setdefault(key,dict(row,members=[]));target['members'].extend(row['members'])
        self.value['observations']['bucket-policy']['bindings']=list(reversed(list(merged.values())))
        self.assertEqual('STAGED_MATCH',self.result()['status'])
    def test_absence_check_stops_on_every_existing_identity_role_and_environment(self):
        v=s.proposal(self.cfg)
        for key,entry in [('accounts',dict(email=v['identities']['runner']['serviceAccount'])),('pools',dict(name=v['identities']['manual']['pool'])),
                          ('roles',dict(name='projects/gse-benchmark/roles/gseV51CleanupCompute'))]:
            self.value=q.fixture(self.cfg,'absent');self.value['observations'][key].append(entry)
            self.assertEqual('BLOCKED',self.result('absent')['status'])
        self.value=q.fixture(self.cfg,'absent');env=self.value['observations']['environments'];env['environments'].append(dict(name='v51-cloud-cleanup'));env['total_count']=2
        self.assertEqual('BLOCKED',self.result('absent')['status'])
        self.value=q.fixture(self.cfg,'absent');self.assertEqual('ABSENCE_REVIEWED',self.result('absent')['status'])
        self.value['observations']['environments']['total_count']=2;self.assertEqual('BLOCKED',self.result('absent')['status'])
    def test_every_collection_command_is_read_only_and_errors_are_redacted(self):
        for mode in ('absent','staged'):
            for args in a.queries(self.cfg,mode).values():
                if args[0]=='gh':self.assertEqual(['gh','api','--method','GET'],args[:4])
                else:self.assertTrue(any(x in args for x in ('list','describe','get-iam-policy')))
                for forbidden in ('print-access-token','update','create','disable','delete','add-iam-policy-binding'):self.assertNotIn(forbidden,args)
        def denied(args):raise RuntimeError('secret token or response body')
        value=a.collect(self.cfg,'staged',reader=denied,wall=lambda:q.NOW)
        self.assertNotIn('secret',json.dumps(value));self.value=value;self.assertEqual('BLOCKED',self.result()['status'])


if __name__=='__main__':unittest.main()
