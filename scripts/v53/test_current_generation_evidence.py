from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import current_generation_evidence as e
from . import current_generation_negatives as n
from . import current_generation_qualification as q
from .test_source_packet import frame


def fixture(path):
    """Independent parser bytes only; not a process, semantic capsule, or force receipt."""
    path.mkdir();catalog=e.f.catalog();sample=lambda k:e.f.sample(catalog['records'][k]['schema'],catalog['types'])
    image=b'original generation image';app=e.sha(image);genesis=sample('GENESIS');genesis.update(application=app,source='EMPTY',sourceDigest=None)
    raw=e.f.encode('records','GENESIS',genesis);root=sample('ROOT');root.update({k:genesis[k] for k in ('groupId','historyId','baseSequence','schema','indexes')})
    root.update(genesis=e.sha(raw),limits=e.sha(e.f.canonical(catalog['resources'])))
    for i,member in enumerate(root['initial'],1):member['node']=f'node-{i}'
    root_raw=e.f.encode('records','ROOT',root);digest=root_raw[16:48].hex()
    view=dict(generation=0,old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'],operation=None)
    cut=dict(index=0,entry=e.sha(raw),view=view);cat=sample('CATALOG');cat.update(root=digest,cut=cut,application=app)
    cat_raw=e.f.encode('records','CATALOG',cat);objects={e.sha(root_raw):root_raw,e.sha(raw):raw,e.sha(cat_raw):cat_raw}
    index=dict(schema='gse-membership-source-index/1.3',objects=[dict(sha256=h,bytes=len(b)) for h,b in sorted(objects.items())],images=[dict(sha256=app,bytes=len(image))])
    capsule=sample('CAPSULE');capsule.update(root=digest,cut=cut,application=app,catalog=e.sha(cat_raw),initial=e.sha(raw),inventory=e.sha(e.f.canonical(index)),items=[])
    cap_raw=e.f.encode('records','CAPSULE',capsule);packet=frame(cap_raw,e.f.canonical(index),objects)
    promise=sample('PROMISE');promise.update(root=digest,view=e.sha(e.f.canonical(dict(root=digest,**view))),basisId='00000000-0000-0000-0000-000000000010')
    promise['ballot']['counter']=10;promise_raw=e.f.encode('records','PROMISE',promise)
    for name,data in {'replica.lock':b'','root.gsr':root_raw,'genesis.gsr':raw,'grants.gsr':promise_raw,
        'node.gsr':e.f.encode('records','NODE',dict(root=digest,identity=root['initial'][0])),
        'allocator.gsr':e.f.encode('records','ALLOCATOR',dict(root=digest,node='node-1',counter=0))}.items():(path/name).write_bytes(data)
    (path/'sources').mkdir();directory=path/'generations/a';directory.mkdir(parents=True)
    files={'source.gscp':packet,'promise.gsr':promise_raw,app+'.image':image}
    for name,data in files.items():(directory/name).write_bytes(data)
    generation=dict(root=digest,node='node-1',generation='a',cut=cut,application=app,catalog=e.sha(cat_raw),capsule=e.sha(cap_raw),
                    promise=e.sha(promise_raw),basis=None,selection=None,ownedTail=None,
                    files=[dict(path=name,size=len(data),sha256=e.sha(data)) for name,data in sorted(files.items())])
    raw=e.f.encode('records','GENERATION',generation);(directory/'generation.gsr').write_bytes(raw)
    (path/'selector.gsr').write_bytes(e.f.encode('records','SELECTOR',dict(root=digest,node='node-1',generation='a',digest=e.sha(raw))))


class CurrentGenerationEvidenceTest(unittest.TestCase):
    def test_matrix_covers_sizes_tail_states_and_every_process_cut(self):
        rows=e.cases();self.assertEqual(90,len(rows));self.assertEqual(90,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for tail in (False,True):
                for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['tail'],r['mode'])==(size,tail,mode)})

    def test_complete_original_replays_after_relocation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'original';fixture(path);expected=e.current(path,3)
            copied=Path(temp)/'copy';n.shutil.copytree(path,copied);self.assertEqual(expected,e.current(copied,3))

    def test_valid_checksums_do_not_allow_semantic_rebinding(self):
        for name,reason in n.CASES:
            if name not in ('selector','node','inactive','packet','promise','cut'):continue
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);fixture(root/'initial');e.current(root/'initial',3);n.mutate(root,name)
                with self.assertRaises(ValueError) as error:e.current(root/'initial',3)
                self.assertEqual(reason,str(error.exception))

    def test_hidden_tail_file_extra_path_and_image_drift_reject(self):
        for variant in ('tail','image','path'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                path=Path(temp)/'current';fixture(path);directory=path/'generations/a'
                if variant=='tail':(directory/'owned-tail.gsr').write_bytes(b'extra')
                elif variant=='image':next(directory.glob('*.image')).write_bytes(b'changed')
                else:n.rewrite(path,lambda row:row['files'][0].update(path='nested/image'))
                with self.assertRaises(ValueError):e.current(path,3)

    def test_missing_selector_and_unknown_generation_never_fall_back(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'current';fixture(path);(path/'selector.gsr').unlink()
            with self.assertRaisesRegex(ValueError,'grant snapshot inventory'):e.current(path,3)

    def test_original_failure_precedes_negative_mutation(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('missing')
            copy.assert_not_called()

    def test_unrelated_error_cannot_count_as_negative_success(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated current negative'):n.run('missing')

    def test_output_never_overwrites_prior_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
