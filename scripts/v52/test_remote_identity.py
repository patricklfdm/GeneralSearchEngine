from pathlib import Path
import tempfile
import unittest
from . import remote_identity as r,remote_topology as t
from .test_remote_topology import fixture
from .evidence import encoded


class RemoteIdentityTest(unittest.TestCase):
    def test_private_address_structure_does_not_qualify_real_cloud_hosts(self):
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(remoteTopology=fixture('owned-private-hosts'),remoteReceivers={})
            with self.assertRaisesRegex(ValueError,'host qualification not implemented'):r.location(Path(directory),binding)

    def test_missing_topology_or_receivers_cannot_fall_back_to_local_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for binding in ({'remoteTopology':fixture()},{'remoteReceivers':{}}):
                with self.assertRaisesRegex(ValueError,'binding fields'):r.location(Path(directory),binding)

    def test_retained_topology_must_equal_the_independent_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);value=fixture();changed=fixture();changed['members'][0]['port']+=10
            (root/t.FILE).write_bytes(encoded(changed))
            with self.assertRaisesRegex(ValueError,'retained topology changed'):
                r.location(root,dict(remoteTopology=value,remoteReceivers={}))

    def test_incomplete_execution_and_oversized_receipts_reject_before_authority_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);value=fixture();(root/t.FILE).write_bytes(encoded(value));path=root/'execution.json'
            binding=dict(remoteTopology=value,remoteReceivers={})
            for result in ({'status':'PASS'},dict(status='STOPPED',failure=None,closeErrors=[{'node':'node-1'}],qualifiedMeasurement=False,paidCloud=False)):
                path.write_bytes(encoded(result))
                with self.assertRaisesRegex(ValueError,'execution incomplete'):r.location(root,binding)
            path.write_bytes(b' ' * ((1<<20)+1))
            with self.assertRaisesRegex(ValueError,'metadata bound'):r.location(root,binding)


if __name__=='__main__':unittest.main()
