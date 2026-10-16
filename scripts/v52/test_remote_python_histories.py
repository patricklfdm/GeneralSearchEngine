import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_python_histories as gate,remote_python_runtime_qualification as runtime
from . import remote_voter_lifecycle_qualification as legacy


class InstalledHistoryTest(unittest.TestCase):
    def test_all_33_frozen_histories_select_the_existing_whole_controller(self):
        plan=gate.h.suite.load();self.assertEqual(33,len(plan['histories']))
        counts={}
        for name,spec in plan['histories'].items():
            chosen=runtime.receiver_type(name);counts[chosen]=counts.get(chosen,0)+1
            self.assertTrue(issubclass(chosen,runtime.Installed))
            self.assertEqual([name],gate.selection([name]))
        self.assertEqual({runtime.Receivers:5,runtime.FormalReceivers:26,runtime.RestartReceivers:1,runtime.PartitionReceivers:1},counts)

    def test_unknown_duplicate_or_partial_names_reject(self):
        for names in ([],[gate.DEFAULTS[0]]*2,['m03'],['candidate-explicit-strong-r4'],['m04-custom-restart']):
            with self.subTest(names=names),self.assertRaises(ValueError):gate.selection(names)

    def test_same_explicit_installation_is_propagated_to_every_receiver_family(self):
        for cls in (runtime.Receivers,runtime.FormalReceivers,runtime.RestartReceivers,runtime.PartitionReceivers):
            own=object.__new__(cls);own.installations={'node-1':dict(root='/private/python',descriptorSha256='a'*64)}
            self.assertEqual(own.installations['node-1'],own.python_context('node-1'))
            changed=own.python_context('node-1');changed['descriptorSha256']='b'*64
            self.assertEqual('a'*64,own.python_context('node-1')['descriptorSha256'])
        self.assertIsNone(legacy.Receivers.python_context(None,'node-1'))

    def test_restart_still_uses_its_original_crash_owner_and_formal_keeps_nonretrying_client(self):
        self.assertIs(runtime.RestartReceivers.start_service,runtime.restart.Receivers.start_service)
        self.assertIs(runtime.FormalReceivers.start_service,runtime.formal.Receivers.start_service)
        self.assertIs(runtime.PartitionReceivers.partition,runtime.partition.Receivers.partition)
        self.assertIs(runtime.RestartReceivers.crash,runtime.restart.Receivers.crash)


class InstalledMatrixTest(unittest.TestCase):
    def result(self,name,source):
        return dict(status='PASS',history=name,sourceBinding=source,fullRemoteQualification=False,paidCloud=False,
            originalReads=11,originalUpdates=3,elapsedSeconds=1,archiveSha256='c'*64,
            negativesPerLocation=24,pythonNegatives=list(range(18)),deliveryNegatives=list(range(14)),
            lifecycleNegatives=list(range(14)),stoppedServices=3)

    def test_failed_history_is_retained_and_never_retried_or_followed_by_next(self):
        source={'source':'a'*40};names=list(gate.DEFAULTS)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            with patch.object(gate.h,'source',return_value=source),patch.object(gate.runtime,'run',side_effect=ValueError('original workload failed')) as invoke:
                with self.assertRaisesRegex(ValueError,'original workload failed'):gate.run(root,names)
            invoke.assert_called_once_with(root/names[0],names[0])
            receipt=json.loads((root/'receipt.json').read_text())
            self.assertEqual('FAIL',receipt['status']);self.assertEqual(names,receipt['selected'])
            self.assertEqual(1,len(receipt['histories']));self.assertEqual('FAIL',receipt['histories'][0]['status'])
            self.assertEqual('original workload failed',receipt['histories'][0]['failure']['message'])
            with patch.object(gate.runtime,'run') as repeated:
                with self.assertRaises(FileExistsError):gate.run(root,names)
                repeated.assert_not_called()

    def test_complete_receipt_cannot_be_substituted_from_another_source(self):
        source={'source':'a'*40};name=gate.DEFAULTS[0]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            with patch.object(gate.h,'source',return_value=source),patch.object(gate.runtime,'run',return_value=self.result(name,{'source':'b'*40})):
                with self.assertRaisesRegex(ValueError,'history source/result'):gate.run(root,[name])
            receipt=json.loads((root/'receipt.json').read_text());self.assertEqual('FAIL',receipt['status'])
            self.assertEqual('FAIL',receipt['histories'][0]['status'])

    def test_source_drift_between_histories_stops_before_another_submission(self):
        source={'source':'a'*40};names=list(gate.DEFAULTS)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            with patch.object(gate.h,'source',side_effect=[source,{'source':'b'*40}]),patch.object(gate.runtime,'run',return_value=self.result(names[0],source)) as invoke:
                with self.assertRaisesRegex(ValueError,'source changed'):gate.run(root,names)
            self.assertEqual(1,invoke.call_count)
            receipt=json.loads((root/'receipt.json').read_text());self.assertEqual('FAIL',receipt['status'])
            self.assertEqual(1,len(receipt['histories']))
            self.assertEqual('FAIL',receipt['histories'][0]['status'])

    def test_subset_pass_records_only_the_requested_whole_history_and_no_cloud_claim(self):
        source={'source':'a'*40};name=gate.DEFAULTS[0]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            with patch.object(gate.h,'source',return_value=source),patch.object(gate.runtime,'run',return_value=self.result(name,source)):
                receipt=gate.run(root,[name])
            self.assertEqual('PASS',receipt['status']);self.assertEqual([name],receipt['selected'])
            self.assertEqual(1,len(receipt['histories']))
            for flag in ('qualifiedMeasurement','fullRemoteQualification','paidCloud','independentHosts'):
                self.assertIs(False,receipt[flag])


if __name__=='__main__':unittest.main()
