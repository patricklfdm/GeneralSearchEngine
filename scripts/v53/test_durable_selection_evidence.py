import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import durable_selection_evidence as e
from . import durable_selection_negatives as n
from . import durable_selection_qualification as q
from .test_grant_evidence import records,frames,ROOT


def selected(counter=20):
    promise,basis=records(counter);basis['basisId']=promise['basisId']=f'00000000-0000-0000-0000-{counter:012d}'
    raw=e.g.f.encode('records','BASIS',basis)
    value=dict(root=ROOT,view=promise['view'],ballot=copy.deepcopy(promise['ballot']),cut=copy.deepcopy(basis['cut']),nextEntry=None,
               sources=[dict(voter='node-1',basisId=basis['basisId'],basisDigest=e.c.sha(raw)),
                        dict(voter='node-2',basisId='00000000-0000-0000-0000-000000000099',basisDigest='12'*32)])
    return promise,basis,value


def data(p,b,s):return frames(p,b)+e.g.f.encode('records','SELECTED',s)


class DurableSelectionEvidenceTest(unittest.TestCase):
    def test_inventory_covers_members_tails_and_real_crash_modes(self):
        rows=e.cases();self.assertEqual(54,len(rows));self.assertEqual(54,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for tail in (False,True):
                for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['tail'],r['mode'])==(size,tail,mode)})

    def test_selection_cannot_repeat_until_new_grant(self):
        p,b,s=selected();raw=data(p,b,s);p2,b2,s2=selected(21)
        self.assertEqual(['PROMISE','BASIS','SELECTED']*2,[r[0] for r in e.g.journal(raw+data(p2,b2,s2),ROOT,'node-1')])
        with self.assertRaisesRegex(ValueError,'duplicate persisted selection'):e.g.journal(raw+e.g.f.encode('records','SELECTED',s),ROOT,'node-1')

    def test_orphan_or_incomplete_local_grant_cannot_select(self):
        p,b,s=selected();raw=e.g.f.encode('records','SELECTED',s)
        for prefix in (b'',frames(p)):
            with self.assertRaisesRegex(ValueError,'selection without local grant'):e.g.journal(prefix+raw,ROOT,'node-1')

    def test_checksum_valid_rebindings_reject(self):
        p,b,s=selected()
        changes=[lambda v:v.update(view='00'*32),lambda v:v['ballot'].update(counter=19),
                 lambda v:v['sources'][0].update(basisDigest='00'*32),lambda v:v['sources'][1].update(voter='node-9'),
                 lambda v:v['sources'][1].update(basisId=b['basisId']),lambda v:v['cut'].update(entry='00'*32)]
        for change in changes:
            value=copy.deepcopy(s);change(value)
            with self.assertRaises(ValueError):e.g.journal(data(p,b,value),ROOT,'node-1')

    def test_torn_selection_is_never_discarded(self):
        p,b,s=selected();raw=data(p,b,s)
        for suffix in (1,10,len(e.g.f.encode('records','SELECTED',s))-20):
            with self.assertRaisesRegex(ValueError,'torn grant journal'):e.g.journal(raw[:-suffix],ROOT,'node-1')

    def test_persisted_selection_is_not_installation_ack(self):
        p,b,s=selected();raw=e.g.f.encode('records','SELECTED',s);row=dict(status='PASS',selection=e.c.sha(raw),counter=20,
            cut=s['cut'],sources=s['sources'],nextEntry=s['nextEntry'],installationAck=False)
        e.result([row],('SELECTED',raw,s));row['installationAck']=True
        with self.assertRaisesRegex(ValueError,'selection returned binding'):e.result([row],('SELECTED',raw,s))

    def test_invalid_original_cannot_count_as_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_failure_cannot_count_as_expected_rejection(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated selection negative'):n.run('absent')

    def test_original_evidence_directory_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
