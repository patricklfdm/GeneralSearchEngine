from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_inflight_evidence as p


class NodeRenameEvidenceTest(unittest.TestCase):
    def events(self, phase):
        return [dict(node='node-1',incarnation=1,event=phase+'_'+suffix) for suffix in
            ('VALIDATED','CANDIDATE_CREATED','PREFIX_WRITTEN','CANDIDATE_WRITTEN',
             'CANDIDATE_FORCED','CANDIDATE_PARENT_FORCED','RENAMED')]

    def test_exact_cut_set_binds_recovered_pending_phase(self):
        for point,phase in [('ACCEPT_RENAMED','ACCEPT'),('PROOF_RENAMED','PROOF'),
                            ('ACCEPT_PARENT_FORCED','ACCEPT'),('PROOF_PARENT_FORCED','PROOF')]:
            self.assertEqual(phase,p.pending_phase(point))
        for point in ('ACCEPT_PREFIX_WRITTEN','PROOF_BEFORE_RETURN','AFTER_DATA_RETURN',None,True):
            with self.subTest(point=point),self.assertRaisesRegex(ValueError,'original crash point'):
                p.pending_phase(point)

    def test_both_complete_original_rename_prefixes_are_accepted(self):
        for phase in ('ACCEPT','PROOF'):
            p.rename_prefix(self.events(phase),phase+'_RENAMED')

    def test_every_write_and_force_event_is_required_in_order(self):
        for phase in ('ACCEPT','PROOF'):
            events=self.events(phase)
            for at in range(len(events)):
                missing=deepcopy(events);missing.pop(at)
                duplicate=deepcopy(events);duplicate.insert(at,deepcopy(events[at]))
                exchanged=deepcopy(events);other=(at+1)%len(events)
                exchanged[at],exchanged[other]=exchanged[other],exchanged[at]
                for variant in (missing,duplicate,exchanged):
                    with self.subTest(phase=phase,at=at),self.assertRaisesRegex(ValueError,'pre-directory-force prefix'):
                        p.rename_prefix(variant,phase+'_RENAMED')

    def test_directory_force_and_return_cannot_be_inferred_from_rename(self):
        for phase in ('ACCEPT','PROOF'):
            for suffix in ('PARENT_FORCED','BEFORE_RETURN'):
                events=self.events(phase)+[dict(node='node-1',event=phase+'_'+suffix)]
                with self.subTest(phase=phase,suffix=suffix),self.assertRaisesRegex(ValueError,'pre-directory-force prefix'):
                    p.rename_prefix(events,phase+'_RENAMED')

    def test_other_voter_cannot_supply_missing_local_force(self):
        for phase in ('ACCEPT','PROOF'):
            events=self.events(phase);events[-3]['node']='node-2'
            with self.assertRaisesRegex(ValueError,'pre-directory-force prefix'):
                p.rename_prefix(events,phase+'_RENAMED')

    def test_proof_prefix_can_follow_completed_accept_without_using_its_force(self):
        accepted=self.events('ACCEPT')+[dict(node='node-1',event='ACCEPT_PARENT_FORCED')]
        p.rename_prefix(accepted+self.events('PROOF'),'PROOF_RENAMED')
        with self.assertRaisesRegex(ValueError,'pre-directory-force prefix'):
            p.rename_prefix(accepted+self.events('PROOF')[:-1],'PROOF_RENAMED')

    def test_existing_cut_negative_contract_stays_exact(self):
        for point in p.CUTS:self.assertEqual(p.NEGATIVES,p.negative_cases(point))
        for point in p.RENAME_CUTS:
            cases=p.negative_cases(point)
            self.assertEqual(22,len(cases));self.assertEqual(set(p.NEGATIVES)|set(p.RENAME_NEGATIVES),set(cases))
            self.assertEqual('inflight exact pre-directory-force prefix',cases['wrong-cut-event'])
        with self.assertRaisesRegex(ValueError,'original crash point'):p.negative_cases('UNKNOWN')

    def test_rename_mutations_change_both_original_observation_streams(self):
        for phase in ('ACCEPT','PROOF'):
            for name in (*p.RENAME_NEGATIVES,'wrong-cut-event'):
                with self.subTest(phase=phase,name=name),tempfile.TemporaryDirectory() as temp:
                    root=Path(temp);raw=root/'history';raw.mkdir();process=root/'process';process.mkdir()
                    events=[dict(node='node-1',event='ROUND_SLOT_BEGIN'),*self.events(phase),dict(node='node-1',event='NODE_CRASH')]
                    (raw/'events.json').write_bytes(p.f.canonical(events))
                    (process/'result.json').write_bytes(p.f.canonical(dict(cut=phase+'_RENAMED')))
                    messages=[dict(action='event',value=v) for v in events[:-1]]+[dict(action='cut',value={})]
                    (process/'life-1.jsonl').write_bytes(b'\n'.join(p.f.canonical(v) for v in messages)+b'\n')
                    p.mutate(root,name)
                    changed=p.n.read(raw/'events.json')
                    child=p.process.transcript(process/'life-1.jsonl')
                    self.assertEqual(changed[:-1],[v['value'] for v in child[:-1]])
                    with self.assertRaisesRegex(ValueError,'pre-directory-force prefix'):
                        p.rename_prefix(changed,phase+'_RENAMED')

    def test_mutation_is_not_applied_to_parent_forced_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'process').mkdir()
            (root/'process/result.json').write_bytes(p.f.canonical(dict(cut='PROOF_PARENT_FORCED')))
            with self.assertRaisesRegex(ValueError,'rename mutation scope'):p.mutate(root,'invented-parent-force')

    def test_invalid_original_stops_before_any_negative_or_copy(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')),patch.object(p,'negative_cases') as cases, \
                patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('unused')
            cases.assert_not_called();copy.assert_not_called()


if __name__=='__main__':unittest.main()
