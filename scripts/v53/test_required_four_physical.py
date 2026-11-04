"""Policy and original-first regressions; conditional fixtures are not native runs."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import required_four_physical as e
from .test_joining_initialization_evidence import preparing
from . import test_joining_same_view_physical as fixtures


class RequiredFourPhysicalTest(unittest.TestCase):
    def test_pin_choice_requires_original_pressure_and_selected_generation(self):
        catalog=e.f.catalog();manifest=e.f.sample(catalog['records']['GENERATION']['schema'],catalog['types'])
        manifest['selection']='a'*64
        files={'generations/a':None,'generations/b':None,
               'generations/a/generation.gsr':e.f.encode('records','GENERATION',manifest),
               'sources/one/source.gscp':b'first','sources/two/source.gscp':b'second'}
        voters=e.semantic.JOINT_LIVE
        with patch.object(e.disk,'current',return_value=('generations/a/',{},{})):
            self.assertTrue(e.pin_required(files,voters))
            for missing in ('generations/b','sources/two/source.gscp'):
                changed=dict(files);del changed[missing]
                self.assertFalse(e.pin_required(changed,voters))
            self.assertFalse(e.pin_required(files,voters[:3]))
            manifest['selection']=None;files['generations/a/generation.gsr']=e.f.encode('records','GENERATION',manifest)
            files['floor-copies/local.gsr']=b'claim cannot supply selection'
            self.assertFalse(e.pin_required(files,voters))

    def test_pinning_keeps_all_original_references_and_only_omits_local_duplicate(self):
        group,_,current,endpoints=fixtures.JoiningSameViewPhysicalTest().copies(True)
        group['node-2']['selector.gsr']=b'exact local selector';before=copy.deepcopy(group)
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.covering.t.confirmation,'endpoints',side_effect=endpoints):
            copied=e.governing(group['node-2'],group,'node-2')
            pinned=e.governing(group['node-2'],group,'node-2',pinned=True)
        floor=e.f.decode(pinned['floor-copies/floor.gsr'],'records','FLOOR')
        self.assertEqual(4,len(floor['sources']));self.assertEqual(copied['floor-copies/floor.gsr'],pinned['floor-copies/floor.gsr'])
        own='floor-copies/'+e.c.sha(group['node-2']['generations/a/generation.gsr'])
        self.assertFalse(any(n==own or n.startswith(own+'/') for n in pinned))
        self.assertEqual(b'exact local selector',pinned['floor-copies/local.gsr'])
        self.assertEqual({n:v for n,v in copied.items() if n!=own and not n.startswith(own+'/')},
                         {n:v for n,v in pinned.items() if n!='floor-copies/local.gsr'})
        self.assertEqual(before,group)

    def test_pinning_cannot_relax_majority_or_replace_original_local_copy(self):
        group,_,current,endpoints=fixtures.JoiningSameViewPhysicalTest().copies(True)
        group['node-2']['selector.gsr']=b'original'
        with patch.object(e.disk,'current',side_effect=current),patch.object(e.covering.t.confirmation,'endpoints',side_effect=endpoints):
            with self.assertRaisesRegex(ValueError,'both governing majorities'):
                e.governing(group['node-2'],{n:group[n] for n in ('node-1','node-2')},'node-2',pinned=True)
            changed=copy.deepcopy(group);changed['node-2']['generations/a/generation.gsr']=b'substitute'
            with self.assertRaisesRegex(ValueError,'exact local floor copy'):
                e.governing(group['node-2'],changed,'node-2',pinned=True)

    def deferred_fixture(self):
        v,files,_,journal,current=preparing();files['grants.gsr']=journal
        files.update({'sources/one/source.gscp':b'first','sources/two/source.gscp':b'second'})
        current[1].update({'promise.gsr':b'older current promise','basis.gsr':b'older current basis'})
        return files,current,dict(v.ballot,counter=v.ballot['counter']+1)

    def test_deferred_capture_requires_new_ballot_clean_unselected_current_cut(self):
        files,current,ballot=self.deferred_fixture()
        with patch.object(e.disk,'current',return_value=current):self.assertTrue(e.deferred(files,ballot))
        for mode in ('same-ballot','one-source','selected','pending','backing-promise','backing-basis','accepted','other-cut'):
            files,current,ballot=self.deferred_fixture()
            rows=e.disk.journal(files['grants.gsr'],current[2]['capsule']['root'],'node-1')
            if mode=='same-ballot':ballot=rows[-2][2]['ballot']
            elif mode=='one-source':del files['sources/two/source.gscp']
            elif mode=='pending':files['pending.accept']=b'pending'
            elif mode=='backing-promise':current[1]['promise.gsr']=rows[-2][1]
            elif mode=='backing-basis':current[1]['basis.gsr']=rows[-1][1]
            elif mode in ('accepted','other-cut'):
                basis=copy.deepcopy(rows[-1][2])
                if mode=='accepted':basis['accepted']='a'*64
                else:basis['cut']['index']+=1
                files['grants.gsr']=files['grants.gsr'][:-len(rows[-1][1])]+e.f.encode('records','BASIS',basis)
            else:
                # Journal decoding has its own validation. Exercise the policy's
                # refusal of a selected suffix without synthesizing its authority.
                rows.append(('SELECTED',b'selected',{}))
            with self.subTest(mode=mode),patch.object(e.disk,'current',return_value=current):
                if mode=='selected':
                    with patch.object(e.disk,'journal',return_value=rows):self.assertFalse(e.deferred(files,ballot))
                else:self.assertFalse(e.deferred(files,ballot))

    def test_departing_owner_cannot_acquire_successor_maintenance(self):
        continuation=object.__new__(e.Continuation);continuation.voters=tuple(e.semantic.JOINT_LIVE)
        group={'node-3':{'selector.gsr':b'original'}}
        packet={'capsule':{'cut':{'view':{'old':e.semantic.NEW,'new':e.semantic.NEW}}}}
        with patch.object(e.disk,'current',return_value=('',{},packet)),patch.object(e.c,'maintenance') as maintain:
            self.assertIs(group['node-3'],continuation.maintenance(group,'node-3'));maintain.assert_not_called()

    def test_bad_original_never_starts_mutation(self):
        with patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(e.shutil,'copytree') as copying:
            with self.assertRaisesRegex(ValueError,'^bad original$'):e.qualify('/unused')
            copying.assert_not_called()

    def test_prerequisite_failures_cannot_qualify_physical_negative(self):
        for prerequisite in (e.semantic,e.retirement.observed):
            with (patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',return_value={}),
                  patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.semantic,'validate'),
                  patch.object(e.retirement.observed,'validate'),patch.object(prerequisite,'validate',side_effect=ValueError('prerequisite'))):
                with self.assertRaisesRegex(ValueError,'^prerequisite$'):e.qualify('/unused')

    def test_accepted_mutation_and_unrelated_failure_do_not_count(self):
        for error,reason in (({},'physical mutation accepted'),(ValueError('other'),'unrelated physical negative')):
            with (patch.object(e.s.collection,'inventory',return_value={}),patch.object(e,'validate',side_effect=[{},error]),
                  patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.semantic,'validate'),
                  patch.object(e.retirement.observed,'validate')):
                with self.assertRaisesRegex(ValueError,reason):e.qualify('/unused')

    def test_original_must_remain_unchanged_through_all_negatives(self):
        with (patch.object(e.s.collection,'inventory',side_effect=[{},dict(changed=True)]),
              patch.object(e,'validate',side_effect=[{}]+[ValueError(v) for v in e.NEGATIVES.values()]),
              patch.object(e.shutil,'copytree'),patch.object(e,'mutate'),patch.object(e.semantic,'validate'),
              patch.object(e.retirement.observed,'validate')):
            with self.assertRaisesRegex(ValueError,'physical original changed'):e.qualify('/unused')

    def test_unknown_mutation_leaves_files_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original';path.write_bytes(b'original')
            with self.assertRaisesRegex(ValueError,'declared physical mutation'):e.mutate(temp,'unknown')
            self.assertEqual(b'original',path.read_bytes())


if __name__=='__main__':unittest.main()
