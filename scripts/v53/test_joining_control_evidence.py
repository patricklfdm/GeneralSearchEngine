"""Control authority boundaries; synthetic cases do not replace native replay."""
import copy
import unittest
from unittest.mock import patch

from . import joining_control_evidence as c
from . import test_joining_export_evidence as fixture


class JoiningControlEvidenceTest(unittest.TestCase):
    def inputs(self):
        base=fixture.JoiningExportEvidenceTest();windows,q=base.inputs();own=windows[1]
        state=c.catalog(own);joining=next(v for v in state['identities'] if v['node']=='node-4')
        request=dict(root=state['root'],number=1,expected=q['view'],kind='ADD',target=state['identities'])
        state.update(active=1,results=[dict(request=request,phase='RESERVED',prepared=None,receipt=None,binding=None,revision=0,terminalIndex=None)])
        raw=c.f.encode('records','CATALOG',state);own['packet']['capsule']['catalog']=c.sha(raw);own['packet']['objects'][c.sha(raw)]=raw
        q.update(sender=joining,ballot=dict(counter=1,proposer=joining['node'],incarnation=joining['storage']))
        values=base.values(q,[('e'*64,b'original','RECORD')])
        values[0]['offer']['request'].update(sequence=1)
        values[0]['offer']['request']['payload'].update(action='REQUEST',offset=0,bytes='')
        return own,joining,request,values

    def test_reservation_requires_active_pre_joint_nonvoting_identity(self):
        own,joining,request,_=self.inputs();self.assertEqual(request,c.reservation(own,joining)['request'])
        state=c.catalog(own)
        for mutation in ('terminal','inactive','joint','voter'):
            changed=copy.deepcopy(state)
            if mutation=='terminal':changed['results'][0]['phase']='CANCELLED'
            elif mutation=='inactive':changed['active']=None
            elif mutation=='joint':changed['cut']['view']['operation']='e'*64
            else:changed['cut']['view']['old'].append(joining['node'])
            with self.subTest(mutation=mutation),patch.object(c,'catalog',return_value=changed),self.assertRaisesRegex(ValueError,'joining control (original reservation|active pre-joint learner)'):
                c.reservation(own,joining)

    def test_original_learner_correlation_does_not_become_a_voter_ballot(self):
        own,joining,request,values=self.inputs();c.initial(values,own,learner_request=request)
        changed=copy.deepcopy(values);changed[0]['offer']['request']['ballot']['counter']=2
        with self.assertRaisesRegex(ValueError,'^joining control original learner correlation$'):c.initial(changed,own,learner_request=request)
        changed=copy.deepcopy(values);changed[0]['offer']['request']['view']='f'*64
        with self.assertRaisesRegex(ValueError,'^joining control original learner correlation$'):c.initial(changed,own,learner_request=request)

    def test_initial_export_needs_original_identity_and_first_empty_request(self):
        own,joining,request,values=self.inputs()
        for field,value in [('sequence',2),('payload',dict(values[0]['offer']['request']['payload'],offset=1))]:
            changed=copy.deepcopy(values);changed[0]['offer']['request'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining control initial request$'):c.initial(changed,own,learner_request=request)
        changed=copy.deepcopy(values);changed[0]['offer']['request']['ballot']['incarnation']='00000000-0000-0000-0000-000000000099'
        with self.assertRaisesRegex(ValueError,'^joining control permanent correlation$'):c.initial(changed,own,learner_request=request)

    def test_exact_alias_cannot_authorize_changed_control_body(self):
        own,joining,request,values=self.inputs();c.exact(values,'e'*64,b'original')
        for reference,raw in [('f'*64,b'original'),('e'*64,b'changed')]:
            with self.assertRaisesRegex(ValueError,'^joining control exact original export$'):c.exact(values,reference,raw)

    def test_fragment_requires_latest_settled_grant_at_unchanged_current_cut(self):
        own,joining,request,_=self.inputs();cap=own['packet']['capsule']
        source=dict(node=own['node'],start=2,end=90,value=dict(cut=cap['cut'],view=request['expected'],accepted=None))
        events=[dict(node=own['node'],event='none') for _ in range(30)]
        self.assertEqual(source,c.active_source([source],events,own,10,20))
        events[15]['event']='PROMISE_FORCED'
        with self.assertRaisesRegex(ValueError,'^joining control active settled grant lifetime$'):c.active_source([source],events,own,10,20)
        events[15]['event']='SELECTED_FORCED'
        self.assertEqual(source,c.active_source([source],events,own,10,20))
        with self.assertRaisesRegex(ValueError,'^joining control active settled grant lifetime$'):c.active_source([source],events,own,10,20,unselected=True)
        source['value']['accepted']={'entry':'e'*64}
        with self.assertRaisesRegex(ValueError,'^joining control active settled grant lifetime$'):c.active_source([source],[],own,10,20)

    def test_learner_offer_waits_for_delivered_recording_and_retains_original_owner(self):
        own,joining,request,values=self.inputs();replay=c.Replay.__new__(c.Replay)
        permit=dict(node=own['node'],request=request,learner=joining,start=10,end=30,cut=own['packet']['capsule']['cut'])
        replay.recordings=[permit]
        self.assertEqual('recorded',replay.learner_content(values,own))
        for change in (dict(start=11),dict(end=13),dict(node='node-1'),dict(request=dict(request,number=2))):
            replay.recordings=[dict(permit,**change)]
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining control learner export without live recording$'):replay.learner_content(values,own)

    def test_completion_cannot_reuse_a_closed_owner_after_native_reopen(self):
        events=[dict(node='node-4',scope='initial-owner',event='other') for _ in range(20)]
        events[1]['event']='CURRENT_VALIDATED'
        events[10]=dict(node='node-4',scope='retaining-owner',event='CURRENT_VALIDATED')
        events[15]=dict(node='node-4',scope='continuation-owner',event='CURRENT_VALIDATED')
        c.owner_lifetime(events,'node-4','initial-owner',2,9)
        c.owner_lifetime(events,'node-4','continuation-owner',16,19)
        for start,end in ((1,8),(9,10),(16,19)):
            with self.assertRaisesRegex(ValueError,'^joining control original owner lifetime$'):c.owner_lifetime(events,'node-4','initial-owner',start,end)

    def test_hint_must_wait_for_the_original_remote_grant_delivery(self):
        own,joining,request,values=self.inputs();q=values[0]['offer']['request']
        ballot=dict(counter=6,proposer=own['node'],incarnation=own['identity']['storage'])
        sources=[dict(node=node,start=1,basis=node.encode(),value=dict(ballot=ballot)) for node in ('node-1','node-2')]
        by_node={v['node']:v for v in sources};replay=c.Replay.__new__(c.Replay)
        replay.model=type('Model',(),{'root':request['root']})();replay.events=[];replay.sources=sources;replay.rows=[]
        reply=dict(kind='PREPARE',request=dict(recipient=dict(node='node-1'),sender=dict(node='node-2'),ballot=ballot),
                   response=dict(payload=dict(basis=c.sha(b'node-1'))),delivered=9)
        with patch.object(c,'initial',return_value=q),patch.object(c,'joint'), \
                patch.object(c,'active_source',side_effect=lambda sources,events,original,*args,**kwargs:by_node[original['node']]), \
                patch.object(replay,'current',side_effect=lambda node,*args:dict(own,node=node)),patch.object(c,'exact'):
            with self.assertRaisesRegex(ValueError,'^joining control hint before delivered grant$'):replay.preparation(values,own)
            replay.rows=[reply];replay.preparation(values,own)
            reply['delivered']=10
            with self.assertRaisesRegex(ValueError,'^joining control hint before delivered grant$'):replay.preparation(values,own)

    def test_control_negative_driver_requires_valid_original_first(self):
        with patch.object(c,'validate',side_effect=ValueError('invalid original')),patch.object(c.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):c.qualify('/unused')
            copied.assert_not_called()

    def test_control_negative_cannot_change_physical_evidence(self):
        original=dict(files={'original.gsr':'digest'},directories=['directory'])
        changed=dict(files={'original.gsr':'changed'},directories=['directory'])
        with patch.object(c,'validate',return_value={}),patch.object(c.n.s.collection,'inventory',side_effect=[original,changed]), \
                patch.object(c.shutil,'copytree'),patch.object(c,'mutate'),patch.object(c.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining control negative changed physical inputs$'):c.qualify('/unused')
            network.assert_not_called()

    def test_control_negative_keeps_both_network_and_prior_export_gates(self):
        for failed in ('network','export'):
            with patch.object(c,'validate',return_value={}),patch.object(c.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                    patch.object(c.shutil,'copytree'),patch.object(c,'mutate'),patch.object(c.n,'network',side_effect=ValueError('bad network') if failed=='network' else None), \
                    patch.object(c.e,'replay',side_effect=ValueError('bad export') if failed=='export' else None),patch.object(c,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'^bad '+failed+'$'):c.qualify('/unused')
                replay.assert_not_called()

    def test_control_negative_rejects_unrelated_errors_and_accepted_mutations(self):
        for failure,reason in ((None,'joining control mutation accepted: root-alias'),
                               (ValueError('unrelated'),'joining unrelated control negative: root-alias: unrelated')):
            with patch.object(c,'validate',return_value={}),patch.object(c.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                    patch.object(c.shutil,'copytree'),patch.object(c,'mutate'),patch.object(c.n,'network'),patch.object(c.e,'replay'),patch.object(c,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):c.qualify('/unused')

    def test_prerequisite_export_failure_stops_control_replay(self):
        with patch.object(c.n.s.collection,'inventory',return_value={}),patch.object(c.e,'validate',side_effect=ValueError('invalid export')),patch.object(c,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^invalid export$'):c.validate('/unused')
            replay.assert_not_called()

    def test_original_inventory_must_stay_unchanged(self):
        with patch.object(c.n.s.collection,'inventory',side_effect=[{}, {'changed':1}]),patch.object(c.e,'validate'),patch.object(c,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'^joining control original changed$'):c.validate('/unused')


if __name__=='__main__':unittest.main()
