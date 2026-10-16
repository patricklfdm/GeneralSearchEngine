import copy
from pathlib import Path
import tempfile
import unittest
from . import remote_topology as t


def fixture(placement='local-no-gcp'):
    hosts=['127.0.0.1']*3 if placement=='local-no-gcp' else ['10.1.0.1','172.16.0.2','192.168.0.3']
    return dict(schema=t.SCHEMA,placement=placement,groupId='bcbfb3ab-9844-4626-865e-ff65bef08526',
                members=[dict(node=node,host=host,port=25001+i) for i,(node,host) in enumerate(zip(t.NODES,hosts))])


class RemoteTopologyTest(unittest.TestCase):
    def test_explicit_local_and_three_private_host_profiles(self):
        for placement in ('local-no-gcp','owned-private-hosts'):
            self.assertEqual(fixture(placement),t.validate(fixture(placement)))
        value=fixture();value['members'][1]['host']='127.0.0.2';self.assertEqual(value,t.validate(value))

    def test_hosts_ports_and_order_cannot_escape_the_declared_profile(self):
        for placement,host in [('local-no-gcp','10.0.0.1'),('owned-private-hosts','127.0.0.1'),
                              ('owned-private-hosts','8.8.8.8'),('owned-private-hosts','169.254.169.254'),
                              ('owned-private-hosts','172.32.0.1'),('owned-private-hosts','192.169.0.1'),
                              ('local-no-gcp','localhost'),('local-no-gcp','127.00.0.1'),('local-no-gcp','::1')]:
            value=fixture(placement);value['members'][0]['host']=host
            with self.subTest(host=host),self.assertRaises(ValueError):t.validate(value)
        for port in (True,None,1023,65536,'25001',25001.0):
            value=fixture();value['members'][0]['port']=port
            with self.subTest(port=port),self.assertRaises(ValueError):t.validate(value)
        value=fixture();value['members'].reverse()
        with self.assertRaisesRegex(ValueError,'ordered'):t.validate(value)

    def test_duplicate_endpoints_and_private_host_aliases_are_rejected(self):
        value=fixture();value['members'][1]['port']=value['members'][0]['port']
        with self.assertRaisesRegex(ValueError,'duplicate'):t.validate(value)
        value=fixture('owned-private-hosts');value['members'][1]['host']=value['members'][0]['host']
        with self.assertRaisesRegex(ValueError,'three private hosts'):t.validate(value)

    def test_closed_domain_group_and_member_shape(self):
        for mutate in (lambda v:v.__setitem__('provider','gcp'),lambda v:v.__setitem__('schema','gse-v51-remote-topology-v1'),
                       lambda v:v.__setitem__('placement','production'),lambda v:v['members'].pop(),
                       lambda v:v['members'][0].__setitem__('extra',True)):
            value=fixture();mutate(value)
            with self.assertRaises(ValueError):t.validate(value)
        for group in ('00000000-0000-0000-0000-000000000000',True,'bcbfb3ab98444626865eff65bef08526',fixture()['groupId'].upper()):
            value=fixture();value['groupId']=group
            with self.assertRaises(ValueError):t.validate(value)

    def test_file_bounds_and_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/t.FILE
            with self.assertRaises(ValueError):t.read(root)
            path.write_bytes(t.encoded(fixture())+b'\n');self.assertEqual(fixture(),t.read(root))
            path.write_bytes(b' '*4097)
            with self.assertRaises(ValueError):t.read(root)
            path.write_bytes(b'{"schema":"first","schema":"second"}')
            with self.assertRaises(ValueError):t.read(root)
            path.unlink();source=root/'other';source.write_bytes(t.encoded(fixture()));path.symlink_to(source)
            with self.assertRaises(ValueError):t.read(root)


if __name__=='__main__':unittest.main()
