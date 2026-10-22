from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
import io
import json

from . import operation_model as m
from . import operation_oracle as o
from . import operation_research as r


def store(size=3,limits=m.Limits()):return m.Store([m.identity('node-'+str(i)) for i in range(1,size+1)],limits=limits)


def req(s,kind='ADD',name='node-6'):
    target=deepcopy(s.state['members'])
    if kind in ('REMOVE','REPLACE'):target.pop(0)
    if kind in ('ADD','REPLACE'):target.append(m.identity(name))
    return m.request(s.state,sorted(target,key=lambda x:x['voter']),kind)


def prepare(s,number=1):
    row=s.state['results'][str(number)];s.commit('PREPARE',number=number,revision=row['revision']+1)
    receipt=s.learner_force(number) if m.joining(s.state,row['request']) else None
    s.commit('READY',number=number,receipt=receipt)
    return receipt


def complete(s,number=1):
    phase=s.state['results'][str(number)]['phase']
    if phase in ('RESERVED','PREPARING'):prepare(s,number)
    if s.state['results'][str(number)]['phase']=='READY':s.commit('SEAL',number=number)
    binding=s.state['results'][str(number)]['binding']
    if s.state['results'][str(number)]['phase']=='SEALED':s.commit('INTENT',number=number,binding=binding)
    s.commit('FINAL',number=number,binding=binding)


