import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import adoption_fence_evidence as e
from . import adoption_fence_negatives as n
from . import adoption_fence_qualification as q
from .test_grant_evidence import records,frames,ROOT


class AdoptionFenceEvidenceTest(unittest.TestCase):
    def test_matrix_includes_old_and_joint_certificate_authorities(self):
        rows=e.cases();self.assertEqual(66,len(rows));self.assertEqual(66,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (6,7):
                for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})

    def test_adoption_replays_without_grant_and_retains_old_basis(self):
        p,b=records();adopt=copy.deepcopy(p);adopt['basisId']=None;adopt['ballot']['counter']=30
        rows=e.g.journal(frames(p,b)+frames(adopt),ROOT,'node-1');self.assertEqual(3,len(rows));self.assertIsNone(rows[-1][2]['basisId'])
        invented=dict(b,ballot=adopt['ballot'])
        with self.assertRaisesRegex(ValueError,'adoption fence is not a grant'):e.g.journal(frames(p,b)+frames(adopt,invented),ROOT,'node-1')
        later=copy.deepcopy(adopt);later['ballot']['counter']=31
        self.assertEqual(4,len(e.g.journal(frames(p,b)+frames(adopt)+frames(later),ROOT,'node-1')))

    def test_equal_or_lower_fence_cannot_append(self):
        p,b=records();adopt=copy.deepcopy(p);adopt['basisId']=None
        for counter in (19,20):
            adopt['ballot']['counter']=counter
            with self.assertRaisesRegex(ValueError,'non-increasing'):e.g.journal(frames(p,b)+frames(adopt),ROOT,'node-1')

    def test_fence_never_becomes_vote_or_installation_ack(self):
        p,_=records();p['basisId']=None;raw=frames(p)
        row=dict(promise=e.c.sha(raw),view=p['view'],ballot=p['ballot'],hasBasis=False,prefixInstalled=False,networkAck=False)
        e.result([row],raw,p)
        for name in ('hasBasis','prefixInstalled','networkAck'):
            value=dict(row);value[name]=True
            with self.assertRaisesRegex(ValueError,'adoption returned binding'):e.result([value],raw,p)

    def test_invalid_original_cannot_count_as_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_failure_cannot_count_as_rejection(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated adoption negative'):n.run('absent')

    def test_never_overwrites_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',path.read_text())


if __name__=='__main__':unittest.main()
