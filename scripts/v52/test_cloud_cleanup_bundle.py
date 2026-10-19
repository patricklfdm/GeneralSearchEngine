from contextlib import redirect_stdout
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_cleanup_bundle as b, cloud_cleanup_workflow as w, cloud_credentials as credentials
from . import cloud_credentials_offline as auth, cloud_preflight_read as r
from .test_cloud_recent_cleanup import evidence,NOW,SOURCE
from .evidence import encoded,strict


class CleanupBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cfg,cls.empty=evidence();_,cls.cleaned=evidence(resources=True)

    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def body(self,files=None):return deepcopy({k:v for k,v in (files or self.cleaned).items() if k!='seal.json'})

    def test_actual_native_factory_journal_and_original_context_replay_all_thirteen_ids(self):
        result=b.verify(self.cleaned,SOURCE,NOW)
        self.assertEqual('PASS',result['status']);self.assertTrue(result['deletionPathExercised'])
        receipt=strict(self.cleaned['receipt.json']);self.assertEqual(13,receipt['resourceDeletesSubmitted'])
        self.assertFalse(b.verify(self.empty,SOURCE,NOW)['deletionPathExercised'])

    def test_missing_or_changed_original_resource_absence_is_rejected(self):
        for mutate in (lambda r:r['cleanup']['checks'].pop(),lambda r:r['cleanup']['checks'][0].update(expectedId='99999'),
                       lambda r:r['cleanup']['checks'][0].update(absent=False),lambda r:r.update(leaseReleased=False),
                       lambda r:r['cleanup'].update(errors=[{}])):
            files=self.body();receipt=strict(files['receipt.json']);mutate(receipt);files['receipt.json']=encoded(receipt)
            with self.assertRaises((ValueError,KeyError)):b.seal(files,SOURCE,NOW)

    def test_cleanup_cannot_erase_the_original_ledger_or_failed_cost(self):
        files=self.body();receipt=strict(files['receipt.json'])
        receipt['controlAfter']['ledger']['value']=b.a.empty_ledger(domain='native')
        files['receipt.json']=encoded(receipt)
        with self.assertRaisesRegex(ValueError,'ledger changed history/cost'):b.seal(files,SOURCE,NOW)

    def test_original_context_configuration_generation_and_receipt_do_not_float(self):
        for mutate in (lambda r:r.update(generation=True),lambda r:r['value'].update(requestSha256='a'*64),
                       lambda r:r['value']['configuration'].update(bucket='foreign-bucket')):
            files=self.body();context=strict(files['original-context.json']);mutate(context);files['original-context.json']=encoded(context)
            with self.assertRaises(ValueError):b.seal(files,SOURCE,NOW)

    def test_journal_truncation_counts_duplicates_and_extra_fields_reject(self):
        original=self.cleaned['exchanges.jsonl'].splitlines()
        for lines in (original[:-1],original+[original[-1]],original+[encoded(dict(secret='token'))]):
            files=self.body();files['exchanges.jsonl']=b'\n'.join(lines)+b'\n'
            with self.assertRaises((ValueError,KeyError)):b.seal(files,SOURCE,NOW)
        files=self.body();receipt=strict(files['receipt.json']);receipt['resourceDeletesSubmitted']=12;files['receipt.json']=encoded(receipt)
        with self.assertRaises(ValueError):b.seal(files,SOURCE,NOW)

    def test_seal_rejects_altered_inventory_unknown_and_missing_payload(self):
        for mutate in (lambda f:f.pop('preflight.json'),lambda f:f.update(extra=b'x'),lambda f:f.update(**{'configuration.json':b'{}'})):
            files=deepcopy(self.empty);mutate(files)
            with self.assertRaises((ValueError,KeyError)):b.verify(files,SOURCE,NOW)

    def test_native_sealing_refuses_failed_original_and_uses_fresh_source(self):
        source=self.root/'original';source.mkdir()
        for name,raw in self.empty.items():
            if name not in ('configuration.json','seal.json'):(source/name).write_bytes(raw)
        with patch.object(r,'source_configuration',return_value=self.cfg),patch.object(r.time,'time',return_value=NOW):
            sealed=b.seal_native(SOURCE,source,self.root/'bundle')
            self.assertEqual('PASS',sealed['inspection']['status'])
            (source/'failure.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'factory failed'):b.seal_native(SOURCE,source,self.root/'failed')
        self.assertFalse((self.root/'failed').exists())

    def test_source_drift_during_copy_cannot_publish_a_seal(self):
        source=self.root/'original';source.mkdir()
        for name,raw in self.empty.items():
            if name not in ('configuration.json','seal.json'):(source/name).write_bytes(raw)
        changed=deepcopy(self.cfg);changed['projectNumber']='99999'
        with patch.object(r,'source_configuration',side_effect=[self.cfg,changed]),patch.object(r.time,'time',return_value=NOW):
            with self.assertRaisesRegex(ValueError,'bundle source changed'):b.seal_native(SOURCE,source,self.root/'bundle')
        self.assertFalse((self.root/'bundle'/'seal.json').exists())

    def test_waiting_uses_decision_time_even_if_final_observation_crosses_expiry(self):
        _,files=evidence(active=True);files.pop('seal.json');receipt=strict(files['receipt.json'])
        lease=receipt['controlAfter']['lease']['value'];expired=lease['expiresAt']+lease['graceSeconds']
        receipt['checkedAt']=expired+10;files['receipt.json']=encoded(receipt)
        self.assertEqual('WAITING',b.seal(files,SOURCE,expired+10)['inspection']['status'])
        receipt['decisionAt']=expired;files['receipt.json']=encoded(receipt)
        with self.assertRaisesRegex(ValueError,'waiting beyond original grace'):b.seal(files,SOURCE,expired+10)

    def test_summary_explains_waiting_and_empty_pass_without_rendering_injected_markup(self):
        (self.root/'receipt.json').write_bytes(self.empty['receipt.json'])
        with redirect_stdout(io.StringIO()) as out:b.summary(self.root)
        self.assertIn('Empty PASS',out.getvalue());self.assertIn('Resource deletes submitted',out.getvalue())
        value=strict(self.empty['receipt.json']);value['source']='<script>|unsafe\ntext';(self.root/'receipt.json').write_bytes(encoded(value))
        with redirect_stdout(io.StringIO()) as out:b.summary(self.root)
        self.assertNotIn('<script>',out.getvalue());self.assertIn('&lt;script&gt;&#124;',out.getvalue())

    def test_workflow_is_manual_only_fixed_source_environment_and_no_stage_timeout(self):
        text=w.contract();self.assertEqual(text,w.render());self.assertNotIn('schedule:',text);self.assertNotIn('timeout ',text)
        self.assertNotIn('timeout-minutes:',text);self.assertIn('cancel-in-progress: false',text)
        self.assertIn('v52-cloud-manual-cleanup',text);self.assertIn('retention-days: 30',text)
        self.assertIn('persist-credentials: false',text);self.assertIn('github.run_attempt',text)

    def test_workflow_drift_rejects_before_bootstrap_credentials(self):
        path=self.root/w.PATH;path.parent.mkdir(parents=True);path.write_text(w.render().replace('id-token: write','id-token: none'))
        with self.assertRaisesRegex(ValueError,'workflow changed'):w.contract(self.root)

    def bootstrap(self,changes=None):
        project,env,descriptor,invocation,issuer=auth.fixture(self.cfg['provider'],'manual',SOURCE)
        output=self.root/'outputs';output.touch();env['GITHUB_OUTPUT']=str(output)
        if changes:env.update(changes)
        with patch.dict(w.os.environ,env,clear=True),patch.object(r,'source_configuration',return_value=self.cfg), \
             patch.object(credentials,'github',side_effect=lambda path,end,clock:invocation.get(path,end)), \
             patch.object(w.time,'monotonic',side_effect=invocation.clock.seconds),patch.object(w.time,'time',side_effect=invocation.clock.wall), \
             patch('scripts.v51.cloud_http.Network.send',side_effect=AssertionError('token/provider exchange forbidden')):
            result=w.identity_native(SOURCE,self.root/'identity')
        return result,output.read_text()

    def test_bootstrap_binds_actual_run_and_only_emits_selected_provider_and_account(self):
        result,text=self.bootstrap();self.assertFalse(result['credentialExchangeCompleted'])
        self.assertEqual(2,result['binding']['runAttempt']);self.assertEqual(2,len(text.splitlines()))
        self.assertIn('gse-v52-manual-cleanup',text);self.assertNotIn('token',text)

    def test_bootstrap_rejects_branch_wrong_event_and_runner_role_before_auth(self):
        for changes in (dict(GITHUB_REF='refs/heads/other'),dict(GITHUB_EVENT_NAME='schedule'),dict(GITHUB_JOB='runner')):
            with self.assertRaises(ValueError):self.bootstrap(changes)
            for file in (self.root/'identity').iterdir():file.unlink()
            (self.root/'identity').rmdir()


if __name__=='__main__':unittest.main()
