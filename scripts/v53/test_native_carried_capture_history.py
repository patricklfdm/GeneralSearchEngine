"""Synthetic entry/receipt guards; these fixtures are not native evidence."""
from contextlib import ExitStack
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_capture_history as m


def raw_tree(root,case):
    kind,cut,mode=m.selected(case);history=root/m.OBSERVED/'history';history.mkdir(parents=True);(history/'process').mkdir()
    (history/'original-plan.gsbp').write_bytes(case.encode())
    m.h.save(history/'process/result.json',dict(status='PARTIAL',producerPassed=True,phase3Complete=False,
        cut=cut,mode=mode,oldPhase='ACCEPTED',carriedKind=kind,clientCalls=0,powerLoss=False,children=[{},{}]))
    for name,path in m.PATHS.items():(root/path/('retirement' if name=='prefixes' else name)).mkdir(parents=True,exist_ok=True)


def replay(case,*,compact=True):
    kind,cut,mode=m.selected(case)
    process=dict(status='PARTIAL',kind=kind,cut=cut,mode=mode,clientCalls=0,freshGroupJvms=2,
        survivingOriginalOwners=0,componentChecks='PASS',processObservations=True,originalPrefixReplayed=True,phase3Complete=False)
    physical=dict(kind=kind,cut=cut,originalPrefixReplayed=True,snapshotByteReplay=True,publishedSlots=list(range(5 if kind=='INTENT' else 6,8)))
    value=dict(status='PARTIAL',process=process,physical=physical,phase3Complete=False)
    for name in ('forces','network','exports','maintenance','retention','resources',*(n for n,_ in m.FAMILIES)):
        row=dict(status='PARTIAL',phase3Complete=False,cohortAdmitted=False,wholeRuntimeResourcesQualified=False)
        flag={'forces':'observedStorageCallbacks','exports':'observedExportAuthorityQualified','maintenance':'completeCopyFloorLifetimesQualified','retention':'retentionRevisionCompositionQualified'}.get(name)
        if flag:row[flag]=True
        if name=='resources':row.update(observedAccountingQualified=True,ownerLifetimes=8)
        if name in m.TRUTHS:
            row.update({m.TRUTHS[name]:True},capturedPrefixes=2,lifetimes=[
                dict(life=i,pid=40+i,capturedPrefixes=1,terminal='CUT_PREFIX' if i==1 else 'CLOSED') for i in (1,2)])
        value=dict(status='PARTIAL',original=value,phase3Complete=False,**{name:row})
    charges=[dict(unit=unit,owner='synthetic-'+unit) for unit in ('GENERATION','SOURCE','JOURNAL','MISC')]+[
        dict(unit='APPLICATION',owner=owner) for owner in ('generation-synthetic','floor:synthetic',
            'retirement:synthetic','00000000-0000-0000-0000-000000000000:'+('a'*64),'application-replay-input','applied-end')]
    owners=[dict(life=life,node='node-'+str(node),snapshots=[dict(required=charges,eventIndex=1,point='TEST')]*(1 if life==2 and node>2 else 2))
            for life in (1,2) for node in range(1,5)]
    coverage=dict(status='PARTIAL',families='all-seven',expectedCallbacks=14,owners=owners,wholeRuntimeResourcesQualified=False)
    original=dict(status='PARTIAL',original=value,coverage=coverage,capturedCallbackBytesQualified=True,
                  wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)
    return dict(original=m.compact_original(original) if compact else original,negatives=m.negative_cases(case),originalPreserved=True)


class NativeCarriedCaptureHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'original'
        self.case='final-proof-kill';raw_tree(self.root,self.case)

    def test_collection_requires_exact_axis_and_all_families_without_admitting(self):
        value=m.collect(self.root,self.case)
        self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['nativeHistoryQualified'])
        with self.assertRaisesRegex(ValueError,'producer scope'):m.collect(self.root,'intent-accept-halt')
        (self.root/'replay').rmdir()
        with self.assertRaisesRegex(ValueError,'family directory'):m.collect(self.root,self.case)

    def test_failed_or_overclaimed_producer_and_boolean_counters_are_rejected(self):
        path=self.root/m.OBSERVED/'history/process/result.json';original=path.read_bytes()
        for change in (dict(producerPassed=False),dict(status='PASS'),dict(clientCalls=False),dict(phase3Complete=True),dict(children=[{}])):
            value=m.retirement.forces.process.read(path);value.update(change);m.h.save(path,value)
            with self.subTest(change=change),self.assertRaises(ValueError):m.collect(self.root,self.case)
            path.write_bytes(original)

    def test_partial_wrong_axis_or_overclaimed_original_never_admits(self):
        for case in m.CASES:m.check_result(replay(case),case)
        with self.assertRaisesRegex(ValueError,'exact original process'):m.check_result(replay('intent-accept-halt'),self.case)
        def stage(v,name):return m.original_chain(v['original'])[name][name]
        changes=[lambda v:v['original'].update(capturedCallbackBytesQualified=False),
            lambda v:stage(v,'votes').update(transientVoteBytesQualified=False),
            lambda v:stage(v,'replay').update(wholeRuntimeResourcesQualified=True),
            lambda v:stage(v,'prefixes')['lifetimes'][0].update(pid=999),
            lambda v:stage(v,'floors')['lifetimes'][0].update(terminal='CLOSED'),
            lambda v:stage(v,'completion').update(capturedPrefixes=True),
            lambda v:v['original']['coverage'].update(expectedCallbacks=13),
            lambda v:v['original']['coverage']['owners'].pop(),
            lambda v:v['original']['coverage']['owners'][0].update(node='node-2'),
            lambda v:v['original']['original'].pop('original'),
            lambda v:v['negatives'].pop(),lambda v:v['negatives'][0].update(reason='other'),
            lambda v:v.update(originalPreserved=False)]
        for index,change in enumerate(changes):
            value=replay(self.case);change(value)
            with self.subTest(change=index),self.assertRaises(ValueError):m.check_result(value,self.case)

    def test_invalid_original_stops_before_any_negative(self):
        with patch.object(m.storage,'validate',side_effect=ValueError('invalid original')),patch.object(m.retirement,'qualify') as negative:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.replay(self.root,self.case)
        negative.assert_not_called()

    def test_complete_chain_precedes_each_family_and_owner_qualification(self):
        result=replay(self.case,compact=False);parts=m.original_chain(result['original']);order=[]
        with ExitStack() as stack:
            first=stack.enter_context(patch.object(m.storage,'validate',return_value=result['original']))
            for name,reader in (*m.FAMILIES,('ownership',m.storage)):
                def qualify(root,name=name):
                    self.assertEqual(1,first.call_count);order.append(name)
                    self.assertEqual(self.root if name=='ownership' else self.root/m.PATHS[name],root)
                    return dict(original=parts[name],originalStorageUnchanged=True,mutatedPrerequisiteReplayed=False,
                        negatives=[{k:v for k,v in row.items() if k!='suite'} for row in result['negatives'] if row['suite']==name])
                stack.enter_context(patch.object(reader,'qualify',side_effect=qualify))
            self.assertEqual(replay(self.case),m.replay(self.root,self.case))
        self.assertEqual([n for n,_ in m.FAMILIES]+['ownership'],order)
        self.assertEqual(210,len(result['negatives']))

    def test_foreign_stage_original_cannot_borrow_other_passing_stages(self):
        result=replay(self.case,compact=False);parts=m.original_chain(result['original']);wrong=copy.deepcopy(parts['prefixes'])
        wrong['prefixes']['capturedPrefixes']=999
        with patch.object(m.storage,'validate',return_value=result['original']),patch.object(m.retirement,'qualify',return_value=dict(original=wrong)),patch.object(m.floor,'qualify') as following:
            with self.assertRaisesRegex(ValueError,'original stage drift'):m.replay(self.root,self.case)
        following.assert_not_called()

    def test_all_negative_reasons_are_part_of_the_catalogue(self):
        self.assertEqual(m.negative_cases('intent-accept-halt'),m.negative_cases('final-proof-kill'))
        rows=m.negative_cases(self.case)
        self.assertEqual(210,len({(v['suite'],v['case']) for v in rows}))
        self.assertEqual(10,sum(v['suite']=='ownership' for v in rows))
        for case in ('intent','final','final-proof-halt',False):
            with self.assertRaisesRegex(ValueError,'exact case'):m.negative_cases(case)

    def test_compact_receipt_retains_digest_binding_within_existing_reader_limit(self):
        full=replay(self.case,compact=False)['original']
        # Exercise serialization size independently of native evidence. The
        # original reader remains mandatory before this summarizer is called.
        full['coverage']['owners'][0]['accountingDiagnostic']='x'*(9*1024*1024)
        before=copy.deepcopy(full);compact=m.compact_original(full)
        m.check_original(compact,self.case,compact=True);self.assertEqual(before,full)
        self.assertEqual(m.h.digest(m.h.snapshot.f.canonical(full['coverage'])),compact['coverage']['originalCoverageSha256'])
        path=self.root/'summary.json';m.h.save(path,dict(original=compact,negatives=m.negative_cases(self.case),originalPreserved=True))
        self.assertLess(path.stat().st_size,128*1024)
        from .remove_process_matrix import read
        m.check_result(read(path),self.case)
        full['coverage']['owners'][0]['accountingDiagnostic']='different'
        changed=m.compact_original(full)
        self.assertNotEqual(compact['coverage']['originalCoverageSha256'],changed['coverage']['originalCoverageSha256'])
        self.assertNotEqual(compact['coverage']['owners'][0]['ownerSha256'],changed['coverage']['owners'][0]['ownerSha256'])
        with self.assertRaisesRegex(ValueError,'bounded ownership summary'):m.check_original(full,self.case,compact=True)

    def test_summary_cannot_omit_owner_digests_targets_or_invent_callback_totals(self):
        changes=[lambda c:c.update(originalCoverageSha256=None),lambda c:c['owners'][0].update(ownerSha256='bad'),
                 lambda c:c['owners'][0].update(callbacks=True),lambda c:c['targets'].pop('GENERATION'),
                 lambda c:c['targets']['GENERATION'].update(eventIndex=True),lambda c:c.update(extra=True),
                 lambda c:c['targets']['GENERATION'].update(unit='SOURCE')]
        for change in changes:
            result=replay(self.case);change(result['original']['coverage'])
            with self.assertRaises(ValueError):m.check_result(result,self.case)


if __name__=='__main__':unittest.main()
