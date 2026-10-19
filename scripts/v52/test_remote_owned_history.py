from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remote_owned_history as h, remote_slots as slots, remote_command as commands
from .test_remote_slots import owner


class OwnedHistoryTest(unittest.TestCase):
    def test_local_backend_rejects_source_mode_or_coordinator_drift(self):
        bound=owner();expected={k:bound['selection']['binding'][k] for k in ('source','checkoutSha256')}
        self.assertEqual(bound['selection']['member']['profiles'][bound['history']],h.validate_local_owner(bound,expected))
        for changed in (dict(expected,source='f'*40),dict(expected,checkoutSha256='f'*64)):
            with self.assertRaisesRegex(ValueError,'source drift'):h.validate_local_owner(bound,changed)
        with self.assertRaisesRegex(ValueError,'coordinator'):h.validate_local_owner(dict(bound,node='node-2'),expected)
        bound=owner('canonical-1');expected={k:bound['selection']['binding'][k] for k in ('source','checkoutSha256')}
        self.assertEqual('M01',h.validate_local_owner(bound,expected)['family'])

    def test_source_failure_is_retained_and_stable_slot_cannot_repeat_work(self):
        with tempfile.TemporaryDirectory() as directory:
            bound=owner();expected={k:bound['selection']['binding'][k] for k in ('source','checkoutSha256')}
            store=commands.CommandStore(Path(directory)/'guest',bound,create=True);request=slots.request(bound,'execute-history')
            with patch.object(h,'source',side_effect=[expected,dict(expected,checkoutSha256='f'*64)]),\
                 patch.object(h.bridge,'smoke',return_value={'status':'PASS'}) as original:
                answer=h.execute_local(store.root,request)
            self.assertEqual('FAILED',answer['state']);self.assertIn('source changed',answer['error']['message']);original.assert_called_once()
            with patch.object(h,'source',return_value=expected),patch.object(h.bridge,'smoke',side_effect=AssertionError('replayed')):
                self.assertEqual(answer,h.execute_local(store.root,request))

    def test_failure_after_submission_intent_never_claims_no_engine_execution(self):
        expected=dict(source='a'*40,checkoutSha256='b'*64,java={})
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'run'
            with patch.object(h,'source',return_value=expected),patch.object(h.subprocess,'Popen',side_effect=OSError('launch uncertainty')):
                with self.assertRaisesRegex(OSError,'launch uncertainty'):h.run(root)
            receipt=commands.read(root/'receipt.json')
            self.assertEqual('FAIL',receipt['status']);self.assertTrue(receipt['executionRequested'])
            self.assertIsNone(receipt['engineWorkloadExecuted']);self.assertEqual([],receipt['processCleanup'])

    def test_rejection_before_claim_does_not_invoke_local_backend(self):
        with tempfile.TemporaryDirectory() as directory:
            bound=owner();store=commands.CommandStore(Path(directory)/'guest',bound,create=True)
            request=slots.request(bound,'execute-history')
            bad=deepcopy(request);bad['payload']={'output':'alternate'}
            for value in (bad,dict(request,commandId='../outside'),slots.request(bound,'collect')):
                with patch.object(h.bridge,'smoke',side_effect=AssertionError('entered')),self.assertRaises(ValueError):
                    h.execute_local(store.root,value)
            self.assertEqual([],list((store.root/'commands').iterdir()))


if __name__=='__main__':unittest.main()
