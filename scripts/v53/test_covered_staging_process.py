import unittest
from unittest.mock import patch
from . import covered_staging_process_evidence as q


class CoveredStagingProcessTest(unittest.TestCase):
    def trace(self):
        cleanup=['STAGED_RETIREMENT_AUTHORITY_VALIDATED','SUPERSEDED_END_VALIDATED']
        events=[cleanup[0],*q.REPLAY_REQUIRED,cleanup[1]]
        return cleanup,[dict(event=v) for v in events]

    def test_force_order_and_explicit_process_scope(self):
        cleanup,rows=self.trace();rows.append(dict(status='PASS',peakImages=6,runtimeEnabled=False))
        self.assertEqual(6,q.force_trace(rows,cleanup,cleanup,'none',None,True))

    def test_missing_replay_force_is_rejected(self):
        cleanup,rows=self.trace();rows.remove(dict(event='REPLAY_CLAIM_FORCED'))
        with self.assertRaisesRegex(ValueError,'replay force order'):q.force_trace(rows,cleanup,cleanup,'halt',cleanup[-1],False)

    def test_replay_after_cleanup_is_rejected(self):
        cleanup,rows=self.trace();rows.insert(1,rows.pop())
        with self.assertRaisesRegex(ValueError,'replay cleanup order'):q.force_trace(rows,cleanup,cleanup,'halt',cleanup[-1],False)

    def test_unknown_replay_events_are_rejected(self):
        cleanup,rows=self.trace();rows.insert(1,dict(event='REPLAY_INVENTED_ACK'))
        with self.assertRaisesRegex(ValueError,'unknown replay event'):q.force_trace(rows,cleanup,cleanup,'halt',cleanup[-1],False)

    def test_kill_requires_exact_boundary_handshake(self):
        cleanup,rows=self.trace()
        with self.assertRaisesRegex(ValueError,'kill handshake'):q.force_trace(rows,cleanup,cleanup,'kill',cleanup[-1],False)
        rows.append(dict(event='AWAITING_KILL',cut=cleanup[-1]));q.force_trace(rows,cleanup,cleanup,'kill',cleanup[-1],False)

    def test_old_application_ack_cannot_be_ignored(self):
        cleanup,rows=self.trace();rows.append(dict(event='APPLY_BEFORE_RETURN'))
        with self.assertRaisesRegex(ValueError,'old ACK'):q.force_trace(rows,cleanup,cleanup,'halt',cleanup[-1],False)

    def test_boolean_capacity_and_enabled_runtime_are_not_accepted(self):
        for capacity,runtime in ((True,False),(8,False),(4,True)):
            cleanup,rows=self.trace();rows.append(dict(status='PASS',peakImages=capacity,runtimeEnabled=runtime))
            with self.assertRaisesRegex(ValueError,'result scope'):q.force_trace(rows,cleanup,cleanup,'none',None,True)

    def test_original_validation_precedes_negative_replays(self):
        with patch.object(q,'validate',side_effect=ValueError('invalid original')),patch.object(q.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'invalid original'):q.qualify('raw')
            copytree.assert_not_called()

    def test_fixed_process_and_negative_inventories(self):
        self.assertEqual(16,len(q.CUTS));self.assertEqual(16,len(set(q.CUTS)));self.assertEqual(19,len(q.VARIANTS))


if __name__=='__main__':unittest.main()
