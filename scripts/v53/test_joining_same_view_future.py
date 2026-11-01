"""Continuous revision, callback scope and original-first negative boundaries."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from . import joining_same_view_future as m


def event(point,node='node-1',scope=None):
    value=dict(node=node,event=point)
    if scope is not None:value['scope']=scope
    return value


class JoiningSameViewFutureTest(unittest.TestCase):
    def reader(self,events=()):
        value=m.Replay.__new__(m.Replay);value.events=list(events);value.root=Path('/original')
        value.model=SimpleNamespace(joining='node-4');value.used=set();value.callbacks=set();value.steps=[]
        value.state={};value.comparisons=0;value.reseals=0;value.tx=[]
        return value

    def initial(self):
        meta=dict(root='a'*64,owner=dict(node='node-1',host='127.0.0.1',port=9001,storage='00000000-0000-0000-0000-000000000001'),
                  revision=0,previous=None,parent=None,peers=[])
        return dict(meta=meta,records={},raw=m.future.frame(meta,{}))

    def test_interleaved_owners_keep_separate_exact_transactions(self):
        rows=[event('unrelated')]
        for point in m.WRITES:rows.extend([event(point),event(point,'node-2')])
        tx,used=m.observations(rows)
        self.assertEqual([('node-1',1,13),('node-2',2,14)],[(v['node'],v['start'],v['end']) for v in tx])
        self.assertEqual(set(range(1,15)),used)

    def test_force_rename_duplicate_and_missing_are_rejected(self):
        rows=[event(p) for p in m.WRITES]
        for changed in (rows[:3]+rows[4:],rows[:3]+[rows[5],rows[3],rows[4],rows[6]],rows[:3]+[rows[2]]+rows[3:]):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'^joining future exact write force order$'):
                m.observations(changed)
        with self.assertRaisesRegex(ValueError,'^joining future incomplete durable write$'):m.observations(rows[:-1])

    def test_unknown_recovery_or_claimed_event_fields_fail_closed(self):
        for row,reason in [(event('FUTURE_RETENTION_DISCARDED'),'unsupported event'),
                           (dict(event(m.WRITES[0]),claimedRevision=1),'event shape'),
                           (event(m.WRITES[0],scope='continuation-owner'),'event shape')]:
            with self.subTest(row=row),self.assertRaisesRegex(ValueError,'^joining future '+reason+'$'):m.observations([row])

    def test_scoped_write_cannot_cross_owner_lifetimes(self):
        rows=[event(p,'node-4','continuation-owner') for p in m.WRITES]
        rows[-1]['scope']='initial-owner'
        with self.assertRaisesRegex(ValueError,'^joining future exact write force order$'):m.observations(rows)

    def test_transaction_requires_one_unused_exact_scope_inside_bounds(self):
        reader=self.reader();reader.tx=[dict(node='node-4',scope='continuation-owner',start=3,end=9)]
        self.assertEqual(3,reader.transaction('node-4',2,10)['start'])
        with self.assertRaisesRegex(ValueError,'^joining future original write owner$'):reader.transaction('node-4',2,10)
        reader.used.clear();reader.tx[0]['scope']='initial-owner'
        with self.assertRaisesRegex(ValueError,'^joining future original write owner$'):reader.transaction('node-4',2,10)
        for lower,upper in [(3,10),(2,9)]:
            with self.assertRaisesRegex(ValueError,'^joining future exact bounded write count$'):reader.transaction('node-4',lower,upper)

    def test_revision_chain_accumulates_instead_of_restarting_from_snapshot(self):
        reader=self.reader();reader.state['node-1']=self.initial();first=reader.state['node-1']['raw']
        for index in (1,2):
            before=reader.state['node-1'];meta=dict(before['meta'],revision=index,previous=m.sha(before['raw']))
            reader.change('node-1',meta,{},dict(start=index*10,end=index*10+6),'clear',index)
        self.assertEqual(2,reader.state['node-1']['meta']['revision'])
        self.assertEqual(reader.steps[0]['after'],reader.steps[1]['before'])
        with self.assertRaisesRegex(ValueError,'^joining future exact continuous ledger: old: node-1$'):
            reader.compare('node-1',{m.future.FILE:first},'old')

    def test_wrong_owner_revision_or_predecessor_cannot_advance_state(self):
        for field,value in [('root','b'*64),('owner',dict(node='node-2')),('revision',3),('previous','c'*64)]:
            reader=self.reader();reader.state['node-1']=self.initial();before=copy.deepcopy(reader.state)
            meta=dict(before['node-1']['meta'],revision=1,previous=m.sha(before['node-1']['raw']));meta[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining future exact revision predecessor$'):
                reader.change('node-1',meta,{},dict(start=1,end=7),'record',1)
            self.assertEqual(before,reader.state)

    def test_applied_snapshot_is_compared_before_deriving_next_target(self):
        reader=self.reader();reader.state['node-1']=self.initial()
        reader.base=SimpleNamespace(phases={(1,'node-1'):{}})
        reader.model=SimpleNamespace(phases=[{}],owner=Mock(return_value={m.future.FILE:b'unrelated'}))
        with self.assertRaisesRegex(ValueError,'^joining future exact continuous ledger: applied-1: node-1$'):reader.phase(1,'node-1')

    def test_completion_requires_exact_scope_order_and_single_occurrence(self):
        rows=[event('start'),event(m.RETURNS[0],'node-4','continuation-owner'),event('end')]
        reader=self.reader(rows);self.assertEqual(1,reader.callback('node-4',m.RETURNS[0],0,2))
        with self.assertRaisesRegex(ValueError,'^joining future original completion owner$'):reader.callback('node-4',m.RETURNS[0],0,2)
        reader.callbacks.clear();rows[1]['scope']='initial-owner'
        with self.assertRaisesRegex(ValueError,'^joining future original completion owner$'):reader.callback('node-4',m.RETURNS[0],0,2)
        with self.assertRaisesRegex(ValueError,'^joining future exact completion lifetime:'):reader.callback('node-4',m.RETURNS[0],1,2)

    def test_reopen_requires_file_then_directory_before_accept_recovery(self):
        names=['CURRENT_VALIDATED','RETENTION_RECOVERY_PARENT_FORCED',*m.RESEAL,'ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED']
        reader=self.reader([event(v) for v in names]);reader.state['node-1']=self.initial()
        with patch.object(m.disk,'inventory',return_value={m.future.FILE:reader.state['node-1']['raw']}):reader.reopen('node-1',None,3)
        self.assertEqual({2,3},reader.callbacks);self.assertEqual(1,reader.reseals)
        reader.events[2],reader.events[3]=reader.events[3],reader.events[2]
        with self.assertRaisesRegex(ValueError,'^joining future reopen force order$'):reader.reopen('node-1',None,2)
        reader.events=[event(v) for v in names[:2]+names[4:]+names[2:4]]
        with self.assertRaisesRegex(ValueError,'^joining future reopen before accept recovery$'):reader.reopen('node-1',None,5)

    def test_original_authority_failure_stops_all_new_replay(self):
        with patch.object(m.a.n.s.collection,'inventory',return_value={}),patch.object(m.a,'validate',side_effect=ValueError('authority')),patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^authority$'):m.validate('/unused')
            replay.assert_not_called()

    def test_validation_keeps_remaining_qualification_false_and_checks_immutability(self):
        with patch.object(m.a.n.s.collection,'inventory',return_value={}),patch.object(m.a,'validate',return_value={}),patch.object(m,'replay',return_value={}):
            result=m.validate('/unused')
        self.assertTrue(result['futureLedgerCompositionQualified'])
        for name in ('learnerLedgerCompositionQualified','sameViewPhysicalQualified','completePhysicalQualified','phase3Complete','processDeathQualified'):
            self.assertIs(False,result[name])
        with patch.object(m.a.n.s.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(m.a,'validate',return_value={}),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining future original changed$'):m.validate('/unused')

    def test_worker_bounds_and_original_first_prevent_unqualified_mutations(self):
        for value in (0,5,True,1.1):
            with patch.object(m,'validate') as original,self.assertRaisesRegex(ValueError,'^joining future replay workers$'):m.qualify('/unused',workers=value)
            original.assert_not_called()
        with patch.object(m,'validate',side_effect=ValueError('authority')),patch.object(m,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^authority$'):m.qualify('/unused',workers=4)
            pool.assert_not_called()

    def negative(self,change=None,error=None,accepted=False):
        before=dict(files={'original':'hash','events.json':'hash','wire.json':'hash'},directories=['empty'])
        after=copy.deepcopy(before);events=[event('CURRENT_VALIDATED')];changed=copy.deepcopy(events)
        if change=='file':after['files']['wire.json']='changed'
        elif change=='directory':after['directories']=[]
        elif change=='observation':changed[0]['event']='CURRENT_DIRECTORY_FORCED'
        name='unbound-write';target=Mock(side_effect=None if accepted else ValueError(error or m.NEGATIVES[name]))
        with patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),patch.object(m.a.n.s.collection,'inventory',return_value=after), \
                patch.object(m.a.n.s.collection,'read_json',side_effect=[events,changed]),patch.object(m,'replay',target):
            return m.negative('/unused',before,name)

    def test_negative_cannot_change_files_wire_directories_or_unrelated_observations(self):
        for change,reason in [('file','original files'),('directory','original files'),('observation','other observations')]:
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining future negative changed '+reason+'$'):self.negative(change)

    def test_wrong_rejection_or_accepted_mutation_cannot_pass(self):
        with self.assertRaisesRegex(ValueError,'^joining future unrelated negative:'):self.negative(error='unrelated')
        with self.assertRaisesRegex(ValueError,'^joining future accepted mutation:'):self.negative(accepted=True)
        self.assertTrue(self.negative()['originalFilesAndOtherObservationsUnchanged'])


if __name__=='__main__':unittest.main()
