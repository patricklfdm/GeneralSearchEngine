import json
import subprocess
import unittest
from unittest.mock import patch
from . import cloud_runner_diagnostics as d, cloud_runner_entry as entry
from . import cloud_runner_resources as resources, cloud_runner_resource_qualification as q
from . import test_cloud_runner_resources as resource_tests, cloud_http as h
from . import cloud_cleanup_auth_fake as auth
from .remote_command import read, write_once


class SafeDiagnosticsTest(unittest.TestCase):
    def test_closed_codes_reject_unknown_messages_attributes_and_secret_exception_types(self):
        for message,code in d.MESSAGES.items():
            self.assertEqual(code,d.failure('admission',ValueError(message))['code'])
        for error in (ValueError('private-secret'),KeyError('private-secret'),
                      subprocess.CalledProcessError(1,['private-secret'],output='private-secret',stderr='private-secret'),
                      type('private-secret',(ValueError,),{})('private-secret')):
            error.reason_code='DESCRIPTOR_AUDIENCE'
            result=d.failure('admission',error)
            self.assertNotIn('private-secret',json.dumps(result))
            self.assertNotEqual('DESCRIPTOR_AUDIENCE',result['code'])
        error=ValueError('prefix Runner plan drift/expiry private-secret')
        self.assertEqual('UNCLASSIFIED',d.failure('admission',error)['code'])

    def test_nested_stage_keeps_first_failure_without_exception_text_or_chaining(self):
        with self.assertRaises(d.AdmissionError) as caught:
            with d.stage('allocation-recheck'):
                with d.stage('artifact-bytes'):raise ValueError('private-secret')
        result=d.failure('admission-recheck',caught.exception)
        self.assertEqual('artifact-bytes',result['admissionStage'])
        self.assertEqual('UNCLASSIFIED',result['code']);self.assertNotIn('private-secret',str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        caught.exception.code='private-secret';caught.exception.error_type='private-secret'
        caught.exception.stage='private-secret';caught.exception.http_status='private-secret'
        self.assertNotIn('private-secret',json.dumps(d.failure('admission',caught.exception)))

    def test_http_status_is_numeric_and_timeout_file_errors_are_distinct(self):
        for error,code in ((h.ApiError(403,'private-secret'),'PROVIDER_HTTP'),
            (TimeoutError('private-secret'),'ADMISSION_TIMEOUT'),
            (subprocess.TimeoutExpired(['private-secret'],30),'ADMISSION_TIMEOUT'),
            (ConnectionError('private-secret'),'ADMISSION_TRANSPORT'),
            (FileNotFoundError('private-secret'),'ADMISSION_FILE_ACCESS')):
            result=d.failure('admission',error);self.assertEqual(code,result['code'])
            self.assertNotIn('private-secret',json.dumps(result))
        for invalid in (True,'private-secret',600):
            self.assertNotIn('httpStatus',d.failure('admission',h.ApiError(invalid,'GET')))

    def test_runtime_codes_keep_identity_transport_and_deadline_distinct_without_secrets(self):
        for error,code in ((ValueError('cleanup compute method/path/operation scope'),'RUNTIME_RESOURCE_SCOPE'),
            (ValueError('owned provider/pinned host changed'),'RUNTIME_IDENTITY_CHANGED'),
            (ValueError('owned runtime durable authority changed'),'RUNTIME_AUTHORITY_CHANGED'),
            (ValueError('provider late response'),'RUNTIME_DEADLINE'),
            (ValueError('owned bounded voter initial fencing'),'RUNTIME_BOUNDED_VOTER_FENCING'),
            (ConnectionError('private-secret'),'RUNTIME_TRANSPORT'),(TimeoutError('private-secret'),'RUNTIME_TIMEOUT'),
            (d.transport.ProcessError('SSH_DISCONNECTED'),'SSH_DISCONNECTED'),
            (d.transport.ProcessRejected('SSH_HOST_KEY'),'SSH_HOST_KEY'),
            (h.ApiError(403,'private-secret'),'PROVIDER_HTTP')):
            result=d.runtime_failure('execution',error)
            self.assertEqual(code,result['code']);self.assertEqual(d.detail(code),result['detail'])
            self.assertNotIn('private-secret',json.dumps(result))
        forged=d.transport.ProcessError('SSH_DISCONNECTED');forged.code='private-secret'
        self.assertEqual('UNCLASSIFIED',d.runtime_failure('execution',forged)['code'])


class AdmissionPathTest(unittest.TestCase):
    setUpClass=classmethod(resource_tests.RunnerResourcesTest.setUpClass.__func__)
    setUp=resource_tests.RunnerResourcesTest.setUp
    mutations=resource_tests.RunnerResourcesTest.mutations

    def check_failure(self,code,stage,output='evidence'):
        result=q.prepare(self.f,self.root/output)
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['paidAdmission'])
        self.assertEqual([],self.mutations());self.assertEqual(0,self.f['http'].inserts)
        failure=result['failure'];self.assertEqual(code,failure['code']);self.assertEqual(stage,failure['admissionStage'])
        self.assertEqual(failure,read(self.root/output/'receipt.json')['failure'])
        for secret in ('private-secret',auth.SUBJECT_SECRET,auth.FEDERATED_SECRET,auth.ACCOUNT_SECRET):
            for path in (self.root/output).rglob('*'):
                if path.is_file():self.assertNotIn(secret.encode(),path.read_bytes())
        summary=self.root/(output+'-summary');summary.mkdir()
        write_once(summary/'receipt.json',dict(status='FAIL',result=dict(preparation=result)))
        text=entry.summary(summary)
        self.assertIn('Failure code | '+code,text);self.assertIn('Admission stage | '+stage,text)
        self.assertIn(d.detail(code),text)
        return failure

    def test_unapproved_plan_and_expired_plan_have_distinct_codes(self):
        self.f['approved']['confirmed']=False
        self.check_failure('APPROVAL_MISMATCH','approval')
        self.f['approved']['confirmed']=True;self.f['clock'].sleep(900)
        self.check_failure('PLAN_CHANGED_OR_EXPIRED','approval','expired')

    def test_corrupt_original_archive_is_not_a_credential_failure(self):
        (self.f['originals']/'package.zip').write_bytes(b'private-secret')
        self.check_failure('ARTIFACT_BYTES_MISMATCH','artifact-bytes')
        self.assertEqual([],self.f['issuer'].calls)

    def test_descriptor_error_survives_constructor_failure(self):
        self.f['descriptor']['audience']='private-secret'
        self.check_failure('DESCRIPTOR_AUDIENCE','credentials')
        self.assertEqual([],self.f['issuer'].calls)

    def test_all_exchange_steps_retain_safe_codes_and_never_create_resources(self):
        for step in ('oidc','sts','impersonation'):
            with self.subTest(step=step):
                self.f['issuer'].fail=step
                self.check_failure(step.upper()+'_EXCHANGE_FAILED','control-read',step)

    def test_provider_denial_retains_http_status_without_response_or_url(self):
        self.f['http'].send=lambda *args:(403,b'private-secret')
        self.assertEqual(403,self.check_failure('PROVIDER_HTTP','control-read')['httpStatus'])

    def test_recheck_failure_is_not_overwritten_by_resource_stage_rejection(self):
        original=self.f['http'].send;changed=False
        def drift(method,url,*args):
            nonlocal changed
            if method=='GET' and '/compute/v1/projects/' in url and not changed:
                changed=True;self.f['data']['branches/master']['commit']['sha']='e'*40
            return original(method,url,*args)
        self.f['http'].send=drift
        failure=self.check_failure('MASTER_CHANGED','ci')
        self.assertEqual('admission-recheck',failure['phase']);self.assertTrue(changed)

    def test_unknown_inspection_failure_still_has_safe_code_before_api_exists(self):
        with patch.object(resources.admission,'OfflineAdmission',side_effect=ValueError('private-secret')):
            result=q.prepare(self.f,self.root/'evidence')
        self.assertEqual('UNCLASSIFIED',result['failure']['code'])
        self.assertEqual([],self.mutations());self.assertNotIn('private-secret',json.dumps(result))

    def test_summary_ignores_untrusted_detail(self):
        root=self.root/'summary';root.mkdir()
        write_once(root/'receipt.json',dict(failure=dict(code='PROVIDER_HTTP',detail='private-secret')))
        text=entry.summary(root);self.assertNotIn('private-secret',text);self.assertIn(d.DETAILS['PROVIDER_HTTP'],text)
