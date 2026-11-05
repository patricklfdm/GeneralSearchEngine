"""Conditional ownership checks; complete original TCP histories are separate."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import source_control_resource_evidence as r
from .test_resource_transitions import charge
from .test_transport_resource_evidence import recount


def lifetime(role='source-request',size=1200,growth=None):
    owner=role+'-'+'a'*64+'-00000000-0000-0000-0000-000000000001'
    first=charge('CONTROL',owner,size);last=first
    rows=[dict(event='START',removed=[],added=[]),dict(event='RESERVE',removed=[],added=[first])]
    if growth is not None:
        last=charge('CONTROL',owner,growth);rows.append(dict(event='CONTROL_GROW',removed=[first],added=[last]))
    rows.append(dict(event='RELEASE',removed=[last],added=[]))
    return {'node-1':recount(rows)}


class SourceControlResourceEvidenceTest(unittest.TestCase):
    def test_all_four_typed_roles_and_exact_cache_growth(self):
        for role in r.ROLES:
            traces=lifetime(role,1024 if role=='transfer-trace' else 1200,33000 if role=='transfer-trace' else None)
            leases,other=r.lifetimes(traces)
            self.assertEqual(1,len(leases));self.assertEqual(0,other)
            self.assertIsNotNone(next(iter(leases.values()))['end'])

    def test_legacy_uuid_only_owners_are_never_guessed_by_extent(self):
        traces=lifetime()
        for row in traces['node-1']['changes']:
            for value in row['removed']+row['added']:value['owner']='source-request-00000000-0000-0000-0000-000000000001'
        with self.assertRaisesRegex(ValueError,'bound owner shape'):r.lifetimes(traces)

    def test_zero_or_noncanonical_allocation_nonce_is_rejected(self):
        for nonce in ('00000000-0000-0000-0000-000000000000','-0000000-0000-0000-0000-000000000001'):
            traces=lifetime()
            for row in traces['node-1']['changes']:
                for value in row['removed']+row['added']:value['owner']='source-request-'+'a'*64+'-'+nonce
            with self.subTest(nonce=nonce),self.assertRaises(ValueError):r.lifetimes(traces)

    def test_request_and_response_cannot_grow_like_completed_cache(self):
        for role in ('source-request','source-response','source-session'):
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'unexpected buffer growth'):r.lifetimes(lifetime(role,growth=1300))

    def test_new_nonce_cannot_hide_a_second_logical_reservation(self):
        traces=lifetime();rows=traces['node-1']['changes'];extra=copy.deepcopy(rows[1:])
        for row in extra:
            for value in row['removed']+row['added']:value['owner']=value['owner'][:-1]+'2'
        traces['node-1']=recount(rows+extra)
        with self.assertRaisesRegex(ValueError,'duplicate logical reservation'):r.lifetimes(traces)

    def test_other_control_does_not_become_source_qualification(self):
        traces=lifetime();rows=traces['node-1']['changes'];value=charge('CONTROL','export-not-qualified',32000)
        rows.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
        traces['node-1']=recount(rows);self.assertEqual(1,r.lifetimes(traces)[1])

    def test_session_binding_includes_root_trace_and_both_complete_identities(self):
        q=dict(root='a'*64,trace='00000000-0000-0000-0000-000000000001',sender=dict(node='node-2',storage='reader',host='127.0.0.1',port=12002),
               recipient=dict(node='node-1',storage='source',host='127.0.0.1',port=12001))
        original=r.binding(q)
        for parent,key in ((None,'root'),(None,'trace'),('sender','node'),('sender','storage'),('sender','host'),('sender','port'),
                           ('recipient','node'),('recipient','storage'),('recipient','host'),('recipient','port')):
            changed=copy.deepcopy(q);where=changed[parent] if parent else changed;where[key]=12003 if key=='port' else 'changed'
            with self.subTest(parent=parent,key=key):self.assertNotEqual(original,r.binding(changed))
        q.update(sequence=99,payload={'irrelevant':'one logical session'});self.assertEqual(original,r.binding(q))

    def test_original_physical_validation_precedes_resource_claims(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(r.physical,'case',side_effect=ValueError('invalid original')),patch.object(r.a,'load') as load:
            with self.assertRaisesRegex(ValueError,'invalid original'):r.case(Path(temp),'lost-offer')
            load.assert_not_called()

    def test_negative_driver_checks_original_before_mutating(self):
        from . import source_control_resource_negatives as n
        with patch.object(r,'replay',side_effect=ValueError('invalid original')),patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'invalid original'):n.replay([])
            mutate.assert_not_called()


if __name__=='__main__':unittest.main()
