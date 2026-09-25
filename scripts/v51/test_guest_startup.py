from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_authority as a, cloud_fake, cloud_runner, guest_setup, guest_startup, guest_startup_fake as fake, guest_volume as v
from . import performance_model as m, remote_command as c


class VolumeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.provider = dict(instanceId='123', diskId='456', node=1, sizeGiB=100, attempt='a'*32)
        self.user = 'gse-'+'a'*24; self.clock = cloud_fake.Clock(); self.block = fake.Block(self.provider, self.clock)
    def raw(self): return v.observe(self.block, self.provider, 601)
    def prepare(self, block=None, recheck=lambda:None):
        return v.prepare(self.root/'volume', self.provider, self.user, block or self.block, 601, recheck=recheck)
    def test_real_read_parser_recognizes_blank_and_mounted_model(self):
        before = self.raw(); self.assertEqual(v.blank(before, self.provider, self.user)['device'], before['device'])
        result = self.prepare(); self.assertEqual(result['status'], 'PASS'); self.assertEqual(self.block.formats, 1)
        self.assertEqual(result['volume']['majorMinor'], '8:16')
        self.assertTrue((self.root/'volume/intent-1.json').exists())
        self.assertNotIn('-F', str(result['commands']))
    def test_nvme_root_ancestry_and_data_alias_are_supported(self):
        raw = self.raw(); names = {'/dev/sda':'/dev/nvme0n1', '/dev/sda1':'/dev/nvme0n1p1', '/dev/sdb':'/dev/nvme0n2'}
        raw.update(resolved=names[raw['resolved']], bootDevice=names[raw['bootDevice']])
        for row in raw['lsblk']['blockdevices']:
            row['name'] = names[row['name']]
            if row['pkname'] is not None: row['pkname'] = names[row['pkname']]
        self.assertEqual(v.blank(raw, self.provider, self.user)['device'], raw['device'])
    def test_initialization_is_consumed_even_after_success(self):
        self.prepare(); count = len(self.block.commands)
        with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual(count, len(self.block.commands))
    def test_lost_write_replies_never_reexecute_or_report_pass(self):
        for fault in ('lost-format-reply', 'lost-mount-reply'):
            with self.subTest(fault=fault):
                block = fake.Block(self.provider, self.clock, fault); root = self.root/fault
                with self.assertRaises(ConnectionError): v.prepare(root, self.provider, self.user, block, 601, recheck=lambda:None)
                self.assertEqual(c.read(root/'receipt.json')['status'], 'FAIL'); self.assertEqual(block.formats, 1)
                count = len(block.commands)
                with self.assertRaises(FileExistsError): v.prepare(root, self.provider, self.user, block, 601, recheck=lambda:None)
                self.assertEqual(count, len(block.commands))
    def test_deadline_is_not_reset_for_each_command(self):
        original = self.block.run
        def delayed(argv, deadline):
            if argv[0] == 'mkfs.ext4': self.clock.sleep(601)
            return original(argv, deadline)
        self.block.run = delayed
        with self.assertRaisesRegex(ValueError, 'deadline'): self.prepare()
        self.assertEqual(self.block.formats, 0)
        self.assertEqual(c.read(self.root/'volume/receipt.json')['status'], 'FAIL')
    def test_live_writes_blocked_before_claim_and_native_command_execution(self):
        native = v.Linux()
        with self.assertRaisesRegex(ValueError, 'disabled'): self.prepare(native)
        self.assertFalse((self.root/'volume').exists())
        with patch('scripts.v51.guest_transport.process') as process:
            with self.assertRaisesRegex(ValueError, 'disabled'): native.run(['mkfs.ext4', '/dev/sdb'], 999999999)
            process.assert_not_called()
    def test_native_read_uses_explicit_columns_and_bounded_output(self):
        with patch('scripts.v51.guest_transport.process', return_value=b'{}') as process:
            self.assertEqual(v.Linux().run(v.LSBLK, 77), b'{}')
            process.assert_called_once_with(v.LSBLK, b'', 77, maximum=65536)
    def test_unsafe_raw_disk_or_target_rejected(self):
        raw = self.raw()
        changes = [lambda r:r.update(instanceId='124'), lambda r:r.update(resolved='/dev/sda'),
            lambda r:r['lsblk']['blockdevices'][2].update(ro=True),
            lambda r:r['lsblk']['blockdevices'][2].update(size=1),
            lambda r:r['lsblk']['blockdevices'][2].update(fstype='ext4'),
            lambda r:r['lsblk']['blockdevices'][2].update(mountpoints=['[SWAP]']),
            lambda r:r['lsblk']['blockdevices'][1].update(pkname='/dev/sdb'),
            lambda r:r['lsblk']['blockdevices'][1].update(pkname='/dev/sda1'),
            lambda r:r['lsblk']['blockdevices'].append(deepcopy(r['lsblk']['blockdevices'][2])),
            lambda r:r['wipefs'].update(signatures=[dict(type='gpt', offset='0')]),
            lambda r:r['target'].update(exists=True, directory=True, empty=False),
            lambda r:r['target'].update(exists=True, directory=True, uid=1001, mode=0o755),
            lambda r:r['target'].update(exists=True, directory=True, uid=0, mode=0o777),
            lambda r:r['target'].update(symlink=True),
            lambda r:r['findmnt']['filesystems'].append(dict(target=v.MOUNT, **{'maj:min':'8:0'})),
            lambda r:r['findmnt']['filesystems'].append(dict(target=v.MOUNT+'/nested', **{'maj:min':'8:0'})),
            lambda r:r['findmnt']['filesystems'].append(dict(target='/elsewhere', **{'maj:min':'8:16'}))]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                bad = deepcopy(raw); change(bad)
                with self.assertRaises(ValueError): v.blank(bad, self.provider, self.user)
    def test_alias_drift_and_signature_failure_do_not_format(self):
        for fault in ('boot-device', 'used-disk', 'alias-drift'):
            with self.subTest(fault=fault):
                block = fake.Block(self.provider, self.clock, fault)
                with self.assertRaises(ValueError): v.prepare(self.root/fault, self.provider, self.user, block, 601, recheck=lambda:None)
                self.assertEqual(block.formats, 0)
    def test_provider_recheck_and_second_guest_observation_precede_format(self):
        def changed(): self.block.fault = 'used-disk'
        with self.assertRaises(ValueError): self.prepare(recheck=changed)
        self.assertEqual(self.block.formats, 0)
    def test_post_mount_requires_exact_device_options_filesystem_owner(self):
        before = self.raw(); self.prepare(); good = self.raw()
        changes = [lambda r:r['findmnt']['filesystems'][1].update(options='rw'),
            lambda r:r['findmnt']['filesystems'][1].update(options='ro,nodev,nosuid'),
            lambda r:r['findmnt']['filesystems'][1].update(**{'maj:min':'8:0'}),
            lambda r:r['lsblk']['blockdevices'][2].update(label='foreign'),
            lambda r:r['lsblk']['blockdevices'][2].update(uuid=None),
            lambda r:r['target'].update(uid=0), lambda r:r['target'].update(mode=0o755),
            lambda r:r['wipefs'].update(signatures=[])]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                bad = deepcopy(good); change(bad)
                with self.assertRaises(ValueError): v.mounted(bad, self.provider, self.user, self.block, before)
    def test_response_limit_checked_even_for_injected_backend(self):
        self.block.run = lambda argv, deadline:b'x'*65537
        with self.assertRaisesRegex(ValueError, 'response'): self.raw()
    def test_initialization_diagnostics_survive_failed_postcondition(self):
        self.block.fault = 'wrong-mount'
        with self.assertRaises(ValueError): self.prepare()
        self.assertTrue((self.root/'volume/after.json').exists())
        self.assertEqual(c.read(self.root/'volume/receipt.json')['status'], 'FAIL')


class StartupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.req,self.pre,self.approval,self.clock,self.http,self.store,self.provider,self.transport = fake.fixture(self.root/'key')
    def allocate(self):
        lease = a.lease(self.req, int(self.clock.wall())); gen = self.store.put(a.LEASE, lease, 0)
        for row in lease['resources']:
            row['attempted'] = True; gen = self.store.put(a.LEASE, lease, gen)
            row['id'] = self.provider.create(row['spec'], 601*10**9)['id']; gen = self.store.put(a.LEASE, lease, gen)
        return lease
    def test_facts_are_exact_id_reads_under_one_deadline(self):
        lease = self.allocate(); start = len(self.http.requests)
        facts = self.provider.guest_facts(lease, 1, deadline=601)
        calls = self.http.requests[start:]
        self.assertEqual(len(calls), 6); self.assertTrue(all(v['path'].rsplit('/',1)[1].isdigit() for v in calls))
        self.assertEqual(facts['provider']['node'], 1); self.assertEqual(facts['requestSha256'], a.validate_request(self.req))
    def test_raw_provider_shape_mismatches_and_late_reply_rejected(self):
        lease = self.allocate(); original = self.http.hook
        variants = [('instance', lambda x:x.update(status='TERMINATED')),
                    ('instance', lambda x:x['networkInterfaces'][0].update(networkIP='203.0.113.1')),
                    ('instance', lambda x:x['disks'][1].update(deviceName='foreign')),
                    ('disk', lambda x:x.update(status='CREATING')),
                    ('disk', lambda x:x.update(users=[])), ('disk', lambda x:x.update(users=['foreign']))]
        for kind, change in variants:
            def hook(method, path, query, body):
                reply = original(method, path, query, body)
                if reply and (('/instances/' in path.path) if kind == 'instance' else ('/disks/' in path.path)):
                    value = m.strict_json(reply[1]); change(value); return self.http.reply(value)
                return reply
            self.http.hook = hook
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.provider.guest_facts(lease, 1, deadline=601)
        self.http.hook = original
        with self.assertRaisesRegex(ValueError, 'deadline'): self.provider.guest_facts(lease, 1, deadline=self.clock.seconds())
    def test_valid_private_ip_change_between_two_provider_reads_is_rejected(self):
        lease = self.allocate(); original = self.http.hook; reads = 0
        def hook(method, path, query, body):
            nonlocal reads
            reply = original(method, path, query, body)
            if reply and '/instances/' in path.path:
                reads += 1
                if reads == 2:
                    value = m.strict_json(reply[1]); value['networkInterfaces'][0]['networkIP'] = '10.0.0.9'
                    return self.http.reply(value)
            return reply
        self.http.hook = hook
        with self.assertRaisesRegex(ValueError, 'changed'): self.provider.guest_facts(lease, 1, deadline=601)
    def test_changed_lease_cannot_borrow_provider_or_access(self):
        lease = self.allocate(); lease['request']['attempt'] = 'e'*32
        with self.assertRaises(ValueError): self.provider.guest_facts(lease, 1, deadline=601)
    def test_private_key_must_match_admitted_public_key(self):
        guest_setup.generate(self.root/'other-key', self.req['attempt'])
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            guest_startup.Prepare(self.provider, self.transport, self.root/'other-key/identity', self.root/'startup')
    def test_live_transport_rejected_before_startup(self):
        self.transport.offline = False
        with self.assertRaisesRegex(ValueError, 'disabled'):
            guest_startup.Prepare(self.provider, self.transport, self.root/'key/identity', self.root/'startup')
    def test_controller_retains_failure_cleans_exact_resources_and_keeps_charge(self):
        self.transport.fault = 'lost-format-reply'
        bridge = guest_startup.Prepare(self.provider, self.transport, self.root/'key/identity', self.root/'startup')
        probe = cloud_fake.Probe(self.root/'probe', self.clock)
        result = cloud_runner.Runner(self.store, self.provider, probe, self.root/'run', clock=self.clock.nanos, wall=self.clock.wall, startup=bridge).run(self.req,self.pre,self.approval)
        self.assertEqual(result['status'],'FAIL'); self.assertEqual(probe.cells,[])
        self.assertEqual(result['cleanup']['status'],'PASS'); self.assertTrue(result['leaseReleased']); self.assertFalse(self.http.resources)
        self.assertEqual(a.inspect_ledger(self.store.get(a.LEDGER)[1])[0],self.approval['maximumCostMicrousd'])
        self.assertTrue(any('/startup/node-2/receipt.json' in key for key in self.http.objects))
        self.assertFalse(any(b'PRIVATE KEY' in value[1] for value in self.http.objects.values()))
    def test_startup_upload_failure_cleans_resources_but_retains_lease_and_charge(self):
        original = self.http.hook
        def hook(method, path, query, body):
            if method == 'POST' and '/startup/' in query.get('name', ''): return 503, b''
            return original(method, path, query, body)
        self.http.hook = hook
        bridge = guest_startup.Prepare(self.provider, self.transport, self.root/'key/identity', self.root/'startup')
        probe = cloud_fake.Probe(self.root/'probe', self.clock)
        result = cloud_runner.Runner(self.store, self.provider, probe, self.root/'run', clock=self.clock.nanos, wall=self.clock.wall, startup=bridge).run(self.req,self.pre,self.approval)
        self.assertEqual(result['status'], 'FAIL'); self.assertFalse(self.http.resources)
        self.assertEqual(result['cleanup']['status'], 'PASS'); self.assertFalse(result['leaseReleased'])
        self.assertIsNotNone(self.store.get(a.LEASE))
        self.assertEqual(a.inspect_ledger(self.store.get(a.LEDGER)[1])[0], self.approval['maximumCostMicrousd'])
    def test_retention_rejects_extra_json_instead_of_uploading_it(self):
        root = self.root/'startup'; root.mkdir(); c.write_once(root/'unrelated.json', dict(secret='fixture'))
        bridge = guest_startup.Prepare(self.provider, self.transport, self.root/'key/identity', root)
        with self.assertRaisesRegex(ValueError, 'retention file'): list(bridge.retention_files())
    def test_invalid_credential_permissions_and_symlinks_rejected(self):
        key = self.root/'key/identity'; key.chmod(0o644)
        with self.assertRaises(ValueError): guest_setup.check_private_key(key, self.provider.guest_access)
        key.chmod(0o600); link = self.root/'key/link'; link.symlink_to(key)
        with self.assertRaises(ValueError): guest_setup.check_private_key(link, self.provider.guest_access)


if __name__ == '__main__': unittest.main()
