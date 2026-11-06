"""Synthetic guards only; none of these receipts represent native execution."""
import copy
from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_capture_history as m
from .test_native_carried_capture_history import replay as seven


def raw_tree(root,case):
    kind,cut,mode=m.selected(case);history=root/m.OBSERVED/'history';(history/'process').mkdir(parents=True)
    (history/'original-plan.gsbp').write_bytes(case.encode())
    m.h.save(history/'process/result.json',dict(status='PARTIAL',producerPassed=True,phase3Complete=False,
        cut=cut,mode=mode,oldPhase='ACCEPTED',carriedKind=kind,clientCalls=0,powerLoss=False,children=[{},{}]))
    for path in m.PATHS.values():(root/path).mkdir(parents=True,exist_ok=True)


def replay(case,*,compact=True):
    kind,cut,mode=m.selected(case)
    process=dict(status='PARTIAL',kind=kind,cut=cut,mode=mode,clientCalls=0,freshGroupJvms=2,
        survivingOriginalOwners=0,componentChecks='PASS',processObservations=True,originalPrefixReplayed=True,phase3Complete=False)
    physical=dict(status='PARTIAL',kind=kind,cut=cut,originalPrefixReplayed=True,snapshotByteReplay=True,freshStableBarrier=True)
    value=dict(status='PARTIAL',process=process,physical=physical,phase3Complete=False)
    for field,flag in (('protocol',None),('exports','observedExportAuthorityQualified'),('maintenance','completeCopyFloorLifetimesQualified'),
                       ('retention','retentionRevisionCompositionQualified'),('resources','observedAccountingQualified')):
        row=dict(status='PARTIAL',phase3Complete=False)
        if flag:row[flag]=True
        if field=='protocol':row.update(callbacks=dict(observedStorageCallbacks=True),network=dict(status='PARTIAL'))
        if field=='resources':row['ownerLifetimes']=8
        value=dict(status='PARTIAL',original=value,phase3Complete=False,**{field:row})
    def life(i):return dict(life=i,pid=40+i,capturedPrefixes=1,terminal='CUT_PREFIX' if i==1 else 'CLOSED')
    app=dict(life(1),status='PARTIAL',interruptedApplicationBytesQualified=True)
    value=dict(status='PARTIAL',original=value,phase3Complete=False,application=app)
    value=dict(status='PARTIAL',original=value,phase3Complete=False,retirement=dict(status='PARTIAL',retiredApplicationBytesQualified=True,lifetime=life(2)))
    flags=dict(retirement='transientRetirementBytesQualified',floors='transientFloorBytesQualified',campaigns='transientCampaignBytesQualified',
               votes='transientVoteBytesQualified',ledgers='transientLedgerBytesQualified',replay='controlScratchBytesQualified')
    families={k:dict(status='PARTIAL',capturedPrefixes=2,lifetimes=[life(1),life(2)],**{flag:True}) for k,flag in flags.items()}
    maintenance=dict(status='PARTIAL',maintenanceTransientBytesQualified=True,capturedPrefixes=6,
                     families={k:families[k] for k in m.MAINTENANCE.FAMILIES})
    value=dict(status='PARTIAL',original=value,phase3Complete=False,maintenance=maintenance)
    def coverage(total,field):
        result=copy.deepcopy(seven('final-proof-kill',compact=False)['original']['coverage'])
        for owner in result['owners']:owner['snapshots']=owner['snapshots'][:1]
        for n in range(total-8):result['owners'][n%8]['snapshots'].append(copy.deepcopy(result['owners'][n%8]['snapshots'][0]))
        result.pop('expectedCallbacks');result[field]=total;return result
    nested=dict(status='PARTIAL',original=value,coverage=coverage(8,'expectedCallbacks'),capturedCallbackBytesQualified=True,
        captureScope='application-five-captured-families',allSevenFamiliesCaptured=False,applicationAndRetirementChargeBindingQualified=True,
        wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)
    captures={k:families[k] for k in ('votes','ledgers','replay')}
    captures['completion']=dict(status='PARTIAL',capturedPrefixes=1,lifetimes=[life(2)])
    original=dict(status='PARTIAL',original=nested,captures=captures,ledger={},coverage=coverage(14,'callbacks'),duplicateReplayCallbacks=1,
        applicationTransientCompositionQualified=True,fullTransientBytesQualified=False,wholeRuntimeResourcesQualified=False,
        cohortAdmitted=False,phase3Complete=False)
    return dict(original=m.compact_original(original) if compact else original,negatives=m.negative_cases(case),originalPreserved=True)


class ApplicationCaptureHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'original'
        self.case='final-application-kill';raw_tree(self.root,self.case)

    def test_exact_four_axes_and_268_unique_negatives(self):
        from itertools import product
        self.assertEqual(set(product(('INTENT','FINAL'),(m.transients.model.protocol.application.CUT,),('halt','kill'))),set(m.CASES.values()))
        for case in m.CASES:
            result=replay(case);m.check_result(result,case)
            self.assertEqual(268,len(result['negatives']))
            self.assertEqual(268,len({(v['suite'],v['case']) for v in result['negatives']}))
        with self.assertRaisesRegex(ValueError,'exact case'):m.selected('final-proof-kill')

    def test_collection_has_all_nine_families_and_exact_axis(self):
        result=m.collect(self.root,self.case);self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])
        with self.assertRaisesRegex(ValueError,'producer scope'):m.collect(self.root,'intent-application-kill')
        (self.root/m.PATHS['votes']).rmdir()
        with self.assertRaisesRegex(ValueError,'family directory'):m.collect(self.root,self.case)

    def test_incomplete_axis_lifetimes_counts_and_scope_refuse(self):
        def parts(v):return m.original_chain(v['original'])
        changes=[lambda v:v['original']['captures'].pop('votes'),
            lambda v:v['original']['captures']['completion']['lifetimes'].append(dict(life=1)),
            lambda v:v['original']['captures']['votes']['lifetimes'][1].update(pid=43),
            lambda v:parts(v)['application']['application'].update(life=2),
            lambda v:parts(v)['old-end']['retirement']['lifetime'].update(terminal='CUT_PREFIX'),
            lambda v:parts(v)['base']['process'].update(mode='halt'),
            lambda v:parts(v)['base']['process'].update(clientCalls=False),
            lambda v:parts(v)['base']['physical'].update(freshStableBarrier=False),
            lambda v:parts(v)['protocol']['protocol']['callbacks'].update(observedStorageCallbacks=False),
            lambda v:parts(v)['ownership-five'].update(applicationAndRetirementChargeBindingQualified=False),
            lambda v:v['original'].update(duplicateReplayCallbacks=True),
            lambda v:v['original'].update(duplicateReplayCallbacks=2),
            lambda v:v['original'].update(wholeRuntimeResourcesQualified=True),
            lambda v:v['original']['captures']['replay'].update(fullTransientBytesQualified=True),
            lambda v:v['original']['captures']['completion'].update(capturedPrefixes=True),
            lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='unrelated'),
            lambda v:v.update(originalPreserved=False)]
        for n,change in enumerate(changes):
            result=replay(self.case);change(result)
            with self.subTest(n=n),self.assertRaises(ValueError):m.check_result(result,self.case)

    def test_both_coverage_levels_are_bounded_and_hash_every_original_owner(self):
        result=replay(self.case,compact=False);original=result['original'];m.check_original(original,self.case)
        for coverage in (original['coverage'],original['original']['coverage']):coverage['owners'][0]['extraDiagnostic']='x'*(9*1024*1024)
        before=copy.deepcopy(original);compact=m.compact_original(original)
        self.assertEqual(before,original);m.check_original(compact,self.case,compact=True)
        self.assertLess(len(m.h.snapshot.f.canonical(compact)),128*1024)
        for old,new in ((original,compact),(original['original'],compact['original'])):
            self.assertEqual(m.h.digest(m.h.snapshot.f.canonical(old['coverage'])),new['coverage']['originalCoverageSha256'])
            self.assertEqual(m.h.digest(m.h.snapshot.f.canonical(old['coverage']['owners'][0])),new['coverage']['owners'][0]['ownerSha256'])
        from .remove_process_matrix import read
        path=self.root/'bounded.json';m.h.save(path,dict(result,original=compact));m.check_result(read(path),self.case)
        with self.assertRaises(ValueError):m.check_original(original,self.case,compact=True)

    def test_both_summaries_reject_omissions_booleans_and_wrong_owner_categories(self):
        for nested in (False,True):
            for change in (lambda c:c['owners'].pop(),lambda c:c['owners'][0].update(node='node-2'),
                           lambda c:c.update(callbacks=True),lambda c:c.update(originalCoverageSha256=None),
                           lambda c:c['owners'][0].update(ownerSha256='bad'),lambda c:c['targets'].pop('GENERATION'),
                           lambda c:c['targets']['GENERATION'].update(unit='SOURCE'),lambda c:c['targets']['GENERATION'].update(eventIndex=True)):
                result=replay(self.case);value=result['original']['original'] if nested else result['original'];change(value['coverage'])
                with self.subTest(nested=nested),self.assertRaises(ValueError):m.check_result(result,self.case)

    def test_failed_original_stops_all_mutations(self):
        with patch.object(m.transients,'validate',side_effect=ValueError('original failure')),patch.object(m.transients,'qualify') as negative,patch.object(m,'owner_negatives') as owners:
            with self.assertRaisesRegex(ValueError,'original failure'):m.replay(self.root,self.case)
        negative.assert_not_called();owners.assert_not_called()

    def test_complete_original_then_exact_stages_and_owner_checks(self):
        result=replay(self.case,compact=False);parts=m.original_chain(result['original']);order=[]
        with ExitStack() as stack:
            first=stack.enter_context(patch.object(m.transients,'validate',return_value=result['original']))
            for name,reader,path in m.STAGES:
                def qualify(root,name=name,path=path):
                    self.assertEqual(1,first.call_count);order.append(name);self.assertEqual(self.root/path,root)
                    return dict(original=parts[name],originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
                        negatives=[{k:v for k,v in row.items() if k!='suite'} for row in result['negatives'] if row['suite']==name])
                stack.enter_context(patch.object(reader,'qualify',side_effect=qualify))
            def owners(root,original):
                self.assertEqual([n for n,_,_ in m.STAGES],order);self.assertEqual(result['original'],original)
                return [row for row in result['negatives'] if row['suite']=='ownership']
            stack.enter_context(patch.object(m,'owner_negatives',side_effect=owners))
            self.assertEqual(replay(self.case),m.replay(self.root,self.case))

    def test_stage_original_drift_cannot_receive_credit(self):
        original=replay(self.case,compact=False)['original'];wrong=copy.deepcopy(original);wrong['duplicateReplayCallbacks']=2
        with patch.object(m.transients,'validate',return_value=original),patch.object(m.transients,'qualify',return_value=dict(original=wrong)),patch.object(m.MAINTENANCE,'qualify') as later:
            with self.assertRaisesRegex(ValueError,'original stage drift'):m.replay(self.root,self.case)
        later.assert_not_called()


    def test_changed_raw_cannot_receive_credit_after_all_rejections(self):
        result=replay(self.case,compact=False);parts=m.original_chain(result['original'])
        with ExitStack() as stack:
            stack.enter_context(patch.object(m.transients,'validate',return_value=result['original']))
            for name,reader,path in m.STAGES:
                stack.enter_context(patch.object(reader,'qualify',return_value=dict(original=parts[name],
                    originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
                    negatives=[{k:v for k,v in row.items() if k!='suite'} for row in result['negatives'] if row['suite']==name])))
            def owners(root,original):
                (root/'changed-original').write_bytes(b'altered')
                return [row for row in result['negatives'] if row['suite']=='ownership']
            stack.enter_context(patch.object(m,'owner_negatives',side_effect=owners))
            with self.assertRaisesRegex(ValueError,'original or captures changed'):m.replay(self.root,self.case)


if __name__=='__main__':unittest.main()
