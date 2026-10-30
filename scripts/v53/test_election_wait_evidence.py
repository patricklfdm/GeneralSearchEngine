from pathlib import Path
import copy
import tempfile
import unittest
from unittest.mock import patch
from . import election_wait_evidence as e


class ElectionWaitEvidenceTest(unittest.TestCase):
    def test_only_complete_initialization_and_reopen_lifecycle_is_allowed(self):
        nodes=['node-1','node-2','node-3']
        calls=[dict(node=node,operation='initialize-retention',events=list(e.INITIAL)) for node in nodes]
        events=[dict(node=node,event=event) for node in nodes for event in e.REOPEN]
        e.lifecycle(calls,events,nodes)
        for name in ('missing','duplicate','reordered','grant','foreign-node'):
            altered=copy.deepcopy(events)
            if name=='missing':altered.pop()
            elif name=='duplicate':altered.append(altered[-1])
            elif name=='reordered':altered[0],altered[1]=altered[1],altered[0]
            elif name=='grant':altered.append(dict(node='node-1',event='GRANT_FORCED'))
            else:altered[-1]['node']='node-4'
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^closed election wait exact reopen only$'):
                e.lifecycle(calls,altered,nodes)
        altered=copy.deepcopy(calls);altered[0]['events'].remove('RETENTION_FORCED')
        with self.assertRaisesRegex(ValueError,'^closed election wait initialization$'):e.lifecycle(altered,events,nodes)

    def test_invalid_original_cannot_become_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(e.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):e.qualify('unused')
            copy.assert_not_called()

    def test_linked_inventory_is_rejected_before_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'file').write_bytes(b'original');(path/'linked').symlink_to('file')
            with patch.object(e.b,'original') as original:
                with self.assertRaisesRegex(ValueError,'^discovered selection regular inventory$'):e.validate(path)
                original.assert_not_called()


if __name__=='__main__':unittest.main()
