import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import adoption_install_evidence as e
from . import adoption_install_negatives as n
from . import adoption_install_qualification as q


class AdoptionInstallEvidenceTest(unittest.TestCase):
    def test_every_cut_under_both_certifying_authorities(self):
        rows=e.cases();self.assertEqual(234,len(rows));self.assertEqual(234,len({r['name'] for r in rows}))
        self.assertEqual(19,len(e.CUTS))
        for size in (3,4,5):
            for through in (6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})

    def test_invalid_original_cannot_be_used_as_successful_negatives(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_rejection_is_not_a_success(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated adoption install negative'):n.run('absent')

    def test_preserves_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
