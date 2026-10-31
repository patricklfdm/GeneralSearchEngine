"""Governing-copy derivation boundaries; synthetic cases are not native history."""
import copy
import unittest
from unittest.mock import patch

from . import joining_retirement_replay as r
from . import test_joining_catalog_evidence as catalog_fixture
from .test_joining_initialization_evidence import preparing


class JoiningRetirementReplayTest(unittest.TestCase):
    def owners(self,joint=False):
        _,parent,identities,root=catalog_fixture.JoiningCatalogEvidenceTest().phase(joint)
        catalog=r.f.catalog();value=r.f.sample(catalog['records']['CATALOG']['schema'],catalog['types'])
        value.update(root=root,cut=parent['cut'],identities=list(identities.values()))
        encoded=r.f.encode('records','CATALOG',value)
        cap=dict(root=root,cut=parent['cut'],catalog=r.sha(encoded),application='e'*64)
        models={n:dict(capsule=copy.deepcopy(cap),objects={r.sha(encoded):encoded}) for n in identities}
        group={n:{'node.gsr':r.f.encode('records','NODE',dict(root=root,identity=v)),
                  'generations/a/generation.gsr':('generation-'+n).encode(),'generations/a/promise.gsr':('promise-'+n).encode()}
               for n,v in identities.items()}
        def current(files):
            n=r.f.decode(files['node.gsr'],'records','NODE')['identity']['node']
            return 'generations/a/',{k.removeprefix('generations/a/'):v for k,v in files.items()
                if k.startswith('generations/a/') and k!='generations/a/generation.gsr'},models[n]
        return group,models,current

    def test_floor_is_built_from_all_derived_members_in_owner_order(self):
        group,_,current=self.owners();before=copy.deepcopy(group)
        with patch.object(r.disk,'current',side_effect=current):
            files=r.governing(group['node-2'],{'node-2':group['node-2'],'node-1':group['node-1']},'node-2')
        floor=r.f.decode(files['floor-copies/floor.gsr'],'records','FLOOR')
        self.assertEqual(['node-1','node-2'],[v['voter'] for v in floor['sources']])
        self.assertEqual('node-2',floor['node']);self.assertEqual(files['floor-copies/floor.gsr'],files['floor-copies/proposal.gsr'])
        for peer in ('node-1','node-2'):
            generation=group[peer]['generations/a/generation.gsr'];prefix='floor-copies/'+r.sha(generation)
            self.assertEqual(generation,files[prefix+'/generation.gsr'])
            self.assertEqual(group[peer]['generations/a/promise.gsr'],files[prefix+'/promise.gsr'])
        self.assertEqual(before,group)

    def test_joint_floor_requires_old_and_new_majorities(self):
        group,_,current=self.owners(True)
        with patch.object(r.disk,'current',side_effect=current):
            with self.assertRaisesRegex(ValueError,'both governing majorities'):
                r.governing(group['node-1'],{n:group[n] for n in ('node-1','node-2')},'node-1')
            r.governing(group['node-1'],{n:group[n] for n in ('node-1','node-2','node-4')},'node-1')

    def test_foreign_identity_and_different_cut_cannot_supply_governing_copy(self):
        for mutation in ('identity','cut'):
            group,models,current=self.owners()
            if mutation=='identity':
                value=r.f.decode(group['node-2']['node.gsr'],'records','NODE');value['identity']['port']+=1
                group['node-2']['node.gsr']=r.f.encode('records','NODE',value)
            else:models['node-2']['capsule']['cut']['index']+=1
            with self.subTest(mutation=mutation),patch.object(r.disk,'current',side_effect=current),self.assertRaisesRegex(ValueError,'governing original cut/identity'):
                r.governing(group['node-1'],{n:group[n] for n in ('node-1','node-2')},'node-1')

    def test_missing_local_copy_or_unreleased_floor_refuses(self):
        group,_,current=self.owners()
        with patch.object(r.disk,'current',side_effect=current):
            with self.assertRaisesRegex(ValueError,'exact local governing copy'):r.governing(group['node-1'],{'node-2':group['node-2']},'node-1')
            group['node-1']['floor-copies']=None
            with self.assertRaisesRegex(ValueError,'previous floor not released'):
                r.governing(group['node-1'],{n:group[n] for n in ('node-1','node-2')},'node-1')

    def test_same_members_with_other_local_generation_manifest_refuse(self):
        group,_,current=self.owners();own=copy.deepcopy(group['node-1'])
        group['node-1']['generations/a/generation.gsr']=b'different manifest'
        with patch.object(r.disk,'current',side_effect=current),self.assertRaisesRegex(ValueError,'exact local governing copy'):
            r.governing(own,{n:group[n] for n in ('node-1','node-2')},'node-1')

    def decision_inputs(self):
        v,files,(old_basis,packet),journal,_=preparing();value=r.f.decode(old_basis,'records','BASIS');identifier=value['basisId']
        value.update(basisId='00000000-0000-0000-0000-000000000099',ballot=dict(value['ballot'],counter=3))
        basis=r.f.encode('records','BASIS',value);promise=r.f.encode('records','PROMISE',{k:value[k] for k in ('root','view','basisId','ballot')})
        files.update({'grants.gsr':journal+promise+basis,'selector.gsr':b'original selector','floor-copies/floor.gsr':b'derived floor',
            'sources/'+identifier:None,'sources/'+identifier+'/source.gscp':packet,
            'sources/'+identifier+'/'+v.cap['application']+'.image':b'independent image',
            'sources/'+value['basisId']:None,'sources/'+value['basisId']+'/source.gscp':packet})
        current=('generations/a/',{'promise.gsr':promise,'basis.gsr':basis},v.current)
        coverage={v.cap['cut']['index']:r.disk.anchor(v.cap)}
        return files,identifier,current,coverage,old_basis,promise+basis

    def test_decision_binds_exact_old_source_and_preserves_latest_grant(self):
        files,identifier,current,coverage,old_basis,kept=self.decision_inputs();before=copy.deepcopy(files)
        with patch.object(r.disk,'current',return_value=current),patch.object(r.t,'require_coverage',return_value=coverage):
            authority,compact=r.decision(files,'node-1',identifier)
        size=48+int.from_bytes(authority[12:16],'big');record=r.f.decode(authority[:size],'records','RETIREMENT')
        self.assertEqual(r.sha(files['floor-copies/floor.gsr']),record['floor'])
        self.assertEqual(r.sha(files['selector.gsr']),record['selector']);self.assertEqual(kept,compact)
        self.assertIn(old_basis,authority);self.assertEqual(before,files)
        self.assertEqual(sorted(v['path'] for v in record['files']),[v['path'] for v in record['files']])

    def test_pinned_source_missing_coverage_or_changed_image_refuses(self):
        for mutation,reason in [('pinned','pinned original source'),('coverage','governing source coverage'),('image','original source image')]:
            files,identifier,current,coverage,_,_=self.decision_inputs()
            if mutation=='pinned':identifier='00000000-0000-0000-0000-000000000099'
            elif mutation=='coverage':coverage={}
            else:files[next(n for n in files if n.endswith('.image'))]=b'changed'
            with self.subTest(mutation=mutation),patch.object(r.disk,'current',return_value=current),patch.object(r.t,'require_coverage',return_value=coverage),self.assertRaisesRegex(ValueError,reason):
                r.decision(files,'node-1',identifier)

    def test_collection_cannot_supply_extra_underived_transaction(self):
        rows=[dict(node='node-1',steps=[])]
        with patch.object(r.observed,'collect',return_value=rows):e=r.Retirements('/unused',[])
        with self.assertRaisesRegex(ValueError,'underived transaction'):e.complete()
        e.positions['node-1']=1;e.complete()

    def test_invalid_original_never_starts_negative_qualification(self):
        with patch.object(r,'validate',side_effect=ValueError('invalid original')),patch.object(r,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):r.qualify('/unused')
            mutate.assert_not_called()

    def test_collection_failure_cannot_count_as_derivation_rejection(self):
        with patch.object(r,'validate',return_value={}) as replay,patch.object(r.shutil,'copytree'),patch.object(r,'mutate'), \
                patch.object(r.observed,'validate',side_effect=ValueError('collection failed')):
            with self.assertRaisesRegex(ValueError,'^collection failed$'):r.qualify('/unused')
            self.assertEqual(1,replay.call_count)

    def test_accepted_mutation_and_unrelated_failure_are_not_success(self):
        for effects,reason in [([{},{}],'mutation accepted'),([{},ValueError('wrong failure')],'unrelated joining retirement negative')]:
            with patch.object(r,'validate',side_effect=effects),patch.object(r.shutil,'copytree'),patch.object(r,'mutate'), \
                    patch.object(r.observed,'validate'),self.assertRaisesRegex(ValueError,reason):r.qualify('/unused')

    def test_floor_force_must_belong_to_latest_unreleased_transaction(self):
        points=['FLOOR_RESERVED','FLOOR_AUTHORITY_WRITTEN','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN']
        rows=[dict(node='node-1',event=v) for v in points]
        self.assertEqual(0,r.floor_order(rows,'node-1',len(rows)))
        for changed,reason in [(rows+[dict(node='node-1',event='FLOOR_RELEASE_CLEARED')],'released governing floor'),
                (rows+[dict(node='node-1',event='FLOOR_RESERVED')],'governing floor force order'),
                ([row for row in rows if row['event']!='FLOOR_AUTHORITY_FORCED'],'governing floor force order'),
                ([dict(row,node='node-2') for row in rows],'governing floor force absent')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):r.floor_order(changed,'node-1',len(changed))


if __name__=='__main__':unittest.main()
