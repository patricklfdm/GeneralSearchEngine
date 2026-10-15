"""Exact installation witness and fault declaration boundaries; real bytes run in the process gate."""
import base64
from pathlib import Path
import unittest
from unittest.mock import patch
from . import public_reads_evidence as e, public_read_fault_evidence as f


class ReadFaultEvidenceTest(unittest.TestCase):
    def test_genesis_has_no_terminal_proof(self):
        self.assertEqual((0,None),e.publication_identity(dict(anchors=[],terminalProof=None)))

    def files(self):return [dict(name=n,bytes=base64.b64encode(b'fixture').decode()) for n in
                          ('current.gsr','generation.gsr','snapshot.gsr','accepted.gsr','proofs.gsr')]

    def test_installed_source_rejects_missing_duplicate_or_unexpected_files_before_reading(self):
        for files in (self.files()[:-1],self.files()+self.files()[:1],
                      [dict(name='../outside',bytes='')]+self.files()[1:],
                      [self.files()[0]]+self.files()[:-1],{}):
            with self.subTest(files=files),patch.object(e.recovery,'source') as source:
                with self.assertRaises(ValueError):e.installed_source(files,{}, {},'node-1')
                source.assert_not_called()

    def test_installed_source_binds_node_and_verified_selected_prefix(self):
        snapshot=dict(anchors=[dict(entryDigest='chosen')],terminalProof=base64.b64encode(b'proof').decode(),application='image')
        source=dict(seal=dict(node='node-1',selectedDigest='selected'),snapshot=snapshot)
        with patch.object(e.recovery,'source',return_value=source):
            self.assertEqual((1,e.digest(b'proof')),e.installed_source(self.files(),{}, {'selected':snapshot},'node-1'))
            with self.assertRaisesRegex(ValueError,'voter'):e.installed_source(self.files(),{}, {'selected':snapshot},'node-2')
            with self.assertRaisesRegex(ValueError,'verified selection'):e.installed_source(self.files(),{}, {},'node-1')
            different=dict(snapshot,application='other')
            with self.assertRaisesRegex(ValueError,'same-cut application'):e.installed_source(self.files(),{}, {'selected':different},'node-1')

    def test_crashed_response_cannot_be_reclassified_as_success(self):
        fault=dict(scenario='capture-kill',node='node-1',lostOp='lost')
        with patch.object(e,'read',return_value=fault):
            with self.assertRaisesRegex(ValueError,'lost read response'):
                f.schedule(Path('/unused'),'capture-kill',{'node-1':[]},[dict(opId='lost',outcome='SUCCESS')],[])

    def test_unknown_fault_never_qualifies(self):
        with patch.object(e,'read',return_value=dict(scenario='invented',node='node-1')):
            with self.assertRaisesRegex(ValueError,'unknown public read fault'):
                f.schedule(Path('/unused'),'invented',{'node-1':[]},[],[])


if __name__=='__main__':unittest.main()
