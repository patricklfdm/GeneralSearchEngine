from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_process_evidence as m


class NativeCarriedProcessEvidenceTest(unittest.TestCase):
    def result(self, mode='kill', cut='ACCEPT_RENAMED'):
        rows=[dict(life=i,pid=100+i,opened=True,started=dict(life=i,pid=100+i,mode=mode,cut=cut),
                   exit=(137 if mode=='kill' else 73) if i==1 else 0) for i in (1,2)]
        rows[0].update(allLocksHeldBeforeDeath=True,allLocksReleasedAfterDeath=True)
        rows[1]['closed']=dict(life=2,elapsedNanos=10,clientCalls=0)
        return dict(status='PARTIAL',producerPassed=True,phase3Complete=False,mode=mode,cut=cut,
            oldPhase='APPLIED',carriedKind='DATA',children=rows,clientCalls=0,powerLoss=False)

    def test_all_cuts_require_two_distinct_complete_group_lives(self):
        for cut in m.CUTS:
            for mode in ('halt','kill'):
                with self.subTest(cut=cut,mode=mode):
                    r=self.result(mode,cut);self.assertEqual(r['children'],m.children(r))

    def test_partial_group_lock_or_normal_exit_cannot_supply_a_crash(self):
        for key,value in [('exit',0),('allLocksHeldBeforeDeath',False),('allLocksReleasedAfterDeath',False),('opened',False),
                          ('allLocksHeldBeforeDeath',1)]:
            with self.subTest(key=key,value=value):
                r=self.result();r['children'][0][key]=value
                with self.assertRaisesRegex(ValueError,'exact death and close'):m.children(r)
        r=self.result();del r['children'][0]['allLocksReleasedAfterDeath']
        with self.assertRaisesRegex(ValueError,'exact death and close'):m.children(r)

    def test_missing_reused_boolean_or_wrong_lifetime_process_is_rejected(self):
        for pid in (None,101,True,-1,0):
            r=self.result();r['children'][1]['pid']=pid
            with self.subTest(pid=pid),self.assertRaisesRegex(ValueError,'fresh child identities'):m.children(r)
        r=self.result();r['children'][1]['started']['life']=1
        with self.assertRaisesRegex(ValueError,'exact death and close'):m.children(r)

    def test_client_retry_invented_completion_or_power_loss_cannot_expand_scope(self):
        for key,value in [('status','PASS'),('producerPassed',False),('phase3Complete',True),('powerLoss',True),
                          ('oldPhase','CERTIFICATE'),('carriedKind','BARRIER'),('clientCalls',False)]:
            r=self.result();r[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'producer scope'):m.children(r)
        r=self.result();r['children'][1]['closed']['clientCalls']=1
        with self.assertRaisesRegex(ValueError,'exact death and close'):m.children(r)

    def test_successor_elapsed_is_observation_not_a_time_budget(self):
        r=self.result();r['children'][1]['closed']['elapsedNanos']=10**20;m.children(r)
        for elapsed in (None,True,0,-1,1.5):
            r=self.result();r['children'][1]['closed']['elapsedNanos']=elapsed
            with self.subTest(elapsed=elapsed),self.assertRaisesRegex(ValueError,'measured successor lifetime'):m.children(r)

    def vote_events(self, phase, renamed=False):
        result=[phase+'_'+s for s in ('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
                                    'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED')]
        return result if renamed else result+[phase+'_PARENT_FORCED',phase+'_BEFORE_RETURN']

    def test_every_vote_force_is_required_once_and_in_order(self):
        for phase in ('ACCEPT','PROOF','CERTIFICATE'):
            for renamed in (False,True):
                events=self.vote_events(phase,renamed);m.vote_order(events,phase,renamed=renamed)
                for i in range(len(events)):
                    missing=events[:i]+events[i+1:];duplicate=events[:i]+[events[i]]+events[i:]
                    swapped=events.copy();j=(i+1)%len(events);swapped[i],swapped[j]=swapped[j],swapped[i]
                    for variant in (missing,duplicate,swapped):
                        with self.subTest(phase=phase,renamed=renamed,i=i),self.assertRaisesRegex(ValueError,'force prefix'):
                            m.vote_order(variant,phase,renamed=renamed)

    def test_rename_does_not_infer_directory_force_or_ack(self):
        for phase in ('ACCEPT','PROOF'):
            events=self.vote_events(phase,True)
            with self.assertRaisesRegex(ValueError,'force prefix'):m.vote_order(events,phase)
            with self.assertRaisesRegex(ValueError,'force prefix'):m.vote_order(events+[phase+'_PARENT_FORCED'],phase,renamed=True)
            # Forcing the old active vote cannot replace a new candidate force.
            changed=events.copy();changed[4]=phase+'_ACTIVE_FORCED'
            with self.assertRaisesRegex(ValueError,'force prefix'):m.vote_order(changed,phase,renamed=True)

    def test_invalid_original_stops_before_any_copy_or_mutation(self):
        with patch.object(m,'validate',side_effect=ValueError('original failed')),patch.object(m.shutil,'copytree') as copied, \
                patch.object(m,'mutate') as mutated:
            with self.assertRaisesRegex(ValueError,'^original failed$'):m.qualify('unused')
            copied.assert_not_called();mutated.assert_not_called()

    def test_inventory_link_or_extra_file_precedes_any_process_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'outside').write_text('x');(p/'alias').symlink_to('outside')
            with patch.object(m.physical,'physical') as physical:
                with self.assertRaisesRegex(ValueError,'regular inventory'):m.validate(p)
                physical.assert_not_called()
            (p/'alias').unlink()
            with self.assertRaisesRegex(ValueError,'process inventory'):m.validate(p)

    def test_original_disk_and_each_disjoint_scratch_are_required(self):
        paths=['/seed']+[p for i in (1,2,3) for p in (f'/nodes/{i}',f'/apps/{i}')]
        plan=dict(plan=dict(descriptor=dict(paths=[dict(path=p) for p in paths])))
        spec=dict(nodes=[dict(replica=f'/nodes/{i}',application=f'/apps/{i}',scratch=f'/scratch/{i}') for i in (1,2,3)])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'process').mkdir();(p/'original-plan.gsbp').write_bytes(b'x');(p/'original-application.image').write_bytes(b'y')
            def check(value):
                (p/'process/spec.json').write_bytes(m.f.canonical(value))
                with patch.object(m.b.t.plans,'decode',return_value=plan):m.configuration(p)
            check(spec)
            for value in ('/nodes/1','/scratch/1/child','relative','/scratch/../copy'):
                changed=deepcopy(spec);changed['nodes'][1]['scratch']=value
                with self.subTest(value=value),self.assertRaisesRegex(ValueError,'disjoint scratch'):check(changed)
            changed=deepcopy(spec);changed['nodes'][0]['replica']+='_copy'
            with self.assertRaisesRegex(ValueError,'original disk paths'):check(changed)

    def test_force_mutations_update_both_views_instead_of_only_breaking_correlation(self):
        names=['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','NODE_OPEN','ROUND_SLOT_BEGIN',
               'ACCEPT_PARENT_FORCED','SUPERSEDED_END_AUTHORITY_FORCED','APPLY_ACK_DIRECTORY_FORCED','ROUND_SLOT_COMPLETE']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'process').mkdir()
            for name in ('missing-cold-force','invented-cold-ack','missing-accept-force','missing-application-force','missing-retirement-force'):
                for life in (1,2):
                    events=[dict(action='event',value=dict(node='node-1',incarnation=life,event=v)) for v in names]
                    m.write_messages(root/f'process/life-{life}.jsonl',events)
                m.mutate(root,name)
                expected=[]
                for life in (1,2):
                    expected += [v['value'] for v in m.process.transcript(root/f'process/life-{life}.jsonl')]
                    if life==1:expected.append(dict(event='GROUP_CRASH',incarnation=1))
                self.assertEqual(expected,m.read(root/'events.json'))

    def test_corrupt_physical_original_precedes_producer_pass(self):
        with patch.object(m,'inventory'),patch.object(m,'read',return_value=self.result()), \
                patch.object(m.physical,'physical',side_effect=ValueError('changed original')),patch.object(m,'children') as children:
            with self.assertRaisesRegex(ValueError,'^changed original$'):m.validate('unused')
            children.assert_not_called()

    def test_negative_scope_is_cut_specific_and_never_complete(self):
        for point in m.CUTS:
            cases=m.negative_cases(point)
            self.assertEqual(32+int(point.endswith('RENAMED')),len(cases))
        with self.assertRaisesRegex(ValueError,'declared negative cut'):m.negative_cases('OTHER')
        with self.assertRaisesRegex(ValueError,'declared cut'):m.physical.physical('unused','OTHER')

    def test_component_success_never_admits_full_process_or_phase(self):
        with patch.object(m,'inventory'),patch.object(m,'read',return_value=self.result()), \
                patch.object(m.physical,'physical',return_value={'status':'PARTIAL'}), \
                patch.object(m,'configuration'),patch.object(m,'original_forces'), \
                patch.object(m,'observations',return_value=([[],[]],[10,20])), \
                patch.object(m,'rounds',return_value=[[],[]]),patch.object(m,'force_order'):
            result=m.validate('unused')
        self.assertEqual('PARTIAL',result['status']);self.assertEqual('PASS',result['componentChecks'])
        for field in ('fullWireReplay','processHistoryQualified','cohortAdmitted','powerLoss','phase3Complete'):
            self.assertIs(False,result[field])

    def test_snapshot_view_only_maps_the_selected_lifetime(self):
        view=m.physical.View(Path('/original'),2)
        for name,target in [('selected-1.gsr','life-2-installed-1.gsr'),('applied-1','life-2-applied-1'),
                            ('published-2','life-2-published-2'),('entry-1.gsr','entry-1.gsr')]:
            self.assertEqual(Path('/original')/target,view/name)


if __name__=='__main__':unittest.main()
