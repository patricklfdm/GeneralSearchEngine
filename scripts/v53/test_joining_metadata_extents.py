"""Synthetic accounting checks; actual conditional captures are retained separately."""
import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joining_metadata_extents as r
from . import native_resource_evidence as native
from . import native_control_closes as closes
from . import direct_export_negatives as charge_tools
from .test_joining_export_request_evidence import fixture as requests_fixture


def frame(kind,**updates):
    catalog=r.f.catalog();value=r.f.sample(catalog['records'][kind]['schema'],catalog['types']);value.update(updates)
    return r.f.encode('records',kind,value)


def content(role):
    if role=='joining-checkpoint-export':return frame('CHECKPOINT_ACK')
    if role=='joining-retention-export':body=dict(basis={},envelope={},peers=[],learner={})
    elif role=='joining-preparation-export':body=dict(schema='gse-v53-joining-preparation-hint/1.3',root='a'*64,cut={},joining={},ballot={},sources=[])
    elif role=='joining-completion-export':body=dict(schema='gse-v53-joining-completion/1.3',root='a'*64,cut={},joining={})
    else:body=dict(schema='gse-v53-joining-intent-metadata/1.3',root='a'*64,owner={},learner={},request={},parent={},target={},
                   records={name:base64.b64encode(frame(name)).decode() for name in r.INTENT_RECORDS},payload=base64.b64encode(b'original INTENT payload').decode())
    return r.f.canonical(body)


def fixture(role='joining-preparation-export',early=False):
    traces,closes,initials=requests_fixture(role,early);initial=next(iter(initials.values()));raw=content(role)
    nested=role in ('joining-retention-export','joining-intent');manifest=frame('GENERATION',node='node-1',root='a'*64) if nested else None
    plan=r.expectation(initial['bytes'],raw,pending_ack=raw if role=='joining-checkpoint-export' else None,manifest=manifest)
    if nested:
        names={v['owner'] for row in traces['node-1']['changes'] for v in row['added'] if v['owner'].startswith('prefix-export-')}
        rename={name:'prefix-export-'+r.sha(manifest)+'-'+name[-36:] for name in names}
        for row in traces['node-1']['changes']:
            for v in row['added']+row['removed']:v['owner']=rename.get(v['owner'],v['owner'])
        for row in closes['node-1']['rows']:row['children']=sorted(rename.get(n,n) for n in row['children'])
    for row in traces['node-1']['changes']:
        for charge in row['added']+row['removed']:
            if charge['owner'].startswith(role+'-'):charge['bytes']=plan['bytes']
            elif charge['owner'].startswith('prefix-export-'):charge['bytes']=4096
    charge_tools.recount(traces['node-1'])
    return traces,closes,initials,{r.sha(r.decoded(initial['bytes'])):plan}


def resize(traces,role):
    for trace in traces.values():
        for row in trace['changes']:
            for v in row['added']+row['removed']:
                if v['owner'].startswith(role+'-'):v['bytes']+=1
        charge_tools.recount(trace)


