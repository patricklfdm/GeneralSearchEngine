"""Synthetic binding/orchestration cases; no maximum native execution credit."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import maximum_native_evidence as m
from . import test_backup_resource_run as fixture


def resources():
    value=fixture.replay();value.update(schema=m.complete.DEFAULT_STAGING_SCHEMA,profile=m.complete.DEFAULT_STAGING_PROFILE)
    value=m.resources.receipt(value,m.resources.DEFAULT)
    value['original']=m.resources.receipt(value['original'],m.resources.DEFAULT)
    value['original']['joinedHandoffResources']=m.resources.receipt(value['original']['joinedHandoffResources'],m.resources.DEFAULT)
    value['negatives']['staging-profile']=[dict(m.complete.STAGING_NEGATIVE)]
    return value


class MaximumNativeEvidenceTest(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def test_only_explicit_four_and_five_member_topologies_can_select_a_seed(self):
        for size in (None,True,3,6,'4'):
            with self.subTest(size=size),patch.object(m.maximum,'source') as source,self.assertRaisesRegex(ValueError,'explicit topology'):
                m.seed(self.root,size=size)
            source.assert_not_called()

    def seed_files(self,image=b'synthetic image'):
        directory=self.root/m.DIRECTORY;directory.mkdir();(directory/'source-backup').mkdir()
        for name in ('calibration.image','source.image'):(directory/name).write_bytes(image)
        (self.root/'original-application.image').write_bytes(b'synthetic other')
        (self.root/'original-plan.gsbp').write_bytes(b'synthetic plan')
        value=m.binding(m.maximum.e.digest(image),1,'00000000-0000-0000-0000-000000000001',m.maximum.e.digest(b'synthetic other'))
        (directory/'binding.json').write_bytes(m.maximum.e.f.canonical(value))
        return image,value

    def test_binding_requires_exact_large_source_and_default_policy(self):
        value=m.binding('a'*64,42,'00000000-0000-0000-0000-000000000001','b'*64);m.check_binding(value)
        for key,changed in [('bootstrapSource','EMPTY'),('wireLayout','JSON'),('resourceProfile',m.resources.SMALL),
                            ('stagingLimit',512*1024**2),('applicationBytes',12),('applicationSequence',0),
                            ('history','changed'),('status','PASS'),('phase3Complete',0),('extra',True),('extra',0),
                            ('bootstrapHistory',m.maximum.HISTORY),('bootstrapHistory','00000000-0000-0000-0000-000000000000'),
                            ('bootstrapHistory',True),('bootstrapApplicationSha256','a'*64),('schema','gse-v53-maximum-native-seed-v1')]:
            bad=dict(value,**{key:changed})
            with self.subTest(key=key,changed=changed),self.assertRaises(ValueError):m.check_binding(bad)
        for key in value:
            bad=dict(value);bad.pop(key)
            with self.subTest(missing=key),self.assertRaises(ValueError):m.check_binding(bad)

    def test_native_image_binds_new_history_and_same_content_to_original_plan(self):
        image,value=self.seed_files()
        plan=dict(root=dict(historyId=value['bootstrapHistory'],baseSequence=41),plan=dict(descriptor=dict(sourceInventory=[])))
        with patch.object(m.maximum,'NATIVE_MAXIMUM',len(image)),patch.object(m.maximum,'source',return_value=(image,1)), \
             patch.object(m.plans,'decode',return_value=plan) as decode,patch.object(m.maximum,'application') as content:
            value['applicationBytes']=len(image)
            (self.root/m.DIRECTORY/'binding.json').write_bytes(m.maximum.e.f.canonical(value))
            self.assertEqual(value,m.seed(self.root))
            content.assert_called_once_with(b'synthetic other',value['bootstrapHistory'],41,m.maximum.documents(1))
            decode.assert_called_once_with(b'synthetic plan',b'synthetic other',size=5,source=m.source_policy.BACKUP,details=True)
            plan['plan']['descriptor']['sourceInventory']=[dict(invented=True)]
            with self.assertRaisesRegex(ValueError,'original source inventory'):m.seed(self.root)
            plan['plan']['descriptor']['sourceInventory']=[]
            (self.root/'original-application.image').write_bytes(image)
            with self.assertRaisesRegex(ValueError,'new bootstrap history'):m.seed(self.root)

    def test_new_history_alone_does_not_allow_changed_documents_or_another_plan(self):
        image,value=self.seed_files();value['applicationBytes']=len(image)
        (self.root/m.DIRECTORY/'binding.json').write_bytes(m.maximum.e.f.canonical(value))
        plan=dict(root=dict(historyId=value['bootstrapHistory'],baseSequence=41),plan=dict(descriptor=dict(sourceInventory=[])))
        with patch.object(m.maximum,'NATIVE_MAXIMUM',len(image)),patch.object(m.maximum,'source',return_value=(image,1)), \
             patch.object(m.plans,'decode',return_value=plan),patch.object(m.maximum,'application',side_effect=ValueError('changed documents')):
            with self.assertRaisesRegex(ValueError,'^changed documents$'):m.seed(self.root)
            plan['root']['baseSequence']=42
            with self.assertRaisesRegex(ValueError,'bootstrap application sequence'):m.seed(self.root)
            plan['root']['baseSequence']=41
            plan['root']['historyId']='00000000-0000-0000-0000-000000000002'
            with self.assertRaisesRegex(ValueError,'exact seed binding'):m.seed(self.root)

    def test_small_source_or_unexpected_seed_members_cannot_start_complete_replay(self):
        self.seed_files()
        with patch.object(m.maximum,'source',return_value=(b'synthetic image',1)),patch.object(m.complete,'qualify_default_staging_backup') as run:
            with self.assertRaisesRegex(ValueError,'exact seed binding'):m.qualify(self.root)
            run.assert_not_called()
        (self.root/m.DIRECTORY/'extra').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'seed layout'):m.seed(self.root)

    def test_original_first_all150_cases_and_same_input_are_required(self):
        binding=m.binding('a'*64,42,'00000000-0000-0000-0000-000000000001','b'*64);gate=resources()
        with patch.object(m,'seed',return_value=binding) as seed,patch.object(m.source_policy,'inventory',return_value={'same':'original'}) as inventory, \
             patch.object(m.complete,'qualify_default_staging_backup',return_value=gate) as run:
            result=m.qualify(self.root);m.check_result(result)
            run.assert_called_once_with(self.root,None)
            self.assertEqual(2,seed.call_count);self.assertEqual(2,inventory.call_count)
            self.assertEqual(150,sum(map(len,result['resources']['negatives'].values())))
            self.assertFalse(result['combinedResourcesQualified']);self.assertFalse(result['phase3Complete'])
        for key in ('wholeReaderMemoryQualified','finalSourceCohortQualified','combinedResourcesQualified','phase3Complete'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'qualification scope'):m.check_result(dict(result,**{key:True}))
        for family in gate['negatives']:
            bad=copy.deepcopy(result);bad['resources']['negatives'][family].pop()
            with self.subTest(family=family),self.assertRaises(ValueError):m.check_result(bad)

    def test_seed_failure_precedes_gate_and_late_changes_reject(self):
        binding=m.binding('a'*64,42,'00000000-0000-0000-0000-000000000001','b'*64)
        with patch.object(m.source_policy,'inventory',return_value={}),patch.object(m,'seed',side_effect=ValueError('bad source')), \
             patch.object(m.complete,'qualify_default_staging_backup') as run:
            with self.assertRaisesRegex(ValueError,'bad source'):m.qualify(self.root)
            run.assert_not_called()
        with patch.object(m.source_policy,'inventory',side_effect=[{'before':1},{'after':2}]), \
             patch.object(m,'seed',return_value=binding),patch.object(m.complete,'qualify_default_staging_backup',return_value=resources()):
            with self.assertRaisesRegex(ValueError,'original changed'):m.qualify(self.root)
        with patch.object(m.source_policy,'inventory',return_value={}),patch.object(m,'seed',side_effect=[binding,dict(binding,extra=43)]), \
             patch.object(m.complete,'qualify_default_staging_backup',return_value=resources()):
            with self.assertRaisesRegex(ValueError,'original changed'):m.qualify(self.root)


if __name__=='__main__':unittest.main()
