"""Portable tool identity guards; synthetic records are not native evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
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
