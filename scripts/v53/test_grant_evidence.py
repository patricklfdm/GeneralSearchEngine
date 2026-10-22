import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import grant_evidence as e
from . import grant_negatives as n
from . import grant_qualification as q
from . import format_fixture as f

ROOT='ab'*32


def records(counter=20,proposer='node-1'):
    view=dict(generation=0,old=['node-1','node-2','node-3'],new=['node-1','node-2','node-3'],operation=None)
    promise=dict(root=ROOT,view=hashlib.sha256(f.canonical(dict(root=ROOT,**view))).hexdigest(),
                 ballot=dict(counter=counter,proposer=proposer,incarnation='00000000-0000-0000-0000-000000000001'),
                 basisId='00000000-0000-0000-0000-000000000002')
    basis=dict(copy.deepcopy(promise),voter='node-1',cut=dict(index=0,entry='cd'*32,view=view),capsule='de'*32,inventory='ef'*32,accepted=None)
    return promise,basis


def frames(p,b=None):return f.encode('records','PROMISE',p)+(b'' if b is None else f.encode('records','BASIS',b))


class GrantEvidenceTest(unittest.TestCase):
    def test_inventory_covers_all_sizes_and_both_crash_modes(self):
        rows=e.cases();self.assertEqual(45,len(rows));self.assertEqual(45,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if r['size']==size and r['mode']==mode})

    def test_complete_and_incomplete_grants_survive_only_a_higher_new_promise(self):
        p,b=records();p2,b2=records(21)
        self.assertEqual(['PROMISE','BASIS'],[r[0] for r in e.journal(frames(p,b),ROOT,'node-1')])
        self.assertEqual(['PROMISE','PROMISE','BASIS'],[r[0] for r in e.journal(frames(p)+frames(p2,b2),ROOT,'node-1')])
        with self.assertRaisesRegex(ValueError,'non-increasing'):e.journal(frames(p)+frames(p,b),ROOT,'node-1')

    def test_orphan_repeated_or_rebound_basis_rejects(self):
        p,b=records();raw=frames(p,b)
        for data in (f.encode('records','BASIS',b),raw+f.encode('records','BASIS',b)):
            with self.assertRaisesRegex(ValueError,'orphan/duplicate'):e.journal(data,ROOT,'node-1')
        for field,value in (('basisId','00000000-0000-0000-0000-000000000003'),('view','00'*32),('voter','node-2')):
            bad=copy.deepcopy(b);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):e.journal(frames(p,bad),ROOT,'node-1')

    def test_torn_corrupt_foreign_and_wrong_kind_are_not_silently_truncated(self):
        p,b=records();raw=frames(p,b);bad=bytearray(raw);bad[-1]^=1;foreign=copy.deepcopy(p);foreign['root']='00'*32
        samples=(raw[:-1],raw[:47],bytes(bad),frames(foreign),f.encode('records','ALLOCATOR',dict(root=ROOT,node='node-1',counter=1)))
        for data in samples:
            before=bytes(data)
            with self.assertRaises(ValueError):e.journal(data,ROOT,'node-1')
            self.assertEqual(before,data)

    def test_equal_counter_uses_full_proposer_order(self):
        p,b=records();p2,b2=records(proposer='node-2')
        self.assertEqual(4,len(e.journal(frames(p,b)+frames(p2,b2),ROOT,'node-1')))
        with self.assertRaisesRegex(ValueError,'non-increasing'):e.journal(frames(p2,b2)+frames(p,b),ROOT,'node-1')

    def test_sentinel_and_invalid_membership_are_rejected(self):
        p,b=records(2**63-1)
        with self.assertRaisesRegex(ValueError,'capacity'):e.journal(frames(p),ROOT,'node-1')
        p,b=records();b['cut']['view']['new'][1]='node-1'
        with self.assertRaisesRegex(ValueError,'membership view'):e.journal(frames(p,b),ROOT,'node-1')

    def test_invalid_original_never_counts_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('bad original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'bad original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_negative_error_is_not_accepted(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated grant negative rejection'):n.run('absent')

    def test_qualification_never_overwrites_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
