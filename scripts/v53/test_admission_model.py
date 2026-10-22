"""Adversarial authority elision, materialization and identity evidence."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import admission_model as m
from . import admission_oracle as o
from . import admission_research as r
from . import transition_model as t
from . import transition_research as tr
from .membership_model import NODES


def ready():
    source, request, identities = r.fixture()
    learner = m.Learner(source,request,identities); image = source.capsule(1)
    learner.reserve();learner.force();learner.image(image);learner.force();learner.receipt();learner.force()
    return source,learner


class AdmissionTest(unittest.TestCase):
    def test_every_cut_recovers_add_and_peak_six_identity_replacement(self):
        for before,after in ((3,4),(5,5)):
            for cut in r.CUTS:
                with self.subTest(profile=(before,after),cut=cut):
                    _,audit = r.scenario(before,after,1,False,cut)
                    self.assertTrue(audit['final']);self.assertGreater(audit['eligible'],0)

    def test_source_proofs_never_assume_the_new_learner_has_voted_or_installed(self):
        for before,after in r.PROFILES:
            source,request,_ = r.fixture(before,after)
            observer = o.Observer(source.evidence());joining = request['joining']['voter']
            self.assertNotIn(joining,observer.source_voters)
            self.assertNotIn(joining,observer.source_installed)
            self.assertEqual((),source.world.nodes[joining].chain)

    def test_observer_rejects_circular_preinstalled_learner_fixture(self):
        record,_ = r.scenario(3,3,1,False,'healthy')
        source,request,_ = r.fixture(3,3)
        node = request['joining']['voter'];source.world.install(node,source.chain);source.world.force_install(node)
        record['source']['input'] = m.plain(source.world.events)
        with self.assertRaisesRegex(ValueError,'already used'):o.check(record)

    def test_stable_data_compresses_but_configuration_proofs_remain(self):
        source,_,_ = r.fixture(3,4,8)
        packet = source.capsule(10)
        self.assertEqual(['gap','configuration','configuration'],[x['kind'] for x in packet['items']])
        self.assertEqual(11,source.verify(packet)['index']); o.Observer(source.evidence())

    def test_all_seven_transition_shapes_keep_complete_boundaries(self):
        for before,after in tr.PROFILES:
            world = t.World(NODES[:before]);chain = tr.commit(world,(),t.Entry('DATA',payload='x'))
            target = NODES[:after] if before!=after else NODES[1:after+1]
            chain = tr.commit(world,chain,t.Entry('INTENT','boundary',target))
            chain = tr.commit(world,chain,t.Entry('FINAL','boundary',target))
            source = m.Source(world,chain); packet = source.capsule(3,last=True)
            self.assertEqual(list(target),packet['next']['old']);o.Observer(source.evidence())

    def test_gap_endorsement_requires_force_and_distinct_real_voters(self):
        source,_,_ = r.fixture(); packet = source.capsule(1)
        for owners in (['node-1','node-1'],['node-1'],['node-1','node-6']):
            changed = deepcopy(packet);changed['items'][0]['owners'] = owners
            with self.subTest(owners=owners),self.assertRaisesRegex(ValueError,'quorum'):source.verify(changed)
        source.endorsed.clear()
        statement = packet['items'][0]['statement']
        for node in ('node-1','node-2'): source.stage_endorsement(node,statement)
        with self.assertRaisesRegex(ValueError,'quorum'):source.verify(packet)
        source.crash_endorser('node-1')
        with self.assertRaisesRegex(ValueError,'staged'):source.force_endorsement('node-1')

    def test_gap_cannot_hide_joint_transition(self):
        source,_,_ = r.fixture()
        with self.assertRaisesRegex(ValueError,'hide configuration'): source.statement(0,3)

    def test_raw_hash_or_latest_configuration_is_not_authority(self):
        source,_,_ = r.fixture(); packet = source.capsule(3)
        for changed in (dict(packet,items=[]),dict(packet,items=packet['items'][2:])):
            with self.assertRaises(ValueError):source.verify(changed)

    def test_same_voters_after_round_trip_do_not_allow_hiding_membership(self):
        world,_ = tr.walk(); chain = world.nodes[NODES[0]].chain;source = m.Source(world,chain)
        packet = source.capsule(len(chain))
        statement = dict(start=m.plain(source.views[0]),after=m.plain(source.views[-1]),
                         stateBefore=source.states[0],stateAfter=source.states[-1])
        # Even a trace that forges matching endorsement stage/force must fail the observer.
        record = source.evidence();record['events'] = []
        for node in NODES[:2]:
            for action in ('endorsement-stage','endorsement-force'):
                record['events'].append(dict(event=action,node=node,statement=statement))
        packet['items'] = [dict(kind='gap',statement=statement,owners=list(NODES[:2]))]
        record['events'].append(dict(event='capsule',packet=packet))
        with self.assertRaisesRegex(ValueError,'hidden membership'):o.Observer(record)

    def test_membership_capacity_does_not_limit_more_data(self):
        world,_ = tr.walk();chain = world.nodes[NODES[0]].chain
        for i in range(8):chain = tr.commit(world,chain,t.Entry('DATA',payload=str(i)))
        source = m.Source(world,chain);packet = source.capsule(len(chain))
        self.assertEqual(4,packet['next']['generation']);self.assertEqual(13,len(packet['items']))
        o.Observer(source.evidence())
        before = len(world.events)
        with self.assertRaisesRegex(ValueError,'capacity'):source.admit_change(packet)
        self.assertEqual(before,len(world.events))
        chain = tr.commit(world,chain,t.Entry('INTENT','too-many',NODES[:4]))
        with self.assertRaisesRegex(ValueError,'capacity'):m.Source(world,chain).capsule(len(chain))

    def test_capsule_root_cut_state_and_attestation_tampering_rejected(self):
        source,_,_ = r.fixture(); packet = source.capsule(1)
        variants = []
        changed = deepcopy(packet);changed['root'] = 'foreign';variants.append(changed)
        changed = deepcopy(packet);changed['state'] = '0'*64;variants.append(changed)
        changed = deepcopy(packet);changed['next']['index'] += 1;variants.append(changed)
        changed = deepcopy(packet);changed['items'][0]['statement']['stateAfter'] = '0'*64;variants.append(changed)
        for changed in variants:
            with self.assertRaises(ValueError):source.verify(changed)

    def test_duplicate_request_exact_and_changed_payload_rejected(self):
        _,learner = ready(); before = deepcopy(learner.durable)
        self.assertFalse(learner.reserve(deepcopy(learner.request)))
        changed = deepcopy(learner.request);changed['joining']['endpoint'] = 'different:9000'
        with self.assertRaisesRegex(ValueError,'duplicate'):learner.reserve(changed)
        self.assertEqual(before,learner.durable)

    def test_receipt_requires_forced_image_and_does_not_grant_vote(self):
        source,request,identities = r.fixture();learner = m.Learner(source,request,identities)
        image = source.capsule(1);learner.reserve();learner.force();learner.image(image)
        with self.assertRaisesRegex(ValueError,'materialization force'):learner.receipt()
        learner.force();learner.receipt();learner.force()
        with self.assertRaisesRegex(ValueError,'cannot vote'):learner.vote(image['next'],request['joining'],1)
        o.check(learner.evidence())

    def test_staged_intent_and_late_session_cannot_vote(self):
        source,learner = ready();joint = source.capsule(2)
        learner.adopt(joint)
        with self.assertRaisesRegex(ValueError,'cannot vote'):learner.vote(joint['next'],learner.request['joining'],1)
        learner.force();learner.crash();learner.restart()
        with self.assertRaisesRegex(ValueError,'session'):learner.vote(joint['next'],learner.request['joining'],1)
        learner.vote(joint['next'],learner.request['joining'],2);o.check(learner.evidence())

    def test_old_cut_and_foreign_operation_materialization_rejected(self):
        source,request,identities = r.fixture(length=8);learner = m.Learner(source,request,identities)
        learner.reserve();learner.force()
        with self.assertRaisesRegex(ValueError,'exact predecessor'):learner.image(source.capsule(1))
        source,request,identities = r.fixture();request = deepcopy(request);request['operation'] = 'different'
        learner = m.Learner(source,request,identities);learner.reserve();learner.force()
        learner.image(source.capsule(1));learner.force();learner.receipt();learner.force()
        with self.assertRaisesRegex(ValueError,'different operation'):learner.adopt(source.capsule(2))

    def test_intent_binds_full_descriptor_not_only_caller_id_and_voter(self):
        source,request,identities = r.fixture();request['joining']['storage'] = 'other-disk'
        learner = m.Learner(source,request,identities);learner.reserve();learner.force()
        learner.image(source.capsule(1));learner.force();learner.receipt();learner.force()
        with self.assertRaisesRegex(ValueError,'different operation'):learner.adopt(source.capsule(2))

    def test_live_and_retired_identity_parts_cannot_be_reused(self):
        source,request,identities = r.fixture()
        for key in ('storage','endpoint'):
            changed = deepcopy(request);changed['joining'][key] = identities[0][key]
            with self.assertRaisesRegex(ValueError,'identity reuse'):m.Learner(source,changed,identities)
        retired = dict(voter=request['joining']['voter'],storage='retired-disk',endpoint='retired:9000')
        with self.assertRaisesRegex(ValueError,'identity reuse'):m.Learner(source,request,identities+[retired])

    def test_new_disk_old_session_and_removed_voter_rejected_by_current_receiver(self):
        source,request,identities = r.fixture(3,3)
        final = source.capsule(3)['next'];joint = source.capsule(2)['next']
        known = identities+[request['joining']]
        self.assertFalse(m.frame_allowed(final,known,identities[0],final))
        self.assertFalse(m.frame_allowed(final,known,request['joining'],joint))
        changed = dict(request['joining'],storage='copy-with-new-id')
        self.assertFalse(m.frame_allowed(final,known,changed,final))
        self.assertTrue(m.frame_allowed(final,known,request['joining'],final))

    def test_adoption_cannot_go_back_from_final_to_joint(self):
        source,learner = ready();final = source.capsule(3);joint = source.capsule(2)
        learner.adopt(final);learner.force()
        with self.assertRaisesRegex(ValueError,'rollback'):learner.adopt(joint)

    def test_observer_rejects_deleted_forces_and_early_eligibility(self):
        record,_ = r.scenario(3,4,1,False,'healthy');o.check(record)
        for kind in ('reservation','image','receipt','authority'):
            changed = deepcopy(record)
            index = next(i for i,e in enumerate(changed['events']) if e['event']=='force' and e['kind']==kind)
            del changed['events'][index]
            with self.subTest(kind=kind),self.assertRaises(ValueError):o.check(changed)
        changed = deepcopy(record);event = next(e for e in record['events'] if e['event']=='eligible')
        changed['events'].insert(0,event)
        with self.assertRaisesRegex(ValueError,'eligibility'):o.check(changed)

    def test_observer_rejects_forged_receipt_and_descriptor_binding(self):
        record,_ = r.scenario(3,4,1,False,'healthy')
        for field in ('image','request'):
            changed = deepcopy(record)
            for event in changed['events']:
                if event.get('kind')=='receipt':event['value'][field]='0'*64
            with self.assertRaisesRegex(ValueError,'receipt'):o.check(changed)

    def test_future_endorsements_cannot_validate_an_earlier_image(self):
        record,_ = r.scenario(3,4,1,False,'healthy')
        for event in record['events']:
            event['sourceThrough'] = 0
        with self.assertRaisesRegex(ValueError,'unforced gap quorum'):o.check(record)

    def test_observer_is_independent_of_live_admission_and_capsule_guards(self):
        record,_ = r.scenario(3,4,1,False,'healthy')
        with patch.object(m.Source,'verify',side_effect=AssertionError('live verifier called')), \
             patch.object(m.Learner,'adopt',side_effect=AssertionError('live admission called')):
            self.assertTrue(o.check(record)['final'])

    def test_portable_evidence_round_trip_and_missing_inventory(self):
        record,audit = r.scenario(3,4,1,False,'healthy')
        self.assertEqual(audit,o.check(json.loads(json.dumps(record))))
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay({r.name(record):record})

    def test_relabelled_crash_cut_or_quorum_cannot_substitute_for_coverage(self):
        record,_ = r.scenario(3,4,1,False,'image-stage')
        changed = deepcopy(record);changed['cut'] = 'image-force'
        with self.assertRaisesRegex(ValueError,'cut relabelled'):r.coverage(changed)
        changed = deepcopy(record);changed['last'] = True
        with self.assertRaisesRegex(ValueError,'quorum relabelled'):r.coverage(changed)

    def test_incomplete_cli_cannot_claim_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'result'
            result = subprocess.run([sys.executable,'-m','scripts.v53.admission_research','--output',str(output),
                                     '--max-cases','0'],capture_output=True,text=True)
            self.assertEqual(2,result.returncode,result.stderr)
            receipt = json.loads((output/'receipt.json').read_text())
            self.assertEqual('INCOMPLETE',receipt['status']);self.assertFalse(receipt['productionQualified'])


if __name__=='__main__':unittest.main()
