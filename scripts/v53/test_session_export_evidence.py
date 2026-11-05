import copy
import unittest
from unittest.mock import patch
from . import session_export_evidence as r
from . import session_export_negatives as negatives
from .test_resource_transitions import charge
from .test_transport_resource_evidence import recount


def fixture(early=False,nested=False,shared=False):
    nonce='00000000-0000-0000-0000-000000000001';binding='a'*64
    service='transfer-service-'+nonce;trace='transfer-trace-'+binding+'-'+nonce
    session='source-session-'+binding+'-'+nonce;response='source-response-'+'b'*64+'-'+nonce
    names=['prefix-export-'+binding+'-'+nonce] if nested else ['record-export-'+binding+'-'+nonce]
    if nested:names+=['learner-root-export-'+binding+'-'+nonce]
    publication='joining-preparation-publication-'+nonce
    changes=[dict(event='START',added=[],removed=[])];rows=[];calls={}
    def change(event,name):changes.append(dict(event=event,added=[charge('CONTROL',name,1024)] if event=='RESERVE' else [],
                                               removed=[charge('CONTROL',name,1024)] if event=='RELEASE' else []))
    def mark(event,name,children=()):
        seq=len(rows)
        if event=='BEGIN':calls[name]=seq
        rows.append(dict(sequence=seq,event=event,call=seq if event=='ATTACHED' else calls[name],
                         resourceSequence=len(changes)-1,owner=name,children=sorted(children)))
    change('RESERVE',service);change('RESERVE',trace)
    if shared:change('RESERVE',publication)
    for name in names:change('RESERVE',name)
    change('RESERVE',session)
    if early:
        for name in names:change('RELEASE',name)
    mark('ATTACHED',session,names);change('RESERVE',response)
    mark('BEGIN',service,[trace]);mark('BEGIN',trace,[session]);mark('BEGIN',session,[response])
    change('RELEASE',response);change('RELEASE',session)
    if not early:
        for name in names:change('RELEASE',name)
    mark('RETURNED',session);change('RELEASE',trace);mark('RETURNED',trace)
    if shared:change('RELEASE',publication)
    change('RELEASE',service);mark('RETURNED',service)
    return {'node-1':recount(changes)},{'node-1':dict(schema='gse-v53-control-close-observations-v1',maximum=65536,
        observations=len(rows),failed=False,truncated=False,rows=rows)}


