import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_history_qualification as q

BOUND=dict(source='a'*40,checkoutSha256='b'*64,java={})


def passed():return dict(status='PASS',sourceBinding=BOUND,submits=1,duplicateReceiptEqual=True,alternateCommandIdRejected=True,
                         qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)


class WholeHistoryQualificationTest(unittest.TestCase):
    def test_controller_coverage_is_not_promoted_to_remote_or_cloud_acceptance(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(q.owned,'source',return_value=BOUND),\
             patch.object(q.owned,'run',side_effect=lambda *a,**kw:passed()) as run:
            value=q.run(Path(directory)/'run')
            self.assertEqual('PASS',value['status']);self.assertEqual(list(q.CASES),[v.kwargs['history'] for v in run.call_args_list])
            self.assertEqual(5,len(value['completed']));self.assertFalse(value['qualifiedMeasurement']);self.assertFalse(value['fullRemoteQualification'])

    def test_failure_keeps_prior_history_and_never_retries_or_starts_next_one(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(q.owned,'source',return_value=BOUND),\
             patch.object(q.owned,'run',side_effect=[passed(),ValueError('original execution failed')]) as run:
            root=Path(directory)/'run'
            with self.assertRaisesRegex(ValueError,'original execution failed'):q.run(root)
            self.assertEqual(2,run.call_count);value=json.loads((root/'receipt.json').read_text())
            self.assertEqual('FAIL',value['status']);self.assertEqual([q.CASES[0]],value['completed'])

    def test_source_drift_rejects_before_new_history_and_duplicate_names_before_any_work(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(q.owned,'source',side_effect=[BOUND,dict(BOUND,checkoutSha256='c'*64)]),\
             patch.object(q.owned,'run') as run:
            with self.assertRaisesRegex(ValueError,'source changed'):q.run(Path(directory)/'run')
            run.assert_not_called()
        with tempfile.TemporaryDirectory() as directory,patch.object(q.owned,'run') as run:
            with self.assertRaisesRegex(ValueError,'history set'):q.run(Path(directory)/'duplicate',[q.CASES[0]]*2)
            run.assert_not_called();self.assertFalse((Path(directory)/'duplicate').exists())


if __name__=='__main__':unittest.main()
