import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import native_application_ingress_evidence as a
from . import native_application_ingress_restart_evidence as r


class NativeApplicationIngressEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_not_counted_as_rejected_mutations(self):
        for module in (a,r):
            with self.subTest(module=module.__name__), tempfile.TemporaryDirectory() as temp, patch.object(module,'validate',side_effect=ValueError('original invalid')), patch.object(module.shutil,'copytree') as copied:
                with self.assertRaisesRegex(ValueError,'original invalid'):module.qualify(Path(temp))
                copied.assert_not_called()

    def test_application_frames_bind_exact_certificate_selection_and_local_end(self):
        catalog=a.f.catalog()
        for name,ident,fields in [('APPLY',27,{'certificate','selection'}),('APPLY_ACK',28,{'certificate','selection','statement','acknowledgement'})]:
            spec=catalog['wire'][name];self.assertEqual(ident,spec['id']);self.assertEqual(32768,spec['maximum'])
            value=a.f.sample(spec['schema'],catalog['types']);self.assertEqual(fields,set(value['payload']))
            self.assertEqual(value,a.f.decode(a.f.encode('wire',name,value),'wire',name))
            for field in fields:
                changed=copy.deepcopy(value);changed['payload'].pop(field)
                with self.subTest(kind=name,field=field),self.assertRaises(ValueError):a.f.encode('wire',name,changed)


if __name__=='__main__':unittest.main()
