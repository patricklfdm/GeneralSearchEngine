import copy
import json
import unittest
from . import composition_model as m
from . import composition_oracle as o
from . import composition_scenarios as s


class CompositionTest(unittest.TestCase):
    def check(self,g):return o.check(json.loads(m.encoded(g.evidence())))
    def small(self):
        g=m.Group();c=g.activate('node-1',['node-1','node-2']);g.commit(c,compact=True);return g,c

    def test_all_profiles_reuse_round_with_catalog_and_real_compacted_inputs(self):
        for size,kind in s.PROFILES:
            with self.subTest(size=size,kind=kind):
                g,c,voters=s.transition(size,kind);result=self.check(g);state=g.state()
                self.assertEqual((14,3),(result['publications'],result['selections']))
                self.assertEqual(1,state['generation']);self.assertEqual(1,state['retiredThrough']);self.assertEqual({},state['results'])
                self.assertEqual(4,len(g.nodes['node-1']['base']['items']));self.assertNotIn('before-reserve',m.encoded(g.nodes['node-1']['base']))
                self.assertEqual(size+(kind!='REMOVE'),len(state['identities']));self.assertTrue(g.campaigns[c]['ready'])

    def test_all_profiles_recover_mixed_compacted_cuts_without_resampling(self):
        for size,kind in s.PROFILES:
            with self.subTest(size=size,kind=kind):
                g,c,_=s.heterogeneous(size,kind);self.check(g);selected=g.campaigns[c]['selected']
                cuts=[m.read(b)['packet']['cut']['index'] for b in selected['bases']]
                self.assertLess(cuts[0],max(cuts));self.assertTrue(all(not m.read(b)['packet']['journal'] for b in selected['bases']))
                self.assertEqual(selected['bases'][0],g.nodes['node-1']['basis'])

    def test_all_profiles_preserve_original_tail_across_each_force_cut(self):
        for size,kind in s.PROFILES:
            for boundary in ('staged','accepted','partial-proof','proof','prefix'):
                with self.subTest(size=size,kind=kind,boundary=boundary):
                    g,c,_=s.recover_tail(size,kind,boundary);result=self.check(g);self.assertIn(c,result['ready'])

    def test_selected_source_loss_requires_new_ballot_and_all_install_acks(self):
        g=m.Group();g.allocate('node-1');g.force_allocation('node-1');c=g.start('node-1',100)
        for node in ('node-1','node-2'):g.prepare(c,node)
        g.select(c,['node-1','node-2']);g.force_selection(c);g.install(c,'node-1');g.ack_install(c,'node-1')
        with self.assertRaisesRegex(ValueError,'uninstalled'):g.propose(c)
        g.crash('node-2')
        with self.assertRaisesRegex(ValueError,'selection already fixed'):g.select(c,['node-1','node-3'])
        g.abandon(c);g.tick(10);new=g.activate('node-1',['node-1','node-3'],deadline=100);g.commit(new,compact=True)
        g.restart('node-2');g.sync('node-2','node-1')
        with self.assertRaises(ValueError):g.ack_install(c,'node-2')
        self.assertEqual(100,g.campaigns[new]['deadline']);self.check(g)

    def test_higher_prepare_fences_already_staged_old_force(self):
        g,c=self.small();g.propose(c,dict(kind='DATA',value='unforced'))
        g.deliver(g.send(c,'ACCEPT','node-2'))
        g.allocate('node-3');g.force_allocation('node-3');new=g.start('node-3',100);g.prepare(new,'node-3')
        with self.assertRaisesRegex(ValueError,'writer busy'):g.deliver(g.send(new,'PREPARE','node-2'))
        with self.assertRaisesRegex(ValueError,'fenced'):g.force_vote('node-2')
        self.assertIsNone(g.nodes['node-2']['tail']);self.check(g)

    def test_lagging_parent_must_be_forced_before_retried_acceptance(self):
        g,c=self.small();g.commit(c,dict(kind='DATA',value='leader-ahead'),apply_to=['node-1'])
        g.propose(c,dict(kind='DATA',value='next'));message=g.send(c,'ACCEPT','node-2')
        with self.assertRaisesRegex(ValueError,'parent'):g.deliver(message)
        g.sync('node-2','node-1');key=next(k for k,v in g.exchanges.items() if v['body']['entry']==g.campaigns[c]['proposal'] and v['body']['node']=='node-2')
        g.deliver(g.retry(key));g.ack_vote(c,g.force_vote('node-2'));self.check(g)

    def test_forced_grant_without_basis_cannot_resample_after_restart(self):
        g=m.Group();g.allocate('node-1');g.force_allocation('node-1');c=g.start('node-1',100)
        message=g.send(c,'PREPARE','node-1');key=next(iter(g.exchanges));duplicate=g.retry(key)
        g.deliver(message);g.force_grant('node-1');g.crash('node-1');g.restart('node-1')
        with self.assertRaisesRegex(ValueError,'fresh ballot'):g.deliver(duplicate)
        self.assertIsNone(g.nodes['node-1']['basis']);new=g.activate('node-1',['node-1','node-2']);g.commit(new,compact=True)
        self.assertGreater(g.campaigns[new]['ballot']['counter'],g.campaigns[c]['ballot']['counter']);self.check(g)

    def test_retries_keep_original_body_deadline_and_stop_at_three(self):
        g=m.Group();g.allocate('node-1');g.force_allocation('node-1');c=g.start('node-1',10)
        first=g.send(c,'PREPARE','node-1');key=next(iter(g.exchanges));g.drop(first);g.tick(1)
        second=g.retry(key);g.drop(second);g.tick(1);third=g.retry(key);g.deliver(third);g.force_grant('node-1');g.force_basis('node-1')
        with self.assertRaisesRegex(ValueError,'exhausted'):g.retry(key)
        g.tick(8)
        with self.assertRaisesRegex(ValueError,'deadline'):g.send(c,'PREPARE','node-2')
        self.check(g)

    def test_stable_round_has_no_time_lease_but_each_entry_keeps_its_deadline(self):
        g,c=self.small();g.tick(1000);g.commit(c,dict(kind='DATA',value='after-campaign-deadline'),compact=True)
        g.propose(c,dict(kind='DATA',value='deadline-cut'),deadline=g.now+2);g.deliver(g.send(c,'ACCEPT','node-2'));g.tick(2)
        raw=g.force_vote('node-2')  # An already admitted force may finish; its caller cannot claim success.
        with self.assertRaisesRegex(ValueError,'deadline'):g.ack_vote(c,raw)
        self.assertIsNotNone(g.nodes['node-2']['tail']);self.check(g)

    def test_forced_selector_survives_restart_and_deletion_requires_floor_and_inventory(self):
        g,c=self.small();g.commit(c,dict(kind='DATA',value='compact-me'))
        g.compact_stage('node-1');g.force_selector('node-1');before=copy.deepcopy(g.nodes['node-1']['base']);g.crash('node-1');g.restart('node-1')
        self.assertEqual(before,g.nodes['node-1']['base'])
        with self.assertRaisesRegex(ValueError,'floor'):g.force_retirement('node-1')
        with self.assertRaisesRegex(ValueError,'inventory'):g.delete_retired('node-1')
        g.force_floor('node-1');g.force_retirement('node-1');g.delete_retired('node-1');self.check(g)

    def test_whole_group_restart_retains_catalog_and_never_restores_ready(self):
        g,c,voters=s.transition(5,'REPLACE');before=g.state()
        for node in m.NODES:g.crash(node)
        for node in m.NODES:g.restart(node)
        self.assertEqual(before,g.state());self.assertFalse(g.campaigns[c]['ready'])
        new=g.activate('node-2',voters);g.commit(new,compact=True);self.check(g)

    def test_stale_learner_revision_rejects_without_changing_catalog_or_proposal(self):
        g,c=self.small();op=m.op
        request=op.request(g.state(),[op.identity(n) for n in ('node-1','node-2','node-3','node-6')],'ADD')
        g.commit(c,dict(kind='RESERVE',request=request),compact=True)
        g.commit(c,dict(kind='PREPARE',number=1,revision=1),compact=True);stale=g.materialize('node-6','node-1')
        with self.assertRaisesRegex(ValueError,'ineligible'):g.allocate('node-6')
        g.commit(c,dict(kind='DATA',value='invalidate-preparation'),compact=True)
        g.commit(c,dict(kind='PREPARE',number=1,revision=2),compact=True);before=copy.deepcopy(g.nodes)
        with self.assertRaisesRegex(ValueError,'stale learner'):g.propose(c,dict(kind='READY',number=1,receipt=stale))
        self.assertEqual(before,g.nodes);self.assertIsNone(g.campaigns[c]['proposal'])
        fresh=g.materialize('node-6','node-1');g.commit(c,dict(kind='READY',number=1,receipt=fresh),compact=True)
        g.commit(c,dict(kind='CANCEL',number=1),compact=True);g.commit(c,dict(kind='RETIRE',through=1),compact=True)
        self.assertEqual(3,len(g.state()['members']));self.check(g)

    def test_missing_frozen_ancestry_fails_closed_and_new_sources_can_recover(self):
        g,_,voters=s.transition(3,'ADD');others=[n for n in voters if n!='node-1']
        old=g.activate('node-2',others);g.commit(old,compact=True)
        g.allocate('node-1');g.force_allocation('node-1');new=g.start('node-1',100);g.prepare(new,'node-1')
        for value in ('beyond-first-cut','beyond-retained-bridge'):
            g.commit(old,dict(kind='DATA',value=value),apply_to=others,compact=True)
        for node in others:g.prepare(new,node)
        before=copy.deepcopy(g.nodes)
        with self.assertRaisesRegex(ValueError,'unavailable original source ancestry'):g.select(new,voters)
        self.assertEqual(before,g.nodes);g.abandon(new)
        recovered=g.activate('node-2',others);g.commit(recovered,apply_to=others,compact=True);self.check(g)

    def test_known_removed_identity_cannot_allocate_a_new_round(self):
        g,_,_=s.transition(5,'REMOVE');before=copy.deepcopy(g.nodes)
        with self.assertRaisesRegex(ValueError,'ineligible'):g.allocate('node-5')
        self.assertEqual(before,g.nodes);self.check(g)

    def test_control_recovery_crosses_authority_boundaries_with_original_bytes(self):
        for control in ('SEAL','INTENT','FINAL'):
            for boundary in ('accepted','proof','prefix'):
                with self.subTest(control=control,boundary=boundary):
                    g,c,voters=s.control_recovery(5,'REPLACE',control,boundary);result=self.check(g)
                    self.assertIn(c,result['ready']);self.assertEqual(1,g.state()['generation'])
                    self.assertEqual(1,g.state()['retiredThrough']);self.assertEqual({},g.state()['results'])
                    self.assertEqual(voters,[r['voter'] for r in g.state()['members']])


if __name__=='__main__':unittest.main()
