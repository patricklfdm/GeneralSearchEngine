"""Continuation refusal boundaries; these fixtures are not native evidence."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from . import competing_campaign_maintenance as m


def replay(events):
    r=m.Replay.__new__(m.Replay);r.root=Path('/original');r.group={'node-1':{}}
    r.events=[dict(node=node,event=kind) for node,kind in events]
    r.stop=0;r.bindings=[]
    return r


class CompetingCampaignMaintenanceTest(unittest.TestCase):
    def test_first_install_without_retirement_keeps_derived_original_group(self):
        r=replay([('node-1','INSTALL_RESERVED')]);r.group={'node-1':{'grants.gsr':b'original'}}
        original=r.group;before=copy.deepcopy(original)
        with patch.object(m.prefix.Replay,'run',return_value={'original':True}), \
                patch.object(r,'transaction') as tx,patch.object(m.disk,'inventory',return_value=before['node-1']):
            result=r.run();tx.assert_not_called()
        self.assertEqual(before,r.group);self.assertEqual(before,original)
        self.assertEqual([],result['transactions']);self.assertEqual(set(),r.maintenance_traces)
        self.assertEqual(0,r.stop);self.assertEqual(-1,result['throughEvent'])
        self.assertTrue(result['finalGrantSourceProjection']);self.assertFalse(result['fullNetworkQualified'])

    def test_no_retirement_still_compares_final_grants_allocator_and_sources(self):
        for name in ('grants.gsr','allocator.gsr','sources/old/source.gscp','sources.retirement.gsr'):
            r=replay([('node-1','INSTALL_RESERVED')]);r.group={'node-1':{name:b'original'}}
            with self.subTest(name=name),patch.object(m.prefix.Replay,'run',return_value={}), \
                    patch.object(m.disk,'inventory',return_value={name:b'changed'}):
                with self.assertRaisesRegex(ValueError,'final grant/source projection'):r.run()

    def test_no_retirement_cannot_skip_earlier_unmodeled_work_or_missing_install(self):
        for points,reason in ((['SOURCE_RETIREMENT_CREATED','INSTALL_RESERVED'],'original floor absent'),
                              (['NETWORK_SEND','INSTALL_RESERVED'],'original floor absent'),
                              ([], 'first installation boundary')):
            r=replay([('node-1',v) for v in points])
            with self.subTest(points=points),patch.object(m.prefix.Replay,'run',return_value={}):
                with self.assertRaisesRegex(ValueError,reason):r.run()

    def test_original_prefix_failure_prevents_any_continuation(self):
        r=replay([])
        with patch.object(m.prefix.Replay,'run',side_effect=ValueError('prefix')),patch.object(r,'transaction') as tx:
            with self.assertRaisesRegex(ValueError,'^prefix$'):r.run()
            tx.assert_not_called()

    def test_floor_must_finish_before_first_install_and_cannot_overlap(self):
        cases=[(['FLOOR_RESERVED','INSTALL_RESERVED'],'incomplete floor release'),
               (['FLOOR_RESERVED','FLOOR_RESERVED','FLOOR_RELEASE_BEFORE_RETURN','INSTALL_RESERVED'],'overlapping intervals')]
        for points,reason in cases:
            r=replay([('node-1',v) for v in points])
            with self.subTest(reason=reason),patch.object(m.prefix.Replay,'run',return_value={}),patch.object(r,'transaction') as tx:
                with self.assertRaisesRegex(ValueError,reason):r.run()
                tx.assert_not_called()

    def test_unmodeled_work_and_unbound_retirement_after_release_are_refused(self):
        for node,event in [('node-1','PROMISE_WRITTEN'),('node-2','SOURCE_RETIREMENT_CREATED'),('node-1','SOURCE_RETIREMENT_FILE_DELETED')]:
            r=replay([('node-1','FLOOR_RESERVED'),('node-1','FLOOR_RELEASE_BEFORE_RETURN'),(node,event),('node-1','INSTALL_RESERVED')])
            with self.subTest(event=event),patch.object(m.prefix.Replay,'run',return_value={}),patch.object(r,'transaction') as tx:
                with self.assertRaisesRegex(ValueError,'unmodeled owner work'):r.run()
                tx.assert_not_called()

    def test_concurrent_selection_requires_explicit_continuation_not_early_projection(self):
        for node in ('node-1','node-2'):
            r=replay([('node-1','FLOOR_RESERVED'),(node,'SELECTED_FORCED'),('node-1','FLOOR_RELEASE_BEFORE_RETURN'),('node-1','INSTALL_RESERVED')])
            with self.subTest(node=node),patch.object(m.prefix.Replay,'run',return_value={}):
                with self.assertRaisesRegex(ValueError,'concurrent selection needs replay'):r.run()

    def test_success_remains_partial_and_does_not_mutate_preceding_group(self):
        r=replay([('node-1','FLOOR_RESERVED'),('node-1','FLOOR_RELEASE_BEFORE_RETURN'),('node-1','INSTALL_RESERVED')])
        original=r.group;before=copy.deepcopy(original)
        with patch.object(m.prefix.Replay,'run',return_value={}),patch.object(r,'transaction',return_value=({'derived':b'bytes'},dict(retiredSources=1))), \
                patch.object(m.disk,'inventory',return_value={'derived':b'bytes'}):
            result=r.run()
        self.assertEqual(before,original);self.assertEqual({'derived':b'bytes'},r.group['node-1'])
        self.assertEqual('PARTIAL',result['status']);self.assertEqual(1,result['throughEvent'])
        for key in ('transientRetirementBytesQualified','fullNetworkQualified','allCampaignsQualified','installationQualified','publicationQualified','phase3Complete'):
            self.assertFalse(result[key])

    def test_invalid_original_cannot_count_as_rejection(self):
        with patch.object(m,'validate',side_effect=ValueError('original')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            mutate.assert_not_called()

    def test_unrelated_failure_or_accepted_mutation_never_qualifies(self):
        for next_result,reason in ((ValueError('unrelated'),'unrelated competing maintenance negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(m,'validate',side_effect=[{},next_result]),patch.object(m.prefix.collection.h,'inventory',return_value={}), \
                    patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')


if __name__=='__main__':unittest.main()
