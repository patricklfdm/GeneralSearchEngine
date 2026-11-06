"""Synthetic orchestration regressions; these are not native acceptance."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_application_refusal_capture_history as m
from . import test_native_carried_application_capture_history as app
from . import test_native_application_refusal as refusal


def raw_tree(root,case):
    app.raw_tree(root/'original',m.BASES[case])
    (root/'original'/m.application.OBSERVED/'history/original-plan.gsbp').write_bytes(case.encode())
    for life,terminal in ((1,'CUT_PREFIX'),(2,'CLOSED')):
        identity=dict(life=life,pid=40+life,terminal=terminal)
        resource=root/'original'/m.application.OBSERVED/f'resources/life-{life}'
        resource.mkdir(parents=True);m.h.save(resource/'index.json',identity)
        directory=root/f'refusals/life-{life}'
        directory.mkdir(parents=True)
        m.h.save(directory/'index.json',dict(identity,schema='gse-v53-native-count-refusals-v1',nodes=['node-1'],phase3Complete=False))
        m.h.save(directory/'node-1.json',dict(synthetic=True));(directory/'node-1.gscp').write_bytes(b'packet')


def replay(case):
    result=app.replay(m.BASES[case]);one=m.probe.check_record(*refusal.case())
    summary=dict(status='PARTIAL',case=m.BASES[case],probes=[dict(one,life=life) for life in (1,2)],
        originalPreserved=True,originalInventorySha256='a'*64,admittedRecoveryCompleted=True,
        wireAdmissionQualified=False,byteLimitQualified=False,wholeRuntimeResourcesQualified=False,cohortAdmitted=False,phase3Complete=False)
    return dict(result,refusals=summary,negatives=m.negative_cases(case))


class NativeRefusalCaptureHistoryTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'raw'
        self.case='final-application-kill-source-refusal';raw_tree(self.root,self.case)

    def probe_result(self):
        value=replay(self.case)
        return dict(value['refusals'],original=value['original'],
            originalInventorySha256=m.h.digest(m.h.snapshot.f.canonical(m.h.inventory(self.root/'original'))),
            negatives=[{k:v for k,v in row.items() if k!='suite'} for row in value['negatives'] if row['suite']=='source-refusal'])

    def test_two_exact_methods_retain_all_280_checks(self):
        self.assertEqual({'intent-application-halt-source-refusal','final-application-kill-source-refusal'},set(m.CASES))
        for case in m.CASES:
            value=replay(case);m.check_result(value,case)
            self.assertEqual(m.application.negative_cases(m.BASES[case]),value['negatives'][:268])
            self.assertEqual(280,len(value['negatives']));self.assertEqual(280,len({(v['suite'],v['case']) for v in value['negatives']}))
        with self.assertRaisesRegex(ValueError,'exact case'):m.selected('final-application-kill')

    def test_collection_includes_original_and_both_sidecars_without_replay(self):
        with patch.object(m.probe,'qualify') as qualify:value=m.collect(self.root,self.case)
        qualify.assert_not_called();self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['nativeHistoryQualified'])
        self.assertEqual(m.h.inventory(self.root),value['inventory']);self.assertEqual({self.case},set(value['plans']))
        (self.root/'refusals/life-2/node-1.gscp').unlink()
        with self.assertRaisesRegex(ValueError,'sidecar inventory'):m.collect(self.root,self.case)

    def test_sidecar_process_must_match_original(self):
        path=self.root/'refusals/life-2/index.json';index=m.probe.read(path);index['pid']+=1;m.h.save(path,index)
        with self.assertRaisesRegex(ValueError,'original process lifetime'):m.collect(self.root,self.case)

    def test_invalid_full_original_or_refusal_prevents_base_mutations(self):
        for reason in ('failed original','failed refusal'):
            with patch.object(m.probe,'qualify',side_effect=ValueError(reason)),patch.object(m.application,'replay') as later:
                with self.assertRaisesRegex(ValueError,reason):m.replay(self.root,self.case)
            later.assert_not_called()

    def test_complete_probe_replay_precedes_all_original_file_checks(self):
        probe=self.probe_result()
        with patch.object(m.probe,'qualify',return_value=probe) as first:
            def application(root,case):
                first.assert_called_once_with(self.root,m.BASES[self.case]);self.assertEqual(self.root/'original',root)
                return app.replay(case)
            with patch.object(m.application,'replay',side_effect=application):result=m.replay(self.root,self.case)
        m.check_result(result,self.case);self.assertEqual(280,len(result['negatives']))
        path=Path(self.temp.name)/'result.json';m.h.save(path,result)
        from .remove_process_matrix import read
        self.assertEqual(result,read(path));self.assertLess(path.stat().st_size,128*1024)

    def test_probe_scope_or_incomplete_negatives_stop_before_base_replay(self):
        for change in (lambda v:v.update(wireAdmissionQualified=True),lambda v:v['negatives'].pop(),
                       lambda v:v['negatives'][0].update(reason='unrelated'),lambda v:v['probes'].pop()):
            value=self.probe_result();change(value)
            with patch.object(m.probe,'qualify',return_value=value),patch.object(m.application,'replay') as later:
                with self.assertRaises(ValueError):m.replay(self.root,self.case)
            later.assert_not_called()

    def test_original_stage_drift_is_not_accepted(self):
        value=app.replay(m.BASES[self.case]);value['original']['ledger']={'changed':True}
        with patch.object(m.probe,'qualify',return_value=self.probe_result()),patch.object(m.application,'replay',return_value=value):
            with self.assertRaisesRegex(ValueError,'original stage drift'):m.replay(self.root,self.case)

    def test_original_inventory_and_refusal_bytes_are_checked_after_replay(self):
        value=self.probe_result();value['originalInventorySha256']='0'*64
        with patch.object(m.probe,'qualify',return_value=value),patch.object(m.application,'replay',return_value=app.replay(m.BASES[self.case])):
            with self.assertRaisesRegex(ValueError,'original inventory binding'):m.replay(self.root,self.case)
        value=self.probe_result()
        def changed(root,case):
            (self.root/'refusals/life-2/node-1.json').write_bytes(b'changed')
            return app.replay(case)
        with patch.object(m.probe,'qualify',return_value=value),patch.object(m.application,'replay',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'original or sidecars changed'):m.replay(self.root,self.case)

    def test_shortened_vectors_duplicate_lifetimes_and_overclaimed_receipts_reject(self):
        changes=[lambda v:v['negatives'].pop(),lambda v:v.update(negatives=v['negatives'][-12:]),
            lambda v:v['negatives'][-1].update(mutationScope='physical-files'),lambda v:v.update(originalPreserved=False),
            lambda v:v['refusals'].update(byteLimitQualified=True),lambda v:v['refusals'].update(cohortAdmitted=True),
            lambda v:v['refusals'].update(admittedRecoveryCompleted=False),lambda v:v['refusals'].update(originalInventorySha256='bad'),
            lambda v:v['refusals'].update(case='intent-application-halt'),lambda v:v['refusals']['probes'].pop(),
            lambda v:v['refusals']['probes'][1].update(life=1),lambda v:v['refusals']['probes'][0].update(life=True),
            lambda v:v['refusals']['probes'][0].update(eventIndex=True),lambda v:v['refusals']['probes'][0].update(afterSequence=2),
            lambda v:v['refusals']['probes'][0].update(physicalBytes=0),lambda v:v['refusals']['probes'][0].update(packetSha256=None),
            lambda v:v['refusals']['probes'][0].update(temporaryControlReturned=False),
            lambda v:v['refusals']['probes'][0]['nonemptyPhysicalOwnerCounts'].update(SOURCE=5)]
        for n,change in enumerate(changes):
            value=copy.deepcopy(replay(self.case));change(value)
            with self.subTest(n=n),self.assertRaises(ValueError):m.check_result(value,self.case)


if __name__=='__main__':unittest.main()
