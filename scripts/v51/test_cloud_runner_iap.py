import os
from pathlib import Path
import shlex
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import cloud_runner_iap as r, cloud_http as h, guest_setup as setup


class RunnerIapTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        access=setup.generate(self.root/'private','a'*32);setup.pin(self.root/'known','123',access['publicKey'])
        self.target=dict(project='test-project',zone='us-west4-a',instance='gse-v51-test',instanceId='123',user=access['user'],
                         key=str(self.root/'private/identity'),knownHosts=str(self.root/'known'))
        self.api=SimpleNamespace(offline=False,clock=lambda:100,deadline=700,tokens=lambda _:h.AccessToken('bound-secret',1000))

    def test_only_bound_token_and_isolated_configuration_reach_iap(self):
        observed=[]
        def process(args,data,deadline,*,maximum,env):
            proxy=shlex.split(next(v.removeprefix('ProxyCommand=') for v in args if v.startswith('ProxyCommand=')))
            token=Path(next(v.split('=',1)[1] for v in proxy if v.startswith('--access-token-file=')))
            self.assertEqual('bound-secret',token.read_text());self.assertEqual(0,token.stat().st_mode & 0o077)
            self.assertEqual([],list(Path(env['CLOUDSDK_CONFIG']).iterdir()))
            self.assertNotIn('CLOUDSDK_AUTH_ACCESS_TOKEN',env);self.assertNotIn('CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE',env)
            self.assertNotIn('CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT',env);self.assertNotIn('GOOGLE_APPLICATION_CREDENTIALS',env)
            self.assertNotIn('bound-secret',str(args));self.assertNotIn('bound-secret',str(env))
            self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('HostKeyAlias=gse-v51-123',args)
            self.assertEqual(list(r.COMMAND),shlex.split(args[-1]));self.assertEqual((b'',160,64),(data,deadline,maximum))
            self.assertEqual(['gcloud','compute','start-iap-tunnel',self.target['instance'],'22'],proxy[:5])
            observed.append((token,Path(env['CLOUDSDK_CONFIG'])));return b'123'
        with patch.dict(os.environ,CLOUDSDK_AUTH_ACCESS_TOKEN='ambient',CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE='/ambient',
                        CLOUDSDK_AUTH_IMPERSONATE_SERVICE_ACCOUNT='foreign',GOOGLE_APPLICATION_CREDENTIALS='/ambient'),\
             patch.object(r.transport,'process',side_effect=process) as run:
            self.assertEqual(b'123',r._network_probe(self.api,self.target,160));self.assertEqual(1,run.call_count)
        self.assertTrue(all(not p.exists() for pair in observed for p in pair))

    def test_secret_diagnostics_and_temporary_credentials_do_not_survive_failure(self):
        seen=[]
        def failure(*args,**kwargs):
            seen.append(Path(kwargs['env']['CLOUDSDK_CONFIG']).parent)
            raise ConnectionError('Authorization: Bearer bound-secret /sensitive/credential.json')
        with patch.object(r.transport,'process',side_effect=failure) as run:
            with self.assertRaisesRegex(ConnectionError,'^Runner IAP identity probe failed$'):
                r._network_probe(self.api,self.target,160)
            self.assertEqual(1,run.call_count)
        self.assertTrue(all(not path.exists() for path in seen))

    def test_expired_short_or_unbound_token_never_starts_a_process(self):
        for token in ('raw-secret',h.AccessToken('secret',159),h.AccessToken('secret',160),h.AccessToken('bad\nsecret',1000)):
            self.api.tokens=lambda _,token=token:token
            with self.subTest(token=type(token).__name__),patch.object(r.transport,'process') as run,self.assertRaises(ValueError):
                r._network_probe(self.api,self.target,160)
            run.assert_not_called()

    def test_offline_or_renewed_deadline_rejected_before_credentials(self):
        for offline,deadline in ((True,160),(False,100),(False,701)):
            self.api.offline=offline
            with patch.object(self.api,'tokens') as tokens,self.assertRaises(ValueError):
                r._network_probe(self.api,self.target,deadline)
            tokens.assert_not_called()

    def test_reuses_only_admitted_token_covering_original_connection_deadline(self):
        self.api.token,self.api.expires='already-bound',1000
        with patch.object(self.api,'tokens',return_value=h.AccessToken('refreshed-bound',1000)) as tokens,\
             patch.object(r.transport,'process',return_value=b'123'):
            r._network_probe(self.api,self.target,160);tokens.assert_not_called()
            self.api.expires=159
            r._network_probe(self.api,self.target,160);self.assertEqual(1,tokens.call_count)
            self.assertEqual(('refreshed-bound',1000),(self.api.token,self.api.expires))

    def test_token_files_must_be_private_owned_regular_files(self):
        token=self.root/'token';token.write_text('fixture');token.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'token file'):r.transport.ssh_args(self.target,r.COMMAND,access_token_file=token)
        token.chmod(0o600);link=self.root/'link';link.symlink_to(token)
        with self.assertRaisesRegex(ValueError,'token file'):r.transport.ssh_args(self.target,r.COMMAND,access_token_file=link)

    def test_actual_child_process_receives_only_selected_environment(self):
        with patch.dict(os.environ,CLOUDSDK_AUTH_ACCESS_TOKEN='ambient'):
            raw=r.transport.process([sys.executable,'-c','import os; print(os.getenv("CLOUDSDK_AUTH_ACCESS_TOKEN","absent"))'],
                                    b'',time.monotonic()+5,env={'PATH':os.environ['PATH']})
        self.assertEqual(b'absent\n',raw)

    def test_only_missing_valid_host_key_is_pending(self):
        with self.assertRaises(setup.HostKeyPending):setup.host_key(dict(queryPath='hostkeys/',queryValue=dict(items=[])))
        for raw in (dict(queryPath='foreign',queryValue=dict(items=[])),
                    dict(queryPath='hostkeys/',queryValue=dict(items=[dict(namespace='hostkeys',key='ssh-ed25519',value='broken')]*2))):
            with self.assertRaises(ValueError) as error:setup.host_key(raw)
            self.assertNotIsInstance(error.exception,setup.HostKeyPending)


if __name__=='__main__':unittest.main()
