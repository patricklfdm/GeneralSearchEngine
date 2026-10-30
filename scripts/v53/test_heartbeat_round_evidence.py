from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import heartbeat_round_evidence as h


class HeartbeatRoundEvidenceTest(unittest.TestCase):
    def test_heartbeat_does_not_relax_original_rejection_policy(self):
        row=dict(node='node-3',kind='FUTURE_RETENTION_INTENT',request='a'*64,
            failure='java.lang.IllegalArgumentException: retention intent installed selection required')
        with self.assertRaisesRegex(ValueError,'^native dispatch bounded unselected rejection$'):h.n.unselected_rejections([row])
        with self.assertRaisesRegex(ValueError,'^heartbeat round bounded unselected rejection$'):h.unselected_rejections([row],False)
        h.unselected_rejections([row]*3,True)

    def test_unknown_owner_kind_error_and_reset_retry_groups_are_rejected(self):
        row=dict(node='node-3',kind='FUTURE_RETENTION_INTENT',request='a'*64,
            failure='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required')
        variants=[[dict(row,**change)] for change in (
            dict(node='node-2'),dict(kind='ACCEPT'),dict(failure='hidden'),dict(request='unknown'))]
        variants += [[row]*4,[row,dict(row,request='b'*64),dict(row,request='c'*64)],
            [row,dict(row,request='b'*64),row]]
        for rows in variants:
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,'^heartbeat round bounded unselected rejection$'):
                h.unselected_rejections(rows,True)

    def test_bad_original_cannot_supply_negative_qualification(self):
        with patch.object(h,'validate',side_effect=ValueError('invalid original')),patch.object(h.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):h.qualify('unused')
            copied.assert_not_called()

    def test_symlink_is_rejected_before_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'real').write_bytes(b'original');(root/'link').symlink_to('real')
            with patch.object(h.shutil,'copytree') as copied:
                with self.assertRaisesRegex(ValueError,'^round original regular inventory$'):h.validate(root)
                copied.assert_not_called()


if __name__=='__main__':unittest.main()
