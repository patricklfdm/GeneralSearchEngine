"""Original charge/route separation and complete session coverage regressions."""
import base64
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import session_content_extents as r
from . import native_control_closes as native
from . import native_resource_evidence as entry
from .test_joining_export_request_evidence import fixture as requests,packet
from .test_joining_metadata_extents import fixture as metadata_fixture,frame
from .direct_export_negatives import recount


def fixture(role='record-export',early=False):
    nested=role in ('joining-retention-export','joining-intent','learner-root-export')
    original_role=role if role in r.exports.REQUEST_BOUND else 'joining-intent' if nested else 'joining-preparation-export'
    traces,closes,initials,old=metadata_fixture(original_role,early)
    initial=next(iter(initials.values()));key=r.sha(r.metadata.decoded(initial['bytes']));previous=old[key]
    binding=key if role in r.exports.REQUEST_BOUND else 'd'*64
    size=previous['bytes'] if role in r.exports.REQUEST_BOUND else 4096 if role=='prefix-export' else 1234
    charges=[r.charge(role,binding,size)]
    if nested:charges.append(r.charge('prefix-export',previous['prefixSha256'],4096))
    rename={}
    for row in traces['node-1']['changes']:
        for value in row['added']:
            name=value['owner']
            if r.exports.kind(name)==original_role:rename[name]=role+'-'+binding+'-'+name[-36:]
    for row in traces['node-1']['changes']:
        for value in row['added']+row['removed']:
            if value['owner'] in rename:value.update(owner=rename[value['owner']],bytes=size)
    for row in closes['node-1']['rows']:
        row['owner']=rename.get(row['owner'],row['owner']);row['children']=sorted(rename.get(n,n) for n in row['children'])
    recount(traces['node-1'])
    account=r.exports.close.replay(traces,closes,export_ownership=True)['owners']['node-1']
    attachment=next(iter(account['exportAttachments'].values()))
    initial['received']=min(account['lifetimes'][n]['start'] for n in attachment['children'])-1
    return traces,closes,initials,{key:dict(node='node-1',request=initial['bytes'],charges=sorted(charges,key=lambda v:v['role']))}


def changed_charge(data,role,*,binding=None,delta=0):
    traces,closes,*_=data;mapping={}
    for trace in traces.values():
        for row in trace['changes']:
            for value in row['added']+row['removed']:
                name=value['owner']
                if r.exports.kind(name)!=role:continue
                if binding is not None:mapping[name]=role+'-'+binding+'-'+name[-36:];value['owner']=mapping[name]
                value['bytes']+=delta
        recount(trace)
    for value in closes.values():
        for row in value['rows']:
            row['owner']=mapping.get(row['owner'],row['owner']);row['children']=sorted(mapping.get(n,n) for n in row['children'])


