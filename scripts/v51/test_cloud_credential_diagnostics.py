"""Credential failures stay closed and retain only fixed, non-secret reason codes."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_cleanup_credentials as c, cloud_cleanup_entry as entry
from . import cloud_permissions as p, cloud_permissions_qualification as q
from . import cloud_cleanup_auth_fake as auth
from .remote_command import read


class CredentialDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.cfg,self.binding,self.env,self.descriptor,*_,self.run = q.fixture('observer')

    def rejected(self, action, code):
        with self.assertRaises(ValueError) as caught:
            action()
        self.assertEqual(code, getattr(caught.exception, 'reason_code', None))
        self.assertEqual({'reasonCode':code}, c.diagnostic(caught.exception))
        for secret in ('private-secret',auth.SUBJECT_SECRET,auth.FEDERATED_SECRET,auth.ACCOUNT_SECRET):
            self.assertNotIn(secret, str(caught.exception))
        return caught.exception

    def test_oidc_environment_failure_codes_identify_the_rejected_component(self):
        for raw,code in (
            (None,'OIDC_URL_SHAPE'), ('https://[private-secret','OIDC_URL_SHAPE'),
            ('http://pipelines.actions.githubusercontent.com/idtoken','OIDC_URL_SCHEME'),
            ('https://private-secret.example/idtoken','OIDC_URL_HOST'),
            ('https://private-secret@pipelines.actions.githubusercontent.com/idtoken','OIDC_URL_AUTHORITY'),
            ('https://pipelines.actions.githubusercontent.com:443/idtoken','OIDC_URL_AUTHORITY'),
            ('https://pipelines.actions.githubusercontent.com','OIDC_URL_PATH'),
            ('https://pipelines.actions.githubusercontent.com/','OIDC_URL_PATH'),
            (auth.OIDC+'#private-secret','OIDC_URL_FRAGMENT'),
            (auth.OIDC+'&audience=private-secret','OIDC_URL_QUERY'),
            (auth.OIDC+'&api-version=private-secret','OIDC_URL_QUERY'),
            (auth.OIDC+'&private-secret','OIDC_URL_QUERY')):
            with self.subTest(code=code,raw=raw):
                env=dict(self.env,ACTIONS_ID_TOKEN_REQUEST_URL=raw)
                self.rejected(lambda:c.descriptor(self.binding,env,self.descriptor),code)
        for raw in (None,'','private-secret\n'):
            self.rejected(lambda:c.descriptor(self.binding,dict(self.env,ACTIONS_ID_TOKEN_REQUEST_TOKEN=raw),self.descriptor),'OIDC_REQUEST_TOKEN_SHAPE')

    def test_descriptor_mismatches_report_fixed_field_codes_without_values(self):
        self.rejected(lambda:c.descriptor(self.binding,self.env,[]),'DESCRIPTOR_TYPE')
        for key,code in (
            ('extra-private-secret','DESCRIPTOR_FIELDS'), ('type','DESCRIPTOR_CREDENTIAL_TYPE'),
            ('audience','DESCRIPTOR_AUDIENCE'), ('subject_token_type','DESCRIPTOR_SUBJECT_TOKEN_TYPE'),
            ('token_url','DESCRIPTOR_TOKEN_URL'), ('service_account_impersonation_url','DESCRIPTOR_IMPERSONATION_URL')):
            value=deepcopy(self.descriptor);value[key]='private-secret'
            with self.subTest(key=key):self.rejected(lambda:c.descriptor(self.binding,self.env,value),code)
        for key in self.descriptor:
            value=deepcopy(self.descriptor);value.pop(key)
            with self.subTest(missing=key):self.rejected(lambda:c.descriptor(self.binding,self.env,value),'DESCRIPTOR_FIELDS')
        for change,code in (
            (None,'DESCRIPTOR_SOURCE_FIELDS'),
            ({'file':'private-secret'},'DESCRIPTOR_SOURCE_FIELDS'),
            ({'url':'https://private-secret/idtoken'},'DESCRIPTOR_SOURCE_URL'),
            ({'url':self.descriptor['credential_source']['url']+'&private-secret=1'},'DESCRIPTOR_SOURCE_QUERY'),
            ({'headers':{'Authorization':'Bearer private-secret'}},'DESCRIPTOR_SOURCE_AUTHORIZATION'),
            ({'format':{'type':'private-secret'}},'DESCRIPTOR_SOURCE_FORMAT')):
            value=deepcopy(self.descriptor)
            if change is None:value['credential_source']=None
            else:value['credential_source'].update(change)
            with self.subTest(code=code):self.rejected(lambda:c.descriptor(self.binding,self.env,value),code)

    def test_equivalent_descriptor_query_order_still_accepts(self):
        value=deepcopy(self.descriptor);url=value['credential_source']['url']
        base,query=url.split('?',1);value['credential_source']['url']=base+'?'+'&'.join(reversed(query.split('&')))
        self.assertEqual(c.descriptor(self.binding,self.env,self.descriptor),c.descriptor(self.binding,self.env,value))

    def test_credential_file_failures_are_bounded_and_do_not_disclose_paths_or_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'private-secret';env=dict(GOOGLE_GHA_CREDS_PATH=str(path))
            self.rejected(lambda:entry.credential_file({}),'CREDENTIAL_FILE_PATH')
            self.rejected(lambda:entry.credential_file(dict(GOOGLE_GHA_CREDS_PATH='private-secret')),'CREDENTIAL_FILE_PATH')
            self.rejected(lambda:entry.credential_file(env),'CREDENTIAL_FILE_OPEN')
            self.rejected(lambda:entry.credential_file(dict(GOOGLE_GHA_CREDS_PATH=str(root))),'CREDENTIAL_FILE_TYPE')
            for raw,code in ((b'','CREDENTIAL_FILE_SIZE'),(b'x'*((128<<10)+1),'CREDENTIAL_FILE_SIZE'),
                             (b'{private-secret','CREDENTIAL_FILE_JSON'),(b'{"a":1,"a":2}','CREDENTIAL_FILE_JSON')):
                path.write_bytes(raw);self.rejected(lambda:entry.credential_file(env),code)
            path.write_text(json.dumps(self.descriptor));self.assertEqual(self.descriptor,entry.credential_file(env))
            link=root/'link';link.symlink_to(path)
            self.rejected(lambda:entry.credential_file(dict(GOOGLE_GHA_CREDS_PATH=str(link))),'CREDENTIAL_FILE_OPEN')
            with patch.object(entry.os,'fstat',side_effect=OSError('private-secret')),patch.object(entry.os,'close',wraps=entry.os.close) as close:
                self.rejected(lambda:entry.credential_file(env),'CREDENTIAL_FILE_READ')
                close.assert_called_once()

    def test_actual_initialization_failure_survives_receipt_summary_and_cli_for_each_role(self):
        for role in p.ROLES:
            cfg,binding,env,descriptor,*_,run=q.fixture(role)
            descriptor['audience']='private-secret'
            with self.subTest(role=role),tempfile.TemporaryDirectory() as tmp,\
                 patch.object(entry,'collect_run',return_value=run),patch.object(p.http.Network,'send') as send:
                root=Path(tmp);path=root/'credential';path.write_text(json.dumps(descriptor))
                env=dict(env,GOOGLE_GHA_CREDS_PATH=str(path));output=root/'result'
                result=p.run(cfg,env,output,role=role,source=binding['source'],checkout=binding['source'])
                self.assertEqual('BLOCKED',result['status']);self.assertEqual('credentials',result['failure']['phase'])
                self.assertEqual('DESCRIPTOR_AUDIENCE',result['failure'].get('reasonCode'))
                self.assertFalse((output/'observations.json').exists());send.assert_not_called()
                self.assertEqual(result,read(output/'receipt.json'))
                self.assertIn('DESCRIPTOR_AUDIENCE',(output/'summary.md').read_text())
                stdout=io.StringIO()
                with patch('sys.argv',['permissions','--role',role,'--source',binding['source'],'--output',str(root/'cli')]),\
                     patch.object(p,'run',return_value=result),patch.object(p.subprocess,'check_output',return_value=binding['source']+'\n'),\
                     contextlib.redirect_stdout(stdout),self.assertRaises(SystemExit) as exit:
                    p.main()
                self.assertEqual(2,exit.exception.code);self.assertIn('DESCRIPTOR_AUDIENCE',stdout.getvalue())
                rendered=stdout.getvalue()+''.join(file.read_text() for file in output.iterdir())
                for secret in ('private-secret',auth.SUBJECT_SECRET,auth.FEDERATED_SECRET,auth.ACCOUNT_SECRET,str(path)):
                    self.assertNotIn(secret,rendered)

    def test_cleanup_entry_reuses_diagnostics_without_reconciliation(self):
        from . import cloud_cleanup_entry_qualification as fixture
        for trigger in ('manual','schedule'):
            invocation=fixture.fixture(self.cfg['provider'],trigger)
            binding=entry.identity(self.cfg,invocation['env'],trigger=trigger,source=invocation['source'],checkout=invocation['checkout'])
            env,descriptor=auth.inputs(binding,invocation['env']);descriptor['token_url']='private-secret'
            with self.subTest(trigger=trigger),tempfile.TemporaryDirectory() as tmp,\
                 patch.object(entry,'collect_run'),patch.object(entry.cleanup,'reconcile') as reconcile,patch.object(p.http.Network,'send') as send:
                path=Path(tmp)/'credential';path.write_text(json.dumps(descriptor));env['GOOGLE_GHA_CREDS_PATH']=str(path)
                output=Path(tmp)/'result'
                result=entry.execute_network(self.cfg,env,output,trigger=trigger,source=invocation['source'],checkout=invocation['checkout'])
                self.assertEqual('FAIL',result['status']);self.assertEqual('DESCRIPTOR_TOKEN_URL',result['failure'].get('reasonCode'))
                self.assertIn('DESCRIPTOR_TOKEN_URL',(output/'summary.md').read_text())
                self.assertFalse(result['credentialExchangeCompleted']);reconcile.assert_not_called();send.assert_not_called()

    def test_unknown_exceptions_cannot_inject_diagnostic_codes_or_summary_text(self):
        error=ValueError('private-secret');error.reason_code='DESCRIPTOR_AUDIENCE'
        self.assertEqual({},c.diagnostic(error))
        with self.assertRaises(ValueError):c.CredentialError('private-secret')
        error=c.CredentialError('DESCRIPTOR_AUDIENCE');error.reason_code='private-secret'
        self.assertEqual({},c.diagnostic(error))
        result={'status':'BLOCKED','failure':{'phase':'credentials','type':'ValueError','reasonCode':'private-secret'}}
        self.assertNotIn('private-secret',p.summary(result));self.assertIn('UNCLASSIFIED',p.summary(result))


if __name__=='__main__':unittest.main()
