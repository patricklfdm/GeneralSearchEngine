"""Fail-closed boundary evidence framing and baseline regression checks."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import full_size_evidence as evidence, format_encoder as enc, performance_fixtures as fixtures, performance_plan


class FullSizeEvidenceTest(unittest.TestCase):
    def test_torn_and_oversized_journals_cannot_supply_votes(self):
        fixture=fixtures.generate(performance_plan.load())
        manifest=dict(evidence.fmt.inspect(fixture['manifest'],'MANIFEST'),digest=fixture['manifest'][16:48].hex())
        header=enc.encode('JOURNAL',dict(manifestDigest=manifest['digest'],node='node-1',recordKind=24))
        row=fixture['votes']['node-1'][0]
        self.assertEqual([row],evidence.journal(header+row,'ACCEPT',manifest))
        for damaged in (b'',header+row[:-1],header+b'x',header+row+row[:47]):
            with self.subTest(size=len(damaged)),self.assertRaises(ValueError):evidence.journal(damaged,'ACCEPT',manifest)
        huge=bytearray(row);huge[12:16]=(1<<20).to_bytes(4,'big')
        with self.assertRaisesRegex(ValueError,'extent'):evidence.journal(header+huge,'ACCEPT',manifest)

    def test_invalid_baseline_cannot_count_as_successful_negatives(self):
        with patch.object(evidence,'validate',side_effect=ValueError('invalid original')),patch.object(evidence,'facts') as oracle:
            with self.assertRaisesRegex(ValueError,'invalid original'):evidence.negatives('/unused')
            oracle.assert_not_called()

    def test_relocated_evidence_requires_exact_inventory(self):
        from .remote_rich_evidence import EvidenceLocation
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'file').write_text('original')
            index=root/evidence.collection.INDEX
            with self.assertRaises((ValueError,FileNotFoundError)):EvidenceLocation(root,'/original/full-size')
            index.write_bytes(evidence.m.canonical({'file':{'bytes':8,'sha256':evidence.m.sha(b'original')}}))
            EvidenceLocation(root,'/original/full-size')
            (root/'file').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'inventory differs'):EvidenceLocation(root,'/original/full-size')

    def test_symbolic_link_cannot_supply_authority_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'real').write_text('{}');(root/'alias').symlink_to(root/'real')
            with self.assertRaisesRegex(ValueError,'member bound'):evidence.read(root/'alias')


if __name__=='__main__':unittest.main()
