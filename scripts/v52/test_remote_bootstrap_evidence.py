import copy
from pathlib import Path
import tempfile
import unittest
from . import measurement_bundle as b, remote_bootstrap_evidence as e, remote_topology as t
from .evidence import encoded


def fixture(root):
    # Parser/inventory negatives only. These dummy bytes are never accepted as
    # protocol evidence; the Java qualification separately creates real seals.
    bindings={}
    for node in t.NODES:
        directory=root/node;directory.mkdir()
        for kind in ('manifest','genesis'):(directory/(kind+'.gsr')).write_bytes(kind.encode())
        bindings[node]=dict(originalRoot='/original/'+node,
                            **{kind+'Sha256':b.sha_file(directory/(kind+'.gsr')) for kind in ('manifest','genesis')})
    (root/b.INDEX).write_bytes(encoded(b.members(root))+b'\n')
    return bindings


class RemoteBootstrapEvidenceTest(unittest.TestCase):
    def test_collection_inventory_is_required_before_any_path_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bindings=fixture(root)
            (root/b.INDEX).unlink()
            with self.assertRaisesRegex(ValueError,'inventory'):e.EvidenceLocation(root,bindings)
            (root/b.INDEX).write_bytes(encoded(b.members(root))+b'\n')
            (root/'node-1/manifest.gsr').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'inventory/hash'):e.EvidenceLocation(root,bindings)

    def test_closed_receiver_set_original_paths_and_common_authority_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bindings=fixture(root)
            edits=[lambda v:v.pop('node-3'),lambda v:v.__setitem__('node-4',copy.deepcopy(v['node-1'])),
                   lambda v:v['node-1'].__setitem__('extra',True),
                   lambda v:v['node-1'].__setitem__('originalRoot','/original/../other'),
                   lambda v:v['node-1'].__setitem__('originalRoot','relative'),
                   lambda v:v['node-1'].__setitem__('originalRoot','/original//other'),
                   lambda v:v['node-1'].__setitem__('genesisSha256','f'*64)]
            for edit in edits:
                value=copy.deepcopy(bindings);edit(value)
                with self.assertRaises(ValueError):e.EvidenceLocation(root,value)

    def test_inventory_reseal_cannot_replace_independently_bound_authority_or_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bindings=fixture(root)
            (root/'node-1/manifest.gsr').write_bytes(b'forged')
            (root/b.INDEX).write_bytes(encoded(b.members(root))+b'\n')
            location=e.EvidenceLocation(root,bindings)
            with self.assertRaisesRegex(ValueError,'authority identity changed'):location.inspect(root/'node-1')
            with self.assertRaisesRegex(ValueError,'authority scope'):location.inspect(root/'node-2'/'nested')


if __name__=='__main__':unittest.main()
