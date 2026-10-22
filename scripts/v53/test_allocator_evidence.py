import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from . import allocator_evidence as e
from . import allocator_negatives as n
from . import allocator_qualification as q
from . import format_fixture as f


def clean_fixture(directory):
    """Independent synthetic reader input; never reported as process evidence."""
    case=next(c for c in e.cases() if c['size']==3 and c['mode']=='clean')
    directory.mkdir();initial=directory/'initial';initial.mkdir();catalog=f.catalog()
    genesis=f.sample(catalog['records']['GENESIS']['schema'],catalog['types'])
    genesis.update(source='EMPTY',sourceDigest=None)
    raw=f.encode('records','GENESIS',genesis)
    root=f.sample(catalog['records']['ROOT']['schema'],catalog['types'])
    root.update({k:genesis[k] for k in ('groupId','historyId','baseSequence','schema','indexes')})
    root.update(genesis=hashlib.sha256(raw).hexdigest(),limits=hashlib.sha256(f.canonical(catalog['resources'])).hexdigest())
    for i,member in enumerate(root['initial'],1):member['node']=f'node-{i}'
    root_raw=f.encode('records','ROOT',root);root_hash=root_raw[16:48].hex()
    (initial/'root.gsr').write_bytes(root_raw);(initial/'genesis.gsr').write_bytes(raw);(initial/'replica.lock').write_bytes(b'')
    (initial/'node.gsr').write_bytes(f.encode('records','NODE',dict(root=root_hash,identity=root['initial'][0])))
    (initial/'allocator.gsr').write_bytes(f.encode('records','ALLOCATOR',dict(root=root_hash,node='node-1',counter=0)))
    shutil.copytree(initial,directory/'final');n.edit_record(directory/'final/allocator.gsr','ALLOCATOR',counter=11)
    shutil.copytree(directory/'final',directory/'authority')
    processes={}
    for name,counter,command in (('init',None,'init'),('first',10,'reserve'),('second',11,'reserve'),('inspect',11,'inspect')):
        rows=[dict(event=c) for c in e.CUTS] if name in ('first','second') else []
        rows.append(dict(status='PASS',command=command,**({} if counter is None else dict(counter=counter))))
        (directory/(name+'.stdout')).write_bytes(b''.join(f.canonical(r)+b'\n' for r in rows))
        (directory/(name+'.stderr')).write_bytes(b'');processes[name]=dict(exitCode=0)
    (directory/'case.json').write_bytes(f.canonical(dict(case=case,execution='private-storage-process',runtimeEnabled=False,processes=processes)))
    return case


class AllocatorEvidenceTest(unittest.TestCase):
    def test_inventory_contains_each_size_mode_and_boundary_once(self):
        rows=e.cases();self.assertEqual(48,len(rows));self.assertEqual(48,len({r['name'] for r in rows}))
        for size in (3,4,5):
            self.assertEqual(16,sum(r['size']==size for r in rows))
            for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if r['size']==size and r['mode']==mode})

    def test_independent_valid_input_replays_after_relocation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'original';case=clean_fixture(root);expected=e.validate_case(root,case)
            copied=Path(temp)/'copied';shutil.copytree(root,copied);self.assertEqual(expected,e.validate_case(copied,case))

    def test_mutations_reject_for_the_intended_reason(self):
        for name,mode,cut,reason in n.CASES:
            if mode!='clean':continue
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'case';case=clean_fixture(root);e.validate_case(root,case);n.mutate(root,name)
                with self.assertRaises(ValueError) as error:e.validate_case(root,case)
                self.assertEqual(reason,str(error.exception))

    def test_missing_extra_and_linked_inputs_reject(self):
        for fault in ('missing','extra','linked','stderr','exit-code'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'case';case=clean_fixture(root)
                if fault=='missing':(root/'final/root.gsr').unlink()
                elif fault=='extra':(root/'unexpected').write_bytes(b'x')
                elif fault=='linked':
                    (root/'first.stdout').rename(root/'original');(root/'first.stdout').symlink_to(root/'original')
                elif fault=='stderr':(root/'first.stderr').write_bytes(b'unhandled failure')
                else:
                    value=e.load(root/'case.json');value['processes']['first']['exitCode']=True
                    (root/'case.json').write_bytes(f.canonical(value))
                with self.assertRaises(ValueError):e.validate_case(root,case)

    def test_original_failure_never_counts_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_mutation_failure_never_counts_as_expected_rejection(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated allocator negative rejection'):n.run('absent')

    def test_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'keep';marker.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',marker.read_text())


if __name__=='__main__':unittest.main()
