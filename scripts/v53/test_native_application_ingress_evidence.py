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


    def test_nonvoting_application_reply_is_explicit_nullable_syntax_not_an_omitted_field(self):
        catalog=a.f.catalog();spec=catalog['wire']['APPLY_ACK']
        self.assertEqual({'nullable':'hash'},spec['schema']['object']['payload']['object']['acknowledgement'])
        value=a.f.sample(spec['schema'],catalog['types'])
        for acknowledgement in (None,'ab'*32):
            value['payload']['acknowledgement']=acknowledgement
            self.assertEqual(value,a.f.decode(a.f.encode('wire','APPLY_ACK',value),'wire','APPLY_ACK'))
        value['payload'].pop('acknowledgement')
        with self.assertRaises(ValueError):a.f.encode('wire','APPLY_ACK',value)

    def test_production_schema_and_java_fixture_copy_match_the_independent_catalog(self):
        root=a.f.ROOT
        self.assertEqual(a.f.canonical(a.f.catalog()),(root/'general-search-engine-replication/src/main/resources/replication/membership-format-v13.json').read_bytes())
        self.assertEqual((root/'docs/v5x/v5.3/byte-fixtures.json').read_bytes(),(root/'general-search-engine-replication/src/test/resources/replication/v53/byte-fixtures.json').read_bytes())


if __name__=='__main__':unittest.main()
