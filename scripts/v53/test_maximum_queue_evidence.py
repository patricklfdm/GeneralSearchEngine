"""Explicit maximum-source and resource guards, without maximum execution claims."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from . import queue_completion_evidence as q
from . import test_queue_completion_evidence as fixture
from . import test_maximum_native_run as native

OPTIONS=dict(wire_layout=q.history.wire_archive.SEGMENTED,maximum_image=True)


class MaximumQueueEvidenceTest(unittest.TestCase):
    def value(self):
        value=fixture.QueueCompletionEvidenceTest().value();seed=native.maximum_result()['seed']
        value['receipt'].update(schema='gse-v53-maximum-queue-completion-v1',bootstrapSource=q.maximum.source_policy.BACKUP,
            wireLayout=q.maximum.source_policy.SEGMENTED,resourceProfile=q.maximum.resources.DEFAULT,
            stagingLimit=16*1024**3,maximumSeed=copy.deepcopy(seed))
        value.update(maximumSeed=seed,image=b'not a maximum image');return value

    def test_maximum_is_explicit_segmented_and_cannot_reinterpret_a_rehearsal(self):
        for kwargs in (dict(maximum_image=True),dict(maximum_image=1),dict(OPTIONS,rehearsal=True)):
            with self.subTest(kwargs=kwargs),patch.object(q.history,'history') as physical,self.assertRaises(ValueError):q.load('/unused',**kwargs)
            physical.assert_not_called()
        with self.assertRaisesRegex(ValueError,'queue completion scope'):q.replay(fixture.QueueCompletionEvidenceTest().value(),**OPTIONS)

    def test_seed_failure_precedes_continuous_physical_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'continuous-result.json').write_bytes(q.queue.f.canonical(dict(status='PASS',kind='REMOVE',activations=3,publicReady=False,automaticLifecycle=False)))
            with patch.object(q.maximum,'seed',side_effect=ValueError('wrong maximum seed')) as seed,patch.object(q.history,'history') as physical:
                with self.assertRaisesRegex(ValueError,'^wrong maximum seed$'):q.load(root,**OPTIONS)
                seed.assert_called_once_with(root,size=4);physical.assert_not_called()
            with patch.object(q.maximum,'seed',return_value={}),patch.object(q.history,'history',side_effect=ValueError('stop at physical')) as physical:
                with self.assertRaisesRegex(ValueError,'^stop at physical$'):q.load(root,**OPTIONS)
                self.assertEqual(128*1024**3,physical.call_args.kwargs['maximum_bytes'])
                self.assertIn(q.maximum.DIRECTORY,physical.call_args.kwargs['additional'])

    def test_changed_seed_and_nonmaximum_image_are_rejected_before_queue_accounting(self):
        value=self.value()
        with patch.object(q.t,'replay') as accounting:
            with self.assertRaisesRegex(ValueError,'^queue completion original maximum image$'):q.replay(value,**OPTIONS)
            accounting.assert_not_called()
            value['receipt']['maximumSeed']['bootstrapHistory']=q.maximum.maximum.HISTORY
            with self.assertRaisesRegex(ValueError,'^queue completion original maximum seed$'):q.replay(value,**OPTIONS)
            accounting.assert_not_called()

    def test_default_pool_cannot_be_inferred_from_a_maximum_label(self):
        value=self.value();value['receipt']['stagingLimit']=512*1024**2
        with self.assertRaisesRegex(ValueError,'^native resource receipt profile$'):q.replay(value,**OPTIONS)
        value=self.value();value['image']=b'x';value['maximumSeed']['bootstrapApplicationSha256']=q.queue.sha(b'x')
        value['maximumSeed']['applicationBytes']=1
        value['receipt']['maximumSeed']=copy.deepcopy(value['maximumSeed'])
        with patch.object(q.maximum.maximum,'NATIVE_MAXIMUM',1):
            with self.assertRaisesRegex(ValueError,'^queue completion default resource limits$'):q.replay(value,**OPTIONS)

    def test_all_negatives_require_the_passing_maximum_original_first(self):
        self.assertEqual(10,len(q.negative_cases()));self.assertEqual(12,len(q.negative_cases(q.history.wire_archive.SEGMENTED)))
        self.assertEqual(15,len(q.negative_cases(**OPTIONS)))
        with patch.object(q,'replay',side_effect=ValueError('bad original')) as replay,patch.object(q.copy,'deepcopy') as mutate:
            with self.assertRaisesRegex(ValueError,'^bad original$'):q.qualify({},**OPTIONS)
            replay.assert_called_once_with({},**OPTIONS);mutate.assert_not_called()


if __name__=='__main__':unittest.main()
