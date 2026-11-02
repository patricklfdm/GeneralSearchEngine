"""REMOVE ballot continuity, original force boundaries and isolated negatives."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import remove_process_ballot as r


def event(name,node='node-1'):return dict(node=node,event=name)


class RemoveProcessBallotTest(unittest.TestCase):
    def reader(self,events=()):
        result=r.Replay.__new__(r.Replay);result.root=Path('/original/history');result.events=list(events)
        result.profile={};result.state=r.b.State('a'*64);result.state.seed('node-1',2,2)
        result.promise_points=set();result.promise_comparisons=0;result.used=set();result.self_grants=0
        result.history=SimpleNamespace(old=('node-1',),states=[dict(identities=[])])
        return result

    def test_reopened_snapshots_compare_and_never_reseed_reserved_or_promised_counters(self):
        reader=self.reader();reader.state.reserve(dict(node='node-1',start=1,end=7));reader.state.promise('node-1',5)
        raw=r.f.encode('records','ALLOCATOR',dict(root='a'*64,node='node-1',counter=3))
        with patch.object(r.c,'inventory',return_value={'allocator.gsr':raw}),patch.object(reader,'promised',return_value=5):
            reader.original('node-1','resume-opened-0/node-1','reopen')
        for counter,promise,reason in ((2,5,'continuous allocator'),(3,2,'continuous promise')):
            raw=r.f.encode('records','ALLOCATOR',dict(root='a'*64,node='node-1',counter=counter))
            with patch.object(r.c,'inventory',return_value={'allocator.gsr':raw}),patch.object(reader,'promised',return_value=promise):
                with self.assertRaisesRegex(ValueError,reason):reader.original('node-1','resume-opened-0/node-1','reopen')
        self.assertEqual(3,reader.state.counters['node-1']);self.assertEqual(5,reader.state.observed['node-1'])
        reader.state.reserve(dict(node='node-1',start=10,end=16));self.assertEqual(6,reader.state.counters['node-1'])

    def test_promise_sequence_is_bound_to_capture_and_cannot_be_reused(self):
        reader=self.reader([event(v) for v in ['CURRENT_BEFORE_CAPTURE',*r.b.PROMISE,'GRANT_BEFORE_RETURN']]);actions=[]
        reader.promise('node-1',0,4,dict(counter=3),actions)
        self.assertEqual([(3,'promise',('node-1',3))],actions)
        with self.assertRaisesRegex(ValueError,'reused promise'):reader.promise('node-1',0,4,dict(counter=3),[])
        with self.assertRaisesRegex(ValueError,'promise force order'):self.reader(reader.events).promise('node-1',1,4,dict(counter=3),[])

    def test_missing_reordered_foreign_and_unknown_promises_cannot_count_as_force(self):
        rows=[event(v) for v in r.b.PROMISE]
        variants=[rows[:-1],list(reversed(rows)),[rows[0],dict(rows[1],node='node-2'),rows[2]],
                  [rows[0],dict(rows[1],claimedHash='a'*64),rows[2]],
                  [rows[0],event('PROMISE_UNKNOWN'),rows[2]],rows+[rows[-1]]]
        for changed in variants:
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'promise force order'):
                self.reader(changed).promise('node-1',-1,len(changed),dict(counter=3),[])

    def test_reserved_ballot_requires_original_counter_and_storage_identity(self):
        reader=self.reader();value=dict(counter=2,proposer='node-1',incarnation='original')
        with patch.object(r.prior.n.n.shared.s.catalog,'identities',return_value={'node-1':dict(storage='original')}):
            reader.grant('node-1',value)
            for change in (dict(counter=3),dict(proposer='node-2'),dict(incarnation='different')):
                with self.assertRaisesRegex(ValueError,'reserved ballot'):reader.grant('node-1',dict(value,**change))

    def test_one_selected_grant_consumes_original_reservation_and_promise(self):
        names=['CURRENT_DIRECTORY_FORCED',*r.b.WRITES,'CURRENT_BEFORE_CAPTURE',*r.b.PROMISE,'GRANT_BEFORE_RETURN']
        reader=self.reader([event(v) for v in names]+[dict(event('ROUND_INSTALLED'),record=r.sha(b'selected'))])
        ballot=dict(counter=3,proposer='node-1',incarnation='original');basis=b'basis'
        selected=dict(ballot=ballot,sources=[dict(voter='node-1',basisDigest=r.sha(basis))])
        reader.tx=r.b.allocations(reader.events,('node-1',),None)
        reader.history.activations=lambda *_:SimpleNamespace(phases=[dict(SELECTED=b'selected')])
        reader.base=SimpleNamespace(events=reader.events,windows=[],sources=[dict(node='node-1',basis=basis,start=12,value=dict(ballot=ballot))])
        reader.snapshot=Mock()
        with patch.object(r.f,'decode',return_value=selected),patch.object(r.prior.n.n.shared.s.catalog,'identities',return_value={'node-1':dict(storage='original')}):
            result=reader.run()
        self.assertEqual({1},reader.used);self.assertEqual({9,10,11},reader.promise_points)
        self.assertEqual(3,reader.state.counters['node-1']);self.assertEqual(3,reader.state.observed['node-1'])
        self.assertEqual(1,result['reservations']);self.assertEqual(1,result['selfGrants'])
        self.assertFalse(result['phase3Complete']);reader.snapshot.assert_called_once_with('after-close')

    def test_failed_original_retirement_prevents_ballot_claim(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.prior,'validate',side_effect=ValueError('bad retirement')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad retirement$'):r.validate('/original')
        replay.assert_not_called()

    def test_changed_original_cannot_qualify(self):
        with patch.object(r.p.run.h,'inventory',side_effect=[{},dict(changed=True)]),patch.object(r.prior,'validate'),\
             patch.object(r.p,'profile_at',return_value={}),patch.object(r,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):r.validate('/original')

    def test_worker_bounds_and_original_failure_prevent_negative_submission(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()
        for workers in (0,5,True,1.1):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'replay workers'):r.qualify('/original',workers=workers)
            validate.assert_not_called()

    def negative(self,*,changed=False,other=False,precondition=None,rejection=None):
        before=dict(files={'selector':'a','history/wire.json':'wire'},directories=[])
        after=dict(files={'selector':'a','history/wire.json':'wrong'},directories=[]) if changed else before
        events=[event('FLOOR_RESERVED')]
        with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
             patch.object(r.prior.n,'observations',side_effect=[(events,[]),([] if other else events,[])]),\
             patch.object(r.prior,'replay',side_effect=precondition),patch.object(r,'replay',side_effect=rejection):
            return r.negative('/original',{},before,'force-missing')

    def test_negative_preserves_files_other_observations_and_retirement_replay(self):
        for kwargs,reason in ((dict(changed=True),'physical or wire inputs'),(dict(other=True),'other observations'),
                              (dict(precondition=ValueError('bad retirement')),'bad retirement')):
            with self.subTest(kwargs=kwargs),self.assertRaisesRegex(ValueError,reason):self.negative(**kwargs)

    def test_wrong_reason_or_accepted_mutation_never_qualifies(self):
        with self.assertRaisesRegex(ValueError,'unrelated ballot negative'):self.negative(rejection=ValueError('unrelated'))
        with self.assertRaisesRegex(ValueError,'mutation accepted'):self.negative()
        result=self.negative(rejection=ValueError(r.NEGATIVES['force-missing']))
        self.assertEqual('REJECTED',result['status']);self.assertEqual('PASS',result['retirementReplay'])


if __name__=='__main__':unittest.main()