class SessionContentExtentsTest(unittest.TestCase):
    def test_all_ten_families_bind_successful_session_and_exact_owned_group(self):
        for role in r.exports.ROLES:
            for early in (False,True):
                data=fixture(role,early);before=copy.deepcopy(data);result=r.bind(*data)
                with self.subTest(role=role,early=early):
                    self.assertEqual('PASS',result['status']);self.assertEqual({role:1},result['families'])
                    self.assertEqual(len(next(iter(data[3].values()))['charges']),result['ownedAllocations'])
                    self.assertTrue(result['allObservedSessionContentExtentsQualified']);self.assertFalse(result['allExportFamiliesQualified'])
                    self.assertFalse(result['wholeRuntimeResourcesQualified']);self.assertFalse(result['phase3Complete']);self.assertEqual(before,data)

    def test_each_extent_is_checked_even_when_all_accounting_totals_are_consistent(self):
        for role in r.exports.ROLES:
            data=fixture(role);changed_charge(data,role,delta=1)
            self.assertEqual('PASS',r.exports.inspect(*data[:2])['status'])
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'original reservation extent'):r.bind(*data)

    def test_each_content_binding_is_independent_of_the_observed_handle(self):
        for role in r.exports.ROLES:
            data=fixture(role);changed_charge(data,role,binding='f'*64)
            self.assertEqual('PASS',r.exports.inspect(*data[:2])['status'])
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'original content binding'):r.bind(*data)

    def test_root_and_joining_nested_prefix_extents_and_generations_are_independent(self):
        for role in ('learner-root-export','joining-intent','joining-retention-export'):
            for fault in ('binding','size'):
                data=fixture(role);changed_charge(data,'prefix-export',binding='f'*64 if fault=='binding' else None,delta=int(fault=='size'))
                with self.subTest(role=role,fault=fault),self.assertRaisesRegex(ValueError,'original content binding|original reservation extent'):r.bind(*data)

    def test_no_session_can_be_omitted_or_replaced_with_unrelated_content(self):
        for fault in ('missing-initial','missing-plan','extra-plan','foreign-plan'):
            data=fixture();key=next(iter(data[3]))
            if fault=='missing-initial':data[2].clear()
            elif fault=='missing-plan':data[3].clear()
            elif fault=='extra-plan':data[3]['f'*64]=copy.deepcopy(data[3][key])
            else:data[3]['f'*64]=data[3].pop(key)
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'complete original sessions|complete original content'):r.bind(*data)

    def test_original_frame_requires_exact_node_session_sequence_and_payload(self):
        for fault in ('route','trace','sequence','offset','bytes'):
            data=fixture();initial=next(iter(data[2].values()));_,q=r.metadata.requests.source.network.t.wire(initial['bytes'])
            if fault=='route':q['recipient']=q['sender']
            elif fault=='trace':q['trace']='00000000-0000-0000-0000-000000000099'
            elif fault=='sequence':q['sequence']=2
            elif fault=='offset':q['payload']['offset']=1
            else:q['payload']['bytes']='eA=='
            initial['bytes']=base64.b64encode(r.f.encode('wire','CHUNK',q)).decode()
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original request session'):r.bind(*data)

    def test_construction_stays_inside_original_request_before_session_attachment(self):
        for fault in ('before','after','boolean','negative','range'):
            data=fixture();initial=next(iter(data[2].values()))
            if fault=='before':initial['received']+=1
            elif fault=='after':initial['offered']-=2
            elif fault=='boolean':initial['received']=False
            elif fault=='negative':initial['received']=-1
            else:initial['offered']=999
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original construction interval|original request boundaries'):r.bind(*data)

    def test_original_expectation_shapes_do_not_accept_booleans_or_extra_fields(self):
        for fault in ('node','request','field','role','size','binding','duplicate','order'):
            data=fixture('learner-root-export');plan=next(iter(data[3].values()));charge=plan['charges'][0]
            if fault=='node':plan['node']='node-2'
            elif fault=='request':plan['request']=packet(trace=999)[0]
            elif fault=='field':charge['ignored']=1
            elif fault=='role':charge['role']=[]
            elif fault=='size':charge['bytes']=True
            elif fault=='binding':charge['binding']='f'*63
            elif fault=='duplicate':plan['charges'][1]=copy.deepcopy(charge)
            else:plan['charges'].reverse()
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original expectation|charge expectation|charge group'):r.bind(*data)

    def test_wrong_but_well_formed_export_family_is_not_authorized(self):
        data=fixture('vote-export');next(iter(data[3].values()))['charges'][0]['role']='record-export'
        with self.assertRaisesRegex(ValueError,'exact original export group'):r.bind(*data)

    def test_invalid_original_observations_precede_extent_comparison(self):
        data=fixture();data[1]['node-1']['failed']=True
        with self.assertRaisesRegex(ValueError,'complete bounded recorder'):r.bind(*data)

    def test_missing_other_export_stays_partial_despite_correct_session_extents(self):
        from .test_transport_resource_evidence import recount as rebuild
        data=fixture();rows=data[0]['node-1']['changes']
        extra=dict(unit='CONTROL',owner='prefix-export-'+'f'*64+'-00000000-0000-0000-0000-000000000099',bytes=4096,claimSource='')
        rows.extend([dict(event='RESERVE',added=[extra],removed=[]),dict(event='RELEASE',added=[],removed=[extra])]);data[0]['node-1']=rebuild(rows)
        result=r.bind(*data)
        self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['wholeRuntimeResourcesQualified'])
        self.assertEqual(1,len(result['exportInventory']['unattachedExports']))

    def test_native_entry_requires_whole_original_admission_before_derivation(self):
        for options in ({},{'export_ownership':True},{'export_ownership':True,'control_closes':True}):
            with self.subTest(options=options),self.assertRaisesRegex(ValueError,'session extents policy'):
                entry.validate('/unused',session_extents=True,**options)
        with patch.object(entry.collection,'inventory',return_value={}),patch.object(entry.Path,'is_dir',return_value=True), \
             patch.object(entry.publication,'validate',side_effect=ValueError('invalid original')),patch.object(r,'derive') as derive:
            with self.assertRaisesRegex(ValueError,'invalid original'):
                entry.validate('/unused','5-REPLACE-required-four',session_extents=True,control_closes=True,export_ownership=True)
            derive.assert_not_called()

    def test_native_close_requires_source_binding_before_content_binding(self):
        with patch.object(native.source,'replay',side_effect=ValueError('invalid source')),patch.object(r,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'invalid source'):
                native.replay([],[],{},[],{},'a'*64,{},export_ownership=True,session_extents={'original':{}})
            bind.assert_not_called()

    def test_native_close_collects_exact_initials_even_without_joining_request_option(self):
        data=fixture();captured={}
        def original(*args,bindings,initials):
            self.assertIsNotNone(initials);initials.update(data[2]);captured.update(initials);return dict(status='PASS')
        with patch.object(native.source,'replay',side_effect=original),patch.object(native,'bind',return_value=dict(status='PASS')):
            result=native.replay([],[],data[0],[],{},'a'*64,data[1],export_ownership=True,session_extents=data[3])
        self.assertEqual(data[2],captured);self.assertEqual('PASS',result['sessionContentExtents']['status'])

    def test_derivation_uses_original_basis_and_promise_lengths(self):
        from . import test_joining_export_evidence as fixtures
        f=fixtures.JoiningExportEvidenceTest();windows,q,source,values=f.source()
        source['basis']=frame('BASIS');source['promise']=frame('PROMISE');values[0]['raw']=source['basis']
        _,initial,_=packet();values[0]['offer']['request']=initial
        initial['payload']['digest']=r.sha(source['basis'])
        values[0]['offer']['requestHash']=r.sha(r.f.encode('wire','CHUNK',initial))
        reader=SimpleNamespace(groups=[values],model=None,windows=windows,sources=[source])
        with patch.object(r.e,'pending_ack',return_value=b'pending'),patch.object(r.e,'authorize_source',return_value=source):
            plan=next(iter(r.derive(reader).values()))
        self.assertEqual([r.charge('source-export',r.sha(source['basis']),len(source['basis'])+len(source['promise']))],plan['charges'])

    def test_vote_receipt_uses_original_alias_while_record_uses_content_digest(self):
        raw=frame('CHECKPOINT');encoded,q,binding=packet();q['payload']['digest']='e'*64
        group=[dict(raw=raw,kind='RECORD',offer=dict(request=q,requestHash=r.sha(r.f.encode('wire','CHUNK',q))))]
        reader=SimpleNamespace(groups=[group],model=None,windows=[],records=[])
        for family,role,expected in (('native-vote-receipt','vote-export','e'*64),('published-record','record-export',r.sha(raw))):
            with patch.object(r.e,'pending_ack',return_value=b'pending'),patch.object(r.e,'authorize_record',return_value=family):
                plan=next(iter(r.derive(reader).values()))
            self.assertEqual([r.charge(role,expected,len(raw))],plan['charges'])

    def test_duplicate_initial_content_and_incomplete_metadata_sessions_are_refused(self):
        from .test_joining_metadata_extents import content
        raw=content('joining-preparation-export');encoded,q,binding=packet()
        group=[dict(raw=raw,kind='RECORD',offer=dict(request=q,requestHash=binding))]
        for groups,reason in (([group,group],'unique original initial request'),([group+group],'singleton metadata export')):
            reader=SimpleNamespace(groups=groups,model=None)
            with patch.object(r.e,'pending_ack',return_value=b'pending'),self.assertRaisesRegex(ValueError,reason):r.derive(reader)


if __name__=='__main__':unittest.main()
