"""Pre-grant causal checks; synthetic records do not replace native evidence."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import competing_pregrant_evidence as m


def original():
    ballot=dict(counter=2,proposer='node-1',incarnation='one')
    higher=dict(counter=2,proposer='node-3',incarnation='three')
    events=[dict(node='node-2',event='NETWORK_SEND') for _ in range(12)]
    events[3]=dict(node='node-1',event='CURRENT_BEFORE_CAPTURE')
    events[5]=dict(node='node-1',event='NETWORK_REQUEST')
    promise=b'original higher promise'
    q=dict(ballot=higher,sender=dict(node='node-3'),recipient=dict(node='node-1'),payload=dict(promise=m.prefix.sha(promise)))
    attempts=[dict(kind='PREPARE',request=q,sent=4,received=5)]
    caps=[dict(node='node-3',ballot=higher,capturedEvent=1,promise=promise),
          dict(node='node-1',ballot=higher,basisSha256='remote',returnEvent=10)]
    allocation=dict(node='node-1',start=0,end=2,ballot=ballot)
    loss=dict(node='node-1',event='LOSS',detail='HIGHER_BALLOT',state='STARTING',rounds=1,pending=0,afterEvent=5)
    return events,attempts,caps,{'remote':7},allocation,loss,11


class CompetingPregrantEvidenceTest(unittest.TestCase):
    def test_same_counter_higher_proposer_fences_without_inventing_local_grant(self):
        args=original();before=copy.deepcopy(args);result=m.bind(*args)
        self.assertEqual(before,args)
        self.assertEqual((2,2),(result['ballot']['counter'],result['higherBallot']['counter']))
        self.assertFalse(result['localGrantCreated'])
        self.assertEqual((2,3,5,5,10),tuple(result[k] for k in ('allocation','capture','higherRequest','lossAt','remoteGrant')))

    def test_observed_loss_must_be_exact_initial_unready_round(self):
        for key,value in [('node','node-2'),('event','RESTART'),('detail','CONTACT_UNAVAILABLE'),('state','READY'),
                          ('rounds',2),('pending',1),('afterEvent',2),('afterEvent',11)]:
            args=original();args[5][key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'actual first-round loss'):m.bind(*args)

    def test_existing_local_grant_cannot_be_classified_as_pregrant_loss(self):
        args=original();args[2].append(dict(node='node-1',ballot=args[4]['ballot']))
        with self.assertRaisesRegex(ValueError,'unexpected local grant'):m.bind(*args)

    def test_capture_absence_duplicates_and_local_durable_writes_refuse(self):
        for change in ('missing','duplicate','promise','selected'):
            args=original()
            if change=='missing':args[0][3]=dict(node='node-1',event='NETWORK_SEND')
            else:args[0][4]=dict(node='node-1',event={'duplicate':'CURRENT_BEFORE_CAPTURE','promise':'PROMISE_FORCED','selected':'SELECTED_FORCED'}[change])
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original capture without writes'):m.bind(*args)

    def test_uncreated_promise_cannot_be_advertised(self):
        args=original();q=copy.deepcopy(args[1][0]);q['request'].update(sender=dict(node='node-1'),ballot=args[4]['ballot'])
        args[1].append(q)
        with self.assertRaisesRegex(ValueError,'advertise missing promise'):m.bind(*args)

    def test_loss_requires_exact_original_received_higher_request(self):
        for change in ('absent','not-received','late','early','same-ballot','lower-proposer','duplicate','other-owner'):
            args=original();v=args[1][0]
            if change=='absent':args[1].clear()
            elif change=='not-received':v['received']=None
            elif change=='late':v['received']=6
            elif change=='early':v['received']=3
            elif change=='same-ballot':v['request']['ballot']=args[4]['ballot']
            elif change=='lower-proposer':v['request']['ballot']=dict(args[4]['ballot'],proposer='node-0')
            elif change=='duplicate':args[1].append(copy.deepcopy(v))
            else:v['request']['recipient']['node']='node-2'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original higher PREPARE'):m.bind(*args)

    def test_higher_request_requires_earlier_exact_proposer_promise(self):
        for change in ('missing','late','alias','wrong-proposer','sent-after-receive'):
            args=original()
            if change=='missing':args[2].pop(0)
            elif change=='late':args[2][0]['capturedEvent']=4
            elif change=='alias':args[1][0]['request']['payload']['promise']='other'
            elif change=='wrong-proposer':args[1][0]['request']['sender']['node']='node-2'
            else:args[1][0]['sent']=6
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original higher promise'):m.bind(*args)

    def test_incoming_grant_is_distinct_and_strictly_after_observed_loss(self):
        for change in ('missing','before-loss','inverted'):
            args=original()
            if change=='missing':args[2].pop()
            elif change=='before-loss':args[3]['remote']=5
            else:args[3]['remote']=10
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'precedes incoming grant'):m.bind(*args)

    def test_invalid_original_lifecycle_stops_binding(self):
        with patch.object(m.lifecycle,'validate',side_effect=ValueError('original lifecycle')),patch.object(m,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'^original lifecycle$'):m.validate(SimpleNamespace(root='/original'),{},0)
            bind.assert_not_called()

    def test_lifecycle_anchor_maps_through_recorded_grant_annotations(self):
        events=[dict(node='node-1',event=str(i)) for i in range(5)]
        merged=events[:1]+[dict(event=m.prefix.g.EVENT)]+events[1:]
        replay=SimpleNamespace(root=Path('/original'),events=merged,attempts=[],by_basis={},starts={})
        allocation=dict(node='node-1',start=2,end=3)
        rows=[dict(node='node-1',event='ROUND_BEGIN',rounds=1,ordinal=1,afterEvent=0),
              dict(node='node-1',event='LOSS',ordinal=2,afterEvent=4)]
        with patch.object(m.lifecycle,'validate'),patch.object(m.prefix.p,'trace',return_value=events), \
                patch.object(m.prefix.p.n,'read',return_value=rows),patch.object(m,'bind',return_value={}) as bind:
            m.validate(replay,allocation,7)
            self.assertEqual(5,bind.call_args.args[5]['afterEvent'])
            self.assertEqual(4,rows[1]['afterEvent'])
            rows[0]['afterEvent']=2
            with self.assertRaisesRegex(ValueError,'round before allocation'):m.validate(replay,allocation,7)
            rows[0]['afterEvent']=0;rows.append(copy.deepcopy(rows[1]))
            with self.assertRaisesRegex(ValueError,'exact observed loss'):m.validate(replay,allocation,7)
            merged[0]=dict(node='other',event='changed')
            with self.assertRaisesRegex(ValueError,'original event mapping'):m.validate(replay,allocation,7)

    def test_invalid_integrated_original_never_qualifies_negatives(self):
        from . import competing_export_evidence as exports
        with patch.object(exports.Replay,'run',side_effect=ValueError('original')), \
                patch.object(m.prefix.collection.h,'inventory',return_value={}),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            mutate.assert_not_called()

    def test_original_negatives_require_exact_reason_and_real_rejection(self):
        from . import competing_export_evidence as exports
        reader=SimpleNamespace(partial=None,replay=SimpleNamespace(transactions=[]),
            run=lambda:dict(precondition=dict(pregrantLosses=[{}])))
        for value,reason in ((ValueError('other'),'unrelated competing pregrant negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(exports,'Replay',return_value=reader), \
                    patch.object(exports,'validate',side_effect=[value]),patch.object(m,'mutate'), \
                    patch.object(m.prefix.collection.h,'inventory',return_value={}),patch.object(m.shutil,'copytree'):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')


if __name__=='__main__':unittest.main()
