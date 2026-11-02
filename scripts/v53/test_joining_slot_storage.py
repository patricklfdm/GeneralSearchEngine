import copy
import unittest
from . import joining_slot_storage as s
from . import joining_catalog_evidence as semantic


def fixture(scope=None):
    end = {'applied-end/'+n: b'original' for n in ('plan.json', 'selector.gsr', 'certificate.gsr',
           'catalog.gsr', 'statement.gsr', 'application.image', 'ack.gsr')}
    members = {'application.image': b'image', 'source.gscp': b'source'}
    names = []
    for phase in ('ACCEPT', 'PROOF', 'CERTIFICATE'):
        names += [phase+'_'+n for n in ('VALIDATED', 'CANDIDATE_CREATED', 'PREFIX_WRITTEN', 'CANDIDATE_WRITTEN',
                  'CANDIDATE_FORCED', 'CANDIDATE_PARENT_FORCED', 'RENAMED', 'PARENT_FORCED', 'BEFORE_RETURN')]
    names += ['APPLICATION_AUTHORITY_VALIDATED', 'REPLAY_RESERVED', 'REPLAY_DIRECTORY_CREATED', 'REPLAY_CLAIM_CREATED',
              'REPLAY_CLAIM_PREFIX_WRITTEN', 'REPLAY_CLAIM_WRITTEN', 'REPLAY_CLAIM_FORCED', 'REPLAY_BEFORE_APPLICATION',
              'REPLAY_APPLICATION_FINISHED']
    names += ['REPLAY_BEFORE_DELETE', 'REPLAY_DELETED'] * 7
    names += ['REPLAY_BEFORE_RETURN', 'APPLY_VALIDATED', 'APPLY_DIRECTORY_CREATED']
    for label in ('PLAN', 'METADATA', 'METADATA', 'METADATA', 'METADATA', 'IMAGE', 'ACK'):
        if label == 'ACK': names.append('APPLY_END_FORCED')
        names += ['APPLY_'+label+'_'+n for n in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')]
    names += ['APPLY_ACK_DIRECTORY_FORCED', 'APPLY_BEFORE_RETURN', 'PUBLICATION_VALIDATED', 'INSTALL_RESERVED',
              'INSTALL_DIRECTORY_CREATED', 'INSTALL_MANIFEST_WRITTEN', 'INSTALL_MANIFEST_FORCED',
              'INSTALL_IMAGE_WRITTEN', 'INSTALL_IMAGE_FORCED', 'INSTALL_MEMBER_WRITTEN', 'INSTALL_MEMBER_FORCED',
              'INSTALL_GENERATION_FORCED', 'INSTALL_SELECTOR_WRITTEN', 'INSTALL_SELECTOR_FORCED', 'INSTALL_SELECTOR_RENAMED',
              'INSTALL_PARENT_FORCED', 'CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
              'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED', 'PUBLICATION_SELECTOR_FORCED',
              'PUBLICATION_COVERAGE_VALIDATED', 'COVERED_END_VALIDATED']
    names += ['COVERED_END_BEFORE_DELETE', 'COVERED_END_FILE_DELETED'] * 7
    names += ['COVERED_END_BEFORE_DIRECTORY_DELETE', 'COVERED_END_DIRECTORY_DELETED', 'COVERED_VOTE_CANDIDATE_CREATED',
              'COVERED_VOTE_PREFIX_WRITTEN', 'COVERED_VOTE_CANDIDATE_WRITTEN', 'COVERED_VOTE_CANDIDATE_FORCED',
              'COVERED_VOTE_CANDIDATE_PARENT_FORCED', 'COVERED_VOTE_RENAMED', 'COVERED_VOTE_PARENT_FORCED', 'PUBLICATION_RETIRED']
    events = [dict(node='node-1', event=n, **({'scope': scope} if scope else {})) for n in names]
    return events, end, members


def check(data, scope=None):
    events, end, members = data
    own = {v['event']: i for i, v in enumerate(events)}
    return s.validate_slot(events, 'node-1', scope, own, end, members, 'BARRIER')


class JoiningSlotStorageTest(unittest.TestCase):
    def test_full_storage_transaction_for_old_and_joined_owner(self):
        for scope in (None, 'continuation-owner'):
            data=fixture(scope); self.assertEqual(len(data[0]), check(data,scope))

    def test_control_profile_does_not_silently_accept_DATA_scratch_shape(self):
        self.assertEqual(set(semantic.CONTROLS)|{'BARRIER'},s.CONTROL)
        with self.assertRaisesRegex(ValueError,'^joining slot unsupported application history$'):
            s.application(fixture()[1],'DATA')

    def test_explicit_data_requires_the_complete_output_cleanup(self):
        data=fixture();events,end,members=data
        start=next(i for i,v in enumerate(events) if v['event']=='REPLAY_BEFORE_RETURN')
        events[start:start]=[dict(node='node-1',event=n) for n in ('REPLAY_BEFORE_DELETE','REPLAY_DELETED')]*4
        own={v['event']:i for i,v in enumerate(events)}
        self.assertEqual(len(events),s.validate_slot(events,'node-1',None,own,end,members,'DATA',allow_data=True))
        self.assertEqual(11,s.application(end,'DATA',allow_data=True).count('REPLAY_DELETED'))
        self.assertEqual(7,s.application(end,'BARRIER',allow_data=True).count('REPLAY_DELETED'))
        for at in range(start,start+8):
            changed=events[:at]+events[at+1:];own={v['event']:i for i,v in enumerate(changed)}
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'complete application storage order'):
                s.validate_slot(changed,'node-1',None,own,end,members,'DATA',allow_data=True)

    def test_data_opt_in_never_admits_unknown_application_kinds(self):
        with self.assertRaisesRegex(ValueError,'unsupported application history'):
            s.application(fixture()[1],'UNMODELED',allow_data=True)

    def test_each_internal_storage_step_is_mandatory(self):
        data=fixture(); boundaries={'ACCEPT_VALIDATED','ACCEPT_BEFORE_RETURN','PROOF_VALIDATED','PROOF_BEFORE_RETURN',
            'CERTIFICATE_VALIDATED','CERTIFICATE_BEFORE_RETURN','APPLICATION_AUTHORITY_VALIDATED','APPLY_BEFORE_RETURN',
            'PUBLICATION_VALIDATED','PUBLICATION_SELECTOR_FORCED','PUBLICATION_COVERAGE_VALIDATED','PUBLICATION_RETIRED'}
        for at,row in enumerate(data[0]):
            if row['event'] in boundaries: continue
            changed=copy.deepcopy(data); changed[0].pop(at)
            with self.subTest(event=row['event'],at=at), self.assertRaisesRegex(ValueError,'^joining slot complete '): check(changed)

    def test_duplicate_or_reordered_callbacks_cannot_supply_missing_force(self):
        for point in ('ACCEPT_PREFIX_WRITTEN','PROOF_CANDIDATE_CREATED','CERTIFICATE_CANDIDATE_WRITTEN',
                      'REPLAY_DELETED','APPLY_IMAGE_PREFIX_WRITTEN','INSTALL_MEMBER_FORCED','COVERED_VOTE_PARENT_FORCED'):
            for mode in ('duplicate','reverse'):
                data=fixture(); events=data[0];at=next(i for i,v in enumerate(events) if v['event']==point)
                if mode=='duplicate':events.insert(at,dict(events[at]))
                else:events[at],events[at-1]=events[at-1],events[at]
                with self.subTest(point=point,mode=mode), self.assertRaisesRegex(ValueError,'^joining slot complete '):check(data)

    def test_wrong_node_lifetime_and_extra_fields_are_rejected(self):
        for patch in ({'node':'node-2'},{'scope':'closed-owner'},{'reported':'PASS'}):
            data=fixture('continuation-owner'); next(v for v in data[0] if v['event']=='INSTALL_MEMBER_FORCED').update(patch)
            with self.assertRaisesRegex(ValueError,'^joining slot complete publication storage order$'):check(data,'continuation-owner')

    def test_unknown_storage_event_is_not_filtered_out(self):
        data=fixture(); at=next(i for i,v in enumerate(data[0]) if v['event']=='COVERED_VOTE_PARENT_FORCED')
        data[0].insert(at,dict(node='node-1',event='COVERED_VOTE_UNKNOWN'))
        with self.assertRaisesRegex(ValueError,'^joining slot complete covered retirement order$'):check(data)

    def test_unrelated_peer_and_network_events_do_not_supply_owned_storage(self):
        data=fixture(); data[0].insert(8,dict(node='node-1',event='NETWORK_RECEIVED',kind='ACK'))
        data[0].insert(15,dict(node='node-2',event='INSTALL_MEMBER_FORCED'))
        self.assertEqual(len(data[0])-2,check(data))

    def test_generation_member_count_is_from_reduced_inventory(self):
        data=fixture();data[2]['ancestry.gsr']=b'original'
        with self.assertRaisesRegex(ValueError,'^joining slot complete publication storage order$'):check(data)

    def test_application_and_cleanup_share_exact_ancestor_inventory(self):
        end=fixture()[1]
        for prefix in ('parent','ancestor-0','ancestor-1'):
            for suffix in ('statement','ack'):end[f'applied-end/{prefix}-{suffix}.gsr']=b'original'
        names=s.application(end,'INTENT')
        self.assertLess(names.index('APPLY_PARENT_STATEMENT_FORCED'), names.index('APPLY_IMAGE_FORCED'))
        self.assertLess(names.index('APPLY_ACK_FORCED'),names.index('APPLY_PARENT_ACK_FORCED'))
        self.assertLess(names.index('APPLY_PARENT_ACK_FORCED'),names.index('APPLY_ANCESTOR_0_ACK_FORCED'))
        self.assertEqual(13,s.retirement(end).count('COVERED_END_FILE_DELETED'))

    def test_missing_or_unpaired_original_members_fail_before_event_comparison(self):
        for case in ('missing-plan','unpaired','extra'):
            end=fixture()[1]
            if case=='missing-plan':del end['applied-end/plan.json']
            elif case=='unpaired':end['applied-end/parent-statement.gsr']=b'original'
            else:end['applied-end/unlisted']=b'original'
            with self.assertRaisesRegex(ValueError,'^joining slot applied member inventory$'):s.application(end,'INTENT')

    def test_ancestor_holes_or_out_of_bound_positions_cannot_reduce_force_count(self):
        for position in (1,5):
            end=fixture()[1]
            for prefix in ('parent','ancestor-'+str(position)):
                for suffix in ('statement','ack'):end[f'applied-end/{prefix}-{suffix}.gsr']=b'original'
            with self.assertRaisesRegex(ValueError,'^joining slot applied (ancestor order|member inventory)$'):s.retirement(end)

    def test_invalid_interval_is_rejected(self):
        for lo,hi in ((-1,2),(True,2),(2,1),(0,999)):
            with self.assertRaisesRegex(ValueError,'^invalid interval$'):
                s.exact(fixture()[0],'node-1',None,lo,hi,[],('APPLY_',),'invalid interval')


if __name__=='__main__':unittest.main()
