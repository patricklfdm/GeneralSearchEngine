from copy import deepcopy
import json
import unittest

from . import integrated_model as m
from . import integrated_oracle as o
from . import operation_model as op
from . import transition_model as t
from . import integrated_research as r


def reserve(group,kind='ADD'):
    state=group.state();target=deepcopy(state['members'])
    if kind in ('REMOVE','REPLACE'):target.pop(0)
    if kind in ('ADD','REPLACE'):target.append(op.identity('node-6'))
    request=op.request(state,sorted(target,key=lambda v:v['voter']),kind)
    group.commit(dict(kind='RESERVE',request=request));return request


def prepared(group,kind='ADD'):
    request=reserve(group,kind);group.commit(dict(kind='PREPARE',number=1,revision=1))
    receipt=group.materialize() if kind!='REMOVE' else None
    group.commit(dict(kind='READY',number=1,receipt=receipt))
    return request,receipt


def finish(group):
    state=group.state();row=state['results']['1']
    if row['phase']=='READY':group.commit(dict(kind='SEAL',number=1))
    state=group.state();row=state['results']['1']
    if row['phase']=='SEALED':group.commit(dict(kind='INTENT',number=1,binding=row['binding']))
    if group.state()['results']['1']['phase']=='JOINT':group.commit()  # default joint recovery selects exact FINAL
    group.commit()  # fresh stable barrier activates a current member


