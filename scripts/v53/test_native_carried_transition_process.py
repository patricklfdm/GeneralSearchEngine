from pathlib import Path
import unittest
from unittest.mock import patch
from . import native_carried_transition_process as m
from . import test_native_carried_process_evidence as data_tests


class NativeCarriedTransitionProcessTest(unittest.TestCase):
    def result(self,kind='INTENT'):
        result=data_tests.NativeCarriedProcessEvidenceTest().result()
        return dict(result,carriedKind=kind,oldPhase='ACCEPTED')

    def test_exact_transition_children_do_not_change_the_data_contract(self):
        for kind in m.t.KINDS:
            for cut in m.CUTS:
                for mode in ('halt','kill'):
                    r=data_tests.NativeCarriedProcessEvidenceTest().result(mode,cut);r.update(carriedKind=kind,oldPhase='ACCEPTED')
                    self.assertEqual(r['children'],m.process.children(r,kind=kind))
                    with self.assertRaisesRegex(ValueError,'producer scope'):m.process.children(r)
        r=data_tests.NativeCarriedProcessEvidenceTest().result()
        with self.assertRaisesRegex(ValueError,'producer scope'):m.process.children(r,kind='FINAL')

    def test_receipt_alone_cannot_supply_correct_process_identity_or_exit(self):
        for key,value in [('exit',0),('allLocksHeldBeforeDeath',False),('allLocksReleasedAfterDeath',False),('opened',False)]:
            r=self.result();r['children'][0][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact death and close'):m.process.children(r,kind='INTENT')
        for key,value in [('oldPhase','APPLIED'),('clientCalls',1),('powerLoss',True),('phase3Complete',True)]:
            r=self.result();r[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'producer scope'):m.process.children(r,kind='INTENT')

    def test_explicit_methods_preserve_the_eight_whole_histories(self):
        source=Path('general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication/V53NativeCarriedTransitionProcessTest.java').read_text()
        self.assertEqual(source.count('@Test void '),8)
        for kind in m.t.KINDS:
            for cut in m.CUTS:
                for mode in ('halt','kill'):self.assertEqual(source.count(f'run("{kind}","{cut}","{mode}")'),1)

    def test_layout_requires_both_lives_every_prefix_and_final_barrier(self):
        for kind in m.t.KINDS:
            with patch.object(m.t.b.selection,'layout') as check:m.layout(Path('raw'),kind)
            names=check.call_args_list[0].args[1]
            self.assertIn('at-cut',names);self.assertIn('before-reopen',names)
            self.assertIn('life-2-published-7',names);self.assertIn('life-2-ready',names)
            self.assertIn('slot-4-settled',names)
            self.assertEqual('campaign-3-settled' in names,kind=='FINAL')
            self.assertEqual('life-2-installed-3' in names,kind=='INTENT')

    def test_missing_rounds_cannot_claim_a_new_barrier_or_inherited_command(self):
        with patch.object(Path,'read_bytes',return_value=b'original'):
            with self.assertRaisesRegex(ValueError,'exact round lifecycle'):
                m.rounds(Path('unused'),'INTENT',[[],[]],[[],[]],b'ready')

    def test_invalid_original_is_not_a_successful_negative(self):
        with patch.object(m.collection,'inventory',return_value={}),patch.object(m,'validate',side_effect=ValueError('original failed')) as original,patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original failed$'):m.qualify('/original')
            original.assert_called_once_with(Path('/original'));copied.assert_not_called()

    def test_negatives_are_unique_exact_reason_checks(self):
        self.assertEqual(len(m.NEGATIVES),14)
        self.assertTrue(all(isinstance(v,str) and v for v in m.NEGATIVES.values()))
        self.assertIn('changed-command',m.NEGATIVES);self.assertIn('changed-dead-directory',m.NEGATIVES)

if __name__=='__main__':unittest.main()
