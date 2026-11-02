import copy
import unittest
from unittest.mock import patch
from . import current_lifecycle_evidence as c

OPEN = ('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED')


def row(point, node='node-1', scope=None):
    return dict(node=node,event=point,**({'scope':scope} if scope is not None else {}))


def join_opens():
    events=[]
    for scope in ('initial-owner','retaining-owner','repeated-basis-owner','continuation-owner','stable-cold-owner'):
        before=['JOINED_NATIVE_TRANSFERRED'] if scope=='initial-owner' else []
        after=['ACCEPT_ACTIVE_FORCED'] if scope=='initial-owner' else ['JOINING_RETENTION_SEED_RECOVERY_FORCED']
        events += [row(point,'node-4',scope) for point in [*before,*OPEN,*after]]
    return events


class CurrentLifecycleEvidenceTest(unittest.TestCase):
    def test_changes_come_from_original_choices_and_proofs_including_unused_voters(self):
        records={b's':dict(sources=[dict(voter=n) for n in ('node-1','node-2')],cut=dict(index=0)),
                 b'p1':dict(index=1,proofs=[dict(voter=n) for n in ('node-1','node-2')]),
                 b'p2':dict(index=2,proofs=[dict(voter=n) for n in ('node-1','node-2')]),
                 b'r':dict(cut=dict(index=2),sources=[dict(voter=n) for n in ('node-4','node-2')])}
        phases=[dict(SELECTED=b's',CERTIFICATE=b'p1'),dict(SELECTED=b's',CERTIFICATE=b'p2')]
        with patch.object(c.f,'decode',side_effect=lambda raw,*args:records[raw]):
            expected=c.changes(phases,('node-1','node-2','node-3','node-4'),joining='node-4',recovery=b'r')
        self.assertEqual(['INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],[p for p,_ in expected['node-1']])
        self.assertEqual([],expected['node-3'])
        self.assertEqual([('ADOPTION_INSTALL_BEFORE_RETURN','final-prefix-2'),('INSTALL_BEFORE_RETURN',c.digest(b'r'))],expected['node-4'])
        self.assertEqual(('INSTALL_BEFORE_RETURN',c.digest(b'r')),expected['node-2'][-1])

    def test_joining_at_final_cut_does_not_invent_an_adoption(self):
        selected=dict(sources=[dict(voter='node-4')],cut=dict(index=1))
        proof=dict(index=2,proofs=[dict(voter='node-4')])
        with patch.object(c.f,'decode',side_effect=lambda raw,*args:selected if raw==b's' else proof):
            steps=c.changes([dict(SELECTED=b's',CERTIFICATE=b'p')],('node-4',),joining='node-4')
        self.assertEqual(['INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],[p for p,_ in steps['node-4']])

    def test_interrupted_installation_has_no_fabricated_publication(self):
        with patch.object(c.f,'decode',return_value=dict(cut=dict(index=4),sources=[dict(voter='node-1')])):
            steps=c.changes([dict(SELECTED=b's')],('node-1',))
        self.assertEqual({'node-1':[('INSTALL_BEFORE_RETURN',c.digest(b's'))]},steps)

    def test_all_five_joining_opens_and_exact_shapes(self):
        events=join_opens();owner=c.Ownership(events);owner.joining_opens('node-4')
        self.assertEqual(25,owner.finish()['callbacks'])
        for name,reason in c.JOINING_NEGATIVES.items():
            changed=copy.deepcopy(events);c.mutate(changed,name)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^'+reason+'$'):
                c.Ownership(changed).joining_opens('node-4')

    def test_complete_generation_is_bounded_by_original_parent_force_and_return(self):
        events=[row('INSTALL_PARENT_FORCED'),*[row(v) for v in OPEN],row('INSTALL_BEFORE_RETURN')]
        expected={'node-1':[('INSTALL_BEFORE_RETURN','a'*64)]}
        owner=c.Ownership(events);owner.generations(expected,None);self.assertEqual(5,owner.finish()['callbacks'])
        for mode in ('missing','scope','field','early'):
            changed=copy.deepcopy(events)
            if mode=='missing':changed.pop(2)
            elif mode=='scope':changed[2]['scope']='foreign'
            elif mode=='field':changed[2]['claim']=True
            else:changed.insert(0,changed.pop(2))
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^current lifecycle complete original interval$'):
                c.Ownership(changed).generations(expected,None)

    def test_observations_cannot_create_an_extra_derived_generation(self):
        events=[row('INSTALL_PARENT_FORCED'),*[row(v) for v in OPEN],row('INSTALL_BEFORE_RETURN')]
        with self.assertRaisesRegex(ValueError,'^current lifecycle derived generation timeline$'):
            c.Ownership(events).generations({'node-1':[]},None)

    def test_each_current_callback_is_consumed_once(self):
        events=[row(v) for v in OPEN];owner=c.Ownership(events);owner.take('node-1',None,-1,5,OPEN,'one')
        with self.assertRaisesRegex(ValueError,'^current lifecycle reused callback$'):owner.take('node-1',None,-1,5,OPEN,'two')
        for name,reason in c.NEGATIVES.items():
            changed=copy.deepcopy(events);c.mutate(changed,name);owner=c.Ownership(changed);owner.take('node-1',None,-1,5,OPEN,'one')
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'^'+reason+'$'):
                owner.captures(c.Counter());owner.finish()

    def test_capture_counts_are_bound_to_original_owner_and_scope(self):
        events=[row('CURRENT_BEFORE_CAPTURE'),row('CURRENT_BEFORE_CAPTURE','node-4','repeated-basis-owner')]
        expected=c.Counter({('node-1',None):1,('node-4','repeated-basis-owner'):1})
        owner=c.Ownership(events);owner.captures(expected);self.assertEqual(2,owner.finish()['callbacks'])
        events[1]['scope']='continuation-owner'
        with self.assertRaisesRegex(ValueError,'^current lifecycle original capture ownership$'):c.Ownership(events).captures(expected)

    def test_original_and_both_process_opens_are_required_without_scope_borrowing(self):
        events=[]
        for i in range(3):events += [*[row(v) for v in OPEN],row('RETENTION_RECOVERY_ACTIVE_FORCED'),row('PROCESS_SNAPSHOT')]
        owner=c.Ownership(events);owner.original_opens(('node-1',),True);self.assertEqual(15,owner.finish()['callbacks'])
        for mode in ('missing','extra'):
            changed=copy.deepcopy(events)
            if mode=='missing':changed.pop(8)
            else:changed+=copy.deepcopy(events[:7])
            with self.subTest(mode=mode),self.assertRaises(ValueError):c.Ownership(changed).original_opens(('node-1',),True)

    def test_independent_node_interleaving_preserves_ownership(self):
        events=[row(point,node) for point in OPEN for node in ('node-1','node-2')]
        events += [row('RETENTION_RECOVERY_ACTIVE_FORCED',node) for node in ('node-1','node-2')]
        owner=c.Ownership(events);owner.original_opens(('node-1','node-2'),False);self.assertEqual(10,owner.finish()['callbacks'])


if __name__=='__main__':unittest.main()
