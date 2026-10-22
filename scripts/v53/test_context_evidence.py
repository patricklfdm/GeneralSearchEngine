import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import context_evidence as e
from . import context_negatives as n
from .format_fixture import canonical


class ContextEvidenceTest(unittest.TestCase):
    def test_original_failure_cannot_count_as_negative_rejections(self):
        with patch.object(e, 'validate', side_effect=ValueError('original invalid')) as validate, patch.object(n.shutil, 'copytree') as copytree:
            with self.assertRaisesRegex(ValueError, 'original invalid'): n.run('absent-fixture')
            validate.assert_called_once(); copytree.assert_not_called()

    def test_canonical_evidence_rejects_duplicate_keys_and_excessive_depth(self):
        for value in (b'{"a":1,"a":2}', b'{ "a":1}', b'['*17+b'0'+b']'*17):
            with self.assertRaises(ValueError): e.parse(value)
        self.assertEqual({'a': [1, None]}, e.parse(b'{"a":[1,null]}'))

    def test_either_single_majority_is_insufficient_in_joint_view(self):
        view = dict(old=['a', 'b', 'c', 'd', 'e'], new=['a', 'b', 'c', 'd', 'f'])
        for names in (['a', 'b', 'e'], ['a', 'b', 'f'], ['a', 'b', 'b'], ['a', 'b', 'z']):
            with self.assertRaises(ValueError): e.majority(view, names)
        e.majority(view, ['a', 'b', 'c'])
        e.majority(view, ['a', 'b', 'e', 'f'])

    def test_manifest_rejects_size_links_and_duplicate_names_before_reading_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'fixture').mkdir(); name = 'fixture/blob.bin'; data = b'abc'; (root/name).write_bytes(data)
            manifest = dict(schema='gse-v53-context-fixture-v1', runtimeEnabled=False, authorityEvidence=False,
                            execution='single-jvm-byte-fixture', files=[dict(path=name, size=3, sha256=e.sha(data))], forces=[])
            def write(value): (root/'manifest.json').write_bytes(canonical(value))
            write(manifest); self.assertEqual({name: data}, e.physical(root)[0])
            for case in ('size', 'duplicate', 'runtime'):
                bad = copy.deepcopy(manifest)
                if case == 'size': bad['files'][0]['size'] = 2**63
                elif case == 'duplicate': bad['files'].append(bad['files'][0])
                else: bad['runtimeEnabled'] = True
                write(bad)
                with self.assertRaises(ValueError): e.physical(root)
            write(manifest); (root/name).unlink(); (root/name).symlink_to(root/'manifest.json')
            with self.assertRaisesRegex(ValueError, 'linked'): e.physical(root)

    def test_retirement_requires_terminal_prefix_and_preserves_identity_registry(self):
        state = dict(active=2, cut=dict(index=8, entry='a'*64, view=dict(generation=1, old=['a','b','c'], new=['a','b','c'], operation=None)),
                     identities=[{'node':'old-voter'}], nextOperation=3, retiredThrough=0,
                     results=[dict(request=dict(number=1), phase='COMPLETED'), dict(request=dict(number=2), phase='RESERVED')])
        with self.assertRaisesRegex(ValueError, 'terminal prefix'): e.reduce_catalog(state, 'c'*64, 'RETIRE', {'through':2}, 'b'*64, 'd'*64)
        after = e.reduce_catalog(state, 'c'*64, 'RETIRE', {'through':1}, 'b'*64, 'd'*64)
        self.assertEqual(state['identities'], after['identities'])
        self.assertEqual([state['results'][1]], after['results'])
        self.assertEqual(0, state['retiredThrough'])


if __name__ == '__main__': unittest.main()
