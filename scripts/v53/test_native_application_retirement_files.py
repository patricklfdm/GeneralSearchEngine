import copy
import unittest
from unittest.mock import patch
from . import native_application_retirement_files as m
from . import test_covered_staging as fixture


class NativeApplicationRetirementFilesTest(unittest.TestCase):
    def project(self):
        before,marker=fixture.CoveredStagingTest().original();self.before=before;self.marker=marker
        replay=[('replay','REPLAY_RESERVED',m.physical(before)),
                ('replay','REPLAY_APPLICATION_FINISHED',m.physical(dict(before,**{'application-replay':None}))),
                ('replay','REPLAY_BEFORE_RETURN',m.physical(before))]
        with patch.object(m.application.p.data,'pending',return_value=({'ENTRY':b'entry','PAYLOAD':b'payload'},('PROOF','CERTIFICATE'))),\
             patch.object(m.application,'retire',return_value=m.retirement.staging.without_staging(before)) as admitted,\
             patch.object(m.retirement,'authority',return_value=marker) as authority,patch.object(m.replay,'retirement',return_value=replay):
            result=m.transaction(before)
        admitted.assert_called_once_with(before,b'entry',b'payload');authority.assert_called_once_with(before)
        self.assertEqual(fixture.CoveredStagingTest().original()[0],before)
        return result

    def test_certificate_reseal_and_scratch_precede_exact_derived_deletion(self):
        steps=self.project();points=[point for _,point,_ in steps]
        self.assertEqual(['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','NATIVE_RETIREMENT_CERTIFICATE_RETAINED',
            'STAGED_RETIREMENT_AUTHORITY_VALIDATED','REPLAY_RESERVED','REPLAY_APPLICATION_FINISHED','REPLAY_BEFORE_RETURN',
            'SUPERSEDED_END_VALIDATED'],points[:8])
        self.assertTrue(all(kind=='application-retirement' for kind,_,_ in steps))
        self.assertLess(points.index('SUPERSEDED_END_AUTHORITY_FORCED'),points.index('SUPERSEDED_END_BEFORE_DELETE'))
        self.assertEqual(m.physical(m.retirement.staging.without_staging(self.before)),steps[-1][2])
        for _,_,state in steps:
            for key in ('pending.accept','selector.gsr'):self.assertEqual(m.physical(self.before)[key],state[key])
        self.assertFalse(any(point.startswith('APPLY_') for point in points))

    def test_marker_candidate_prefix_rename_and_last_plan_delete_are_distinct(self):
        steps=self.project();states={point:state for _,point,state in steps};key='applied-end/retirement.gsat'
        self.assertEqual(m.physical({'x':b''})['x'],states['SUPERSEDED_END_RETIREMENT_CREATED'][key+'.next'])
        self.assertEqual(m.physical({'x':self.marker[:len(self.marker)//2]})['x'],states['SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN'][key+'.next'])
        self.assertEqual(m.physical({'x':self.marker})['x'],states['SUPERSEDED_END_RETIREMENT_RENAMED'][key])
        self.assertNotIn(key+'.next',states['SUPERSEDED_END_RETIREMENT_RENAMED'])
        removed=[next(iter(state.keys()-steps[i+1][2].keys())) for i,(_,point,state) in enumerate(steps) if point=='SUPERSEDED_END_BEFORE_DELETE']
        self.assertEqual('applied-end/plan.json',removed[-1])
        self.assertNotIn(key,states['SUPERSEDED_END_RETIREMENT_DELETED']);self.assertIn('applied-end',states['SUPERSEDED_END_RETIREMENT_DELETED'])
        self.assertNotIn('applied-end',states['SUPERSEDED_END_DIRECTORY_DELETED'])

    def test_recovery_of_partial_retirement_is_not_silently_relabelled_as_fresh(self):
        before,_=fixture.CoveredStagingTest().original()
        for key in ('applied-end/retirement.gsat','applied-end/retirement.gsat.next','application-replay','application-replay/claim.json'):
            with self.subTest(key=key),patch.object(m.application.p.data,'pending') as pending:
                with self.assertRaisesRegex(ValueError,'fresh original derived end'):m.transaction(dict(before,**{key:b'old'}))
                pending.assert_not_called()
        del before['applied-end']
        with self.assertRaisesRegex(ValueError,'fresh original derived end'):m.transaction(before)

    def test_original_authority_and_control_replay_cannot_be_bypassed(self):
        before,_=fixture.CoveredStagingTest().original()
        with patch.object(m.application.p.data,'pending',return_value=({},('PROOF',))):
            with self.assertRaisesRegex(ValueError,'original certified phase'):m.transaction(before)
        with patch.object(m.application.p.data,'pending',return_value=({'ENTRY':b'e','PAYLOAD':b'p'},('PROOF','CERTIFICATE'))),\
             patch.object(m.application,'retire',side_effect=ValueError('unadmitted original')),patch.object(m.replay,'retirement') as replay:
            with self.assertRaisesRegex(ValueError,'unadmitted original'):m.transaction(before)
            replay.assert_not_called()


if __name__=='__main__':unittest.main()