class IntegratedTest(unittest.TestCase):
    def audit(self,g):
        result=o.check(g.evidence())
        for node,store in g.catalogs.items():self.assertEqual(store.state,result['states'][node])
        return result

    def test_all_changes_with_actual_global_grants_accepts_and_proofs(self):
        for size,kind in ((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE')):
            with self.subTest(size=size,kind=kind):
                g=m.Group(size);g.commit();request,_=prepared(g,kind);finish(g)
                self.assertEqual(request['target'],g.state()['members']);self.assertEqual('COMPLETED',g.state()['results']['1']['phase'])
                self.audit(g)

    def test_learner_cannot_prepare_before_matching_intent_installation(self):
        g=m.Group();g.commit();prepared(g)
        self.assertFalse(g.can_vote('node-6'))
        with self.assertRaisesRegex(ValueError,'ineligible'):g.begin(node='node-6')
        g.commit(dict(kind='SEAL',number=1));binding=g.state()['results']['1']['binding']
        g.commit(dict(kind='INTENT',number=1,binding=binding));self.assertTrue(g.can_vote('node-6'))
        g.commit(node='node-6');g.commit(node='node-6');result=self.audit(g)
        self.assertGreater(result['learnerVoteEvents'],0)

    def test_lost_seal_ack_recovers_seal_instead_of_cancelling(self):
        g=m.Group();g.commit();prepared(g)
        handle,owners=g.begin(dict(kind='SEAL',number=1));g.select(handle,owners);g.exchange(handle,'accept',owners)
        for node in m.NODES:g.crash(node);g.restart(node)
        # A CANCEL request is legal against the last applied READY state, but the
        # selected ACCEPT tail wins. The driver must apply that selected SEAL.
        certificate=g.commit(dict(kind='CANCEL',number=1))
        selected=t.Entry.read(certificate.value);self.assertEqual('SEAL',g.commands[selected.payload]['kind'])
        self.assertEqual('SEALED',g.state()['results']['1']['phase'])
        with self.assertRaisesRegex(ValueError,'irreversible'):g.commit(dict(kind='CANCEL',number=1))
        finish(g);self.audit(g)

    def test_cancel_chosen_first_blocks_delayed_transition(self):
        g=m.Group();g.commit();prepared(g);g.commit(dict(kind='CANCEL',number=1))
        with self.assertRaisesRegex(ValueError,'active'):g.commit(dict(kind='SEAL',number=1))
        g.commit(dict(kind='RETIRE',through=1));self.audit(g)

    def test_new_preparation_after_data_uses_same_client_request(self):
        g=m.Group();g.commit();request,old=prepared(g);g.commit(dict(kind='DATA',value='advanced'))
        with self.assertRaisesRegex(ValueError,'stale'):g.commit(dict(kind='SEAL',number=1))
        g.commit(dict(kind='PREPARE',number=1,revision=2))
        with self.assertRaisesRegex(ValueError,'stale'):g.commit(dict(kind='READY',number=1,receipt=old))
        g.commit(dict(kind='READY',number=1,receipt=g.materialize()));finish(g)
        self.assertEqual(request,g.state()['results']['1']['request']);self.audit(g)

    def test_joint_final_and_new_barrier_survive_proof_before_publication_crash(self):
        g=m.Group();g.commit();prepared(g,'REPLACE');g.commit(dict(kind='SEAL',number=1))
        handle,owners=g.begin(dict(kind='INTENT',number=1,binding=g.state()['results']['1']['binding']))
        g.select(handle,owners);g.exchange(handle,'accept',owners);g.exchange(handle,'proof',owners)
        g.engine.certify(handle);g.flush()
        for node in m.NODES:g.crash(node);g.restart(node)
        g.commit();finish(g)
        self.assertFalse(g.can_vote('node-1'));self.assertTrue(g.can_vote('node-6'));self.audit(g)

    def test_missing_learner_force_or_body_is_rejected_by_combined_observer(self):
        g=m.Group();g.commit();prepared(g);finish(g);record=g.evidence();self.audit(g)
        for event in ('image-force','receipt-force','command'):
            changed=deepcopy(record);index=next(i for i,e in enumerate(changed['events']) if e['event']==event)
            del changed['events'][index]
            with self.subTest(event=event),self.assertRaises(ValueError):o.check(changed)

    def test_higher_global_fence_blocks_pending_control_force(self):
        g=m.Group();g.commit();prepared(g);handle,owners=g.begin(dict(kind='SEAL',number=1));g.select(handle,owners)
        message=g.engine.send(handle,'accept',owners)[0];g.engine.deliver(handle,message);g.flush()
        node=owners[0];g.engine.observe(node,m.a.b.Ballot(handle[1].counter+10,'node-2','durable-node-2'));g.flush()
        with self.assertRaisesRegex(ValueError,'promise'):g.engine.force_vote(handle,node)
        self.audit(g)

    def test_configuration_change_cannot_be_wrapped_as_ordinary_control(self):
        g=m.Group();g.commit();prepared(g);g.commit(dict(kind='SEAL',number=1))
        command=dict(kind='INTENT',number=1,binding=g.state()['results']['1']['binding']);name=g.register(command)
        with self.assertRaisesRegex(ValueError,'kind confusion'):g.decode(t.Entry('CONTROL',payload=name),g.state())

    def test_directed_crash_matrix_and_serialized_replay(self):
        for target in r.TARGETS:
            for cut in r.CUTS:
                record,audit=r.scenario(3,'ADD',target,cut)
                restored=r.decode(json.loads(t.encoded(record)))
                self.assertEqual(audit['events'],o.check(restored)['events']);r.coverage(restored)

    def test_case_labels_require_the_actual_interrupted_force_boundary(self):
        record,_=r.scenario(3,'ADD','SEAL','accept-one');record['cut']='accept-all'
        with self.assertRaisesRegex(ValueError,'relabelled'):r.coverage(record)
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay({})

    def test_five_to_four_removed_proposer_stays_in_joint_selected_sources(self):
        g=m.Group(5);g.commit();prepared(g,'REMOVE');g.commit(dict(kind='SEAL',number=1))
        g.commit(dict(kind='INTENT',number=1,binding=g.state()['results']['1']['binding']))
        handle,owners=g.begin(node='node-1')
        self.assertIn('node-1',owners);self.assertEqual(4,len(owners));self.assertTrue(handle[0].quorum(owners))
        self.audit(g)


if __name__=='__main__':unittest.main()
