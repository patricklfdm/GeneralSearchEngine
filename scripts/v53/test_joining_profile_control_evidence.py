"""Conditional profile/control boundaries, not native cohort evidence."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_profile_control_evidence as p
from . import test_joining_export_evidence as export_fixture


def row(peer,delivered,*,trace='round',owner='node-1',intent='original',sent=2):
    return dict(kind='LEARNER_RETENTION_INTENT',delivered=delivered,sent=sent,
                request=dict(sender=dict(node=owner),recipient=dict(node=peer),trace=trace,
                             view='original-view',ballot={'counter':1},payload=dict(intent=intent)))


class ProfileControlTest(unittest.TestCase):
    def view(self,size):
        nodes=['node-'+str(i) for i in range(1,size+1)]
        return dict(old=nodes,new=list(nodes),operation=None)

    def test_four_and_five_voters_require_two_distinct_remote_deliveries(self):
        for size in (4,5):
            view=self.view(size)
            with self.assertRaisesRegex(ValueError,'^joining profile control original retention quorum$'):
                p.quorum_time(view,'node-1',[row('node-2',10)],100)
            self.assertEqual(30,p.quorum_time(view,'node-1',[row('node-3',30),row('node-2',10)],100))
        self.assertEqual(10,p.quorum_time(self.view(3),'node-1',[row('node-2',10)],100))

    def test_joint_sides_are_checked_separately(self):
        view=dict(old=['node-1','node-2','node-3'],new=['node-1','node-4','node-5'],operation='joint')
        with self.assertRaisesRegex(ValueError,'^joining profile control original retention quorum$'):
            p.quorum_time(view,'node-1',[row('node-2',10),row('node-3',11)],100)
        self.assertEqual(20,p.quorum_time(view,'node-1',[row('node-2',10),row('node-4',20)],100))

    def test_duplicate_self_and_foreign_ack_cannot_supply_a_vote(self):
        for rows in ([row('node-2',10),row('node-2',20)],[row('node-1',10)],[row('foreign',10)]):
            with self.subTest(rows=rows),self.assertRaisesRegex(ValueError,'^joining profile control distinct retention voters$'):
                p.quorum_time(self.view(4),'node-1',rows,100)
        with self.assertRaisesRegex(ValueError,'^joining profile control recording owner$'):
            p.quorum_time(self.view(4),'foreign',[row('node-2',10)],100)

    def test_undelivered_or_fenced_acks_never_complete_a_recording(self):
        for at in (None,50,51):
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'^joining profile control original retention quorum$'):
                p.quorum_time(self.view(5),'node-1',[row('node-2',10),row('node-3',at)],50)
        self.assertEqual(30,p.quorum_time(self.view(5),'node-1',[row('node-2',10),row('node-3',30),row('node-4',60)],50))
        for at in (True,-1,'30'):
            with self.assertRaisesRegex(ValueError,'^joining profile control retention delivery$'):
                p.quorum_time(self.view(4),'node-1',[row('node-2',at)],100)

    def test_authorization_starts_at_first_complete_majority_not_last_extra_reply(self):
        self.assertEqual(30,p.quorum_time(self.view(5),'node-1',[row('node-4',90),row('node-2',10),row('node-3',30)],100))

    def grouped(self,*,split=False,mixed=False):
        reader=p.Replay.__new__(p.Replay);reader.recordings=[];reader.rows=[];reader.groups=[];reader.model=SimpleNamespace(joining='node-5')
        view=self.view(4);own_by_round={}
        for ordinal in (1,2):
            own=dict(node='node-1',start=0,end=100,packet=dict(capsule=dict(cut=dict(view=view),marker=ordinal)))
            own_by_round['round-'+str(ordinal)]=own
            for peer,at in (('node-2',10*ordinal),('node-3',10*ordinal+3)):
                reader.rows.append(row(peer,at,trace='round-'+str(ordinal),intent='original-'+str(ordinal)))
            reader.groups.append([dict(raw=b'learner content',offer=dict(received=40,request=dict(sender=dict(node='node-5'),recipient=dict(node='node-1'),marker=ordinal)),commit=dict(offered=41))])
        if split:reader.rows[1]['request']['trace']='separate-round'
        if mixed:reader.rows[1]['request']['payload']['intent']='different'
        def derive(r):
            ordinal=1 if r['request']['trace'] in ('round-1','separate-round') else 2
            own=own_by_round['round-'+str(ordinal)]
            return dict(node='node-1',cut=own['packet']['capsule']['cut'],request={'number':ordinal},learner={'node':'node-5'},end=100,own=own)
        reader.retention_exchange=derive
        # Required endpoints come from two actual learner export groups. This
        # fixture maps each received time to its original generation.
        for ordinal,group in enumerate(reader.groups,1):
            group[0]['offer'].update(received=40+ordinal,offered=50+ordinal)
            group[0]['commit']['offered']=60+ordinal
        reader.current=lambda node,start,end: own_by_round['round-'+str(start-40)]
        return reader

    def grouped_run(self,reader):
        with patch.object(reader,'local_recording') as local,patch.object(p.e,'learner_alias',return_value='prefix'), \
             patch.object(p.c.disk,'anchor',side_effect=lambda cap:dict(marker=cap['marker'])):
            reader.quorum()
            return local

    def test_whole_round_groups_force_locally_once_before_first_send(self):
        reader=self.grouped();local=self.grouped_run(reader)
        self.assertEqual(2,local.call_count);self.assertEqual([13,23],[v['start'] for v in reader.recordings])
        self.assertEqual([2,2],[v.args[1] for v in local.call_args_list])

    def test_ack_from_another_trace_or_intent_cannot_complete_quorum(self):
        for variant,reason in ((dict(split=True),'original retention quorum'),(dict(mixed=True),'mixed retention round')):
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'^joining profile control '+reason+'$'):
                self.grouped_run(self.grouped(**variant))

    def test_complete_recordings_must_match_actual_required_export_endpoints(self):
        reader=self.grouped();reader.groups.pop()
        with self.assertRaisesRegex(ValueError,'^joining profile control complete recording endpoints$'):self.grouped_run(reader)

    def test_pending_old_reader_has_its_own_authority_not_a_learner_recording(self):
        reader=self.grouped()
        reader.groups.insert(0,[dict(offer=dict(received=0,request=dict(sender=dict(node='node-2'),recipient=dict(node='node-5'))),
                                    commit=dict(offered=1))])
        self.grouped_run(reader);self.assertEqual(2,len(reader.recordings))

    def test_frozen_source_transfer_uses_its_own_authority_across_generation_switch(self):
        reader=self.grouped();current=reader.current
        reader.groups.append([dict(raw=b'other content',offer=dict(received=70,offered=71,request=dict(sender=dict(node='node-5'),recipient=dict(node='node-1'),marker=3)),
                                   commit=dict(offered=90))])
        def window(node,start,end):
            if start!=70:return current(node,start,end)
            if end>=80:raise ValueError('joining export inactive current generation')
            return dict(node=node,packet=dict(capsule=dict(cut=dict(view=self.view(4)),marker=3)))
        reader.current=window
        with patch.object(reader,'local_recording'),patch.object(p.e,'learner_alias',side_effect=lambda own,q: 'prefix' if q['marker']<3 else None), \
             patch.object(p.c.disk,'anchor',side_effect=lambda cap:dict(marker=cap['marker'])):
            reader.quorum();self.assertEqual(2,len(reader.recordings))

    def frozen_group(self):
        reader=self.grouped();windows,q,source,values=export_fixture.JoiningExportEvidenceTest().switching_source()
        schema=p.e.f.catalog();basis=p.e.f.sample(schema['records']['BASIS']['schema'],schema['types'])
        basis.update(root=q['root'],view=q['view'],ballot=q['ballot'])
        source['basis']=p.e.f.encode('records','BASIS',basis);source['value']=basis
        values[0]['raw']=source['basis'];values[0]['offer']['request']['payload']['digest']=p.e.sha(source['basis'])
        reader.model.joining=q['sender']['node']
        for group in reader.groups:group[0]['offer']['request']['sender']=q['sender']
        reader.windows=windows;reader.sources=[source];reader.groups.append(values)
        current=reader.current
        reader.current=lambda node,start,end: p.e.current(windows,node,start,end) if node==q['recipient']['node'] else current(node,start,end)
        return reader

    def test_quorum_classifies_verified_frozen_basis_without_borrowing_current_generation(self):
        reader=self.frozen_group();self.grouped_run(reader)
        self.assertEqual(2,len(reader.recordings))

    def test_basis_kind_alone_cannot_skip_quorum_source_authorization(self):
        reader=self.frozen_group();reader.groups[-1][1]['raw']=b'foreign promise'
        with self.assertRaisesRegex(ValueError,'^joining export exact frozen source$'):self.grouped_run(reader)

    def test_actual_learner_export_cannot_cross_generation_switch(self):
        reader=self.grouped();current=reader.current
        def window(node,start,end):
            if end>=60:raise ValueError('joining export inactive current generation')
            return current(node,start,end)
        reader.current=window
        with self.assertRaisesRegex(ValueError,'^joining export inactive current generation$'):self.grouped_run(reader)

    def test_all_profile_head_voters_come_from_the_original_intent_certificate(self):
        for profile in p.PROFILES:
            size,kind,old,new=p.topology(profile);voters=old[:size//2+1]
            model=SimpleNamespace(kind=kind,joining=new[-1],old=old,phases=[{'CERTIFICATE':b'original'}]*9)
            context=SimpleNamespace(model=model,events=[])
            with patch.object(p.exports,'context',return_value=context),patch.object(p.c.n.phase,'blocks',return_value={}), \
                 patch.object(p.f,'decode',return_value=dict(proofs=[dict(voter=v) for v in voters])):
                reader=p.Replay('/unused',profile)
                self.assertEqual(set(voters),reader.expected_confirmations)
                self.assertEqual(len(voters),reader.expected_controls['retention'])

    def test_foreign_intent_voter_is_rejected(self):
        model=SimpleNamespace(kind='ADD',joining='node-5',old=['node-1'],phases=[{'CERTIFICATE':b'original'}]*9)
        with patch.object(p.exports,'context',return_value=SimpleNamespace(model=model,events=[])),patch.object(p.c.n.phase,'blocks',return_value={}), \
             patch.object(p.f,'decode',return_value=dict(proofs=[dict(voter='node-5')])):
            with self.assertRaisesRegex(ValueError,'^joining profile control original INTENT voters$'):p.Replay('/unused','4-ADD')

    def test_larger_head_confirmation_requires_actual_joiner_and_all_original_old_proofs(self):
        for joining in ('node-5','node-6'):
            reader=p.Replay.__new__(p.Replay);reader.root=Path('/unused');reader.confirmations={}
            reader.expected_confirmations={'node-1','node-2','node-3'}
            reader.events=[dict(node=joining,scope='pending-intent',event='LEARNER_JOINING_RETAIN_TRANSFERRED')];reader.rows=[]
            reader.model=SimpleNamespace(joining=joining,root='root',states=[{}]*8+[dict(cut={'index':8},application={})],catalogs=[b'']*8+[b'catalog'])
            endpoint=dict(cut={'index':8},catalog=p.e.sha(b'catalog'),application={})
            for node in sorted(reader.expected_confirmations):
                at=len(reader.events)
                reader.events.extend(dict(node=joining,event='observation') for _ in range(4));reader.events[at+1]['scope']='retained-head'
                reader.rows.append(dict(kind='LEARNER_HEAD_QUERY',answer='LEARNER_HEAD_ACK',sent=at,received=at+1,offered=at+2,delivered=at+3,
                    request=dict(sender=dict(node=node),recipient=dict(node=joining)),response={}))
                reader.events.extend(dict(node=node,event=point) for point in p.c.RETENTION_FORCE+['LEARNER_RETENTION_CONFIRMATION_BEFORE_RETURN'])
            reader.current=lambda node,*_:dict(node=node,path=node,end=len(reader.events),packet=dict(capsule=dict(cut={'index':9})))
            with patch.object(p.c,'reservation',return_value=dict(phase='JOINT',request={})),patch.object(p.f,'encode',return_value=b'wire'), \
                 patch.object(p.c.learner,'confirmation',return_value=endpoint),patch.object(p.c.disk,'inventory',return_value={p.c.learner.FILE:b'before'}), \
                 patch.object(p.c.init,'confirmed_learner',return_value=b'after'),patch.object(p.c.init.transition,'require_coverage'), \
                 patch.object(p.c.learner,'decode',return_value=dict(plan={})): 
                reader.heads();self.assertEqual(reader.expected_confirmations,set(reader.confirmations))
                reader.confirmations={};reader.rows[-1]['request']['recipient']['node']='node-4'
                with self.assertRaisesRegex(ValueError,'^joining control original retained head$'):reader.heads()

    def test_composed_result_requires_all_original_transfers_and_preserves_phase_scope(self):
        prior=dict(exports={},precondition=dict(network=dict(committedTransfers=100,transferSessions=50,rejectedTransferAttempts=2)))
        result=dict(observedCommittedContents=100,observedContentSessions=48)
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.exports,'validate',return_value=prior),patch.object(p,'replay',return_value=result):
            answer=p.validate('/unused','4-ADD');self.assertTrue(answer['observedControlExportsQualified'])
            for flag in ('allMembershipProfilesQualified','maintenanceAndPeerCompositionQualified','processDeathQualified','phase3Complete'):
                self.assertFalse(answer[flag])
            for key in result:
                result[key]-=1
                with self.assertRaisesRegex(ValueError,'^joining profile control complete transfer coverage$'):p.validate('/unused','4-ADD')
                result[key]+=1

    def test_changed_original_is_rejected_after_composition(self):
        prior=dict(exports={},precondition=dict(network=dict(committedTransfers=100,transferSessions=50,rejectedTransferAttempts=2)))
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.exports,'validate',return_value=prior), \
             patch.object(p,'replay',return_value=dict(observedCommittedContents=100,observedContentSessions=48)):
            with self.assertRaisesRegex(ValueError,'^joining profile control original changed$'):p.validate('/unused','4-ADD')

    def test_invalid_original_does_not_reach_control_or_mutations(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.exports,'validate',side_effect=ValueError('invalid original')), \
             patch.object(p,'replay') as replay,patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused','4-ADD')
            replay.assert_not_called();copied.assert_not_called()

    def test_network_or_content_failure_is_not_a_control_rejection(self):
        for stage in ('network','export'):
            with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.c,'mutate'), \
                 patch.object(p.c.n,'network',side_effect=ValueError('bad network') if stage=='network' else None), \
                 patch.object(p.exports,'replay',side_effect=ValueError('bad export') if stage=='export' else None),patch.object(p,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'^bad '+stage+'$'):p.qualify('/unused','5-REPLACE')
                replay.assert_not_called()

    def test_negative_rejects_changed_physical_inputs(self):
        with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',side_effect=[dict(files={},directories=[]),dict(files={'altered':'hash'},directories=[])]), \
             patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.c,'mutate'),patch.object(p.c.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining profile control negative changed physical inputs$'):p.qualify('/unused','4-REPLACE')
            network.assert_not_called()

    def test_missing_required_mutation_target_fails_explicitly(self):
        with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
             patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.c,'mutate',side_effect=StopIteration):
            with self.assertRaisesRegex(ValueError,'^joining profile control missing negative target: root-alias$'):p.qualify('/unused','3-ADD')

    def test_unrelated_errors_and_accepted_mutations_do_not_pass(self):
        for failure,message in ((None,'joining profile control mutation accepted: root-alias'),(ValueError('other'),'joining profile unrelated control negative: root-alias: other')):
            with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.c,'mutate'), \
                 patch.object(p.c.n,'network'),patch.object(p.exports,'replay'),patch.object(p,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,'^'+message+'$'):p.qualify('/unused','3-ADD')


if __name__=='__main__':unittest.main()
