"""Conditional profile boundaries; these do not replace native profile runs."""
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import joining_profile_maintenance_evidence as p
from . import joining_same_view_physical as physical
from . import test_joining_retirement_replay as fixtures


class ProfileMaintenanceTest(unittest.TestCase):
    def governing(self,profile):
        size,kind,old,new=p.topology(profile);joining=new[-1]
        base,models,_=fixtures.JoiningRetirementReplayTest().owners(True);template=models['node-1']
        catalog=p.f.decode(template['objects'][template['capsule']['catalog']],'records','CATALOG')
        ids={v['node']:v for v in catalog['identities']}
        for ordinal in range(1,size+2):
            node='node-'+str(ordinal)
            if node not in ids:ids[node]=dict(ids['node-1'],node=node,port=19000+ordinal,storage='00000000-0000-0000-0000-'+str(ordinal).zfill(12))
        cap=copy.deepcopy(template['capsule']);cap['cut']['view'].update(old=old,new=new)
        catalog.update(cut=cap['cut'],identities=list(ids.values()))
        raw=p.f.encode('records','CATALOG',catalog);cap['catalog']=p.e.sha(raw)
        packet=dict(capsule=cap,objects={cap['catalog']:raw})
        files={node:{'root.gsr':b'original root','node.gsr':p.f.encode('records','NODE',dict(root=cap['root'],identity=ids[node])),
                     'generations/a/generation.gsr':('manifest-'+node).encode(),'generations/a/promise.gsr':('promise-'+node).encode()}
               for node in (*old,joining)}
        def current(value):
            return 'generations/a/',{'promise.gsr':value['generations/a/promise.gsr']},packet
        reader=p.Replay.__new__(p.Replay);reader.root=Path('/original')
        owners={node:dict(node=node,path=node) for node in files}
        return reader,owners,files,packet,current

    def run_governing(self,profile,names):
        reader,owners,files,packet,current=self.governing(profile)
        with patch.object(p.disk,'inventory',side_effect=lambda path:files[path.name]),patch.object(p.disk,'current',side_effect=current), \
             patch.object(physical.t.confirmation,'endpoints',return_value={packet['capsule']['cut']['index']:p.disk.anchor(packet['capsule'])}):
            reader.governing({node:owners[node] for node in names},owners['node-1'])

    def test_all_profiles_require_both_majorities_not_an_unconditional_joining_vote(self):
        for profile in p.PROFILES:
            size,_,old,new=p.topology(profile);voters=old[:size//2+1]
            if profile=='3-ADD':
                with self.assertRaisesRegex(ValueError,'both governing majorities'):self.run_governing(profile,voters)
            else:self.run_governing(profile,voters)
            self.run_governing(profile,[*voters,new[-1]])
            with self.assertRaisesRegex(ValueError,'both governing majorities'):self.run_governing(profile,['node-1'])

    def test_adapter_still_rejects_missing_local_copy_and_foreign_identity(self):
        with self.assertRaisesRegex(ValueError,'exact local floor copy'):self.run_governing('5-REPLACE',['node-2','node-3','node-6'])
        reader,owners,files,packet,current=self.governing('4-ADD')
        node=p.f.decode(files['node-2']['node.gsr'],'records','NODE');node['identity']['port']+=1
        files['node-2']['node.gsr']=p.f.encode('records','NODE',node)
        with patch.object(p.disk,'inventory',side_effect=lambda path:files[path.name]),patch.object(p.disk,'current',side_effect=current), \
             patch.object(physical.t.confirmation,'endpoints',return_value={packet['capsule']['cut']['index']:p.disk.anchor(packet['capsule'])}):
            with self.assertRaisesRegex(ValueError,'governing copy identity/view'):
                reader.governing({n:owners[n] for n in ('node-1','node-2','node-3')},owners['node-1'])

    def direct_reader(self,profile):
        size,_,old,new=p.topology(profile);joining=new[-1];voters=set(old[:size//2+1]);cut=dict(index=9)
        reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining=joining,states=[dict(cut=cut)]*10)
        reader.expected_confirmations=voters;reader.direct_nodes=set();reader.floor_inputs=[]
        reader.events=[dict(node=joining,scope='initial-owner',event='unused') for _ in range(20)]
        reader.events[0]['event']='CURRENT_VALIDATED';reader.events[1]['event']='CURRENT_DIRECTORY_FORCED'
        for at,node in enumerate(sorted(voters|{joining}),2):reader.events[at]=dict(node=node,event='FLOOR_COPY_BEFORE_RETURN')
        reader.events[15]=dict(node=joining,scope='retaining-owner',event='CURRENT_VALIDATED')
        reader.windows=[dict(node=n,start=-1,end=20,packet=dict(capsule=dict(cut=cut))) for n in voters|{joining}]
        own=next(v for v in reader.windows if v['node']=='node-1')
        return reader,own

    def test_direct_copies_follow_all_actual_proof_voters_and_joiner(self):
        for profile in p.PROFILES:
            reader,own=self.direct_reader(profile)
            copies=reader.direct(own,10)
            self.assertEqual(reader.expected_confirmations|{reader.model.joining},set(copies))
            self.assertEqual({'node-1'},reader.direct_nodes);self.assertEqual(1,len(reader.floor_inputs))
            with self.assertRaisesRegex(ValueError,'^joining maintenance direct fixture boundary$'):reader.direct(own,11)

    def test_direct_copy_requires_each_original_callback_and_original_owner_lifetime(self):
        for profile in ('4-ADD','5-REPLACE'):
            reader,own=self.direct_reader(profile)
            for row in reader.events:
                if row.get('node')==reader.model.joining and row['event']=='FLOOR_COPY_BEFORE_RETURN':row['event']='removed'
            with self.assertRaisesRegex(ValueError,'^joining maintenance direct original copy missing$'):reader.direct(own,10)
            reader,own=self.direct_reader(profile)
            with self.assertRaisesRegex(ValueError,'^joining control original owner lifetime$'):reader.direct(own,16)

    def test_wrong_direct_owner_or_cut_cannot_create_a_fixture_floor(self):
        for changed in ('owner','cut'):
            reader,own=self.direct_reader('5-REPLACE');own=copy.deepcopy(own)
            if changed=='owner':own['node']='node-6'
            else:own['packet']['capsule']['cut']['index']=10
            with self.assertRaisesRegex(ValueError,'^joining maintenance direct fixture boundary$'):reader.direct(own,10)

    def test_every_old_proof_voter_must_complete_exactly_one_direct_floor(self):
        reader,_=self.direct_reader('4-REPLACE')
        with patch.object(p.m.Replay,'floors',return_value=dict(directFixtureFloors=3)):
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance complete direct cohort$'):reader.floors()
            reader.direct_nodes=set(reader.expected_confirmations);self.assertEqual(3,reader.floors()['directFixtureFloors'])
        with patch.object(p.m.Replay,'floors',return_value=dict(directFixtureFloors=2)):
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance complete direct cohort$'):reader.floors()

    def test_retirement_callbacks_cannot_survive_a_deleted_or_foreign_floor(self):
        events=[dict(node='node-1',event=v) for v in ('FLOOR_RESERVED','RETIREMENT_RESERVED','SOURCE_RETIREMENT_FORCED','FLOOR_RELEASE_BEFORE_RETURN')]
        self.assertEqual(2,p.retirement_coverage(events))
        for changed in (events[1:-1],[dict(events[0],node='node-2'),*events[1:]]):
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance unbound retirement event$'):p.retirement_coverage(changed)
        with self.assertRaisesRegex(ValueError,'^joining profile maintenance overlapping floor$'):p.retirement_coverage([events[0],*events])
        with self.assertRaisesRegex(ValueError,'^joining profile maintenance incomplete floor$'):p.retirement_coverage(events[:-1])
        with self.assertRaisesRegex(ValueError,'^joining profile maintenance floor release without reservation$'):p.retirement_coverage(events[-1:])

    def test_retirement_coverage_tracks_concurrent_owners_separately(self):
        events=[dict(node=node,event=event) for node,event in [('node-1','FLOOR_RESERVED'),('node-2','FLOOR_RESERVED'),
                ('node-1','RETIREMENT_BEFORE_RETURN'),('node-1','FLOOR_RELEASE_BEFORE_RETURN'),
                ('node-2','SOURCE_RETIREMENT_BEFORE_RETURN'),('node-2','FLOOR_RELEASE_BEFORE_RETURN')]]
        self.assertEqual(2,p.retirement_coverage(events))

    def test_discovery_binds_actual_joiner_endpoint_and_owner_scope(self):
        for joining in ('node-5','node-6'):
            reader=p.Replay.__new__(p.Replay);reader.model=SimpleNamespace(joining=joining)
            ids={node:dict(node=node,storage='storage-'+node,host='127.0.0.1',port=19000+i)
                 for i,node in enumerate(('node-1','node-2',joining))};cut=dict(index=11)
            reader.rows=[dict(kind='STATUS_PROBE',received=2,offered=3,answer='STATUS',
                request=dict(sequence=1,payload=dict(nonce='nonce'),sender=ids['node-1'],recipient=ids[joining],
                             ballot=dict(proposer='node-1',incarnation=ids['node-1']['storage'])),
                response=dict(payload=dict(nonce='nonce',cut=cut,ready=False)))]
            reader.windows=[dict(node=joining,start=-1,end=5,packet=dict(capsule=dict(cut=cut)))]
            reader.events=[dict(node=joining,scope='continuation-owner',event='CURRENT_VALIDATED'),dict(event='unused'),
                           dict(node=joining,scope='continuation-endpoint',event='received'),dict(event='offered'),dict(event='end')]
            with patch.object(p.c,'catalog',return_value=dict(identities=list(ids.values()))):
                reader.statuses();self.assertEqual(1,len(reader.status_rows))
                reader.events[2]['scope']='initial-endpoint'
                with self.assertRaisesRegex(ValueError,'^joining maintenance discovery endpoint$'):reader.statuses()
                reader.events[2]['scope']='continuation-endpoint';reader.events[1]=dict(node=joining,scope='closed-owner',event='CURRENT_VALIDATED')
                with self.assertRaisesRegex(ValueError,'^joining control original owner lifetime$'):reader.statuses()

    def test_acquired_copies_retain_exact_original_order_for_later_ledger_composition(self):
        reader=p.Replay.__new__(p.Replay);reader.floor_inputs=[];own=dict(node='node-2');copies={'node-2':own,'node-1':dict(node='node-1')}
        with patch.object(p.m.Replay,'acquired',return_value=(copies,['original-probe'])):
            self.assertEqual((copies,['original-probe']),reader.acquired(own,0,20))
        self.assertEqual(['node-2','node-1'],reader.floor_inputs[0]['order'])

    def test_original_control_failure_prevents_maintenance_and_mutations(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.control,'validate',side_effect=ValueError('original failed')), \
             patch.object(p,'replay') as replay,patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify('/unused','4-ADD')
            replay.assert_not_called();copied.assert_not_called()

    def test_result_does_not_claim_ledger_or_profile_cohort_and_detects_original_change(self):
        with patch.object(p.collection,'inventory',return_value={}),patch.object(p.control,'validate',return_value={}),patch.object(p,'replay',return_value={}):
            result=p.validate('/unused','5-REPLACE');self.assertTrue(result['maintenanceForceQualified'])
            for key in ('peerLedgerCompositionQualified','allMembershipProfilesQualified','processDeathQualified','phase3Complete'):self.assertFalse(result[key])
        with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.control,'validate'),patch.object(p,'replay'):
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance original changed$'):p.validate('/unused','4-ADD')

    def test_negative_must_preserve_original_physical_members(self):
        with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',side_effect=[dict(files={},directories=[]),dict(files={'added':'sha'},directories=[])]), \
             patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.m,'mutate'),patch.object(p.n,'network') as network:
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance negative changed physical inputs$'):p.qualify('/unused','4-ADD')
            network.assert_not_called()

    def test_prior_network_export_or_control_failure_is_not_a_maintenance_rejection(self):
        for module,name in ((p.n,'network'),(p.control.exports,'replay'),(p.control,'replay')):
            with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.m,'mutate'),patch.object(p.n,'network'), \
                 patch.object(p.control.exports,'replay'),patch.object(p.control,'replay'),patch.object(module,name,side_effect=ValueError('prior failed')),patch.object(p,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'^prior failed$'):p.qualify('/unused','4-ADD')
                replay.assert_not_called()

    def test_missing_target_is_an_explicit_failure(self):
        with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
             patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.m,'mutate',side_effect=StopIteration):
            with self.assertRaisesRegex(ValueError,'^joining profile maintenance missing negative target: status-cut$'):p.qualify('/unused','4-ADD')

    def test_wrong_rejection_reason_or_accepted_mutation_cannot_pass(self):
        for failure,reason in ((None,'mutation accepted: status-cut'),(ValueError('wrong'),'unrelated maintenance negative: status-cut: wrong')):
            with patch.object(p,'validate',return_value={}),patch.object(p.collection,'inventory',return_value=dict(files={},directories=[])), \
                 patch.object(p.shutil,'copytree'),patch.object(p,'Replay'),patch.object(p.m,'mutate'),patch.object(p.n,'network'), \
                 patch.object(p.control.exports,'replay'),patch.object(p.control,'replay'),patch.object(p,'replay',side_effect=failure):
                with self.assertRaisesRegex(ValueError,reason):p.qualify('/unused','5-REPLACE')


if __name__=='__main__':unittest.main()
