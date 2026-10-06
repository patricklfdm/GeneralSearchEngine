"""Native session claims/clocks/configurations with modeled provider/OS context."""
import base64
from copy import deepcopy
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from . import guest_native_session as s, guest_native_owned as owned, cloud_runner_guest_setup as setup
from . import guest_package_receiver as package, guest_native_package as native, cloud_guest as guest
from . import guest_delivery_receiver as r, performance_model as m
from . import test_cloud_runner_guest_setup as fixture


class SessionTest(unittest.TestCase):
    deadline=fixture.NativePackageTest.deadline
    perform=fixture.NativePackageTest.perform
    receive=fixture.NativePackageTest.receive
    def setUp(self):
        fixture.NativePackageTest.setUp(self)
        self.receive();answer=self.perform('finish')['receipt'];self.base=Path(answer['installed']['package'])
        self.budget=r.decode(base64.b64decode(self.token))
        self.session=dict(schema=s.SCHEMA,packageSha256=m.sha(m.canonical(self.value)),preparation=self.budget,
            leaseExpiresNanos=self.budget['sample']['sampledNanos']+4000*10**9,hosts=['10.0.0.1','10.0.0.2','10.0.0.3'],port=19151)
        self.cfg=s.configuration(self.value,self.session,s.MODES[2])
    def test_session_claim_is_exact_and_cannot_renew_deadline_or_topology(self):
        expected=s.begin(self.base,self.session,self.value)
        self.assertEqual('SUCCEEDED',expected['state']);self.assertEqual(expected,s.begin(self.base,self.session,self.value))
        for name in ('leaseExpiresNanos','hosts','port'):
            bad=deepcopy(self.session)
            bad[name]=bad[name]+1 if type(bad[name]) is int else ['10.0.0.4','10.0.0.5','10.0.0.6']
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'consumed'):s.observe(self.base,bad,self.value)
    def test_torn_claim_stays_uncertain_and_is_not_recreated(self):
        folder=self.base.parent/'native-session';folder.mkdir(mode=0o700)
        self.assertEqual({'state':'UNCERTAIN'},s.begin(self.base,self.session,self.value))
        self.assertEqual([],list(folder.iterdir()))
    def test_completed_service_uses_original_lease_after_preparation_expires(self):
        s.begin(self.base,self.session,self.value)
        with patch.object(s.time,'monotonic_ns',return_value=self.budget['expiresNanos']+1):
            self.assertEqual(self.session['leaseExpiresNanos']/1e9,s.service_deadline(self.base,self.cfg))
            with self.assertRaisesRegex(ValueError,'deadline'):s.begin(self.base,self.session,self.value)
    def test_expired_lease_or_reboot_blocks_service(self):
        s.begin(self.base,self.session,self.value)
        for patcher in (patch.object(s.time,'monotonic_ns',return_value=self.session['leaseExpiresNanos']),
                        patch.object(r,'boot_identity',return_value='00000000-0000-0000-0000-000000000000')):
            with patcher,self.assertRaisesRegex(ValueError,'expired/boot'):s.service_deadline(self.base,self.cfg)
    def test_configuration_cannot_change_root_group_package_or_peer(self):
        s.begin(self.base,self.session,self.value)
        for field,value in (('root','/tmp/elsewhere'),('groupId','foreign'),('execution',guest.EXECUTION),
                            ('packageManifestSha256','0'*64),('ports',[1,2,3]),('hosts',['10.0.0.2']*3)):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'configuration'):
                s.service_deadline(self.base,dict(self.cfg,**{field:value}))
    def test_prepared_config_requires_session_before_writing(self):
        with patch.object(guest.c,'write_once') as write,self.assertRaises(FileNotFoundError):guest.prepared_config(self.base,self.cfg)
        write.assert_not_called()
    def test_session_rejects_foreign_package_oversized_lease_public_or_duplicate_peers(self):
        for field,value in (('packageSha256','0'*64),('leaseExpiresNanos',self.budget['sample']['sampledNanos']+5400*10**9+1),
                            ('hosts',['8.8.8.8','10.0.0.2','10.0.0.3']),('hosts',['10.0.0.1']*3),('hosts',['127.0.0.1','127.0.0.2','127.0.0.3'])):
            with self.subTest(field=field),self.assertRaises(ValueError):s.validate(dict(self.session,**{field:value}),self.value)
    def test_closed_dispatch_rejects_arbitrary_actions_and_local_source_paths(self):
        s.begin(self.base,self.session,self.value)
        config=base64.b64encode(m.canonical(self.cfg)).decode()
        with patch.object(package,'installed',return_value=self.base):
            for action,tail in (('shell',[]),('service',[config,'exec','rm']),('bootstrap',['install',base64.b64encode(m.canonical(dict(config=self.cfg,folder='/tmp/source',descriptorSha256='d'*64))).decode()])):
                with self.subTest(action=action),self.assertRaises(ValueError):s.dispatch(action,self.value,self.session,tail,io.BytesIO())
    def test_tampered_installed_bytes_block_before_service_import(self):
        s.begin(self.base,self.session,self.value);(self.base/'guest.py').write_text('must not import')
        # Fixed receiver root is mapped to this synthetic installation only.
        installed=package.installed
        with patch.object(package,'installed',side_effect=lambda _,v:installed(self.parent,v)),\
             self.assertRaisesRegex(ValueError,'inventory'):
            s.dispatch('service',self.value,self.session,[base64.b64encode(m.canonical(self.cfg)).decode(),'ready'],io.BytesIO())
    def test_changed_original_preparation_budget_cannot_start_service(self):
        s.begin(self.base,self.session,self.value)
        bad=deepcopy(self.budget);bad['expiresNanos']+=1
        (self.base.parent/'deadline.json').write_bytes(m.canonical(bad))
        with self.assertRaisesRegex(ValueError,'original package clock'):s.service_deadline(self.base,self.cfg)


class BoundaryTest(unittest.TestCase):
    def test_trusted_session_loads_without_repository(self):
        result=subprocess.run([sys.executable,'-I','-c',setup.trusted_source('session')],cwd='/tmp',capture_output=True,timeout=10)
        self.assertNotEqual(0,result.returncode);self.assertIn(b'not enough values to unpack',result.stderr)
        self.assertNotIn(b'ImportError',result.stderr)
    def test_native_bridge_rejects_plain_configuration_or_fake_services(self):
        for source in ({},object()):
            with self.assertRaises(ValueError):owned.creation(source)
        with self.assertRaises(ValueError):owned.Probe(object(),'/tmp/unused')
