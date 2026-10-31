"""Reader grammar and original-first qualification regressions; no native claim."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import transfer_fault_evidence as e


def attempt(drop=False):
    rows=[dict(event='CALL',request='q',expected='SOURCE_OFFER',deadline=123),
          dict(event='BEFORE_REQUEST_WRITE',side='client',request='q'),
          dict(event='AFTER_REQUEST_READ',side='server',request='q'),
          dict(event='BEFORE_RESPONSE_WRITE',side='server',request='q',response='a')]
    if drop:
        rows += [dict(event='DROP',request='q',response='a'),dict(event='FAILURE',request='q',reason='IO')]
    else:
        rows += [dict(event='AFTER_RESPONSE_READ',side='client',request='q',response='a'),
                 dict(event='REPLY',request='q',response='a')]
    return rows


class TransferFaultEvidenceTest(unittest.TestCase):
    def test_actual_drop_and_success_have_distinct_delivery(self):
        attempts,controls=e.calls([dict(event='OPEN')]+attempt(True)+attempt()+[dict(event='BEFORE_CLOSE')])
        self.assertEqual([(0,dict(event='OPEN')),(2,dict(event='BEFORE_CLOSE'))],controls)
        self.assertEqual([False,True],[v['reply'] for v in attempts])
        self.assertEqual([True,False],[v['drop'] for v in attempts])
        self.assertEqual(['a','a'],[v['response'] for v in attempts])

    def test_terminal_refusal_has_no_server_reply(self):
        rows=attempt()[:3]+[dict(event='FAILURE',request='q',reason='IO')]
        values,_=e.calls(rows);self.assertIsNone(values[0]['response']);self.assertFalse(values[0]['reply'])

    def test_drop_cannot_also_be_delivered(self):
        rows=attempt(True);rows[-1]=dict(event='REPLY',request='q',response='a')
        with self.assertRaisesRegex(ValueError,'TCP attempt order'):e.calls(rows)

    def test_missing_server_read_is_not_a_completed_exchange(self):
        rows=attempt();del rows[2]
        with self.assertRaisesRegex(ValueError,'TCP attempt order'):e.calls(rows)

    def test_mismatched_request_is_rejected(self):
        rows=attempt();rows[2]['request']='different'
        with self.assertRaisesRegex(ValueError,'exact attempt request'):e.calls(rows)

    def test_received_response_must_equal_server_bytes(self):
        rows=attempt();rows[-1]['response']='different'
        with self.assertRaisesRegex(ValueError,'exact attempted response'):e.calls(rows)

    def test_missing_drop_marker_is_not_a_proven_loss(self):
        rows=attempt(True);del rows[-2]
        with self.assertRaisesRegex(ValueError,'TCP attempt order'):e.calls(rows)

    def test_other_failure_does_not_qualify_original_io(self):
        rows=attempt(True);rows[-1]['reason']='TIMEOUT'
        with self.assertRaisesRegex(ValueError,'original IO outcome'):e.calls(rows)

    def test_incomplete_attempt_does_not_qualify(self):
        with self.assertRaisesRegex(ValueError,'missing attempt outcome'):e.calls(attempt()[:-1])

    def test_unbound_delivery_and_control_inside_attempt_reject(self):
        with self.assertRaisesRegex(ValueError,'unbound observation'):e.calls([attempt()[-1]])
        rows=attempt();rows.insert(2,dict(event='EXPIRE'))
        with self.assertRaisesRegex(ValueError,'exact attempt request'):e.calls(rows)

    def test_collection_shape_and_bound(self):
        for rows in ({},[None],[{}],[dict(event='OPEN')]*1025):
            with self.subTest(rows=str(rows)[:30]),self.assertRaisesRegex(ValueError,'event collection'):e.calls(rows)

    def test_resource_shape_rejects_boolean_negative_and_inconsistent_counts(self):
        original=dict(leases=1,metadata=10,staging=20,queued=0,counts={'SOURCE':1})
        self.assertEqual(original,e.resource(original))
        for key,value in [('leases',True),('metadata',-1),('counts',{'SOURCE':2}),('counts',{'SOURCE':True}),('counts',{'SOURCE':0})]:
            bad=copy.deepcopy(original);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'resource observation shape'):e.resource(bad)

    def test_empty_resources_are_consistent(self):
        value=dict(leases=0,metadata=0,staging=0,queued=0,counts={});self.assertEqual(value,e.resource(value))

    def test_duplicate_json_keys_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'x.json';p.write_text('{"status":"FAIL","status":"PASS"}')
            with self.assertRaisesRegex(ValueError,'duplicate JSON key'):e.load(p)

    def test_missing_linked_and_incomplete_originals_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);raw=p/'raw';raw.mkdir();link=p/'link';link.symlink_to(raw,target_is_directory=True)
            for root in (p/'missing',raw,link):
                with self.subTest(root=root),self.assertRaises(ValueError):e.validate(root)

    def test_original_failure_prevents_all_mutations(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e,'validate',side_effect=ValueError('bad original')),\
                patch.object(e.shutil,'copytree') as copier,patch.object(e,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):e.qualify(temp)
            copier.assert_not_called();mutate.assert_not_called()

    def test_exact_reason_and_original_preservation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'marker').write_bytes(b'original');before=e.history.inventory(root)
            def mutate(target,name):
                self.assertNotEqual(root,target);(target/'marker').write_bytes(b'mutated')
            with patch.object(e,'NEGATIVES',[('test','exact')]),patch.object(e,'mutate',side_effect=mutate),\
                    patch.object(e,'validate',side_effect=[{'status':'PASS'},ValueError('exact')]):
                result=e.qualify(root)
            self.assertTrue(result['originalPreserved']);self.assertEqual(before,e.history.inventory(root))
            self.assertEqual([dict(case='test',reason='exact',status='REJECTED')],result['negatives'])

    def test_unrelated_or_substring_rejection_is_not_success(self):
        for reason in ('unrelated','exact plus extra'):
            with tempfile.TemporaryDirectory() as temp,patch.object(e,'NEGATIVES',[('test','exact')]),\
                    patch.object(e,'mutate'),patch.object(e,'validate',side_effect=[{},ValueError(reason)]):
                with self.assertRaisesRegex(ValueError,'unrelated negative'):e.qualify(temp)

    def test_accepted_negative_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(e,'NEGATIVES',[('test','exact')]),\
                patch.object(e,'mutate'),patch.object(e,'validate',return_value={}):
            with self.assertRaisesRegex(ValueError,'accepted negative'):e.qualify(temp)

    def test_original_mutation_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);marker=root/'marker';marker.write_bytes(b'original')
            with patch.object(e,'NEGATIVES',[('test','exact')]),patch.object(e,'mutate',side_effect=lambda *_:marker.write_bytes(b'changed')),\
                    patch.object(e,'validate',side_effect=[{},ValueError('exact')]):
                with self.assertRaisesRegex(ValueError,'original modified'):e.qualify(root)

    def test_negative_names_are_unique_and_cover_physical_and_transfer_boundaries(self):
        names=[v[0] for v in e.NEGATIVES];self.assertEqual(len(names),len(set(names)))
        self.assertTrue({'changed-after','changed-record','foreign-sender','extended-deadline','missing-promise-force',
                         'basis-before-force','missing-source-image-force','server-resource-leak','early-expiry'}<=set(names))


if __name__=='__main__':unittest.main()
