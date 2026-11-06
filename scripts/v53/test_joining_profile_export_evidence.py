"""Conditional profile fixtures; these are not five native executions."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_profile_export_evidence as p
from . import test_joining_export_evidence as fixture

e=p.e


class JoiningProfileExportTest(unittest.TestCase):
    def generations(self,profile,*,lagging=False):
        _,kind,old,new=p.topology(profile);joining=new[-1];nodes=(*old,joining)
        selected=dict(cut=dict(index=0),sources=[dict(voter=v) for v in (old[0],joining)])
        records={b's':selected,b'c1':dict(index=1,proofs=[dict(voter=v) for v in (old[0],joining)]),
                 b'c2':dict(index=2,proofs=[dict(voter=old[0])])}
        phases=[dict(SELECTED=b's',CERTIFICATE=b'c1')]
        if lagging:phases.append(dict(SELECTED=b's',CERTIFICATE=b'c2'))
        model=SimpleNamespace(joining=joining,old=old,kind=kind,phases=phases,states=[dict(cut=dict(index=2 if lagging else 1))])
        events=[dict(node=joining,scope='initial-owner',event='CURRENT_DIRECTORY_FORCED')]
        for node in (old[0],joining):
            for point in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'):
                events += [dict(node=node,event='INSTALL_SELECTOR_RENAMED'),dict(node=node,event=point)]
        if lagging:
            events += [dict(node=old[0],event='INSTALL_SELECTOR_RENAMED'),dict(node=old[0],event='PUBLICATION_BEFORE_RETURN'),
                       dict(node=joining,event='INSTALL_SELECTOR_RENAMED'),dict(node=joining,event='ADOPTION_INSTALL_BEFORE_RETURN')]
        events.append(dict(node=old[0],event='history-end'))
        def inventory(path):
            node=joining if Path(path).name=='replica' else Path(path).name
            return {'node.gsr':node.encode(),'g/generation.gsr':b'original manifest'}
        def decode(raw, *_):return records[raw] if raw in records else dict(identity=dict(node=raw.decode()))
        for row in events:
            if row.get('node')==joining:row['scope']='initial-owner'
        return model,nodes,events,inventory,decode

    def windows(self,profile,*,lagging=False,change=None):
        model,nodes,events,inventory,decode=self.generations(profile,lagging=lagging)
        if change:change(events,model)
        with patch.object(e.disk,'inventory',side_effect=inventory),patch.object(e.disk,'current',return_value=('g/',{},{})), \
             patch.object(e.f,'decode',side_effect=decode):
            return e.generation_windows('/unused',events,model,nodes=nodes,final_adoption=True),model,events

    def test_all_profiles_bind_actual_joiner_and_unused_original_voters(self):
        for profile in p.PROFILES:
            with self.subTest(profile=profile):
                windows,model,events=self.windows(profile)
                self.assertEqual(set((*model.old,model.joining)),{v['node'] for v in windows})
                joined=[v for v in windows if v['node']==model.joining]
                self.assertEqual(['joining-originals-native/replica','joining-installed-0/replica',
                                  'joining-published-1/replica'],[v['path'] for v in joined])
                for node in model.old[1:]:
                    original=[v for v in windows if v['node']==node]
                    self.assertEqual(1,len(original));self.assertEqual((-1,len(events)),(original[0]['start'],original[0]['end']))

    def test_lagging_joiner_owns_the_derived_adoption_only_after_its_return(self):
        windows,model,_=self.windows('5-REPLACE',lagging=True)
        joined=[v for v in windows if v['node']==model.joining]
        self.assertEqual('joining-after-final-recovery/replica',joined[-1]['path'])
        self.assertLess(joined[-2]['end'],joined[-1]['start'])
        with self.assertRaisesRegex(ValueError,'^joining export inactive current generation$'):
            e.current(windows,model.joining,joined[-2]['end'],joined[-1]['start'])

    def test_source_predecessors_require_observed_continuous_journal_ownership(self):
        windows,model,_=self.windows('5-REPLACE')
        joined=[v for v in windows if v['node']==model.joining]
        self.assertNotIn('sourcePredecessor',joined[0])
        for before,after in zip(joined,joined[1:]):
            self.assertEqual((before['start'],before['end']),after['sourcePredecessor'])
        def close(events,model):
            at=next(i for i,v in enumerate(events) if v.get('node')==model.joining and v['event']=='INSTALL_SELECTOR_RENAMED')
            events.insert(at,dict(node=model.joining,scope='initial-owner',event='JOINING_OWNER_CLOSE_BEGIN'))
        windows,model,_=self.windows('5-REPLACE',change=close)
        joined=[v for v in windows if v['node']==model.joining]
        self.assertNotIn('sourcePredecessor',joined[1])
        def reopen(events,model):
            for row in events:
                if row.get('node')==model.joining and row['event']=='INSTALL_BEFORE_RETURN':row['scope']='continuation-owner'
        windows,model,_=self.windows('5-REPLACE',change=reopen)
        joined=[v for v in windows if v['node']==model.joining]
        self.assertTrue(all('sourcePredecessor' not in v for v in joined))

    def test_old_voter_cold_scope_cannot_be_joined_to_its_previous_owner(self):
        def cold(events,model):
            for row in events:
                if row['node']==model.old[0] and row['event']=='PUBLICATION_BEFORE_RETURN':
                    row['scope']='joint-floor-reopened'
        windows,model,_=self.windows('5-REPLACE',change=cold)
        old=[v for v in windows if v['node']==model.old[0]]
        self.assertEqual((old[0]['start'],old[0]['end']),old[1]['sourcePredecessor'])
        self.assertNotIn('sourcePredecessor',old[2])

    def test_observed_adoption_cannot_invent_a_generation_if_joiner_is_current(self):
        def extra(events,model):
            events[-1:-1]=[dict(node=model.joining,event='INSTALL_SELECTOR_RENAMED'),
                            dict(node=model.joining,event='ADOPTION_INSTALL_BEFORE_RETURN')]
        with self.assertRaisesRegex(ValueError,'^joining export complete generation timeline$'):
            self.windows('4-ADD',change=extra)

    def test_missing_adoption_or_early_return_is_rejected(self):
        def missing(events,model):
            events[:]=[v for v in events if v['event']!='ADOPTION_INSTALL_BEFORE_RETURN']
        def early(events,model):events[-3],events[-2]=events[-2],events[-3]
        for change,reason in ((missing,'complete generation timeline'),(early,'selector completion order')):
            with self.subTest(change=change.__name__),self.assertRaisesRegex(ValueError,'^joining export '+reason+'$'):
                self.windows('4-REPLACE',lagging=True,change=change)

    def test_pending_ack_comes_from_actual_joiner(self):
        for node in ('node-4','node-5','node-6'):
            model=SimpleNamespace(joining=node,entries=[],checkpoint=lambda *_:{},
                acks={(e.sha(b'statement'),node):b'actual ack',(e.sha(b'statement'),'foreign'):b'foreign ack'})
            with patch.object(e.n.s.capsules,'spans',return_value=[(1,9,'MEMBERSHIP')]), \
                 patch.object(e.f,'encode',return_value=b'statement'):
                self.assertEqual(b'actual ack',e.pending_ack(model))

    def test_pending_force_and_recipient_cannot_borrow_node_four_for_larger_profiles(self):
        for joining in ('node-5','node-6'):
            q,raw,values,events,model=fixture.JoiningExportEvidenceTest().pending()
            model.joining=joining
            for state in model.states:
                for identity in state['identities']:
                    if identity['node']=='node-4':identity['node']=joining
            for row in events:row['node']=joining
            q['recipient']['node']=joining
            with patch.object(e,'pending_ack',return_value=raw),patch.object(e.f,'decode',return_value=dict(view=q['view'],ballot=q['ballot'])):
                e.authorize_pending(values,events,model)
                foreign=copy.deepcopy(events)
                for row in foreign:row['node']='node-4'
                with self.assertRaisesRegex(ValueError,'^joining export pending ACK lifetime$'):e.authorize_pending(values,foreign,model)
                values[0]['offer']['request']['recipient']=dict(q['recipient'],node='node-4')
                with self.assertRaisesRegex(ValueError,'^joining export pending ACK original scope$'):e.authorize_pending(values,events,model)

    def test_invalid_profile_or_original_never_reaches_exports(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.network,'validate',side_effect=ValueError('original failure')), \
             patch.object(p,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^joining prefix profile$'):p.validate('/unused','5-ADD')
            with self.assertRaisesRegex(ValueError,'^original failure$'):p.validate('/unused','5-REPLACE')
            replay.assert_not_called()

    def test_larger_joining_exports_use_the_actual_open_owner_interval(self):
        for node in ('node-5','node-6'):
            reader=SimpleNamespace(model=SimpleNamespace(joining=node),events=[{},dict(scope='continuation-endpoint')],
                contents=[],windows=[],sources=[],records=[],groups=[[
                    dict(raw=b'export',offer=dict(received=1,request=dict(recipient=dict(node=node))),commit=dict(offered=8))]])
            with patch.object(p,'context',return_value=reader),patch.object(e,'authorize_contents',return_value={}), \
                 patch.object(e,'pending_ack',return_value=b'pending'),patch.object(p,'owner_lifetime') as owner:
                self.assertEqual(1,p.replay('/unused','5-REPLACE')['joiningExportLifetimes'])
                owner.assert_called_once_with(reader.events,node,'continuation-owner',1,8)
                owner.side_effect=ValueError('closed original owner')
                with self.assertRaisesRegex(ValueError,'^closed original owner$'):p.replay('/unused','5-REPLACE')
                reader.events[1]['scope']='retired-endpoint'
                with self.assertRaisesRegex(ValueError,'^joining profile export owner scope$'):p.replay('/unused','5-REPLACE')

    def result(self):
        original=dict(network=dict(committedTransfers=7,transferSessions=5,rejectedTransferAttempts=1))
        result=dict(boundTransfers={'original':5},unqualifiedTransfers=2,boundSessions={'original':3},unqualifiedSessionCount=1)
        return original,result

    def test_every_session_is_accounted_but_control_and_full_cohort_remain_unqualified(self):
        original,result=self.result()
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.network,'validate',return_value=original),patch.object(p,'replay',return_value=result):
            answer=p.validate('/unused','4-ADD')
            self.assertTrue(answer['temporalContentExportsQualified'])
            for field in ('completeControlExportQualified','maintenanceAndPeerCompositionQualified','allMembershipProfilesQualified','processDeathQualified','phase3Complete'):
                self.assertFalse(answer[field])
            for field in ('unqualifiedTransfers','unqualifiedSessionCount'):
                result[field]+=1
                with self.assertRaisesRegex(ValueError,'^joining profile export complete session accounting$'):p.validate('/unused','4-ADD')
                result[field]-=1

    def test_original_inventory_cannot_change_during_replay(self):
        original,result=self.result()
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]), \
             patch.object(p.network,'validate',return_value=original),patch.object(p,'replay',return_value=result):
            with self.assertRaisesRegex(ValueError,'^joining profile export original changed$'):p.validate('/unused','4-ADD')

    def test_invalid_original_never_counts_as_negative_success(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')),patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/unused','3-ADD')
            copied.assert_not_called()

    def test_only_unobserved_pending_ack_has_explicit_nonpassing_applicability(self):
        for count in (0,1,4):
            cases,absent=p.negative_plan(dict(exports=dict(boundSessions={'pending-joining-checkpoint':count})))
            self.assertEqual(12 if count else 11,len(cases))
            self.assertEqual(bool(count),'pending-after-retain' in cases)
            self.assertEqual([] if count else [dict(case='pending-after-retain',status='NOT_APPLICABLE',reason=p.PENDING_ABSENT)],absent)
            self.assertEqual(set(p.NEGATIVES)-{'pending-after-retain'},set(cases)-{'pending-after-retain'})

    def test_missing_required_mutation_target_fails_instead_of_becoming_inapplicable(self):
        with patch.object(p,'validate',return_value=dict(exports=dict(boundSessions={}))), \
             patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])),patch.object(p.shutil,'copytree'), \
             patch.object(p,'context'),patch.object(e,'mutate',side_effect=StopIteration),patch.object(e.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining profile export missing negative target: generation-alias$'):
                p.qualify('/unused','3-REPLACE')
            network.assert_not_called()

    def test_qualification_rejects_changed_physical_files_or_broken_transcript(self):
        before=dict(files={'root.gsr':'original'},directories=[])
        for changed,network_error,message in ((dict(files={'root.gsr':'altered'},directories=[]),None,'joining profile export negative changed physical inputs'),
                (before,ValueError('broken transcript'),'broken transcript')):
            with patch.object(p,'validate',return_value=dict(exports=dict(boundSessions={}))),patch.object(p.collection,'inventory',side_effect=[before,changed]), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'context'),patch.object(e,'mutate'), \
                 patch.object(e.n,'network',side_effect=network_error),patch.object(p,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'^'+message+'$'):p.qualify('/unused','5-REPLACE')
                replay.assert_not_called()

    def test_wrong_negative_reason_or_acceptance_does_not_pass(self):
        for failure,message in ((None,'joining profile export mutation accepted: generation-alias'),
                                (ValueError('other'),'joining profile unrelated export negative: generation-alias: other')):
            with patch.object(p,'validate',return_value=dict(exports=dict(boundSessions={}))),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'context'),patch.object(e,'mutate'), \
                 patch.object(e.n,'network'),patch.object(p,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,'^'+message+'$'):p.qualify('/unused','5-REPLACE')


if __name__=='__main__':unittest.main()
