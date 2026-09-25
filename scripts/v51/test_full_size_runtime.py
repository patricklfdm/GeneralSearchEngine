"""Adversarial public-history tests. Synthetic records are not execution evidence."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import full_size_runtime_evidence as e, performance_fixtures as fixtures, cloud_workload_contract as cloud


class FullSizeRuntimeTest(unittest.TestCase):
    def test_all_boundary_mutations_stay_in_frozen_rich_corpus(self):
        from .full_size_runtime import mutation
        observed=[]
        for ordinal in range(1,512):
            args=mutation(ordinal);doc=e.m.document(args['key'],args['revision'])
            self.assertEqual(doc,e.m.decode_document(e.m.encode_document(doc)))
            observed.append((args['key'],args['revision']))
        self.assertEqual(511,len(set(observed)))
        for ordinal in (0,512):
            with self.assertRaises(ValueError):mutation(ordinal)

    def test_stop_target_preserves_every_possible_selected_majority(self):
        from .full_size_runtime import spare_follower, NODES
        for leader in NODES:
            for peer in NODES:
                if peer==leader:continue
                selected=dict(ballot=dict(epoch=13,proposer=leader),bases=[dict(node=n) for n in sorted((leader,peer))])
                with self.subTest(leader=leader,peer=peer):
                    stopped=spare_follower(leader,dict(state='LEADER_READY',epoch=13,provenIndex=500),selected)
                    self.assertEqual(set(NODES)-{leader,peer},{stopped})
        # Hosted failure: node-3 was using node-1; the ordinal-based choice killed node-1.
        self.assertEqual('node-2',spare_follower('node-3',dict(state='LEADER_READY',epoch=13,provenIndex=500),
            dict(ballot=dict(epoch=13,proposer='node-3'),bases=[dict(node='node-1'),dict(node='node-3')])))

    def test_stop_target_rejects_stale_leader_cut_and_invalid_pairs(self):
        from .full_size_runtime import spare_follower
        state=dict(state='LEADER_READY',epoch=13,provenIndex=500)
        selected=dict(ballot=dict(epoch=13,proposer='node-3'),bases=[dict(node='node-1'),dict(node='node-3')])
        for changed in (dict(state='FOLLOWER'),dict(epoch=14),dict(provenIndex=499),dict(provenIndex=501)):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'current slot-500 leader'):
                spare_follower('node-3',dict(state,**changed),selected)
        for pair in (['node-1','node-2'],['node-3','node-3'],['node-3','node-4'],['node-3']):
            with self.subTest(pair=pair),self.assertRaisesRegex(ValueError,'selected pair'):
                spare_follower('node-3',state,dict(selected,bases=[dict(node=n) for n in pair]))
        with self.assertRaisesRegex(ValueError,'current slot-500 leader'):
            spare_follower('node-3',state,dict(selected,ballot=dict(epoch=13,proposer='node-1')))

    def stop_sample(self):
        # Codec stand-ins isolate stop-to-original-selection/publication binding.
        encode=lambda v:base64.b64encode(e.m.canonical(v)).decode()
        ballot=dict(epoch=13,proposer='node-3',incarnation='ballot')
        selected=encode(dict(ballot=ballot,bases=[dict(node='node-1'),dict(node='node-3')]))
        proof=encode(dict(ballot,index=500,receipts=[dict(voter='node-1'),dict(voter='node-3')]))
        snapshot=encode(dict(anchors=[None]*500,terminalProof=proof))
        runtime=dict(fullTransferNode='node-2',followerStop=dict(leader='node-3',leaderGeneration=1,
            generation=2,selected=selected,beforeNanos=30),
            processes=[dict(node='node-2',generation=2,startNanos=1,endNanos=40,exitCode=0)])
        traces={'node-3':[dict(event='PROMISE_QUORUM',generation=1,localNanos=10,selected=selected),
                          dict(event='PUBLISHED',generation=1,localNanos=20,snapshot=snapshot)]}
        return runtime,traces

    def test_stop_evidence_binds_original_selection_publication_and_lifetime(self):
        runtime,traces=self.stop_sample()
        with patch.object(e.fmt,'contextual_frame',side_effect=lambda data,*_:e.m.strict_json(data)):
            e.follower_stop(runtime,traces,{})
            for field,value,reason in [('fullTransferNode','node-1','stopped selected voter')]:
                with self.assertRaisesRegex(ValueError,reason):e.follower_stop(dict(runtime,**{field:value}),traces,{})
            for field,value,reason in [('generation',1,'stop lifetime'),('beforeNanos',41,'stop lifetime'),
                                      ('leaderGeneration',2,'stop selection')]:
                changed=copy.deepcopy(runtime);changed['followerStop'][field]=value
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,reason):e.follower_stop(changed,traces,{})
            for event,reason in [('PROMISE_QUORUM','stop selection'),('PUBLISHED','stop publication')]:
                changed=copy.deepcopy(traces);changed['node-3']=[r for r in changed['node-3'] if r['event']!=event]
                with self.subTest(event=event),self.assertRaisesRegex(ValueError,reason):e.follower_stop(runtime,changed,{})

    def test_stop_evidence_rejects_wrong_publication_cut_or_vote_pair(self):
        for change in ('cut','pair','epoch'):
            runtime,traces=self.stop_sample();row=traces['node-3'][-1]
            snapshot=e.m.strict_json(e.raw(row['snapshot']));proof=e.m.strict_json(e.raw(snapshot['terminalProof']))
            if change=='cut':snapshot['anchors'].pop();proof['index']=499
            elif change=='pair':proof['receipts'][0]['voter']='node-2'
            else:proof['epoch']=12
            snapshot['terminalProof']=base64.b64encode(e.m.canonical(proof)).decode()
            row['snapshot']=base64.b64encode(e.m.canonical(snapshot)).decode()
            with self.subTest(change=change),patch.object(e.fmt,'contextual_frame',side_effect=lambda data,*_:e.m.strict_json(data)):
                with self.assertRaisesRegex(ValueError,'wrong cut/pair'):e.follower_stop(runtime,traces,{})

    def recovery_sample(self):
        # Actual encoded frames: capture at slot 2/epoch 2, then a forced slot-3
        # proof in epoch 5 while the captured node remains the other voter.
        from . import format_encoder as enc
        fixture=fixtures.generate(e.plan.load(),program=[cloud.call('UPDATE',[1],0),cloud.call('UPDATE',[2],0)])
        ballot=dict(epoch=5,proposer='node-1',incarnation='22222222-2222-2222-2222-222222222222')
        for votes in fixture['votes'].values():
            vote=e.fmt.inspect(votes[-1],'ACCEPT');vote.update(ballot);votes[-1]=enc.encode('ACCEPT',vote)
        proof=e.fmt.inspect(fixture['proofs'][-1],'PROOF');proof.update(ballot)
        for receipt in proof['receipts']:
            receipt['digest']=fixtures.fixtures.fixture_receipt('ACCEPT_ACK',proof['manifestDigest'],receipt['voter'],
                proof['epoch'],proof['proposer'],proof['incarnation'],proof['index'],proof['entryDigest'])
        encoded=enc.encode('PROOF',proof)
        snapshot=e.fmt.inspect(fixture['snapshots'][-1],'SNAPSHOT');snapshot['terminalProof']=base64.b64encode(encoded).decode()
        row=dict(node='node-2',event='FORCE',kind='PROOF',localNanos=30,record=base64.b64encode(encoded).decode(),
                 snapshot=base64.b64encode(enc.encode('SNAPSHOT',snapshot)).decode())
        projected=e.projection.project_cloud(fixture['manifest'],fixture['genesis'],fixture['votes'])
        capture=dict(node='node-2',index=2,sequence=projected['states'][2].sequence,epoch=2)
        return row,capture,dict(localNanos=20),projected

    def test_released_follower_recovers_from_exact_forced_quorum_proof(self):
        row,capture,release,projected=self.recovery_sample()
        self.assertEqual(dict(node='node-2',event='FORCED_PROOF',index=3,sequence=6),
                         e.released_recovery([row],capture,release,projected))
        # Both earlier recovery paths remain valid under the same prefix oracle.
        for event in ('REJOIN_INSTALLED','PUBLISHED'):
            owner='node-1' if event=='PUBLISHED' else 'node-2'
            result=e.released_recovery([dict(row,event=event,node=owner)],dict(capture,node=owner),release,projected)
            self.assertEqual((event,3,6),(result['event'],result['index'],result['sequence']))

    def test_released_recovery_rejects_wrong_owner_time_or_no_new_application_state(self):
        row,capture,release,projected=self.recovery_sample()
        for changed in (dict(node='node-1'),dict(localNanos=20),dict(localNanos=19),dict(event='RECONSTRUCT_END')):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError,'did not recover newer prefix'):
                e.released_recovery([dict(row,**changed)],capture,release,projected)
        for changed in (dict(index=3),dict(sequence=6),dict(epoch=5)):
            with self.subTest(capture=changed),self.assertRaisesRegex(ValueError,'did not recover newer prefix'):
                e.released_recovery([row],dict(capture,**changed),release,projected)
        with self.assertRaisesRegex(ValueError,'did not recover newer prefix'):
            e.released_recovery([],capture,release,projected)
        with self.assertRaisesRegex(ValueError,'did not recover newer prefix'):
            e.released_recovery([dict(row,node='node-3')],dict(capture,node='node-3'),release,projected)

    def test_released_recovery_requires_exact_ballot_votes_and_chosen_digest(self):
        row,capture,release,projected=self.recovery_sample()
        proof=e.fmt.inspect(e.raw(row['record']),'PROOF')
        identity=tuple(proof[k] for k in ('epoch','proposer','incarnation','index','entryDigest'))
        for variant in ('missing-ballot','missing-voter','different-chosen'):
            changed=copy.deepcopy(projected)
            if variant=='missing-ballot':del changed['accepted'][identity]
            elif variant=='missing-voter':changed['accepted'][identity].remove('node-2')
            else:changed['chosen'][3]='0'*64
            with self.subTest(variant=variant),self.assertRaisesRegex(ValueError,'proof lacks exact chosen votes'):
                e.released_recovery([row],capture,release,changed)

    def test_released_recovery_rejects_corrupt_frames_and_unprojected_snapshots(self):
        from . import format_encoder as enc
        row,capture,release,projected=self.recovery_sample()
        damaged=bytearray(e.raw(row['record']));damaged[-1]^=1
        with self.assertRaises(ValueError):
            e.released_recovery([dict(row,record=base64.b64encode(damaged).decode())],capture,release,projected)
        snapshot=e.fmt.inspect(e.raw(row['snapshot']),'SNAPSHOT');snapshot['applicationSequence']+=1
        changed=dict(row,event='REJOIN_INSTALLED',snapshot=base64.b64encode(enc.encode('SNAPSHOT',snapshot)).decode())
        with self.assertRaisesRegex(ValueError,'application sequence'):
            e.released_recovery([changed],capture,release,projected)

    def sample(self):
        program=[cloud.call('UPDATE',[1],0),cloud.call('GET',[1],0),cloud.call('UPDATE',[2],0)]
        fixture=fixtures.generate(e.plan.load(),program=program)
        projected=e.projection.project_cloud(fixture['manifest'],fixture['genesis'],fixture['votes'])
        snapshots={i:e.fmt.inspect(raw,'SNAPSHOT') for i,raw in enumerate(fixture['snapshots'],1)}
        published={2:(snapshots[2],3),3:(snapshots[3],7)}
        proof=e.fmt.inspect(e.raw(snapshots[3]['terminalProof']),'PROOF')
        votes={(proof['epoch'],proof['incarnation'],3,proof['entryDigest']):6}
        promise=(proof['epoch'],proof['incarnation'])
        history=[dict(opId='write',kind='update',node='node-1',generation=1,pid=42,startNanos=0,endNanos=100,outcome='SUCCESS',key=1,revision=1),
                 dict(opId='read',kind='read',node='node-1',generation=1,pid=42,startNanos=0,endNanos=100,outcome='SUCCESS',documents=e.documents(projected['states'][3])),
                 dict(opId='crash',kind='update',node='node-1',generation=1,pid=42,startNanos=0,endNanos=None,outcome='PENDING',disconnectNanos=100,key=2,revision=1)]
        rows=[]
        def row(event,order,**values):rows.append(dict(event=event,order=order,localNanos=order,node='node-1',pid=42,generation=1,**values))
        def invoke(index,order):row('CLIENT_INVOKE',order,**{k:v for k,v in history[index].items() if k in ('opId','kind','key','revision')})
        invoke(0,1);row('CLIENT_RESULT',4,opId='write',kind='update',outcome='SUCCESS')
        invoke(1,5);row('PUBLIC_READ_INVOKE',5.5,opId='read',readId=1)
        for event,order in [('READ_CAPTURE_VALIDATED',8),('READ_CAPTURED',9),('READ_RELEASED',10)]:
            row(event,order,readId=1,index=3,epoch=proof['epoch'],sequence=snapshots[3]['applicationSequence'])
        row('CLIENT_RESULT',11,opId='read',kind='read',outcome='SUCCESS',documents=history[1]['documents'])
        invoke(2,12)
        return history,rows,projected,published,votes,promise

    def audit(self,sample):
        history,rows,projected,published,votes,promise=sample
        calls=e.Calls(history,{'uncertainOpId':'crash'})
        for row in rows:calls.event('node-1',row,projected,published,votes,promise)
        calls.finish();return calls

    def test_chosen_crash_has_no_fabricated_success(self):
        audit=self.audit(self.sample());self.assertEqual(2,len(audit.mutations));self.assertEqual(1,len(audit.read_barriers))
        sample=self.sample();sample[0][-1]['outcome']='SUCCESS'
        with self.assertRaisesRegex(ValueError,'invented crash response'):self.audit(sample)

    def test_resealed_controller_and_worker_answer_from_other_cut_fails(self):
        sample=self.sample();wrong=e.documents(sample[2]['states'][4]);self.assertNotEqual(wrong,sample[0][1]['documents'])
        sample[0][1]['documents']=wrong;next(r for r in sample[1] if r['event']=='CLIENT_RESULT' and r['kind']=='read')['documents']=wrong
        with self.assertRaisesRegex(ValueError,'captured answer'):self.audit(sample)

    def test_missing_release_stale_capture_and_old_barrier_fail(self):
        sample=self.sample();sample[1][:]=[r for r in sample[1] if r['event']!='READ_RELEASED']
        with self.assertRaisesRegex(ValueError,'before read release'):self.audit(sample)
        sample=list(self.sample());sample[-1]=(99,sample[-1][1])
        with self.assertRaisesRegex(ValueError,'stale capture'):self.audit(sample)
        sample=self.sample();sample[4][next(iter(sample[4]))]=1
        with self.assertRaisesRegex(ValueError,'fresh read barrier'):self.audit(sample)

    def test_reordered_write_missing_invocation_and_changed_release_fail(self):
        for event,field,value,reason in [('CLIENT_RESULT','order',2,'before own publication'),
                ('PUBLIC_READ_INVOKE','opId','write','read identity'),('READ_RELEASED','index',4,'changed read release')]:
            with self.subTest(event=event):
                sample=self.sample();next(r for r in sample[1] if r['event']==event)[field]=value
                with self.assertRaisesRegex(ValueError,reason):self.audit(sample)

    def test_read_ids_are_scoped_to_original_process_generation(self):
        sample=self.sample();self.audit(sample)
        for row in sample[1]:
            if row['event']=='READ_RELEASED':row['generation']=2
        with self.assertRaisesRegex(ValueError,'unowned release'):self.audit(sample)

    def test_refused_reads_still_consume_the_auxiliary_attempt_budget(self):
        sample=self.sample();history=sample[0]
        for i in range(8):history.append(dict(history[1],opId='refused-'+str(i),outcome='NOT_APPLICABLE'))
        with self.assertRaisesRegex(ValueError,'auxiliary read attempt bound'):e.Calls(history,{'uncertainOpId':'crash'})

    def test_whole_transfer_includes_pre_offer_work_and_requires_probe(self):
        # Synthetic codec stand-ins isolate the clock/range algorithm, not execution evidence.
        encode=lambda value:base64.b64encode(e.m.canonical(value)).decode()
        image=b'x'*64;snapshot=base64.b64encode(b'snapshot').decode()
        offer=dict(transferId='transfer',imageBytes=len(image),imageDigest=image[16:48].hex(),response=False)
        chunk=dict(transferId='transfer',offset=0,maxChunkBytes=4096,chunk=base64.b64encode(image).decode(),action='DATA')
        install=dict(transferId='transfer',imageDigest=offer['imageDigest'],response=False)
        def message(kind,payload):return dict(recipient='node-2',type=kind,payload=payload,epoch=2,incarnationId='epoch',traceId='trace',proposer='node-1')
        def event(kind,payload,time,response=None):
            row=dict(event='REQUEST' if response is None else 'RECEIVED',pid=1,localNanos=time,request=encode(message(kind,payload)))
            if response is not None:row['frame']=encode(message(kind,response))
            return row
        rows=[event('AUTHORITY_STATUS_PROBE',{},0),event('SNAPSHOT_OFFER',offer,1_000_000_000),
              event('SNAPSHOT_CHUNK',chunk,2_000_000_000,dict(chunk,action='ACK',chunk='')),
              event('REJOIN_INSTALL',install,3_000_000_000,dict(install,response=True))]
        traces={'node-1':rows,'node-2':[dict(event='REJOIN_INSTALLED',transferId='transfer',snapshot=snapshot)]}
        with patch.object(e.fmt,'wire',side_effect=lambda data,_:e.m.strict_json(data)), \
             patch.object(e.fmt,'contextual_frame',return_value={'snapshot':snapshot}), \
             patch.object(e.fmt,'inspect',return_value={'anchors':[None]*512}):
            self.assertEqual(2_000_000_000,e.transfer(traces,{},'node-2')['elapsedNanos'])
            rows[0]['localNanos']=-7_000_000_000
            with self.assertRaisesRegex(ValueError,'whole transfer deadline'):e.transfer(traces,{},'node-2')
            rows.pop(0)
            with self.assertRaisesRegex(ValueError,'without authority probe'):e.transfer(traces,{},'node-2')

    def test_invalid_original_cannot_be_accepted_as_negative_evidence(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')):
            with self.assertRaisesRegex(ValueError,'invalid original'):e.negatives('/unused')

    def test_relocation_inventory_is_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'member').write_bytes(b'x')
            with self.assertRaises((FileNotFoundError,ValueError)):e.remote.EvidenceLocation(root,'/original')


if __name__=='__main__':unittest.main()
