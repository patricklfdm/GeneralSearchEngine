"""Composition guards; synthetic journals do not establish native execution."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_resources as m
from . import test_native_carried_resource_evidence as fixtures


class NativeCarriedApplicationResourcesTest(unittest.TestCase):
    def test_application_prerequisite_must_pass_before_accounting_or_mutations(self):
        with patch.object(m.collection,'inventory',return_value={}), \
             patch.object(m.application,'validate',side_effect=ValueError('invalid application original')) as prior, \
             patch.object(m.resources,'replay') as replay,patch.object(m.resources,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'invalid application original'):m.qualify('/original')
            prior.assert_called_once_with(Path('/original/history'))
            replay.assert_not_called();negative.assert_not_called()

    def test_complete_application_chain_is_preserved_with_distinct_lifetime_accounting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);fixture=fixtures.NativeCarriedResourceTest();fixture.fixture(root,1)
            _,_,inventory,decode=fixture.fixture(root,2);original=dict(application='synthetic prerequisite')
            before=m.collection.inventory(root)
            with patch.object(m.application,'validate',return_value=original) as prior, \
                 patch.object(m.resources.c,'inventory',side_effect=inventory), \
                 patch.object(m.resources.f,'decode',side_effect=decode):
                result=m.qualify(root)
            prior.assert_called_once_with(root/'history')
            self.assertEqual(original,result['original']['original'])
            resources=result['original']['resources']
            self.assertEqual((8,4,4),(resources['ownerLifetimes'],resources['crashedOwnerPrefixes'],resources['normalOwnerCloses']))
            self.assertEqual(['CUT_PREFIX','CLOSED'],[v['terminal'] for v in resources['lifetimes']])
            self.assertFalse(resources['physicalStorageQualified']);self.assertFalse(resources['wholeRuntimeResourcesQualified'])
            self.assertFalse(result['original']['phase3Complete']);self.assertFalse(resources['cohortAdmitted'])
            self.assertEqual([(k,v) for k,v in m.NEGATIVES.items()],[(v['case'],v['reason']) for v in result['negatives']])
            self.assertEqual(23,len(result['negatives']));self.assertTrue(result['originalStorageUnchanged'])
            self.assertEqual(before,m.collection.inventory(root))

    def test_history_or_resource_changes_during_validation_reject(self):
        with patch.object(m.collection,'inventory',side_effect=[{},dict(changed=True)]), \
             patch.object(m.application,'validate'),patch.object(m.resources,'replay'):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_a_later_mutation_failure_cannot_be_reported_as_qualified(self):
        with patch.object(m,'validate',return_value={}),patch.object(m.collection,'inventory',return_value={}), \
             patch.object(m.resources,'negative',side_effect=[dict(case='first'),ValueError('wrong negative')]):
            with self.assertRaisesRegex(ValueError,'wrong negative'):m.qualify('/original')

    def test_original_change_during_negatives_is_retained_as_failure(self):
        with patch.object(m,'validate',return_value={}), \
             patch.object(m.collection,'inventory',side_effect=[{},dict(history=True),dict(changed=True)]), \
             patch.object(m.resources,'negative',return_value=dict(status='REJECTED')):
            with self.assertRaisesRegex(ValueError,'qualification changed original'):m.qualify('/original')

    def test_previous_accept_proof_reader_keeps_its_own_prerequisite(self):
        with patch.object(m.resources.collection,'inventory',return_value={}), \
             patch.object(m.resources.t,'validate',side_effect=ValueError('wrong original cut')), \
             patch.object(m.application,'validate') as application,patch.object(m.resources,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'wrong original cut'):m.resources.validate('/original')
            application.assert_not_called();replay.assert_not_called()


if __name__=='__main__':unittest.main()
