import base64
import copy
import unittest
from unittest.mock import patch
from . import joining_export_request_evidence as r
from . import native_control_closes as native
from . import native_resource_evidence as accounting
from . import session_export_negatives
from .test_session_export_evidence import fixture as ownership


def packet(trace=100,sequence=1):
    from uuid import UUID
    identity=lambda n:dict(node='node-'+str(n),storage=str(UUID(int=n)),host='127.0.0.1',port=9000+n)
    value=dict(root='a'*64,view='b'*64,sender=identity(2),recipient=identity(1),
               ballot=dict(counter=2,proposer='node-2',incarnation=identity(2)['storage']),trace=str(UUID(int=trace)),
               sequence=sequence,payload=dict(id=str(UUID(int=200)),action='REQUEST',offset=0,digest='c'*64,bytes=''))
    raw=r.source.network.t.f.encode('wire','CHUNK',value)
    return base64.b64encode(raw).decode(),value,r.source.component.physical.e.digest(raw)


def fixture(role='joining-preparation-export',early=False):
    nested=role in ('joining-intent','joining-retention-export')
    traces,closes=ownership(nested=nested,early=early,shared=role=='joining-preparation-export')
    raw,q,digest=packet();binding=r.source.component.binding(q);rename={}
    for row in traces['node-1']['changes']:
        for value in row['added']:
            name=value['owner'];new=name
            if name.startswith(('source-session-','transfer-trace-')):new=name.replace('a'*64,binding)
            if name.startswith('learner-root-export-' if nested else 'record-export-'):
                new=role+'-'+digest+'-'+name[-36:]
            rename[name]=new
    for row in traces['node-1']['changes']:
        for value in row['added']+row['removed']:value['owner']=rename[value['owner']]
    for row in closes['node-1']['rows']:
        row['owner']=rename[row['owner']];row['children']=sorted(rename[n] for n in row['children'])
    owner=r.exports.close.replay(traces,closes,export_ownership=True)['owners']['node-1']
    session=next(iter(owner['exportAttachments']));meta=next(n for n in owner['lifetimes'] if n.startswith(role+'-'))
    initials={('node-1',session):dict(bytes=raw,received=owner['lifetimes'][meta]['start']-1,
                                   offered=owner['exportAttachments'][session]['resourceSequence']+1)}
    return traces,closes,initials


def rename_metadata(data,change):
    traces,closes,_=data
    names={v['owner'] for row in traces['node-1']['changes'] for v in row['added'] if r.exports.kind(v['owner']) in r.exports.REQUEST_BOUND}
    mapping={n:change(n) for n in names}
    for row in traces['node-1']['changes']:
        for value in row['added']+row['removed']:value['owner']=mapping.get(value['owner'],value['owner'])
    for row in closes['node-1']['rows']:
        row['owner']=mapping.get(row['owner'],row['owner']);row['children']=sorted(mapping.get(n,n) for n in row['children'])


