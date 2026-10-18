from copy import deepcopy
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_setup as s, cloud_preflight as f, cloud_credentials as credentials, cloud_authority as a
from . import cloud_cleanup_workflow, cloud_runner_workflow
from .cloud_preflight_offline import Server
from .test_cloud_preflight import configuration
from .cloud_credentials_offline import Clock
from .evidence import encoded, strict


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name)/'review';self.cfg=configuration()

    def test_tracked_configuration_matches_native_quota_and_both_workflow_contracts(self):
        cfg=s.configuration();f.configuration(cfg)
        self.assertEqual('pd-ssd',cfg['provider']['diskType'])
        self.assertEqual(dict(bootDiskGiB=50,dataDiskGiB=100),cfg['layout'])
        self.assertEqual(200000000,cfg['policy']['budgetMicrousd'])
        self.assertEqual(3600,cfg['policy']['leaseSeconds'])
        self.assertEqual(300,cfg['policy']['operationGraceSeconds'])
        cloud_cleanup_workflow.contract();cloud_runner_workflow.contract()
        server=Server(cfg,'runner',Clock())
        observed=f.facts(cfg,server.rows)
        self.assertEqual(450,observed['machine']['diskGiB'])
        f.storage(cfg,server.rows['bucket'])

    def test_distinct_disabled_identities_match_native_selection_and_numeric_repository_claims(self):
        value=s.proposal(self.cfg);self.assertEqual({'runner','manual'},set(value['identities']))
        for role,row in value['identities'].items():
            self.assertEqual(credentials.selection(self.cfg['provider'],self.cfg['projectNumber'],role),row['selection'])
            self.assertTrue(row['serviceAccountDisabled'] and row['poolDisabled'] and row['providerDisabled'])
            for name,want in dict(repository_id=str(credentials.REPOSITORY_ID),repository_owner_id=str(credentials.OWNER_ID),
                event_name='workflow_dispatch',ref='refs/heads/master',environment=row['selection']['environment']).items():
                self.assertEqual(want,row['claims'][name]);self.assertIn("assertion."+name+" == '"+want+"'",row['attributeCondition'])
            self.assertNotIn('assertion.job',row['attributeCondition'])
        self.assertFalse(value['applied'] or value['paidAdmission'] or value['cleanupReady'] or value['fullRemoteQualification'])

    def test_unreviewed_provider_quota_policy_rejects_before_bundle_creation(self):
        for key,value in (('diskType','pd-balanced'),('machineType','c3-standard-4')):
            cfg=deepcopy(self.cfg);cfg['provider'][key]=value
            with self.assertRaisesRegex(ValueError,'quota policy'):s.write(self.output,cfg)
            self.assertFalse(self.output.exists())

    def test_permissions_follow_actual_adapters_without_admin_external_ip_or_cleanup_creation(self):
        value=s.proposal(self.cfg);roles=value['roles']
        self.assertEqual(set(f.RUNNER),set(roles['gseV52RunnerCompute']['includedPermissions']))
        self.assertEqual(set(f.CLEANUP),set(roles['gseV52CleanupCompute']['includedPermissions']))
        for role in roles.values():self.assertFalse(set(role['includedPermissions']) & set(f.FORBIDDEN))
        self.assertNotIn('compute.images.useReadOnly',roles['gseV52RunnerCompute']['includedPermissions'])
        self.assertNotIn('compute.disks.create',roles['gseV52CleanupCompute']['includedPermissions'])
        iap=[v for v in value['projectBindings'] if v['role'].endswith('gseV52RunnerIap')]
        self.assertEqual(1,len(iap));self.assertEqual('destination.port == 22',iap[0]['condition']['expression'])
        self.assertIn('gse-v52-runner@',iap[0]['members'][0])

    def test_object_permissions_preserve_attempt_evidence_and_exact_mutable_keys(self):
        value=s.proposal(self.cfg);rows=value['bucketBindings']
        for row in rows:
            role=row['role'].rsplit('/',1)[1];permissions=value['roles'][role]['includedPermissions']
            if permissions==['storage.buckets.get']:
                self.assertNotIn('condition',row);continue
            expr=row['condition']['expression']
            self.assertIn("resource.type == 'storage.googleapis.com/Object'",expr)
            self.assertIn(a.PREFIX,expr);self.assertNotIn('v5.1-',expr)
            self.assertNotIn('storage.objects.list',permissions)
            if permissions==['storage.objects.delete']:
                self.assertNotIn('startsWith',expr)
                self.assertIn(a.LEASE,expr);self.assertIn(a.LEDGER,expr)
            if 'attempts/' in expr:self.assertEqual(['storage.objects.create'],permissions)
        self.assertEqual(2,len([v for v in rows if v['role'].endswith('ControlDelete')]))

    def test_environments_require_manual_review_master_and_runner_only_secret(self):
        value=s.proposal(self.cfg)
        self.assertEqual({'v52-cloud-benchmark','v52-cloud-manual-cleanup'},set(value['environments']))
        for name,row in value['environments'].items():
            self.assertEqual(dict(name='master',type='branch'),row['branchPolicy'])
            self.assertEqual([dict(type='User',id=credentials.OWNER_ID)],row['body']['reviewers'])
            self.assertEqual(['V52_EXPERIMENT_SSH_KEY'] if name=='v52-cloud-benchmark' else [],row['secrets'])

    def test_generator_runs_no_commands_and_does_not_overwrite_existing_evidence(self):
        with patch.object(subprocess,'run',side_effect=AssertionError('command forbidden')),patch.object(subprocess,'Popen',side_effect=AssertionError('command forbidden')):
            receipt=s.write(self.output,self.cfg)
            self.assertEqual('REVIEW_ONLY',receipt['status']);self.assertEqual(receipt,s.check(self.output,self.cfg))
            with self.assertRaises(FileExistsError):s.write(self.output,self.cfg)
        self.assertFalse(any(p.suffix=='.sh' for p in self.output.iterdir()))

    def test_inventory_bytes_configuration_and_symlink_changes_reject(self):
        s.write(self.output,self.cfg);path=self.output/'commands.json';original=path.read_bytes()
        path.write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError,'file drift'):s.check(self.output,self.cfg)
        path.write_bytes(original);extra=self.output/'unreviewed.sh';extra.write_text('true')
        with self.assertRaisesRegex(ValueError,'inventory'):s.check(self.output,self.cfg)
        extra.unlink();path.unlink();path.symlink_to(self.output/'proposal.json')
        with self.assertRaises(ValueError):s.check(self.output,self.cfg)
        path.unlink();path.write_bytes(original)
        changed=deepcopy(self.cfg);changed['projectNumber']='9999'
        with self.assertRaises(ValueError):s.check(self.output,changed)
        alias=self.output.parent/'alias';alias.symlink_to(self.output,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'output link'):s.check(alias,self.cfg)

    def test_inspection_is_read_only_and_staging_disables_before_any_binding(self):
        commands=strict(s.files(self.cfg)['commands.json'])
        for row in commands['inspect']:
            if row[0]=='gh':self.assertEqual('GET',row[row.index('--method')+1])
            else:self.assertTrue(any(v in row for v in ('describe','get-iam-policy','list')))
            self.assertFalse(set(row)&{'create','delete','update','enable','add-iam-policy-binding'})
        stage=commands['stageDisabled']
        for identity in s.proposal(self.cfg)['identities'].values():
            sa=identity['selection']['serviceAccount'];name=identity['name']
            create=next(i for i,r in enumerate(stage) if r[:4]==['gcloud','iam','service-accounts','create'] and name in r)
            disable=next(i for i,r in enumerate(stage) if r[:4]==['gcloud','iam','service-accounts','disable'] and sa in r)
            bind=next(i for i,r in enumerate(stage) if r[:4]==['gcloud','iam','service-accounts','add-iam-policy-binding'] and sa in r)
            self.assertLess(create,disable);self.assertLess(disable,bind)
        self.assertTrue(all('--disabled' in r for r in stage if 'workload-identity-pools' in r and ('create' in r or 'create-oidc' in r)))
        self.assertFalse(any('enable' in r or '--no-disabled' in r for r in stage))
        self.assertEqual({'runner','manual'},set(commands['activate']))
        self.assertFalse(any('delete' in r for r in commands['disable']['manual']))

    def test_every_generated_file_argument_resolves_and_shell_quoting_round_trips(self):
        files=s.files(self.cfg);commands=strict(files['commands.json'])
        rows=commands['inspect']+commands['stageDisabled']+sum(commands['activate'].values(),[])+sum(commands['disable'].values(),[])
        for row in rows:
            self.assertEqual(row,shlex.split(shlex.join(row)))
            for flag in ('--file=','--condition-from-file='):
                for arg in row:
                    if arg.startswith(flag):self.assertIn(arg[len(flag):],files)
            if '--input' in row:self.assertIn(row[row.index('--input')+1],files)
        script='set -euo pipefail\n'+'\n'.join(shlex.join(r) for r in rows)+'\n'
        result=subprocess.run(['bash','-n'],input=script,text=True,capture_output=True)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertNotIn('workflow run',script);self.assertNotIn('services enable',script)


if __name__=='__main__':unittest.main()
