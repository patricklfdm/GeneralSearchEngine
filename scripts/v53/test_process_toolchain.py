"""Portable tool identity guards; synthetic records are not native evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
from unittest.mock import patch
from . import process_toolchain as t


def record(home='/one',kernel='first'):
    props=dict(zip(t.PROPERTIES,('21.0.12','21.0.12+8-LTS','Eclipse Adoptium','OpenJDK 64-Bit Server VM','21.0.12+8-LTS','amd64','Linux')))
    return dict(schema=t.SCHEMA,exit=0,stdout='Apache Maven 3.9.11 (pinned)\nMaven home: '+home+'/maven\nJava version: 21.0.12, vendor: Eclipse Adoptium, runtime: '+home+'/java\nOS name: Linux, version: '+kernel+'\n',stderr='',
        javaDiagnostics=''.join('    '+k+' = '+v+'\n' for k,v in props.items()),
        identity=dict(schema=t.SCHEMA,maven='3.9.11 (pinned)',java=props,
            binaries={k:'a'*64 for k in ('java/bin/java','java/lib/modules','maven/bin/mvn','maven/lib/core.jar')}))


class ProcessToolchainTest(unittest.TestCase):
    def pin(self,value):return t.pin(json.dumps(value).encode())

    def test_host_paths_and_kernel_remain_diagnostic_not_cohort_identity(self):
        a=record();b=record('/two','second')
        self.assertNotEqual(a['stdout'],b['stdout']);self.assertEqual(self.pin(a),self.pin(b))

    def test_real_binary_or_version_drift_changes_identity(self):
        a=record();b=copy.deepcopy(a);b['identity']['binaries']['java/lib/modules']='b'*64
        self.assertNotEqual(self.pin(a),self.pin(b))
        b=copy.deepcopy(a);b['stdout']=b['stdout'].replace('3.9.11','3.9.12');b['identity']['maven']='3.9.12 (pinned)'
        self.assertNotEqual(self.pin(a),self.pin(b))

    def test_diagnostic_property_version_and_inventory_tampering_fail(self):
        changes=[lambda v:v.update(exit=1),lambda v:v.update(exit=False),
            lambda v:v['identity']['java'].update({'java.version':'21.0.13'}),
            lambda v:v.update(javaDiagnostics=v['javaDiagnostics']+'    os.name = Linux\n'),
            lambda v:v['identity'].update(maven='claimed'),
            lambda v:v['identity']['binaries'].pop('java/bin/java'),
            lambda v:v['identity']['binaries'].update({'maven/lib/../escape.jar':'a'*64}),
            lambda v:v['identity']['binaries'].update({'maven/lib/x.jar':'not a hash'})]
        for change in changes:
            with self.subTest(change=change):
                value=record();change(value)
                with self.assertRaises(ValueError):self.pin(value)

    def test_legacy_record_preserves_exact_raw_hash(self):
        raw=json.dumps(dict(exit=0,stdout='original host diagnostics',stderr=''),indent=2).encode()
        self.assertEqual(t.h.digest(raw),t.pin(raw))
        self.assertNotEqual(t.pin(raw),t.pin(raw+b'\n'))

    def test_streamed_file_hash(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'module';p.write_bytes(b'x'*(1024*1024+19))
            self.assertEqual(t.h.digest(p.read_bytes()),t.file_hash(p))

    def test_only_completed_transient_wrapper_failure_retries_before_locating(self):
        with tempfile.TemporaryDirectory() as root:
            home=Path(root);maven=home/'maven/bin/mvn';maven.parent.mkdir(parents=True);maven.touch()
            failed=subprocess.CompletedProcess([],22,'','curl: (22) The requested URL returned error: 503')
            good=subprocess.CompletedProcess([],0,record(root)['stdout'],'')
            with patch.object(t.subprocess,'run',side_effect=[failed,good]) as run,patch.object(t.time,'sleep') as sleep:
                self.assertEqual(str(maven),t.locate(home/'mvnw',home))
                self.assertEqual(2,run.call_count);sleep.assert_called_once_with(2)
                self.assertTrue(all(v.args[0]==[str(home/'mvnw'),'-version'] for v in run.call_args_list))
                self.assertTrue(all(v.kwargs['env']['MVNW_VERBOSE']=='true' for v in run.call_args_list))

    def test_verbose_wget_classifies_network_and_server_failures_only(self):
        for message in ('wget: unable to resolve host address example.invalid',
                        'HTTP request sent, awaiting response... 503 Service Unavailable\nERROR 503: Service Unavailable.'):
            self.assertTrue(t.transient_initialization(subprocess.CompletedProcess([],1,'',message)))
        for message in ('wget: Failed to fetch https://repo.maven.apache.org/maven.zip',
                        'ERROR 404: Not Found.', 'ERROR 403: Forbidden.',
                        'ERROR 503: certificate failure', 'checksum mismatch; ERROR 503'):
            self.assertFalse(t.transient_initialization(subprocess.CompletedProcess([],1,'',message)))

    def test_failure_threshold_keeps_all_attempt_diagnostics(self):
        failed=subprocess.CompletedProcess([],6,'bootstrap','curl: (6) Could not resolve host')
        with patch.object(t.subprocess,'run',return_value=failed) as run,patch.object(t.time,'sleep'):
            with self.assertRaisesRegex(ValueError,'process Maven wrapper initialization:') as caught:t.locate('/wrapper','/work')
            attempts=json.loads(str(caught.exception).split(': ',1)[1])
            self.assertEqual([1,2,3],[v['attempt'] for v in attempts]);self.assertEqual(3,run.call_count)
            self.assertTrue(all(v['exit']==6 and v['stdout']=='bootstrap' and 'resolve host' in v['stderr'] for v in attempts))

    def test_permanent_unknown_and_timeout_fail_without_retry(self):
        for message in ('checksum failed; connection timed out','curl: (22) HTTP status 403',
                        'permission denied','unexpected bootstrap error','JAVA_HOME missing',
                        'SSL certificate error','curl: (22) HTTP status 404'):
            with self.subTest(message=message),patch.object(t.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'',message)) as run,patch.object(t.time,'sleep') as sleep:
                with self.assertRaisesRegex(ValueError,'process Maven wrapper initialization:'):t.locate('/wrapper','/work')
                self.assertEqual(1,run.call_count);sleep.assert_not_called()
        error=subprocess.TimeoutExpired(['/wrapper','-version'],300,output=b'download started',stderr=b'stalled')
        with patch.object(t.subprocess,'run',side_effect=error) as run,patch.object(t.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'download started') as caught:t.locate('/wrapper','/work')
            self.assertIn('timeoutSeconds',str(caught.exception));self.assertEqual(1,run.call_count);sleep.assert_not_called()

    def test_setup_diagnostic_redacts_url_secrets_and_is_bounded(self):
        value=subprocess.CompletedProcess([],1,'x'*9000,'https://user:secret@example.org/distribution?token=secret')
        result=t.initialization_detail(value)
        self.assertNotIn('secret',json.dumps(result));self.assertEqual(4000,len(result['stdout']))
        self.assertIn('example.org/distribution',result['stderr'])
