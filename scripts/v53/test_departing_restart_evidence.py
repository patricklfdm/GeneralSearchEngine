from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from . import departing_restart_evidence as e


class DepartingRestartEvidenceTest(unittest.TestCase):
    def interruption_fixture(self,root):
        for i,(mode,n) in enumerate((mode,n) for mode in ('halt','kill') for n in (1,2)):
            path=root/f'interruptions/{mode}-{n}';(path/'store').mkdir(parents=True)
            (path/'store/selected.gsr').write_bytes(b'exact original')
            (path/'worker.stdout').write_text('CUT PUBLICATION_ACK_BEFORE_RETURN\n');(path/'worker.stderr').write_bytes(b'')
            (path/'process.json').write_text(json.dumps(dict(parentPid=1,workerPid=10+i,exit=23 if mode=='halt' else 137,
                                                          mode=mode,attempt=n,liveLockRefused=mode=='kill')))
        return e.c.inventory(root/'interruptions/halt-1/store')

    def test_failed_process_marker_cannot_hide_store_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);original=self.interruption_fixture(root)
            e.interruptions(root,original,1,2)
            (root/'interruptions/kill-1/store/selected.gsr').write_bytes(b'new authority')
            with self.assertRaisesRegex(ValueError,'^departing interrupted original store$'):e.interruptions(root,original,1,2)

    def test_child_identity_and_lock_observation_are_required(self):
        for field,value in (('workerPid',2),('liveLockRefused',False),('liveLockRefused',1),('exit',0)):
            with self.subTest(field=field,value=value),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);original=self.interruption_fixture(root);path=root/'interruptions/kill-1/process.json'
                record=json.loads(path.read_text());record[field]=value;path.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError,'^departing interrupted process outcome$'):e.interruptions(root,original,1,2)

    def test_failed_original_never_counts_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify(Path('/original'))
        copy.assert_not_called()

    def test_symlink_refuses_before_opening_original_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'history').symlink_to('/absent')
            with patch.object(e.native,'validate') as original:
                with self.assertRaisesRegex(ValueError,'^departing restart regular inventory$'):e.validate(root)
            original.assert_not_called()

    def test_success_marker_does_not_replace_native_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'worker.stdout').write_text('v53DepartingRestart=PASS\n')
            with patch.object(e,'layout'),patch.object(e.native,'validate',side_effect=ValueError('original native history failed')):
                with self.assertRaisesRegex(ValueError,'^original native history failed$'):e.validate(root)


if __name__=='__main__':unittest.main()
