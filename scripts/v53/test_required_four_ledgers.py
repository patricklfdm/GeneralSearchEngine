"""Conditional continuous-ledger composition, original-first and scope checks."""
from concurrent.futures import Future
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import required_four_ledgers as r


class RequiredFourLedgerTest(unittest.TestCase):
    def base(self):
        return SimpleNamespace(model=SimpleNamespace(old=['node-'+str(i) for i in range(1,6)],joining='node-6'),
                               direct_nodes={'node-1'},pinned_floors={('node-1',4)},floor_inputs=['old'],events=[])

    def readers(self,missing=None):
        owners=['node-'+str(i) for i in range(1,7)];readers={}
        for stage in r.READERS:
            key='finalCounters' if stage=='ballot' else 'finalRevisions'
            result={key:{node:0 for node in owners}}
            if stage==missing:result[key].pop('node-5')
            instance=SimpleNamespace(run=Mock(return_value=result),steps=[dict(node='node-1'),dict(node='node-6')],adoption_fences=[])
            readers[stage]=Mock(return_value=instance)
        return readers

    def test_peer_adapter_preserves_covering_floor_and_pin_dispatch(self):
        self.assertIs(r.PeerReplay.expected_events,r.maintenance.Replay.expected_events)
        for name in ('acquired','direct','governing','floors'):
            self.assertIs(getattr(r.PeerReplay,name),getattr(r.maintenance.Replay,name))
        self.assertIs(r.PeerReplay.floor,r.profile_peer.Replay.floor)
        self.assertIsNone(r.PeerReplay.expected_write_counts)

    def test_peer_mutable_state_does_not_reset_or_modify_shared_original_context(self):
        base=self.base();before=copy.deepcopy(vars(base))
        with patch.object(r.peer,'reseal_lifetimes',return_value=[]) as reseals:
            reader=r.PeerReplay('/unused',base=base)
        reseals.assert_called_once();self.assertIs(reader.model,base.model)
        self.assertEqual(set(),reader.direct_nodes);self.assertEqual(set(),reader.pinned_floors)
        self.assertEqual([],reader.floor_inputs);self.assertEqual({},reader.state)
        self.assertEqual(before,vars(base))

    def test_other_readers_receive_the_exact_required_four_context(self):
        base=self.base()
        for cls,parent in ((r.LearnerReplay,r.learner.Replay),(r.FutureReplay,r.future.Replay),
                           (r.BallotReplay,r.ballot_profile.ballot.Replay)):
            with self.subTest(reader=cls.__name__),patch.object(parent,'__init__',return_value=None) as initialize, \
                 patch.object(r.maintenance,'Replay') as context:
                cls('/original',base=base);initialize.assert_called_once_with('/original',base=base);context.assert_not_called()
        with patch.object(r.maintenance,'Replay',return_value=base) as context,patch.object(r.future.Replay,'__init__',return_value=None) as initialize:
            r.FutureReplay('/original');context.assert_called_once_with('/original');initialize.assert_called_once_with('/original',base=base)

    def test_all_four_readers_share_one_original_and_keep_all_six_final_owners(self):
        base=self.base();readers=self.readers();progress=[]
        with patch.object(r.maintenance,'Replay',return_value=base) as context,patch.dict(r.READERS,readers,clear=True):
            result=r.replay('/original',progress.append)
        context.assert_called_once_with('/original')
        for reader in readers.values():reader.assert_called_once_with('/original',base=base)
        self.assertEqual(list(readers),list(result));self.assertEqual(1,result['learner']['joiningWrites'])
        self.assertEqual([],result['ballot']['adoptionFences']);self.assertEqual(4,len(progress))
        for stage in readers:
            with self.subTest(stage=stage),patch.object(r.maintenance,'Replay',return_value=base),patch.dict(r.READERS,self.readers(missing=stage),clear=True):
                with self.assertRaisesRegex(ValueError,'complete ledger owners: '+stage):r.replay('/original')

    def test_original_maintenance_failure_precedes_any_chain_or_negative(self):
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.maintenance,'validate',side_effect=ValueError('original refused')), \
             patch.object(r,'replay') as replay,patch.object(r,'ProcessPoolExecutor') as pool:
            for action in (r.validate,r.qualify):
                with self.assertRaisesRegex(ValueError,'^original refused$'):action('/unused')
            replay.assert_not_called();pool.assert_not_called()

    def test_receipt_does_not_claim_resource_process_or_final_source_qualification(self):
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r.maintenance,'validate',return_value={}), \
             patch.object(r,'replay',return_value={}):
            receipt=r.validate('/unused')
            for name in ('peer','learner','future','ballot'):self.assertTrue(receipt[name+'LedgerCompositionQualified' if name!='ballot' else 'ballotCompositionQualified'])
            for name in ('wholeRuntimeResourcesQualified','completePhysicalQualified','processDeathQualified','finalSourceCohortQualified','phase3Complete'):
                self.assertFalse(receipt[name])
            with patch.object(r.collection,'inventory',side_effect=[{},dict(changed=True)]):
                with self.assertRaisesRegex(ValueError,'ledgers original changed'):r.validate('/unused')

    def original(self,joining=1,fences=None):
        return dict(ledgers=dict(learner=dict(joiningWrites=joining),ballot=dict(adoptionFences=[dict(promiseAppended=True)] if fences is None else fences)))

    def test_case_plan_keeps_every_existing_mutation_and_only_three_conditional_absences(self):
        full,absent=r.cases(self.original());self.assertEqual(86,len(full));self.assertEqual([],absent)
        self.assertEqual({(stage,name,reason) for stage,module in r.MODULES.items() for name,reason in module.NEGATIVES.items()},set(full))
        cases,absent=r.cases(self.original(joining=0,fences=[]));self.assertEqual(83,len(cases))
        self.assertEqual({('learner','wrong-write-scope'),('ballot','adoption-fence-missing'),('ballot','adoption-promise-missing')},
                         {(v['stage'],v['case']) for v in absent})
        self.assertTrue(all(v['status']=='NOT_APPLICABLE' for v in absent))
        _,absent=r.cases(self.original(fences=[dict(promiseAppended=False)]))
        self.assertEqual(['adoption-promise-missing'],[v['case'] for v in absent])

    def test_callback_scope_excludes_transport_publication_and_floor_events(self):
        for stage in r.READERS:
            for name in ('TRANSPORT_SENT','FLOOR_RESERVED','PUBLICATION_BEFORE_RETURN','INSTALL_BEFORE_RETURN'):
                self.assertFalse(r.relevant(stage,dict(event=name)),(stage,name))
        for stage,name in (('peers','RETENTION_FORCED'),('peers','SELECTED_RETENTION_COMPLETED'),
                           ('learner','LEARNER_RETENTION_FORCED'),('future','FUTURE_RETENTION_FORCED'),
                           ('ballot','PROMISE_FORCED'),('ballot','ALLOCATOR_FORCED')):
            self.assertTrue(r.relevant(stage,dict(event=name)),(stage,name))

    def original_files(self,root):
        (root/'events.json').write_bytes(r.peer.f.canonical([dict(event='TRANSPORT_SENT'),dict(event='RETENTION_FORCED')]))
        (root/'wire.json').write_bytes(r.peer.f.canonical([]));(root/'original.gsr').write_bytes(b'original authority')
        return r.collection.inventory(root)

    def test_peer_marker_is_an_actual_omission_and_unknown_markers_are_not_erased(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def mutation(*args,**kwargs):
                (root/'events.json').write_bytes(r.peer.f.canonical([dict(event='OTHER'),dict(event='REMOVED_PEER_FORCE'),dict(event='UNKNOWN')]))
            with patch.dict(r.READERS,peers=Mock()),patch.object(r.peer,'mutate',side_effect=mutation):
                r.mutate(root,'peers','force-missing')
                self.assertEqual([dict(event='OTHER'),dict(event='UNKNOWN')],json.loads((root/'events.json').read_text()))
            with patch.dict(r.READERS,peers=Mock()),patch.object(r.peer,'mutate'):
                with self.assertRaisesRegex(ValueError,'exact peer omissions'):r.mutate(root,'peers','force-missing')

    def test_negative_protects_wire_authority_and_other_observations(self):
        for target in ('wire.json','original.gsr','other-event','no-change'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);before=self.original_files(root)
                def mutation(changed,*args):
                    if target in ('wire.json','original.gsr'):(changed/target).write_bytes(b'changed')
                    elif target=='other-event':(changed/'events.json').write_bytes(r.peer.f.canonical([]))
                reader=Mock()
                with patch.object(r,'mutate',side_effect=mutation),patch.dict(r.READERS,peers=reader):
                    reason='other observations' if target=='other-event' else 'protected inputs'
                    with self.assertRaisesRegex(ValueError,reason):r.negative(root,before,('peers','force-missing','intended'))
                    reader.assert_not_called()
                self.assertEqual(before,r.collection.inventory(root))

    def test_exact_negative_and_missing_or_unrelated_failure(self):
        for failure,expected in ((ValueError('intended'),None),(ValueError('unrelated'),'unrelated ledger negative'),(None,'mutation accepted')):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);before=self.original_files(root)
                def mutation(changed,*args):(changed/'events.json').write_bytes(r.peer.f.canonical([dict(event='TRANSPORT_SENT')]))
                reader=Mock(return_value=SimpleNamespace(run=Mock(side_effect=failure)))
                with patch.object(r,'mutate',side_effect=mutation),patch.dict(r.READERS,peers=reader):
                    if expected:
                        with self.assertRaisesRegex(ValueError,expected):r.negative(root,before,('peers','force-missing','intended'))
                    else:self.assertEqual('REJECTED',r.negative(root,before,('peers','force-missing','intended'))['status'])
                with patch.object(r,'mutate',side_effect=StopIteration()):
                    with self.assertRaisesRegex(ValueError,'missing ledger mutation target'):r.negative(root,before,('peers','force-missing','intended'))
                self.assertEqual(before,r.collection.inventory(root))

    def test_workers_are_bounded_and_one_failed_case_fails_the_matrix(self):
        for workers in (0,5,True,'2'):
            with patch.object(r,'validate') as validate:
                with self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/unused',workers=workers)
                validate.assert_not_called()
        task=Future();task.set_exception(ValueError('original target absent'))
        pool=Mock();pool.__enter__=Mock(return_value=pool);pool.__exit__=Mock(return_value=False);pool.submit.return_value=task
        progress=[]
        with patch.object(r.collection,'inventory',return_value={}),patch.object(r,'validate',return_value=self.original()), \
             patch.object(r,'cases',return_value=([('peers','force-missing','intended')],[])),patch.object(r,'ProcessPoolExecutor',return_value=pool):
            with self.assertRaisesRegex(ValueError,'negative matrix failed'):r.qualify('/unused',progress=progress.append)
        self.assertEqual('FAIL',progress[-1]['status']);self.assertEqual('original target absent',progress[-1]['failure'])


if __name__=='__main__':unittest.main()