class JoiningMetadataExtentsTest(unittest.TestCase):
    def test_all_five_extents_preserve_scope_and_early_release(self):
        for role in r.exports.REQUEST_BOUND:
            for early in (False,True):
                with self.subTest(role=role,early=early):
                    result=r.bind(*fixture(role,early));self.assertEqual('PASS',result['status'])
                    self.assertEqual({role:1},result['families']);self.assertTrue(result['metadataExtentsQualified'])
                    self.assertFalse(result['nativeContentAuthorityQualified']);self.assertFalse(result['wholeRuntimeResourcesQualified'])
                    self.assertFalse(result['phase3Complete']);self.assertFalse(result['allJoiningFamiliesObserved'])

    def test_intent_counts_original_frames_and_payload_not_encoded_container(self):
        raw=content('joining-intent');body=json.loads(raw)
        size=65536+4*(len(r.decoded(body['payload']))+sum(len(r.decoded(v)) for v in body['records'].values()))
        self.assertEqual(('joining-intent',size),r.classify(raw));self.assertNotEqual(len(raw),size)
        body['payload']=base64.b64encode(r.decoded(body['payload'])+b'!').decode()
        self.assertEqual(size+4,r.classify(r.f.canonical(body))[1])

    def test_intent_requires_exact_original_records_and_canonical_encoding(self):
        raw=content('joining-intent')
        for fault in ('missing','wrong-kind','base64','extra','noncanonical'):
            body=json.loads(raw)
            if fault=='missing':body['records'].pop('ENTRY')
            elif fault=='wrong-kind':body['records']['ENTRY']=body['records']['ACCEPT']
            elif fault=='base64':body['payload']='%%%%'
            elif fault=='extra':body['ignored']=1
            value=json.dumps(body).encode() if fault=='noncanonical' else r.f.canonical(body)
            with self.subTest(fault=fault),self.assertRaises(ValueError):r.classify(value)

    def test_intent_keeps_eight_mib_frame_bound_separate_from_four_mib_chunks(self):
        body=json.loads(content('joining-intent'));body['payload']=base64.b64encode(b'x'*(3*1024*1024)).decode()
        raw=r.f.canonical(body);self.assertGreater(len(raw),4*1024*1024);self.assertLess(len(raw),8*1024*1024)
        self.assertEqual('joining-intent',r.classify(raw)[0])

    def test_hint_and_fragment_limits_are_original_limits(self):
        for role,limit in (('joining-retention-export',2*1024*1024),('joining-preparation-export',16384),('joining-completion-export',16384)):
            body=json.loads(content(role));key='basis' if role=='joining-retention-export' else 'root';body[key]='x'*limit
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'extent'):r.classify(r.f.canonical(body))

    def test_ack_requires_exact_admitted_pending_original(self):
        raw=content('joining-checkpoint-export');self.assertIsNone(r.classify(raw))
        self.assertEqual(('joining-checkpoint-export',len(raw)),r.classify(raw,raw))
        with self.assertRaises(ValueError):r.classify(b'corrupt',b'corrupt')

    def test_every_metadata_extent_is_checked_even_with_consistent_totals(self):
        for role in r.exports.REQUEST_BOUND:
            data=fixture(role);resize(data[0],role)
            self.assertEqual('PASS',r.requests.bind(*data[:3])['status'])
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'reservation extent'):r.bind(*data)

    def test_original_nested_generation_and_its_own_size_are_required(self):
        for fault in ('digest','size','missing'):
            data=fixture('joining-intent');plan=next(iter(data[3].values()))
            if fault=='digest':plan['prefixSha256']='e'*64
            elif fault=='size':resize(data[0],'prefix-export')
            else:plan['prefixSha256']=None
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'(nested generation|prefix extent|prefix expectation)'):r.bind(*data)

    def test_matching_extent_cannot_replace_request_identity_or_role(self):
        for fault in ('request','role','node','bool','extra'):
            data=fixture();key=next(iter(data[3]));plan=data[3][key]
            if fault=='request':data[3]['e'*64]=data[3].pop(key)
            elif fault=='role':plan['role']='joining-completion-export'
            elif fault=='node':plan['node']='node-2'
            elif fault=='bool':plan['bytes']=True
            else:data[3]['e'*64]=copy.deepcopy(plan)
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'(expectation shape|complete original expectations)'):r.bind(*data)

    def test_invalid_owner_original_precedes_extent_checks(self):
        data=fixture();data[1]['node-1']['failed']=True
        with self.assertRaisesRegex(ValueError,'complete bounded recorder'):r.bind(*data)

    def test_missing_unobserved_export_remains_partial(self):
        from . import session_export_negatives
        data=fixture();session_export_negatives.mutate(*data[:2],'unclaimed-export')
        result=r.bind(*data);self.assertEqual('PARTIAL',result['status'])

    def test_native_entry_requires_original_joining_mode_and_full_prerequisites(self):
        for flags in ({'joining_extents':True},{'joining_extents':True,'joining_requests':True}):
            with self.subTest(flags=flags),self.assertRaisesRegex(ValueError,'policy'):native.validate('/unused',**flags)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'control-close-captures').mkdir()
            with patch.object(native.publication,'validate',side_effect=ValueError('invalid original')),patch.object(r,'derive') as derive:
                with self.assertRaisesRegex(ValueError,'invalid original'):
                    native.validate(directory,'5-REPLACE-required-four',control_closes=True,export_ownership=True,joining_requests=True,joining_extents=True)
                derive.assert_not_called()
            from . import required_four_ledgers
            with patch.object(native.publication,'validate',return_value={}),patch.object(required_four_ledgers,'validate',side_effect=ValueError('invalid capability')),patch.object(r,'derive') as derive:
                with self.assertRaisesRegex(ValueError,'invalid capability'):
                    native.validate(directory,'5-REPLACE-required-four',control_closes=True,export_ownership=True,joining_requests=True,joining_extents=True)
                derive.assert_not_called()

    def test_native_source_failure_cannot_be_replaced_with_extent_results(self):
        with patch.object(closes.source,'replay',side_effect=ValueError('invalid source')),patch.object(r,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'invalid source'):
                closes.replay([],[],{},[],{},'a'*64,{},export_ownership=True,joining_requests=True,joining_extents={'expected':1})
            bind.assert_not_called()

    def test_derive_uses_original_request_and_generation_windows(self):
        data=fixture('joining-intent');initial=next(iter(data[2].values()));_,q=r.requests.source.network.t.wire(initial['bytes'])
        raw=content('joining-intent');manifest=frame('GENERATION',node='node-1',root='a'*64)
        group=[dict(raw=raw,kind='RECORD',offer=dict(request=q,requestHash=r.sha(r.decoded(initial['bytes'])),received=3),commit=dict(offered=5))]
        reader=SimpleNamespace(model=object(),groups=[group],windows=[dict(node='node-1',start=0,end=10,manifest=manifest)])
        with patch.object(r.control.e,'pending_ack',return_value=frame('CHECKPOINT_ACK')):
            self.assertEqual(data[3],r.derive(reader))
            for fault in ('request','window','duplicate'):
                changed=copy.deepcopy(reader)
                if fault=='request':changed.groups[0][0]['offer']['requestHash']='e'*64
                elif fault=='window':changed.windows[0]['end']=5
                else:changed.groups*=2
                with self.subTest(fault=fault),self.assertRaises(ValueError):r.derive(changed)

    def write_component(self,directory,role):
        data=fixture(role);key,initial=next(iter(data[2].items()));root=Path(directory)
        values={'scope.json':dict(schema='gse-v53-joining-export-request-component-v1',node=key[0],role=role,nativeMembershipQualified=False),
                'initial.json':dict(initial,session=key[1]),'resources.json':data[0][key[0]],'closes.json':data[1][key[0]]}
        for name,value in values.items():(root/name).write_bytes(r.f.canonical(value))
        (root/'content.bin').write_bytes(content(role))
        if role=='joining-retention-export':(root/'generation.gsr').write_bytes(frame('GENERATION',node='node-1',root='a'*64))

    def test_component_is_partial_and_inventory_is_exact(self):
        for role in ('joining-retention-export','joining-preparation-export'):
            with tempfile.TemporaryDirectory() as directory:
                self.write_component(directory,role);result=r.validate_component(directory)
                self.assertEqual('PARTIAL',result['status']);self.assertEqual('PASS',result['component']['status'])
                self.assertFalse(result['nativeMembershipQualified']);self.assertFalse(result['phase3Complete'])
                (Path(directory)/'extra').write_bytes(b'x')
                with self.assertRaisesRegex(ValueError,'exact component inventory'):r.validate_component(directory)

    def test_originals_are_unchanged(self):
        data=fixture('joining-intent');before=copy.deepcopy(data);r.bind(*data);self.assertEqual(before,data)

    def test_exact_negatives_for_all_families_preserve_originals(self):
        for role in r.exports.REQUEST_BOUND:
            data=fixture(role);before=copy.deepcopy(data);result=r.qualify(*data)
            with self.subTest(role=role):
                self.assertEqual(9 if role in ('joining-retention-export','joining-intent') else 7,len(result['negatives']))
                self.assertEqual(before,data)

    def test_invalid_original_is_not_negative_qualification(self):
        data=fixture();resize(data[0],'joining-preparation-export')
        with patch.object(r.copy,'deepcopy') as clone:
            with self.assertRaisesRegex(ValueError,'original reservation extent'):r.qualify(*data)
            clone.assert_not_called()


if __name__=='__main__':unittest.main()
