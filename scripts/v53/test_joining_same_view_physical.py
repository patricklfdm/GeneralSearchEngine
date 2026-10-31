"""Conditional covering-copy regressions; native originals are a separate gate."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import joining_same_view_physical as e
from . import test_joining_retirement_replay as fixtures


class JoiningSameViewPhysicalTest(unittest.TestCase):
    def copies(self,joint=False):
        group,models,current=fixtures.JoiningRetirementReplayTest().owners(joint)
        for files in group.values():files['root.gsr']=b'original-root'
        old=e.disk.anchor(models['node-2']['capsule'])
        models['node-1']['capsule']['cut']['index']+=1
        models['node-1']['capsule']['catalog']='a'*64
        models['node-1']['capsule']['application']='b'*64
        def endpoints(packet,ancestry):return {old['cut']['index']:old,packet['capsule']['cut']['index']:e.disk.anchor(packet['capsule'])}
        return group,models,current,endpoints

    def test_covering_floor_keeps_local_cut_and_remote_original_catalog(self):
        group,models,current,endpoints=self.copies();before=copy.deepcopy(group)
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.t.confirmation,'endpoints',side_effect=endpoints):
            result=e.covering_floor(group['node-2'],{n:group[n] for n in ('node-1','node-2')},'node-2')
        floor=e.f.decode(result['floor-copies/floor.gsr'],'records','FLOOR')
        self.assertEqual(models['node-2']['capsule']['cut'],floor['cut'])
        self.assertEqual(['node-1','node-2'],[v['voter'] for v in floor['sources']])
        self.assertEqual(('a'*64,'b'*64),(floor['sources'][0]['catalog'],floor['sources'][0]['snapshot']))
        for ref in floor['sources']:
            prefix='floor-copies/'+ref['generation']+'/'
            self.assertEqual(group[ref['voter']]['generations/a/generation.gsr'],result[prefix+'generation.gsr'])
        self.assertEqual(before,group)

    def test_larger_index_without_exact_ancestor_cannot_protect_floor(self):
        for changed in ('missing','cut','catalog','application'):
            group,models,current,endpoints=self.copies()
            def available(packet,ancestry):
                result=copy.deepcopy(endpoints(packet,ancestry))
                if packet is models['node-1']:
                    index=models['node-2']['capsule']['cut']['index']
                    if changed=='missing':result.pop(index)
                    elif changed=='cut':result[index]['cut']['entry']='f'*64
                    else:result[index][changed]='f'*64
                return result
            with self.subTest(changed=changed),patch.object(e.disk,'current',side_effect=current), \
                 patch.object(e.t.confirmation,'endpoints',side_effect=available):
                with self.assertRaisesRegex(ValueError,'^joining same-view exact covering ancestor$'):
                    e.covering_floor(group['node-2'],{n:group[n] for n in ('node-1','node-2')},'node-2')

    def test_foreign_owner_root_view_or_older_copy_refuses(self):
        for changed in ('identity','root','view','older'):
            group,models,current,endpoints=self.copies()
            if changed=='identity':
                value=e.f.decode(group['node-1']['node.gsr'],'records','NODE');value['identity']['port']+=1
                group['node-1']['node.gsr']=e.f.encode('records','NODE',value)
            elif changed=='root':group['node-1']['root.gsr']=b'other root'
            elif changed=='view':models['node-1']['capsule']['cut']['view']['generation']+=1
            else:models['node-1']['capsule']['cut']['index']=models['node-2']['capsule']['cut']['index']-1
            with self.subTest(changed=changed),patch.object(e.disk,'current',side_effect=current), \
                 patch.object(e.t.confirmation,'endpoints',side_effect=endpoints):
                with self.assertRaisesRegex(ValueError,'^joining same-view governing copy identity/view$'):
                    e.covering_floor(group['node-2'],{n:group[n] for n in ('node-1','node-2')},'node-2')

    def test_local_original_generation_and_majorities_remain_required(self):
        group,models,current,endpoints=self.copies(True)
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.t.confirmation,'endpoints',side_effect=endpoints):
            with self.assertRaisesRegex(ValueError,'^joining same-view exact local floor copy$'):
                e.covering_floor(group['node-2'],{'node-1':group['node-1']},'node-2')
            with self.assertRaisesRegex(ValueError,'both governing majorities'):
                e.covering_floor(group['node-2'],{n:group[n] for n in ('node-1','node-2')},'node-2')
            replaced=copy.deepcopy(group);replaced['node-2']['generations/a/generation.gsr']=b'substitute'
            with self.assertRaisesRegex(ValueError,'^joining same-view exact local floor copy$'):
                e.covering_floor(group['node-2'],replaced,'node-2')
            group['node-2']['floor-copies']=None
            with self.assertRaisesRegex(ValueError,'^joining same-view preceding floor not released$'):
                e.covering_floor(group['node-2'],group,'node-2')

    def test_same_cut_encoding_matches_existing_floor_reader(self):
        group,models,current,endpoints=self.copies();models['node-1']['capsule']=copy.deepcopy(models['node-2']['capsule'])
        copies={n:group[n] for n in ('node-1','node-2')}
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.t.confirmation,'endpoints',side_effect=endpoints):
            self.assertEqual(e.retirement.governing(group['node-2'],copies,'node-2'),e.covering_floor(group['node-2'],copies,'node-2'))

    def test_quorum_copy_choice_stops_at_majority_and_skips_lagging_peers(self):
        group,models,current,endpoints=self.copies()
        with patch.object(e.disk,'current',side_effect=current),patch.object(e,'covering_floor'):
            self.assertEqual(('node-2','node-1'),e.floor_voters(group,'node-2'))
            self.assertEqual(('node-1',),e.floor_voters(group,'node-1'))
        # The final covering proof must still reject a missing second copy.
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.t.confirmation,'endpoints',side_effect=endpoints):
            with self.assertRaisesRegex(ValueError,'both governing majorities'):e.floor_voters(group,'node-1')

    def test_bad_original_prevents_any_negative_execution(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',side_effect=ValueError('bad original')), \
             patch.object(e.shutil,'copytree') as copying:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify(temp)
            copying.assert_not_called()

    def test_semantic_or_capture_failure_cannot_be_counted_as_physical_rejection(self):
        for target in (e.semantic,e.retirement.observed):
            with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',return_value={}), \
                 patch.object(e.shutil,'copytree'),patch.object(e,'mutate'), \
                 patch.object(e.semantic,'validate'),patch.object(e.retirement.observed,'validate'), \
                 patch.object(target,'validate',side_effect=ValueError('prior gate')):
                with self.assertRaisesRegex(ValueError,'^prior gate$'):e.qualify(temp)

    def test_unrelated_rejection_and_accepted_mutation_cannot_qualify(self):
        for error,reason in ((ValueError('unrelated'),'unrelated physical negative'),({},'physical mutation accepted')):
            with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',side_effect=[{},error]), \
                 patch.object(e.shutil,'copytree'),patch.object(e,'mutate'), \
                 patch.object(e.semantic,'validate'),patch.object(e.retirement.observed,'validate'):
                with self.assertRaisesRegex(ValueError,reason):e.qualify(temp)

    def test_unknown_mutation_never_touches_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original';path.write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'^joining same-view unknown physical mutation$'):e.mutate(temp,'unknown')
            self.assertEqual(b'original',path.read_bytes())


if __name__=='__main__':unittest.main()