class OperationTest(unittest.TestCase):
    def audit(self,s):self.assertEqual(s.state,o.check(s.evidence())['state'])

    def test_all_add_remove_replace_sizes(self):
        for size,kind in ((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE')):
            with self.subTest(size=size,kind=kind):
                s=store(size);request=req(s,kind);s.submit(request);prepare(s);complete(s)
                self.assertEqual('COMPLETED',s.query(s.state['root'],1)['phase']);self.assertEqual(request['target'],s.state['members'])
                self.audit(s)

    def test_preparation_revisions_preserve_client_identity(self):
        s=store();request=req(s);s.submit(request);old=prepare(s);s.commit('DATA',value='during-transfer')
        before=deepcopy(s.state)
        with self.assertRaisesRegex(ValueError,'stale'):s.commit('SEAL',number=1)
        self.assertEqual(before,s.state)
        s.commit('PREPARE',number=1,revision=2)
        with self.assertRaisesRegex(ValueError,'stale'):s.commit('READY',number=1,receipt=old)
        current=s.learner_force(1);s.commit('READY',number=1,receipt=current);complete(s)
        self.assertEqual(request,s.submit(request)['request']);self.assertEqual(2,s.submit(request)['revision']);self.audit(s)

    def test_unforced_receipt_cannot_mark_ready(self):
        s=store();s.submit(req(s));s.commit('PREPARE',number=1,revision=1)
        receipt=m.receipt_for(s.state,1)
        with self.assertRaisesRegex(ValueError,'unforced'):s.commit('READY',number=1,receipt=receipt)
        s.learner_force(1);s.commit('READY',number=1,receipt=receipt);self.audit(s)

    def test_timeout_or_future_cancel_does_not_cancel_operation(self):
        s=store();s.submit(req(s));before=deepcopy(s.state);s.detach_waiter()
        self.assertEqual(before,s.state);self.audit(s)

    def test_cancel_before_seal_consumes_identity_and_result(self):
        for phase in ('RESERVED','PREPARING','READY'):
            s=store();request=req(s);s.submit(request)
            if phase!='RESERVED':s.commit('PREPARE',number=1,revision=1)
            if phase=='READY':s.commit('READY',number=1,receipt=s.learner_force(1))
            s.commit('CANCEL',number=1);self.assertEqual('CANCELLED',s.submit(request)['phase'])
            self.assertEqual(2,s.state['nextOperation']);self.assertIsNone(s.state['active']);self.audit(s)

    def test_cancel_after_seal_or_intent_is_rejected(self):
        for phase in ('SEALED','JOINT'):
            s=store();s.submit(req(s));prepare(s);s.commit('SEAL',number=1)
            if phase=='JOINT':s.commit('INTENT',number=1,binding=s.state['results']['1']['binding'])
            before=deepcopy(s.state)
            with self.assertRaisesRegex(ValueError,'irreversible'):s.commit('CANCEL',number=1)
            with self.assertRaisesRegex(ValueError,'pauses data'):s.commit('DATA',value='late-write')
            self.assertEqual(before,s.state);complete(s);self.audit(s)

    def test_unsealed_or_wrong_binding_cannot_change_members(self):
        s=store();s.submit(req(s));prepare(s)
        with self.assertRaisesRegex(ValueError,'sealed'):s.commit('INTENT',number=1,binding='fake')
        s.commit('SEAL',number=1)
        with self.assertRaisesRegex(ValueError,'exact'):s.commit('INTENT',number=1,binding='fake')
        with self.assertRaisesRegex(ValueError,'joint'):s.commit('FINAL',number=1,binding=s.state['results']['1']['binding'])
        self.audit(s)

    def test_only_final_publishes_new_configuration(self):
        s=store();request=req(s);old=s.state['configuration'];s.submit(request);prepare(s);s.commit('SEAL',number=1)
        binding=s.state['results']['1']['binding'];s.commit('INTENT',number=1,binding=binding)
        self.assertEqual(old,s.state['configuration']);s.stage(dict(kind='FINAL',number=1,binding=binding))
        self.assertEqual(old,s.state['configuration']);s.force();self.assertNotEqual(old,s.state['configuration']);self.audit(s)

    def test_duplicate_payload_conflict_future_number_and_foreign_root(self):
        s=store();request=req(s);s.submit(request);events=len(s.events)
        self.assertEqual(request,s.submit(request)['request']);self.assertEqual(events,len(s.events))
        for key,value in (('root','different'),('number',3),('target',[m.identity(n) for n in ('node-1','node-2','node-3','node-7')])):
            changed=deepcopy(request);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):s.submit(changed)
        self.audit(s)

    def test_result_retirement_never_makes_an_old_request_new(self):
        s=store();request=req(s);s.submit(request);s.commit('CANCEL',number=1);s.commit('RETIRE',through=1)
        before=deepcopy(s.state);self.assertEqual('RETIRED',s.submit(request)['status']);self.assertEqual(before,s.state)
        self.assertEqual('RETIRED',s.query(s.state['root'],1)['status']);self.audit(s)

    def test_retirement_does_not_release_cancelled_identity(self):
        s=store();s.submit(req(s));s.commit('CANCEL',number=1);s.commit('RETIRE',through=1)
        with self.assertRaisesRegex(ValueError,'identity reuse'):s.submit(req(s))
        for key in ('storage','endpoint'):
            request=req(s,name='node-7');request['target'][-1][key]=m.identity('node-6')[key]
            with self.assertRaisesRegex(ValueError,'identity reuse'):s.submit(request)
        self.audit(s)

    def test_retirement_cannot_delete_active_or_unknown_slot(self):
        s=store();s.submit(req(s))
        with self.assertRaisesRegex(ValueError,'active'):s.commit('RETIRE',through=1)
        with self.assertRaisesRegex(ValueError,'range'):s.commit('RETIRE',through=2)

    def test_retirement_crash_preserves_contiguous_high_watermark(self):
        for boundary in ('stage','force'):
            s=store();request=req(s);s.submit(request);s.commit('CANCEL',number=1)
            s.stage(dict(kind='RETIRE',through=1))
            if boundary=='force':s.force()
            s.crash();s.restart()
            self.assertEqual(1 if boundary=='force' else 0,s.state['retiredThrough'])
            self.assertEqual('RETIRED' if boundary=='force' else 'CANCELLED',s.submit(request).get('status',s.submit(request).get('phase')))
            self.audit(s)

    def test_result_capacity_is_released_only_by_certified_retirement(self):
        s=store(limits=replace(m.Limits(),results=1));s.submit(req(s));s.commit('CANCEL',number=1)
        with self.assertRaisesRegex(ValueError,'capacity'):s.submit(req(s,name='node-7'))
        s.commit('DATA',value='data-still-works');s.commit('RETIRE',through=1);s.submit(req(s,name='node-7'));self.audit(s)

    def test_identity_change_revision_and_counter_limits_refuse_before_mutation(self):
        for limit,first in ((replace(m.Limits(),identities=3),'reserve'),(replace(m.Limits(),revisions=1),'revision')):
            s=store(limits=limit)
            if first=='reserve':
                with self.assertRaisesRegex(ValueError,'capacity'):s.submit(req(s))
            else:
                s.submit(req(s));prepare(s)
                with self.assertRaisesRegex(ValueError,'unavailable'):s.commit('PREPARE',number=1,revision=2)
            self.audit(s)
        s=store(limits=replace(m.Limits(),operations=1));s.submit(req(s));s.commit('CANCEL',number=1);s.commit('RETIRE',through=1)
        with self.assertRaisesRegex(ValueError,'number'):s.submit(req(s,name='node-7'))
        self.assertEqual(2,s.state['nextOperation']);s.commit('DATA',value='counter-exhausted');self.audit(s)

    def test_membership_limit_still_permits_data_and_retirement(self):
        s=store(limits=replace(m.Limits(),changes=1));s.submit(req(s));prepare(s);complete(s)
        s.commit('DATA',value='after-last-change');s.commit('RETIRE',through=1)
        with self.assertRaisesRegex(ValueError,'capacity'):s.submit(req(s,'REMOVE'))
        self.audit(s)

    def test_pending_write_excludes_other_commands_and_crash_keeps_durable_prefix(self):
        s=store();request=req(s);s.stage(dict(kind='RESERVE',request=request))
        with self.assertRaisesRegex(ValueError,'busy'):s.commit('DATA',value='concurrent')
        s.crash();s.restart();self.assertEqual(1,s.state['nextOperation']);s.submit(request)
        s.crash();s.restart();self.assertEqual(request,s.submit(request)['request']);self.audit(s)

    def test_oracle_rejects_missing_forces_forged_results_and_future_receipts(self):
        s=store();s.submit(req(s));prepare(s);complete(s);record=s.evidence();self.audit(s)
        for kind in ('RESERVE','PREPARE','READY','SEAL','INTENT'):
            bad=deepcopy(record);index=next(i for i,e in enumerate(bad['events']) if e['event']=='force' and e['command']['kind']==kind)
            del bad['events'][index]
            with self.subTest(kind=kind),self.assertRaises(ValueError):o.check(bad)
        bad=deepcopy(record);bad['events'][-1]['state']['results']['1']['requestHash']='0'*64
        with self.assertRaises(ValueError):o.check(bad)
        bad=deepcopy(record);index=next(i for i,e in enumerate(bad['events']) if e['event']=='learner-force')
        row=bad['events'].pop(index);bad['events'].append(row)
        with self.assertRaisesRegex(ValueError,'forced receipt'):o.check(bad)

    def test_oracle_does_not_call_model_reducer(self):
        s=store();s.submit(req(s));prepare(s);complete(s)
        with patch.object(m,'apply',side_effect=AssertionError('model reducer called')):self.audit(s)

    def test_new_reads_after_known_removal_drain_or_learner_state_fail_all_policies(self):
        for policy in ('LEADER_STRONG','STALE_ALLOWED','AT_LEAST_INDEX'):
            for overrides in (dict(known_removed=True),dict(draining=True),dict(role='LEARNER'),dict(readable=False),
                              dict(role='STARTING'),dict(role='STOPPED'),dict(role='UNKNOWN')):
                values=dict(readable=True,role='LEADER_READY',known_removed=False,draining=False,barrier=True,minimum=5,cut=5)
                values.update(overrides);self.assertFalse(m.read_allowed(policy,**values))

    def test_isolated_unaware_follower_local_reads_keep_their_explicit_contract(self):
        values=dict(readable=True,role='FOLLOWER',known_removed=False,draining=False,minimum=5,cut=5)
        self.assertTrue(m.read_allowed('STALE_ALLOWED',**values));self.assertTrue(m.read_allowed('AT_LEAST_INDEX',**values))
        self.assertFalse(m.read_allowed('LEADER_STRONG',**values))
        self.assertFalse(m.read_allowed('LEADER_STRONG',**dict(values,role='LEADER_READY',barrier=False)))

    def test_maintenance_requires_fresh_challenge_surviving_majority_and_no_operation(self):
        for size in (3,4,5):
            s=store(size);target='node-1';nonce='check-1'
            responses=[dict(voter=row['voter'],configuration=s.state['configuration'],index=s.state['index'],nonce=nonce,ready=True)
                       for row in s.state['members'][1:]]
            plan=m.maintenance(s.state,target,responses,nonce);self.assertEqual(target,plan['target'])
            with self.assertRaises(ValueError):m.maintenance(s.state,target,responses[:size//2],nonce)
            with self.assertRaises(ValueError):m.maintenance(s.state,target,responses,'new-check')
            with self.assertRaises(ValueError):m.maintenance(s.state,target,responses+[responses[0]],nonce)
            s.commit('DATA',value='progress')
            with self.assertRaises(ValueError):m.maintenance(s.state,target,responses,nonce)
            s.submit(req(s,'REMOVE' if size==5 else 'ADD'))
            with self.assertRaisesRegex(ValueError,'pending'):m.maintenance(s.state,target,responses,nonce)

    def test_complete_matrix_replays_serialized_histories(self):
        with redirect_stdout(io.StringIO()):result=r.run()
        self.assertEqual(308,result['counts']['cases'])
        replay=r.replay(json.loads(json.dumps(result['examples'])))
        self.assertEqual(308,replay['histories']);self.assertEqual(result['counts']['commits'],replay['commits'])

    def test_partial_matrix_and_relabelled_cuts_are_not_complete_evidence(self):
        with redirect_stdout(io.StringIO()):result=r.run(1)
        self.assertEqual('INCOMPLETE',result['status'])
        with self.assertRaisesRegex(ValueError,'inventory'):r.replay(result['examples'])
        record=next(iter(result['examples'].values()));record['boundary']='force'
        with self.assertRaisesRegex(ValueError,'relabelled'):r.coverage(record)

    def test_counters_and_limits_never_use_signed_overflow(self):
        for limits in (dict(results=True),dict(operations=2**63-1),dict(revisions=0)):
            with self.assertRaisesRegex(ValueError,'limits'):m.Limits(**limits)


if __name__=='__main__':unittest.main()
