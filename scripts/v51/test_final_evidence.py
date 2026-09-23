"""Read-only archives cannot become startup authority; refusals retain outcomes."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from . import storage_fixture as fixture, storage_inspector as storage, public_final_evidence as e


class FinalEvidenceTest(unittest.TestCase):
    def archive(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root=Path(temp.name); fixture.create(root)
        original=root/'node-1'; before=storage.inventory(original); retired=root/'lost-node-1'; original.rename(retired)
        return original,retired,before

    def test_archive_keeps_sealed_original_path_and_remains_read_only(self):
        original,retired,before=self.archive()
        self.assertEqual('PASS',storage.inspect_archive(retired,original,before)['status'])
        self.assertEqual(before,storage.inventory(retired))
        with self.assertRaisesRegex(ValueError,'seal path'): storage.inspect(retired)

    def test_live_original_and_wrong_original_path_cannot_be_retired(self):
        original,retired,before=self.archive()
        with self.assertRaisesRegex(ValueError,'seal path'): storage.inspect_archive(retired,original.with_name('other'),before)
        shutil.copytree(retired,original)
        with self.assertRaisesRegex(ValueError,'still present'): storage.inspect_archive(retired,original,before)

    def test_archive_inventory_change_or_corrupt_record_stays_rejected(self):
        original,retired,before=self.archive(); path=retired/'manifest.gsr'
        path.write_bytes(path.read_bytes()[:-1]+b'x')
        with self.assertRaisesRegex(ValueError,'inventory'): storage.inspect_archive(retired,original,before)
        with self.assertRaises(ValueError): storage.inspect_archive(retired,original,storage.inventory(retired))

    def test_symlink_is_never_a_missing_disk(self):
        original,retired,before=self.archive(); original.symlink_to(original.with_name('absent'))
        with self.assertRaisesRegex(ValueError,'still present'): storage.inspect_archive(retired,original,before)

    def refusals(self):
        return {str(i):dict(node='node-1',kind=kind,outcome=outcome,reasonCode='NOT_LEADER',startNanos=20,endNanos=30)
                for i,(kind,outcome) in enumerate([('read','NOT_APPLICABLE'),('addAll','NOT_SUBMITTED')])}

    def test_distinct_public_refusals_after_loss(self): e.refused(self.refusals(),['0','1'],'node-1',10)

    def test_missing_duplicate_success_uncertainty_or_early_refusal_rejected(self):
        for ids in (['0'],['0','0']):
            with self.assertRaises(ValueError): e.refused(self.refusals(),ids,'node-1',10)
        for key,value in [('outcome','SUCCESS'),('outcome','INDETERMINATE'),('kind','read'),('node','node-2'),('startNanos',9),('endNanos',19),('reasonCode','CLOSED')]:
            rows=copy.deepcopy(self.refusals());rows['1'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): e.refused(rows,['0','1'],'node-1',10)


if __name__=='__main__': unittest.main()
