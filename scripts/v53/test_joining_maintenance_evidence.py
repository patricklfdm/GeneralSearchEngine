"""Maintenance evidence boundaries; native qualification remains separate."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from . import joining_maintenance_evidence as m
from . import test_joining_export_evidence as fixture


class JoiningMaintenanceEvidenceTest(unittest.TestCase):
    def copies(self):
        windows,_=fixture.JoiningExportEvidenceTest().inputs()
        for own in windows:own['packet']['capsule']['application']='f'*64
        return {v['node']:copy.deepcopy(v) for v in windows}

    def retirement(self):
        return [dict(node='node-1',event=name) for name in
                ('FLOOR_RESERVED','FLOOR_BEFORE_RETURN','RETIREMENT_RESERVED','RETIREMENT_AUTHORITY_FORCED',
                 'RETIREMENT_PARENT_FORCED','RETIREMENT_DELETE_VALIDATED','RETIREMENT_BEFORE_RETURN',
                 'FLOOR_RELEASE_AUTHORITY_CREATED','FLOOR_RELEASE_BEFORE_RETURN')]

    def acquisition(self):
        copies=self.copies();own,remote=copies['node-1'],copies['node-2'];_,q=fixture.JoiningExportEvidenceTest().inputs()
        q=dict(q,payload=dict(digest=m.e.native.current_reference(remote['packet']['capsule'],'retained-current-generation-metadata')))
        packet_q=dict(q,payload=dict(digest=m.e.native.current_reference(remote['packet']['capsule'],'retained-current-packet')))
        packet=[dict(raw=remote['members']['source.gscp'],offer=dict(sent=6,received=7,offered=7,request=packet_q),commit=dict(delivered=9,offered=8))]
        generation=[dict(offer=dict(sent=10,received=11,offered=12,request=q),commit=dict(delivered=15,offered=14))]
        replay=m.Replay.__new__(m.Replay);replay.windows=list(copies.values());replay.groups=[packet,generation]
        replay.status_rows=[dict(sent=1,delivered=5,requestHash='status',request=q,response=dict(payload=dict(cut=remote['packet']['capsule']['cut'])))]
        return replay,own,generation

    def test_governing_copies_require_original_identity_and_same_endpoint(self):
        copies=self.copies();m.same_cut(copies,copies['node-1'])
        for mutation in ('identity','catalog','application','cut'):
            changed=copy.deepcopy(copies)
            if mutation=='identity':changed['node-2']['identity']['storage']='00000000-0000-0000-0000-000000000001'
            elif mutation=='cut':changed['node-2']['packet']['capsule']['cut']['index']+=1
            else:changed['node-2']['packet']['capsule'][mutation]='e'*64
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'^joining maintenance exact governing copies$'):
                m.same_cut(changed,copies['node-1'])

    def test_discovery_waiting_for_same_cut_install_remains_only_a_hint(self):
        windows,q,_=fixture.JoiningExportEvidenceTest().installed_offer()
        q=dict(q,sequence=1,payload=dict(nonce='original'))
        a=dict(payload=dict(nonce='original',cut=windows[-1]['packet']['capsule']['cut'],ready=False))
        r=m.Replay.__new__(m.Replay);r.windows=windows;r.model=SimpleNamespace(joining='node-4');r.expected_status_count=1
        r.rows=[dict(kind='STATUS_PROBE',answer='STATUS',request=q,response=a,received=10,offered=17)]
        r.statuses();self.assertEqual(r.rows,r.status_rows)
        for change in ('no-link','wrong-cut','ready'):
            row=copy.deepcopy(r.rows[0]);original=copy.deepcopy(windows)
            if change=='no-link':windows[-1].pop('sourcePredecessor')
            elif change=='wrong-cut':row['response']['payload']['cut']['index']+=1
            else:row['response']['payload']['ready']=True
            r.rows=[row]
            with self.subTest(change=change),self.assertRaises(ValueError):r.statuses()
            windows[:]=original;r.rows=[dict(kind='STATUS_PROBE',answer='STATUS',request=q,response=a,received=10,offered=17)]

    def test_governing_copy_set_needs_local_owner_and_actual_majority(self):
        copies=self.copies()
        with self.assertRaisesRegex(ValueError,'^joining maintenance original local copy$'):m.same_cut({'node-2':copies['node-2']},copies['node-1'])
        with self.assertRaises(ValueError):m.same_cut({'node-1':copies['node-1']},copies['node-1'])

    def test_joint_floor_cannot_omit_joining_copy_even_if_majorities_pass(self):
        copies=self.copies()
        for own in copies.values():
            own['packet']=copy.deepcopy(own['packet']);cap=own['packet']['capsule']
            cap['cut']['view'].update(new=['node-1','node-2','node-4'],operation='f'*64)
        with self.assertRaisesRegex(ValueError,'^joining maintenance missing original joining copy$'):m.same_cut(copies,copies['node-1'])

    def test_floor_force_counts_follow_complete_members_including_images(self):
        copies=self.copies();events=m.floor_events(copies,'node-1',True)
        self.assertEqual(2,events.count('FLOOR_MANIFEST_FORCED'))
        self.assertEqual(2,events.count('FLOOR_IMAGE_FORCED'))
        self.assertEqual(4,events.count('FLOOR_MEMBER_FORCED'))
        self.assertEqual(8,events.count('FLOOR_RELEASE_FILE_DELETED'))
        self.assertEqual(2,events.count('FLOOR_COPY_HANDED_OFF'))
        copies['node-2']['members']['ancestry.gsr']=b'original ancestry'
        extended=m.floor_events(copies,'node-1',True)
        self.assertEqual(5,extended.count('FLOOR_MEMBER_FORCED'));self.assertEqual(9,extended.count('FLOOR_RELEASE_FILE_DELETED'))
        self.assertNotIn('FLOOR_COPY_HANDED_OFF',m.floor_events(copies,'node-1',False))

    def test_acquisition_waits_for_delivered_complete_copy_not_server_commit(self):
        replay,own,generation=self.acquisition()
        with patch.object(m.e,'authorize_generation'):
            copies,used=replay.acquired(own,0,20);self.assertEqual({'node-1','node-2'},set(copies));self.assertEqual(['status'],used)
            generation[-1]['commit']['delivered']=20
            with self.assertRaisesRegex(ValueError,'^joining maintenance copy delivered after floor$'):replay.acquired(own,0,20)

    def test_packet_only_acquisition_cannot_invent_a_borrowed_application(self):
        replay,own,_=self.acquisition();image=next(k for k in own['members'] if k.endswith('.image'))
        with patch.object(m.e,'authorize_generation'):
            for raw in (None,b'changed'):
                own['members'][image]=raw
                with self.assertRaisesRegex(ValueError,'^joining maintenance missing borrowed original image$'):replay.acquired(own,0,20)

    def test_discovery_must_precede_packet_and_keep_original_correlation(self):
        replay,own,_=self.acquisition()
        with patch.object(m.e,'authorize_generation'):
            for change in ('late','ballot','cut'):
                original=copy.deepcopy(replay.status_rows);row=replay.status_rows[0]
                if change=='late':row['delivered']=6
                elif change=='ballot':row['request']=dict(row['request'],ballot=dict(row['request']['ballot'],counter=9))
                else:row['response']=dict(payload=dict(cut=dict(row['response']['payload']['cut'],index=9)))
                with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining maintenance acquisition before discovery$'):
                    replay.acquired(own,0,20)
                replay.status_rows=original

    def test_waiting_packet_is_not_mistaken_for_a_complete_copy(self):
        replay,own,generation=self.acquisition();before=copy.deepcopy(replay.windows[1]);before['end']=7
        after=replay.windows[1];after.update(start=9,sourcePredecessor=(0,7))
        replay.windows.append(before)
        packet=replay.groups[0][0];packet['offer'].update(received=6,offered=10);packet['commit'].update(offered=11,delivered=12)
        generation[0]['offer'].update(sent=13,received=14,offered=15);generation[0]['commit'].update(offered=16,delivered=17)
        with patch.object(m.e,'authorize_generation'):
            copies,used=replay.acquired(own,0,20)
            self.assertIs(after,copies['node-2']);self.assertEqual(['status'],used)
            replay.groups.remove(generation)
            with self.assertRaisesRegex(ValueError,'absent acquired copies'):replay.acquired(own,0,20)

    def test_retirement_force_and_delete_must_stay_inside_original_floor(self):
        original=self.retirement();self.assertEqual(1,m.retirement_order(original,'node-1',0,len(original)-1,None))
        for left,right in ((1,2),(3,4),(4,5),(6,7)):
            changed=copy.deepcopy(original);changed[left],changed[right]=changed[right],changed[left]
            with self.subTest(left=left),self.assertRaisesRegex(ValueError,'^joining maintenance generation retirement lifetime$'):
                m.retirement_order(changed,'node-1',0,len(changed)-1,None)

    def test_retirement_capture_label_normalization_does_not_accept_foreign_owners(self):
        events=self.retirement();events.insert(6,dict(node='node-1',event=m.n.physical.observed.EVENT,scope='network-owner'))
        m.retirement_order(events,'node-1',0,len(events)-1,None)
        events[6]['scope']='initial-owner'
        with self.assertRaisesRegex(ValueError,'^joining maintenance retirement outside floor$'):m.retirement_order(events,'node-1',0,len(events)-1,None)

    def test_missing_retirement_parent_force_is_not_a_completed_cleanup(self):
        events=self.retirement();events[4]['event']='REMOVED_FORCE'
        with self.assertRaisesRegex(ValueError,'^joining maintenance generation retirement lifetime$'):m.retirement_order(events,'node-1',0,len(events)-1,None)

    def test_validate_requires_original_control_gate_and_unchanged_inventory(self):
        with patch.object(m.n.s.collection,'inventory',return_value={}),patch.object(m.c,'validate',side_effect=ValueError('invalid original')),patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.validate('/unused')
            replay.assert_not_called()
        with patch.object(m.n.s.collection,'inventory',side_effect=[{}, {'changed':1}]),patch.object(m.c,'validate'),patch.object(m,'replay'):
            with self.assertRaisesRegex(ValueError,'^joining maintenance original changed$'):m.validate('/unused')

    def test_negative_driver_cannot_use_invalid_original_as_success(self):
        with patch.object(m,'validate',side_effect=ValueError('invalid original')),patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.qualify('/unused')
            copied.assert_not_called()

    def test_negatives_preserve_files_and_require_prior_control_validation(self):
        with patch.object(m,'validate',return_value={}),patch.object(m.n.s.collection,'inventory',side_effect=[dict(files={'original':'digest'},directories=[]),dict(files={'original':'altered'},directories=[])]), \
                patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),patch.object(m.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining maintenance negative changed physical inputs$'):m.qualify('/unused')
            network.assert_not_called()
        with patch.object(m,'validate',return_value={}),patch.object(m.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),patch.object(m.n,'network'),patch.object(m.e,'replay'), \
                patch.object(m.c,'replay',side_effect=ValueError('invalid control')),patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^invalid control$'):m.qualify('/unused')
            replay.assert_not_called()

    def test_negatives_reject_unrelated_errors_and_accepted_mutations(self):
        for failure,reason in ((None,'joining maintenance mutation accepted: status-cut'),
                               (ValueError('unrelated'),'joining unrelated maintenance negative: status-cut: unrelated')):
            with patch.object(m,'validate',return_value={}),patch.object(m.n.s.collection,'inventory',return_value=dict(files={},directories=[])), \
                    patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),patch.object(m.n,'network'),patch.object(m.e,'replay'), \
                    patch.object(m.c,'replay'),patch.object(m,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):m.qualify('/unused')


if __name__=='__main__':unittest.main()
