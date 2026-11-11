"""Continuous carried-ledger scope and exact negative-credit boundaries."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import copy
import unittest
from unittest.mock import patch
from . import carried_transition_retention as r


class CarriedRetentionTest(unittest.TestCase):
    def test_forged_peer_write_fails_at_the_declared_shape_gate(self):
        # Exercise the real shared constructor, not a mocked negative result.
        # The generic transaction parser must not obscure this exact rejection.
        base=SimpleNamespace(events=[dict(node='node-1',event=r.r.peer.WRITES[0],revision=99)],
                             history=SimpleNamespace(old=('node-1',)))
        with patch.object(r.r.n.phase,'blocks',return_value={}):
            with self.assertRaisesRegex(ValueError,'^REMOVE peer event shape$'):
                r.r.PeerReplay('/unused','INTENT',base=base)

    def test_admitted_prelude_is_derived_for_both_starting_kinds(self):
        for kind in ('INTENT','FINAL'):
            reader=r.PeerReplay.__new__(r.PeerReplay);reader.root=Path('/original');reader.kind=kind
            group={'node-1':{r.r.peer.FILE:b'derived revision'}}
            with patch.object(r.e.network.physical,'prelude',return_value=(SimpleNamespace(group=group),None,None)) as derive:
                self.assertIs(group,reader.initial_states())
            derive.assert_called_once_with(reader.root,kind)

    def test_peer_snapshot_comparison_never_replaces_the_current_chain(self):
        reader=r.PeerReplay.__new__(r.PeerReplay);reader.state={'node-1':b'latest'};reader.comparisons=0
        with self.assertRaisesRegex(ValueError,'exact original ledger'):reader.compare('node-1',b'stale','installed')
        self.assertEqual({'node-1':b'latest'},reader.state)

    def test_bad_kind_and_original_prevent_credit(self):
        with patch.object(r.n.collection,'inventory') as inventory:
            with self.assertRaisesRegex(ValueError,'exact kind'):r.validate('/unused','DATA')
        inventory.assert_not_called()
        with patch.object(r.n.collection,'inventory',return_value={}),patch.object(r.e,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'bad original'):r.validate('/unused','INTENT')
        replay.assert_not_called()
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify('/unused','INTENT')
        negative.assert_not_called()

    def test_changed_original_and_invalid_parallelism_refuse(self):
        with patch.object(r.n.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.e,'validate'),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/unused','FINAL')
        for workers in (0,5,True,1.2):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/unused','FINAL',workers=workers)
            validate.assert_not_called()

    def test_retention_does_not_claim_retirement_crashes_public_service_or_phase_closure(self):
        with patch.object(r,'PeerReplay'),patch.object(r,'FutureReplay'):result=r.replay('/unused','INTENT')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['retentionRevisionCompositionQualified'])
        for name in ('completeRetirementTransactions','processDeathQualified','publicReady','phase3Complete'):self.assertFalse(result[name])

    def test_exact_negatives_preserve_files_and_every_other_observation_family(self):
        before=dict(files={'ledger':'a','wire.json':'w','events.json':'e'},directories=['empty'])
        for change in ('file','directory','event','wrong-reason','accepted','correct'):
            after=copy.deepcopy(before);original=[dict(node='node-1',event='CURRENT_VALIDATED')];changed=copy.deepcopy(original)
            if change=='file':after['files']['wire.json']='changed'
            elif change=='directory':after['directories']=[]
            elif change=='event':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
            reason=r.NEGATIVES['future']['unbound-write']
            with ExitStack() as stack:
                stack.enter_context(patch.object(r.shutil,'copytree'));stack.enter_context(patch.object(r,'mutate'))
                stack.enter_context(patch.object(r.n.collection,'inventory',return_value=after))
                stack.enter_context(patch.object(r.n.collection,'read_json',side_effect=[original,changed]))
                reader=stack.enter_context(patch.object(r,'FutureReplay'))
                reader.return_value.run.side_effect=None if change=='accepted' else ValueError('wrong' if change=='wrong-reason' else reason)
                if change=='correct':self.assertEqual(reason,r.negative('/unused','FINAL',before,'future','unbound-write')['reason'])
                else:
                    expected={'file':'original files','directory':'original files','event':'other observations','wrong-reason':'unrelated','accepted':'mutation accepted'}[change]
                    with self.subTest(change=change),self.assertRaisesRegex(ValueError,expected):r.negative('/unused','FINAL',before,'future','unbound-write')


if __name__=='__main__':unittest.main()
