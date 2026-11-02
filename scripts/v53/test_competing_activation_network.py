"""Bounded incomplete transfers are observable failures, never authority."""
import base64
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import competing_activation_network as m


def incomplete():
    raw=b'original selected record';digest=m.sha(raw)
    ballot=dict(counter=2,proposer='node-1',incarnation='00000000-0000-0000-0000-000000000001')
    header=dict(root='a'*64,view='b'*64,ballot=ballot,sender=dict(node='node-2'),recipient=dict(node='node-1'),
                trace='00000000-0000-0000-0000-000000000002')
    identifier='00000000-0000-0000-0000-000000000003'
    payload=dict(id=identifier,action='REQUEST',offset=0,digest=digest,bytes='')
    def exchange(sequence,kind,answer,response,at):
        request=dict(header,sequence=sequence,payload=payload)
        return dict(kind=kind,answer=answer,request=request,response=dict(request,sender=header['recipient'],
                    recipient=header['sender'],payload=response),sent=at,received=at+1,offered=at+2,delivered=at+3)
    offer=exchange(1,'CHUNK','SOURCE_OFFER',dict(id=identifier,kind='RECORD',digest=digest,bytes=len(raw)),2)
    chunk=exchange(2,'CHUNK','CHUNK',dict(id=identifier,action='DATA',offset=0,digest=digest,bytes=base64.b64encode(raw).decode()),6)
    value=dict(sender='node-2',peer='node-1',first=digest,ballot=ballot,ordered=[offer,chunk])
    phase=SimpleNamespace(sources=[value],unfinished=0)
    attempts=[dict(kind='CHUNK',request=row['request'],sent=row['sent'],received=row['received']) for row in (offer,chunk)]
    request=dict(header,sequence=3,payload=dict(id=identifier,digest=digest))
    attempts.extend(dict(kind='TRANSFER_COMMIT',request=copy.deepcopy(request),sent=at,received=at+1) for at in (10,12,14))
    return phase,attempts,[offer,chunk],raw,ballot,'node-2','node-1',0,20


