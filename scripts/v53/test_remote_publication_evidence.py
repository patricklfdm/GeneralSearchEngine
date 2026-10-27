import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import remote_publication_evidence as r
from . import format_fixture as f


class RemotePublicationEvidenceTest(unittest.TestCase):
    def test_original_failure_is_never_counted_as_negative_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(r,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(r.shutil,'copytree') as copies:
                with self.assertRaisesRegex(ValueError,'invalid original'):r.qualify(Path(temp))
                validate.assert_called_once();copies.assert_not_called()

    def test_publication_ack_is_distinct_and_binds_full_original_target(self):
        catalog=f.catalog();spec=catalog['wire']['PUBLISH_ACK'];self.assertEqual(26,spec['id']);self.assertEqual(32768,spec['maximum'])
        value=f.sample(spec['schema'],catalog['types']);raw=f.encode('wire','PUBLISH_ACK',value)
        self.assertEqual(value,f.decode(raw,'wire','PUBLISH_ACK'))
        self.assertEqual({'certificate','selection','published','generation'},set(value['payload']))
        for field in value['payload']:
            changed={**value,'payload':dict(value['payload'])};del changed['payload'][field]
            with self.subTest(field=field),self.assertRaises(ValueError):f.encode('wire','PUBLISH_ACK',changed)
        with self.assertRaises(ValueError):f.decode(raw,'wire','CHECKPOINT_ACK')


if __name__=='__main__':unittest.main()
