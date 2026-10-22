import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from . import pending_proof_evidence as e
from . import pending_proof_negatives as n

class PendingProofEvidenceTest(unittest.TestCase):
    def test_complete_profiles_and_each_death_boundary(self):
        rows=e.cases();self.assertEqual(45,len(rows));self.assertEqual(45,len({r['name'] for r in rows}))
        self.assertEqual({(s,t) for s in (3,4,5) for t in (0,6,7)},{(r['size'],r['through']) for r in rows if r['mode']=='clean'})
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if r['mode']==mode})
        for mode in ('repeat-halt','repeat-kill'):self.assertEqual(set(e.RECOVERY+e.SEAL),{r['cut'] for r in rows if r['mode']==mode})
    def test_optional_proof_keeps_original_frames_and_payload(self):
        raw=e.container([b'a',b'bc'],b'def',b'original-proof')
        self.assertEqual(len(raw),struct.unpack('>I',raw[8:12])[0]);self.assertEqual(b'abc\0\0\0\3deforiginal-proof',raw[12:])
        self.assertEqual(e.a.container([b'a'],b'b'),e.container([b'a'],b'b',b''))
    def test_missing_case_set_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'proof complete case set'):e.validate(temp)
            (Path(temp)/'extra').mkdir()
            with self.assertRaisesRegex(ValueError,'proof complete case set'):e.validate(temp)
    def test_original_validation_precedes_negative_mutations(self):
        with mock.patch.object(e,'validate',side_effect=ValueError('bad original')),mock.patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('/absent')
            mutate.assert_not_called()
    def test_negatives_cover_real_peer_bytes_and_both_force_chains(self):
        self.assertEqual(12,len(n.CASES));self.assertEqual(12,len({name for name,_ in n.CASES}))
        self.assertTrue({'peer-vote','peer-force','candidate-force','active-proof'}<={name for name,_ in n.CASES})
        for name,reason in n.CASES:self.assertIn(n.selected(name),e.cases());self.assertTrue(reason.startswith('proof '))

    def test_inventory_keeps_per_voter_bounds_and_rejects_extra_root_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for node in range(1,4):(root/f'node-{node}').mkdir()
            (root/'node-2/vote').write_bytes(b'original')
            self.assertEqual(e.a.info(b'original'),e.inventory(root)['node-2/vote'])
            (root/'extra').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'proof voter inventory'):e.inventory(root)
    def test_inventory_has_six_voter_limit_and_original_eighty_file_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for node in range(1,4):(root/f'node-{node}').mkdir()
            for i in range(81):(root/'node-1'/str(i)).write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'source evidence file count'):e.inventory(root)
            for node in range(4,8):(root/f'node-{node}').mkdir()
            with self.assertRaisesRegex(ValueError,'proof voter inventory'):e.inventory(root)
