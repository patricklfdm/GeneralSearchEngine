import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import generation_install_evidence as e
from . import generation_install_negatives as n
from . import generation_install_qualification as q


class GenerationInstallEvidenceTest(unittest.TestCase):
    def test_complete_crash_inventory(self):
        rows=e.cases();self.assertEqual(174,len(rows));self.assertEqual(174,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for tail in (False,True):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['tail'],r['mode'])==(size,tail,mode)})

    def test_actual_sorted_file_order_controls_crash_prefix(self):
        events,writes=e.transaction({'source.gscp':b'','generation.gsr':b'','00.image':b'','basis.gsr':b''})
        self.assertLess(events.index('INSTALL_IMAGE_WRITTEN'),events.index('INSTALL_MEMBER_WRITTEN'))
        self.assertEqual(4,writes['00.image']);self.assertEqual(6,writes['basis.gsr'])
        self.assertLess(events.index('INSTALL_GENERATION_FORCED'),events.index('INSTALL_SELECTOR_WRITTEN'))
        self.assertLess(events.index('INSTALL_SELECTOR_FORCED'),events.index('INSTALL_SELECTOR_RENAMED'))

    def test_probe_does_not_share_pid_keyed_monitoring_files(self):
        command=q.Probe(Path('/tmp/unused-install'),dict(size=3,tail=False),'fixture').command('init')
        self.assertEqual(['java','-XX:-UsePerfData','-cp','fixture'],command[:4])

    def test_receipt_does_not_imply_network_ack(self):
        files={'generation.gsr':b'authority'};manifest=dict(cut={},selection='ab'*32,ownedTail=None)
        row=dict(manifest=e.c.sha(files['generation.gsr']),**manifest,localInstallation=True,networkAck=False)
        e.result([row],files,manifest)
        for field in ('networkAck','localInstallation'):
            changed=dict(row);changed[field]=not changed[field]
            with self.assertRaisesRegex(ValueError,'install returned binding'):e.result([changed],files,manifest)

    def test_invalid_original_never_counts_as_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_failure_never_counts_as_expected_rejection(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated install negative'):n.run('absent')

    def test_existing_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