class SessionExportEvidenceTest(unittest.TestCase):
    def test_original_late_release_and_early_revocation_have_distinct_valid_orders(self):
        for early in (False,True):
            for nested in (False,True):
                result=r.replay(*fixture(early,nested));self.assertEqual(1,result['sessions'])
                self.assertEqual(2 if nested else 1,result['ownedAllocations'])
                self.assertEqual((2 if nested else 1) if early else 0,result['revokedBeforeAttachment'])
                self.assertFalse(result['phase3Complete']);self.assertFalse(result['exportContentExtentsQualified'])

    def test_all_annotation_negatives_reject_for_their_named_obligation(self):
        for early in (False,True):
            self.assertEqual(len(negatives.NEGATIVES),len(negatives.replay(*fixture(early))))

    def test_export_may_outlive_session_metadata_but_not_close_return(self):
        data=fixture();rows=data[1]['node-1']['rows'];end=next(v for v in rows if v['event']=='RETURNED' and v['owner'].startswith('source-session-'))
        self.assertEqual('PASS',r.replay(*data)['status']);end['resourceSequence']-=1
        with self.assertRaisesRegex(ValueError,'export release before normal return'):r.replay(*data)

    def test_missing_nested_metadata_cannot_be_promoted_to_plain_prefix(self):
        data=fixture(nested=True);attached=data[1]['node-1']['rows'][0]
        attached['children']=[v for v in attached['children'] if v.startswith('prefix-export-')]
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.replay(*data)
        result=r.inspect(*data);self.assertEqual('PARTIAL',result['status'])
        self.assertFalse(result['completeExportAllocationInventory']);self.assertEqual(1,len(result['unattachedExports']))

    def test_metadata_without_its_nested_borrow_is_not_complete(self):
        data=fixture(nested=True);attached=data[1]['node-1']['rows'][0]
        attached['children']=[v for v in attached['children'] if v.startswith('learner-root-export-')]
        with self.assertRaisesRegex(ValueError,'exact owned group'):r.replay(*data)

    def test_shared_publication_is_never_owned_by_a_session(self):
        data=fixture(shared=True);self.assertEqual('PASS',r.replay(*data)['status'])
        data[1]['node-1']['rows'][0]['children']=[next(name for name in r.close.allocations(data[0]['node-1']) if name.startswith('joining-preparation-publication-'))]
        with self.assertRaisesRegex(ValueError,'exact owned group'):r.replay(*data)

    def test_attachment_after_close_begins_is_rejected(self):
        data=fixture();value=data[1]['node-1'];rows=value['rows'];attachment=rows.pop(0);rows.insert(3,attachment)
        attachment['resourceSequence']=rows[2]['resourceSequence'];negatives.renumber(value)
        with self.assertRaisesRegex(ValueError,'original export attachment'):r.replay(*data)

    def test_opt_in_is_explicit_and_old_captures_cannot_claim_it(self):
        data=fixture()
        with self.assertRaisesRegex(ValueError,'original export attachment'):r.close.replay(*data)
        data[1]['node-1']['rows'].pop(0);negatives.renumber(data[1]['node-1'])
        self.assertEqual('PASS',r.close.replay(*data)['status'])
        with self.assertRaisesRegex(ValueError,'complete export attachments'):r.replay(*data)

    def test_original_failure_cannot_be_counted_as_mutation_rejection(self):
        with patch.object(r,'replay',side_effect=ValueError('original failed')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'original failed'):negatives.replay(*fixture())
            mutate.assert_not_called()

    def test_content_bound_names_cannot_downgrade_to_legacy_uuid(self):
        with self.assertRaisesRegex(ValueError,'original content binding'):r.kind('record-export-00000000-0000-0000-0000-000000000001')

    def test_mutations_leave_original_evidence_unchanged(self):
        data=fixture(nested=True);before=copy.deepcopy(data);negatives.replay(*data);self.assertEqual(before,data)

    def test_inspection_keeps_unattached_scope_explicit_and_cannot_accept_more(self):
        data=fixture();negatives.mutate(*data,'unclaimed-export')
        self.assertEqual('PARTIAL',r.inspect(*data)['status'])
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.replay(*data)
        self.assertEqual(len(negatives.NEGATIVES),len(negatives.replay(*data,inspect=True)))

    def test_native_close_binding_propagates_partial_export_inventory(self):
        from . import native_control_closes
        data=fixture();negatives.mutate(*data,'unclaimed-export')
        names=r.close.allocations(data[0]['node-1'])
        key=lambda prefix:('node-1',next(n for n in names if n.startswith(prefix+'-')))
        bindings={key('source-response'):(key('source-session'),key('transfer-trace'))}
        result=native_control_closes.bind(*data,bindings,export_ownership=True)
        self.assertEqual('PARTIAL',result['status']);self.assertEqual('PARTIAL',result['exportOwnership']['status'])

    def test_zero_export_identity_is_not_a_real_allocation(self):
        with self.assertRaisesRegex(ValueError,'original allocation identity'):
            r.kind('joining-preparation-export-00000000-0000-0000-0000-000000000000')

    def test_native_physical_failure_precedes_ownership_mutations(self):
        with patch.object(negatives.native.collection,'inventory',return_value={}), \
             patch.object(negatives.native,'validate',side_effect=ValueError('bad native original')),patch.object(negatives,'replay') as mutate:
            with self.assertRaisesRegex(ValueError,'bad native original'):negatives.validate('/unused')
            mutate.assert_not_called()


if __name__=='__main__':unittest.main()
