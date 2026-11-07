"""Targeted boundary/original-first guards; real TCP qualification is separate."""
import tempfile
import unittest
from unittest.mock import patch
from . import source_queue_evidence as q


class SourceQueueEvidenceTest(unittest.TestCase):
    def test_byte_refusal_requires_exceeding_limit_not_merely_reaching_it(self):
        usage=dict(queued=q.LIMIT-4096,counts={'CONTROL':25})
        with self.assertRaisesRegex(ValueError,'byte-bound refusal'):q.byte_refusal(usage,4096)
        q.byte_refusal(usage,4097)

    def test_other_capacity_dimensions_cannot_impersonate_aggregate_bytes(self):
        for queued,count,size in ((q.LIMIT,256,4096),(q.LIMIT-4096,25,8*q.t.MIB+1),(q.LIMIT-8192,25,4096)):
            with self.subTest(count=count,size=size),self.assertRaisesRegex(ValueError,'byte-bound refusal'):
                q.byte_refusal(dict(queued=queued,counts={'CONTROL':count}),size)

    def test_original_physical_rejection_precedes_observation_loading(self):
        with tempfile.TemporaryDirectory() as root,patch.object(q.physical,'case',side_effect=ValueError('original rejected')) as physical,patch.object(q.t,'read') as trace:
            with self.assertRaisesRegex(ValueError,'original rejected'):q.load(root)
            self.assertTrue(physical.call_args.kwargs['backup']);trace.assert_not_called()

    def test_invalid_original_cannot_count_as_successful_negative_replay(self):
        with patch.object(q,'replay',side_effect=ValueError('bad original')) as replay,patch.object(q.copy,'deepcopy') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):q.qualify({})
            replay.assert_called_once_with({});mutate.assert_not_called()

    def test_unrelated_rejection_is_not_accepted_as_declared_negative(self):
        with patch.object(q,'replay',side_effect=[{'status':'PASS'},ValueError('unrelated')]):
            with self.assertRaisesRegex(ValueError,'negative reason drift'):
                q.qualify(dict(events=[{}],trace={},frames={}))


if __name__=='__main__':unittest.main()