class CompetingActivationNetworkTest(unittest.TestCase):
    def test_original_publication_failure_stops_network_interpretation(self):
        with patch.object(m.publication,'Replay') as replay,patch.object(m.net.net,'Phase') as phase:
            replay.return_value.run.side_effect=ValueError('invalid original')
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.validate('/original')
            phase.assert_not_called()

    def test_incomplete_transfer_remains_unfinished_without_synthesizing_commit(self):
        args=incomplete();before=copy.deepcopy(args[1:3]);result=m.incomplete_selected(*args)
        self.assertEqual({10,12,14},result);self.assertEqual(1,args[0].unfinished)
        self.assertEqual([],args[0].sources);self.assertEqual(before,args[1:3])

    def test_received_bytes_do_not_make_a_commit_or_install_ack(self):
        args=incomplete();args[2].append(dict(kind='TRANSFER_COMMIT',request=args[1][-1]['request']))
        with self.assertRaisesRegex(ValueError,'commit must stay unanswered'):m.incomplete_selected(*args)
        self.assertEqual(0,args[0].unfinished);self.assertEqual(1,len(args[0].sources))

    def test_missing_extra_or_changed_commit_attempts_refuse(self):
        for mode in ('missing','extra','changed','no-receive','wrong-sequence'):
            args=incomplete()
            if mode=='missing':args[1].pop()
            elif mode=='extra':args[1].append(copy.deepcopy(args[1][-1]))
            elif mode=='changed':args[1][-1]['request']['payload']['digest']='f'*64
            elif mode=='no-receive':args[1][-1]['received']=None
            else:args[1][-1]['request']['sequence']=4
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'commit must stay unanswered'):
                m.incomplete_selected(*args)

    def test_commit_attempt_order_and_original_request_inventory_are_required(self):
        args=incomplete();args[1][3]['sent']=10
        with self.assertRaisesRegex(ValueError,'ordered commit attempts'):m.incomplete_selected(*args)
        args=incomplete();args[1].insert(0,copy.deepcopy(args[1][0]))
        with self.assertRaisesRegex(ValueError,'complete attempts'):m.incomplete_selected(*args)

    def test_offer_type_extent_and_exact_original_bytes_are_required(self):
        for mode in ('type','size','data','hash','offset'):
            args=incomplete();offer,chunk=args[2]
            if mode=='type':offer['response']['payload']['kind']='CAPSULE'
            elif mode=='size':offer['response']['payload']['bytes']+=1
            elif mode=='data':chunk['response']['payload']['bytes']=base64.b64encode(b'forged').decode()
            elif mode=='hash':chunk['response']['payload']['digest']='f'*64
            else:chunk['request']['payload']=dict(chunk['request']['payload'],offset=1)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'exact original bytes'):
                m.incomplete_selected(*args)

    def test_transfer_must_be_delivered_while_original_source_is_available(self):
        args=incomplete();args[2][1]['delivered']=None
        with self.assertRaisesRegex(ValueError,'causal prefix'):m.incomplete_selected(*args)
        args=list(incomplete());args[-1]=9
        with self.assertRaisesRegex(ValueError,'causal prefix'):m.incomplete_selected(*args)
        args=incomplete();args[2][1]['sent']=4
        with self.assertRaisesRegex(ValueError,'transfer next before delivery'):m.incomplete_selected(*args)

    def test_another_owner_ballot_or_trace_cannot_supply_missing_selection(self):
        for mode in ('owner','ballot','trace'):
            args=incomplete()
            if mode=='owner':args[0].sources[0]['peer']='node-3';reason='original transfer'
            elif mode=='ballot':args[0].sources[0]['ballot']=dict(counter=3);reason='exact prefix'
            else:args[2][1]['request']['trace']='00000000-0000-0000-0000-000000000004';reason='exact original bytes'
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,reason):m.incomplete_selected(*args)

    def test_higher_promise_alone_does_not_retire_old_source(self):
        cap=dict(node='node-1',basisId='old')
        replay=SimpleNamespace(events=[dict(node='node-1',event='PROMISE_FORCED')]*10,transactions=[])
        self.assertEqual(10,m.end_of_source(replay,cap))
        replay.events[6]=dict(node='node-1',event='SOURCE_RETIREMENT_CREATED')
        replay.transactions=[dict(node='node-1',start=3,end=8,decisions=[dict(identifier='old')])]
        self.assertEqual(6,m.end_of_source(replay,cap))
        replay.transactions.append(dict(node='node-2',start=4,end=9,decisions=[dict(identifier='old')]))
        self.assertEqual(6,m.end_of_source(replay,cap))

    def test_duplicate_source_retirement_and_reused_grant_boundaries_refuse(self):
        cap=dict(node='node-1',basisId='old',returnEvent=4)
        replay=SimpleNamespace(events=[dict(node='node-1',event='PROMISE_FORCED')]+[{}]*2+
            [dict(node='node-1',event='SOURCE_RETIREMENT_CREATED')]+[{}]*2,
            transactions=[dict(node='node-1',start=3,end=5,decisions=[dict(identifier='old')])]*2,
            by_basis={'prior':dict(node='node-1',returnEvent=2)})
        with self.assertRaisesRegex(ValueError,'retired twice'):m.end_of_source(replay,cap)
        with self.assertRaisesRegex(ValueError,'another grant'):m.point(replay,cap,'PROMISE_FORCED')

    def test_invalid_original_never_counts_as_successful_negative(self):
        with patch.object(m,'validate',side_effect=ValueError('original')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            mutate.assert_not_called()

    def test_unrelated_rejection_and_accepted_mutation_refuse_qualification(self):
        for value,reason in ((ValueError('other'),'unrelated competing activation negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(m,'validate',side_effect=[{},value]), \
                    patch.object(m.publication.preceding.prefix.collection.h,'inventory',return_value={}), \
                    patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')


if __name__=='__main__':unittest.main()
