import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import basis_sources_evidence as e
from . import basis_sources_negatives as n
from . import basis_sources_qualification as q
from .test_source_packet import fixture,frame


class BasisSourcesEvidenceTest(unittest.TestCase):
    def test_all_sizes_real_process_modes_and_source_boundaries(self):
        rows=e.cases();self.assertEqual(69,len(rows));self.assertEqual(69,len({c['name'] for c in rows}))
        for size in (3,4,5):
            for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{c['cut'] for c in rows if c['size']==size and c['mode']==mode})

    def fixture(self,path):
        capsule,index,objects=fixture();root=b'original root';objects[hashlib.sha256(root).hexdigest()]=root
        index['objects']=[dict(sha256=h,bytes=len(b)) for h,b in sorted(objects.items())]
        cap=e.f.decode(capsule,'records','CAPSULE');cap['inventory']=hashlib.sha256(e.f.canonical(index)).hexdigest()
        capsule=e.f.encode('records','CAPSULE',cap);raw=frame(capsule,e.f.canonical(index),objects)
        value=e.f.sample(e.f.catalog()['records']['BASIS']['schema'],e.f.catalog()['types'])
        value.update(root=cap['root'],cut=cap['cut'],capsule=hashlib.sha256(capsule).hexdigest(),inventory=cap['inventory'],
                     view=hashlib.sha256(e.f.canonical(dict(root=cap['root'],**cap['cut']['view']))).hexdigest())
        promise={k:value[k] for k in ('root','view','ballot','basisId')}
        directory=path/'sources'/value['basisId'];directory.mkdir(parents=True)
        (directory/'source.gscp').write_bytes(raw)
        (directory/(index['images'][0]['sha256']+'.image')).write_bytes(b'independent image')
        rows=[('PROMISE',e.f.encode('records','PROMISE',promise),promise),('BASIS',e.f.encode('records','BASIS',value),value)]
        return directory,({'root.gsr':root},rows)

    def test_missing_altered_extra_and_relocated_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);directory,state=self.fixture(path)
            with patch.object(e.g,'state',return_value=state):
                expected=e.state(path,3)
                image=next(directory.glob('*.image'));raw=image.read_bytes();image.write_bytes(b'x'*len(raw))
                with self.assertRaisesRegex(ValueError,'retained image integrity'):e.state(path,3)
                image.write_bytes(raw);image.unlink()
                with self.assertRaisesRegex(ValueError,'retained source file inventory'):e.state(path,3)
                image.write_bytes(raw);(directory/'extra').write_bytes(b'x')
                with self.assertRaisesRegex(ValueError,'retained source file inventory'):e.state(path,3)
                (directory/'extra').unlink();self.assertEqual(expected,e.state(path,3))
                copy=path.parent/(path.name+'-copy')
                try:n.shutil.copytree(path,copy);self.assertEqual(expected,e.state(copy,3))
                finally:n.shutil.rmtree(copy,ignore_errors=True)

    def test_missing_directory_and_unbound_original_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);directory,state=self.fixture(path)
            with patch.object(e.g,'state',return_value=state):
                (path/'sources'/'unknown').mkdir()
                with self.assertRaisesRegex(ValueError,'missing or unbound'):e.state(path,3)
                (path/'sources'/'unknown').rmdir();n.shutil.rmtree(directory)
                with self.assertRaisesRegex(ValueError,'missing or unbound'):e.state(path,3)

    def test_partial_inventory_never_validates_as_complete_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);directory,state=self.fixture(path);state[1].pop()
            next(directory.glob('*.image')).unlink()
            with patch.object(e.g,'state',return_value=state):
                e.state(path,3,partial=True)
                with self.assertRaisesRegex(ValueError,'retained source file inventory'):e.state(path,3)

    def test_links_and_inode_aliases_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'one').write_bytes(b'a');(path/'two').symlink_to(path/'one')
            with self.assertRaisesRegex(ValueError,'source file type'):e.inventory(path)
            (path/'two').unlink();(path/'two').hardlink_to(path/'one')
            with self.assertRaisesRegex(ValueError,'source file type/limit'):e.inventory(path)

    def test_partial_refusal_checks_actual_filesystem_type_and_exact_missing_member(self):
        result=dict(type='ReplicationException',reason='authority member is not a single regular file: /original/location/sources/id/source.gscp')
        e.partial_refusal(result,'SOURCE_CREATED','id')
        for changed in (dict(result,type='IOException'),dict(result,reason='missing source.gscp'),dict(result,reason=result['reason']+'-other')):
            with self.assertRaisesRegex(ValueError,'source partial refusal'):e.partial_refusal(changed,'SOURCE_CREATED','id')
        e.partial_refusal(dict(type='IllegalArgumentException',reason='retained source file inventory'),'SOURCE_PACKET_FORCED','id')

    def test_original_must_validate_before_negative_mutation(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_error_cannot_pass_negative(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated source negative'):n.run('absent')

    def test_qualification_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
