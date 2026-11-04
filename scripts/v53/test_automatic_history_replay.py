"""Synthetic composition guards; these fixtures are never native qualification."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_history_replay as r


def original(case,branch='pregrant'):
    if case=='competition':
        publication=dict(physicalPublicationQualified=True,clientCompletionQualified=True,scratchTransfersDrained=True,slots=2,clientMutations=1,
                         precondition=dict(precondition={}))
        activation=dict(fullNetworkQualified=True,originalActivationNetworkQualified=True,pregrantLosses=[{}] if branch=='pregrant' else [],precondition=publication)
        exports=dict(status='PARTIAL',observedTemporalExportAuthorityQualified=True,completeExportLifetimesQualified=False,processDeathQualified=False,
                     finalSourceCohortQualified=False,phase3Complete=False,precondition=activation,
                     sourceWindows=2 if branch=='pregrant' else 4,incompleteTransfers=0 if branch=='pregrant' else 1)
        life=dict(status='PARTIAL',actualStateTransitionsQualified=True,originalDeadlinePreserved=True,physicalNetworkQualified=False,lossCauseQualified=False,
                  fullLifecycleQualified=False,finalSourceCohortQualified=False,phase3Complete=False,
                  owners=[dict(node=n,started=True,drained=True) for n in ('node-1','node-2','node-3')])
        return dict(exports=exports,lifecycle=life,branch=branch,firstCapture='node-1')
    if case=='higher-ballot-restart':
        return dict(status='PARTIAL',scope='one-native-higher-ballot-observed-restart',actualStateTransitionsQualified=True,originalDeadlinePreserved=True,
                    lossCauseQualified=True,physicalNetworkQualified=True,fullLifecycleQualified=False,processRestart=False,finalSourceCohortQualified=False,
                    phase3Complete=False,state=dict(rounds=2,losses=['HIGHER_BALLOT'],drained=True,started=True,readyCallbacks=[1,2]),precondition=dict(phase3Complete=False))
    return dict(status='PASS',scope='native-PROMISE-export-pre-return-revocation',caseCount=48,remoteElectionQualified=False,
        allExportKindsQualified=False,phase3Complete=False,clockInjection='explicit-offset',higherBallotInjection='local-native-owner-observation',
        cases=[dict(size=n,boundary=b,fault=f,attempts=3,materialized=1,delivered=0,refused=3,
            resources=dict(observations=7,maximumObservedQueued=dict(server=100,client=100),physicalStorageBaselineDerived=True,
                observedControlChargesQualified=True,wholeRuntimePeakQualified=False,publicationCapacityQualified=False)) for n,b,f in r.replies.CASES])


def result(case,branch='pregrant'):
    value=original(case,branch);rows,skipped=r.vector(case,value)
    return dict(original=value,negatives=rows,notApplicable=skipped,originalPreserved=True)


class AutomaticHistoryReplayTest(unittest.TestCase):
    def test_reply_resource_coverage_and_scope_are_required(self):
        for mutate in (lambda v:v.pop('resources'),lambda v:v['resources'].update(observations=6),
                       lambda v:v['resources'].update(observedControlChargesQualified=False),
                       lambda v:v['resources'].update(wholeRuntimePeakQualified=True),
                       lambda v:v['resources']['maximumObservedQueued'].update(server=True)):
            value=result('reply-revocation');mutate(value['original']['cases'][0])
            with self.assertRaises(ValueError):r.check_result(value,'reply-revocation')

    def test_all_declared_vectors_and_explicit_inapplicability(self):
        for case in ('competition','higher-ballot-restart','reply-revocation'):
            r.check_result(result(case),case)
        r.check_result(result('competition','superseded'),'competition')
        self.assertEqual(39,len(result('competition')['negatives']))
        self.assertEqual(7,len(result('competition')['notApplicable']))
        self.assertEqual(73,len(result('higher-ballot-restart')['negatives']))
        self.assertEqual(44,len(result('reply-revocation')['negatives']))
        self.assertEqual({},result('competition','superseded')['notApplicable'])

    def test_missing_extra_or_substituted_negatives_refuse(self):
        for case in ('competition','higher-ballot-restart','reply-revocation'):
            for change in (lambda v:v['negatives'].pop(),lambda v:v['negatives'].append(v['negatives'][0]),
                           lambda v:v['negatives'][0].update(reason='another failure'),lambda v:v.update(originalPreserved=False)):
                value=result(case);change(value)
                with self.subTest(case=case),self.assertRaises(ValueError):r.check_result(value,case)

    def test_inapplicable_is_never_counted_as_rejected_or_silently_omitted(self):
        for change in (lambda v:v['notApplicable'].clear(),lambda v:v['notApplicable'].update(extra='unobserved'),
                       lambda v:v['negatives'].append(dict(suite='exports',case='partial-bytes',status='REJECTED',reason=r.exports.NEGATIVES['partial-bytes']))):
            value=result('competition');change(value)
            with self.assertRaises(ValueError):r.check_result(value,'competition')

    def test_scope_inflation_and_missing_physical_precondition_refuse(self):
        value=result('competition');value['original']['exports']['completeExportLifetimesQualified']=True
        with self.assertRaisesRegex(ValueError,'export scope'):r.check_result(value,'competition')
        value=result('competition');value['original']['exports']['precondition']['fullNetworkQualified']=False
        with self.assertRaisesRegex(ValueError,'physical/network'):r.check_result(value,'competition')
        value=result('higher-ballot-restart');value['original']['state']['rounds']=True
        with self.assertRaisesRegex(ValueError,'two rounds'):r.check_result(value,'higher-ballot-restart')
        value=result('reply-revocation');value['original']['cases'].pop()
        with self.assertRaisesRegex(ValueError,'complete cases'):r.check_result(value,'reply-revocation')

    def test_unsupported_original_shape_fails_without_selecting_a_fallback(self):
        value=original('competition')['exports'];value['sourceWindows']=3
        with self.assertRaisesRegex(ValueError,'unsupported original'):r.competition_branch(value)
        for name,bad in [('sourceWindows',True),('incompleteTransfers',False)]:
            value=original('competition')['exports'];value[name]=bad
            with self.assertRaisesRegex(ValueError,'derived shape'):r.competition_branch(value)

    def test_unknown_case_refuses(self):
        for case in (None,'other','',False):
            with self.subTest(case=case),self.assertRaises(ValueError):r.suites(case)

    def test_bad_original_never_runs_negatives(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.replies,'validate',side_effect=ValueError('bad original')),\
                patch.object(r.replies,'qualify') as qualify:
            with self.assertRaisesRegex(ValueError,'bad original'):r.replay(Path(temp),'reply-revocation')
            qualify.assert_not_called()

    def test_lifecycle_failure_cannot_be_replaced_by_export_success(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.exports.Replay,'run',return_value=original('competition')['exports']),\
                patch.object(r.lifecycle,'validate',side_effect=ValueError('lost lifecycle')),patch.object(r.exports,'qualify') as qualify:
            with self.assertRaisesRegex(ValueError,'lost lifecycle'):r.replay(Path(temp),'competition')
            qualify.assert_not_called()

    def test_complete_restart_before_any_current_negative(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.restart,'validate',side_effect=ValueError('bad attachment')),\
                patch.object(r.current,'qualify') as qualify:
            root=Path(temp);side=root/'captures';side.mkdir()
            with self.assertRaisesRegex(ValueError,'bad attachment'):r.replay(root,'higher-ballot-restart',side)
            qualify.assert_not_called()

    def test_original_reader_drift_is_rejected(self):
        case='reply-revocation';value=result(case)
        with tempfile.TemporaryDirectory() as temp,patch.object(r.replies,'validate',return_value=value['original']),\
                patch.object(r.replies,'qualify',return_value=dict(original={},negatives=[])):
            with self.assertRaisesRegex(ValueError,'reader drift'):r.replay(Path(temp),case)

    def test_changed_original_during_qualification_is_rejected(self):
        case='reply-revocation';value=result(case)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);marker=root/'marker';marker.write_bytes(b'original')
            def qualify(*args):
                marker.write_bytes(b'changed');return dict(original=value['original'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in value['negatives']])
            with patch.object(r.replies,'validate',return_value=value['original']),patch.object(r.replies,'qualify',side_effect=qualify):
                with self.assertRaisesRegex(ValueError,'original changed'):r.replay(root,case)

    def test_restart_and_reply_stage_results_are_composed_once(self):
        for case in ('higher-ballot-restart','reply-revocation'):
            value=result(case)
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);side=root/'sidecar' if case=='higher-ballot-restart' else None
                if side:side.mkdir()
                if side:
                    one=dict(original=value['original']['precondition'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in value['negatives'] if row['suite']=='current'])
                    two=dict(original=value['original'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in value['negatives'] if row['suite']=='restart'])
                    with patch.object(r.restart,'validate',return_value=value['original']),patch.object(r.current,'qualify',return_value=one) as a,patch.object(r.restart,'qualify',return_value=two) as b:
                        self.assertEqual(value,r.replay(root,case,side));a.assert_called_once();b.assert_called_once()
                else:
                    returned=dict(original=value['original'],negatives=[{k:v for k,v in row.items() if k!='suite'} for row in value['negatives']])
                    with patch.object(r.replies,'validate',return_value=value['original']),patch.object(r.replies,'qualify',return_value=returned) as a:
                        self.assertEqual(value,r.replay(root,case));a.assert_called_once()


if __name__=='__main__':unittest.main()