class JoiningExportRequestEvidenceTest(unittest.TestCase):
    def test_all_five_families_keep_request_and_content_claims_separate(self):
        for role in r.exports.REQUEST_BOUND:
            for early in (False,True):
                with self.subTest(role=role,early=early):
                    result=r.bind(*fixture(role,early));self.assertEqual('PASS',result['status'])
                    self.assertEqual({role:1},result['families']);self.assertTrue(result['joiningExportRequestsQualified'])
                    self.assertFalse(result['allJoiningFamiliesObserved']);self.assertFalse(result['exportContentQualified'])
                    self.assertFalse(result['metadataExtentsQualified']);self.assertFalse(result['phase3Complete'])

    def test_other_request_digest_cannot_own_this_session(self):
        data=fixture();rename_metadata(data,lambda n:n.replace(packet()[2],'e'*64))
        self.assertEqual('PASS',r.exports.inspect(*data[:2])['status'])
        with self.assertRaisesRegex(ValueError,'original request digest'):r.bind(*data)

    def test_matching_digest_still_needs_the_original_route_and_trace(self):
        data=fixture();raw,_,digest=packet(trace=101);next(iter(data[2].values()))['bytes']=raw
        rename_metadata(data,lambda n:n.replace(packet()[2],digest))
        with self.assertRaisesRegex(ValueError,'original request session'):r.bind(*data)

    def test_a_later_chunk_cannot_be_the_initial_request(self):
        data=fixture();next(iter(data[2].values()))['bytes']=packet(sequence=2)[0]
        with self.assertRaisesRegex(ValueError,'original initial request'):r.bind(*data)

    def test_all_sessions_need_independently_bound_first_requests(self):
        for mode in ('missing','extra','foreign'):
            data=fixture();key=next(iter(data[2]));value=data[2][key]
            if mode=='missing':data[2].clear()
            elif mode=='extra':data[2]['node-1','fake']=value
            else:data[2]['node-2',key[1]]=data[2].pop(key)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'complete original initial requests'):r.bind(*data)

    def test_allocation_must_follow_received_request_and_precede_session(self):
        data=fixture();first=next(iter(data[2].values()));first['received']+=1
        with self.assertRaisesRegex(ValueError,'original construction interval'):r.bind(*data)

    def test_attachment_cannot_postdate_offered_response(self):
        data=fixture();next(iter(data[2].values()))['offered']-=2
        with self.assertRaisesRegex(ValueError,'original construction interval'):r.bind(*data)

    def test_boolean_negative_and_out_of_range_boundaries_are_rejected(self):
        for field in ('received','offered'):
            for value in (True,-1,999,'1'):
                data=fixture();next(iter(data[2].values()))[field]=value
                with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'original request boundaries'):r.bind(*data)

    def test_legacy_uuid_handles_keep_old_scope_without_new_request_qualification(self):
        for role in r.exports.REQUEST_BOUND:
            data=fixture(role);rename_metadata(data,lambda n:role+'-'+n[-36:])
            previous=r.exports.inspect(*data[:2]);self.assertEqual('PASS',previous['status'])
            self.assertFalse(previous['joiningExportRequestsQualified'])
            with self.assertRaisesRegex(ValueError,'legacy request binding'):r.bind(*data)

    def test_malformed_new_binding_cannot_downgrade_to_legacy(self):
        for role in r.exports.REQUEST_BOUND:
            with self.assertRaisesRegex(ValueError,'original content binding'):
                r.exports.kind(role+'-broken-'+('0'*8+'-0000-0000-0000-000000000001'))

    def test_unclaimed_probe_is_preserved_as_partial_not_dropped(self):
        data=fixture();session_export_negatives.mutate(*data[:2],'unclaimed-export')
        result=r.bind(*data);self.assertEqual('PARTIAL',result['status'])
        self.assertEqual(1,len(result['exportInventory']['unattachedExports']))

    def test_ownership_failure_precedes_request_binding(self):
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(r.source.network.t,'wire') as wire:
            with self.assertRaisesRegex(ValueError,'complete bounded recorder'):r.bind(*data)
            wire.assert_not_called()

    def test_native_original_failure_cannot_be_replaced_by_request_checks(self):
        with patch.object(native.source,'replay',side_effect=ValueError('invalid original')),patch.object(r,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'invalid original'):
                native.replay([],[],{},[],{},'a'*64,{},export_ownership=True,joining_requests=True)
            bind.assert_not_called()

    def test_required_four_and_export_opt_in_are_mandatory_at_native_entry(self):
        for options in ({'joining_requests':True},{'joining_requests':True,'export_ownership':True,'control_closes':True}):
            with self.assertRaisesRegex(ValueError,'joining requests policy'):accounting.validate('/unused',**options)

    def test_exact_negative_suite_preserves_originals_and_rejects_every_obligation(self):
        from . import joining_export_request_negatives as negatives
        for role in r.exports.REQUEST_BOUND:
            data=fixture(role);before=copy.deepcopy(data);result=negatives.replay(*data)
            self.assertEqual(len(negatives.NEGATIVES),len(result['negatives']));self.assertEqual(before,data)

    def test_invalid_original_never_counts_as_successful_negatives(self):
        from . import joining_export_request_negatives as negatives
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete bounded recorder'):negatives.replay(*data)
            mutate.assert_not_called()

    def component(self,directory):
        from pathlib import Path
        data=fixture();key,initial=next(iter(data[2].items()));node,session=key
        rows={'resources.json':data[0][node],'closes.json':data[1][node],
              'initial.json':dict(initial,session=session),
              'scope.json':dict(schema='gse-v53-joining-export-request-component-v1',node=node,
                                role='joining-preparation-export',nativeMembershipQualified=False)}
        for name,value in rows.items():(Path(directory)/name).write_bytes(r.source.network.t.f.canonical(value))

    def test_component_receipt_stays_partial_after_every_negative_passes(self):
        import tempfile
        from . import joining_export_request_negatives as negatives
        with tempfile.TemporaryDirectory() as directory:
            self.component(directory);result=negatives.validate_component(directory,qualify=True)
            self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeMembershipQualified'])
            self.assertFalse(result['allJoiningFamiliesQualified']);self.assertFalse(result['phase3Complete'])
            self.assertEqual(10,len(result['component']['negatives']))

    def test_component_inventory_and_scope_cannot_promote_or_hide_inputs(self):
        import tempfile
        from pathlib import Path
        from . import joining_export_request_negatives as negatives
        for mode in ('extra','missing','promoted'):
            with tempfile.TemporaryDirectory() as directory:
                self.component(directory);path=Path(directory)
                if mode=='extra':(path/'unexpected').write_text('extra')
                elif mode=='missing':(path/'closes.json').unlink()
                else:
                    import json
                    scope=json.loads((path/'scope.json').read_bytes());scope['nativeMembershipQualified']=True
                    (path/'scope.json').write_bytes(r.source.network.t.f.canonical(scope))
                with self.subTest(mode=mode),self.assertRaises(ValueError):negatives.validate_component(directory)

    def test_reader_does_not_change_original_inputs(self):
        data=fixture();before=copy.deepcopy(data);r.bind(*data);self.assertEqual(before,data)

    def test_source_outputs_stay_empty_when_original_is_rejected(self):
        bindings={};initials={}
        with self.assertRaisesRegex(ValueError,'required original bindings absent'):
            r.source.replay([],[],{},[],{},'a'*64,bindings=bindings,initials=initials)
        self.assertEqual({},bindings);self.assertEqual({},initials)
