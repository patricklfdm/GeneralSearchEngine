from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_inflight_evidence as p


class NodeInFlightEvidenceTest(unittest.TestCase):
    def test_bad_original_cannot_count_as_negative_success(self):
        with patch.object(p,'validate',side_effect=ValueError('bad original')),patch.object(p.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):p.qualify('unused')
            copied.assert_not_called()

    def test_link_is_rejected_before_physical_reduction(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'original').write_text('bytes');(root/'link').symlink_to('original')
            with patch.object(p,'physical') as physical:
                with self.assertRaisesRegex(ValueError,'regular inventory'):p.validate(root)
                physical.assert_not_called()

    def service(self):
        service=p.Service.__new__(p.Service)
        catalog=p.f.catalog();fields=p.f.sample(catalog['records']['ENTRY']['schema'],catalog['types'])
        fields['index']=2;fields['kind']='DATA'
        service.carried=p.f.encode('records','ENTRY',fields)
        return service,fields

    def test_reaccept_keeps_exact_old_origin_and_payload(self):
        service,fields=self.service();changed=dict(fields,origin=dict(fields['origin'],counter=fields['origin']['counter']+1))
        self.assertEqual(service.carried,service.entry_bytes(changed))
        for key,value in [('payload','0'*64),('previous','0'*64),('kind','BARRIER')]:
            mutation=dict(changed,**{key:value})
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact carried request'):service.entry_bytes(mutation)

    def test_later_barrier_uses_fresh_original_request(self):
        service,fields=self.service();fields=dict(fields,index=3,kind='BARRIER',payload=p.e.digest(b''))
        self.assertEqual(p.f.encode('records','ENTRY',fields),service.entry_bytes(fields))

    def test_unknown_crash_cut_is_not_a_publication_receipt(self):
        service,_=self.service()
        with self.assertRaisesRegex(ValueError,'original crash point'):service.interrupt('AFTER_DATA_RETURN')

    def test_recovery_cannot_skip_carried_data_to_ready_barrier(self):
        service,_=self.service();service.slot=1
        with self.assertRaisesRegex(ValueError,'original DATA first'):service.advance('BARRIER')


if __name__=='__main__':unittest.main()
