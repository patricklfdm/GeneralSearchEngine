"""Reader failure discipline; native proof comes from separately captured originals."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import transfer_reply_lifetime as r


class TransferReplyLifetimeTest(unittest.TestCase):
    def test_catalogue_covers_every_declared_boundary_and_revocation(self):
        self.assertEqual(48,len(r.CASES));self.assertEqual(48,len(set(r.CASES)))
        for size in (3,4,5):
            self.assertEqual({(boundary,fault) for boundary in r.BOUNDARIES for fault in r.FAULTS},
                             {(b,f) for n,b,f in r.CASES if n==size})

    def test_missing_linked_and_incomplete_originals_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=root/'raw';raw.mkdir();link=root/'link';link.symlink_to(raw,target_is_directory=True)
            for path in (root/'missing',raw,link):
                with self.subTest(path=path),self.assertRaises(ValueError):r.validate(path)

    def test_event_shape_is_bounded_before_frame_decoding(self):
        for rows in ({},[],[None],[{}]*1025):
            with self.subTest(rows=str(rows)[:20]),self.assertRaisesRegex(ValueError,'event collection'):
                r.replay_events(rows,None,None,None,None,'offer','expiry')

    def test_missing_open_is_not_an_original_scope(self):
        with self.assertRaisesRegex(ValueError,'event order: OPEN'):
            r.replay_events([dict(event='CALL')],None,None,None,None,'offer','expiry')

    def test_clock_is_positive_integer_not_boolean(self):
        for value in (True,False,0,-1,1.0,'1',None):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'original clock'):
                r.replay_events([dict(event='OPEN',started=value)],None,None,None,None,'offer','expiry')

    def test_canonical_equality_does_not_accept_boolean_counts(self):
        with self.assertRaisesRegex(ValueError,'exact'):
            r.same(dict(live=True),dict(live=1),'exact')

    def test_uuid_requires_canonical_nonzero_identity(self):
        for value in (None,1,'bad','00000000-0000-0000-0000-000000000000','AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA'):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'original UUID'):r.identifier(value)
        r.identifier('12345678-1234-1234-1234-123456789012')

    def test_original_failure_prevents_all_mutations(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'validate',side_effect=ValueError('bad original')),\
                patch.object(r.shutil,'copytree') as copier,patch.object(r,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):r.qualify(temp)
            copier.assert_not_called();mutate.assert_not_called()

    def test_exact_rejection_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'marker').write_bytes(b'original');before=r.h.inventory(root)
            def change(target,name):
                self.assertNotEqual(root,target);(target/'marker').write_bytes(b'changed')
            with patch.object(r,'NEGATIVES',{'test':'exact'}),patch.object(r,'mutate',side_effect=change),\
                    patch.object(r,'validate',side_effect=[dict(status='PASS'),ValueError('exact')]):
                result=r.qualify(root)
            self.assertEqual(before,r.h.inventory(root));self.assertTrue(result['originalPreserved'])
            self.assertEqual([dict(case='test',status='REJECTED',reason='exact')],result['negatives'])

    def test_unrelated_failure_is_not_an_accepted_negative(self):
        for error in ('different','exact extra'):
            with tempfile.TemporaryDirectory() as temp,patch.object(r,'NEGATIVES',{'test':'exact'}),\
                    patch.object(r,'mutate'),patch.object(r,'validate',side_effect=[{},ValueError(error)]):
                with self.assertRaisesRegex(ValueError,'unrelated negative'):r.qualify(temp)

    def test_accepted_mutation_fails_qualification(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r,'NEGATIVES',{'test':'exact'}),\
                patch.object(r,'mutate'),patch.object(r,'validate',return_value={}):
            with self.assertRaisesRegex(ValueError,'accepted negative'):r.qualify(temp)

    def test_mutating_original_fails_qualification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);marker=root/'marker';marker.write_bytes(b'original')
            with patch.object(r,'NEGATIVES',{'test':'exact'}),\
                    patch.object(r,'mutate',side_effect=lambda *_:marker.write_bytes(b'changed')),\
                    patch.object(r,'validate',side_effect=[{},ValueError('exact')]):
                with self.assertRaisesRegex(ValueError,'original changed'):r.qualify(root)

    def test_negative_catalogue_covers_authority_and_response_boundaries(self):
        self.assertEqual(44,len(r.NEGATIVES))
        self.assertTrue({'changed-source','changed-after','late-response','non-higher-ballot',
                         'cached-live-export','same-fresh-trace','missing-clock-reset','immediate-leak',
                         'resource-invented-baseline','resource-cached-double-charge','resource-storage-released',
                         'resource-outgoing-request','resource-received-request','resource-server-response',
                         'resource-client-response','resource-closed-owner'}<=set(r.NEGATIVES))


if __name__=='__main__':unittest.main()
