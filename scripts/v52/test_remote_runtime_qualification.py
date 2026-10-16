import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_runtime_qualification as r


class RemoteRuntimeQualificationTest(unittest.TestCase):
    def test_source_change_stops_before_another_original_history(self):
        same=dict(source='a'*40,checkoutSha256='b'*64,java={});changed=dict(same,checkoutSha256='c'*64)
        for snapshots,retained in (([same,same,changed],0),([same,same,same,changed],1)):
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory)/'run';calls=[]
                def smoke(root,mode,expected):calls.append(mode);return dict(status='PASS',mode=mode)
                with patch.object(r.runtime.build,'binding',side_effect=snapshots),\
                     patch.object(r.runtime.subprocess,'check_output',return_value='a'*40),patch.object(r,'smoke',side_effect=smoke):
                    with self.assertRaisesRegex(ValueError,'source changed'):r.run(out)
                self.assertEqual([r.model.MODES[0]],calls)
                value=json.loads((out/'receipt.json').read_bytes());self.assertEqual('FAIL',value['status'])
                self.assertEqual(retained,len(value['cases']));self.assertFalse(value['qualifiedMeasurement'])

    def test_single_mode_is_partial_and_never_full_remote_qualification(self):
        binding=dict(source='a'*40,checkoutSha256='b'*64,java={})
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(r.runtime.build,'binding',return_value=binding),\
                 patch.object(r.runtime.subprocess,'check_output',return_value='a'*40),\
                 patch.object(r,'smoke',return_value=dict(status='PASS')) as smoke:
                result=r.run(Path(directory)/'run',r.model.MODES[-1])
            smoke.assert_called_once();self.assertEqual('PARTIAL',result['status'])
            self.assertFalse(result['fullRemoteQualification']);self.assertFalse(result['paidCloud'])

    def test_interruption_is_retained_without_retry(self):
        binding=dict(source='a'*40,checkoutSha256='b'*64,java={})
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'run'
            with patch.object(r.runtime.build,'binding',return_value=binding),\
                 patch.object(r.runtime.subprocess,'check_output',return_value='a'*40),\
                 patch.object(r,'smoke',side_effect=KeyboardInterrupt) as smoke:
                with self.assertRaises(KeyboardInterrupt):r.run(out)
            smoke.assert_called_once();result=json.loads((out/'receipt.json').read_bytes())
            self.assertEqual('KeyboardInterrupt',result['failure']['type']);self.assertEqual('FAIL',result['status'])


if __name__=='__main__':unittest.main()
