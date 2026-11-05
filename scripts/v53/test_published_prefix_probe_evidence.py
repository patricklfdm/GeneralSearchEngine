"""Synthetic original-call bindings; no full native execution claim."""
import base64
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import published_prefix_probe_evidence as r
from . import native_resource_evidence as native
from . import test_joining_control_evidence as authority_fixture
from .test_joining_metadata_extents import frame
from .test_probe_export_evidence import fixture as ownership
from .direct_export_negatives import renumber


def inputs():
    own,joining,request,values=authority_fixture.JoiningControlEvidenceTest().inputs();c=r.control;state=c.catalog(own)
    prepared=c.f.sample('prepared',c.f.catalog()['types']);prepared['cut']=copy.deepcopy(state['cut'])
    state['cut']['view'].update(operation='e'*64,new=[v['node'] for v in state['identities']]);state['cut']['index']=9
    state['results'][0].update(phase='JOINT',prepared=prepared)
    raw=c.f.encode('records','CATALOG',state);own['packet']['objects'][c.sha(raw)]=raw
    own['packet']['capsule'].update(catalog=c.sha(raw),cut=state['cut'])
    own['manifest']=frame('GENERATION',root=state['root'],node=own['node'])
    alias=c.sha(c.f.canonical(dict(schema='gse-v53-learner-progress-reference/1.3',root=state['root'],learner=joining,
                                 request=request,cut=state['cut'],scope='prefix')))
    q=values[0]['offer']['request'];q['trace']='00000000-0000-0000-0000-000000000010'
    q['payload'].update(id='00000000-0000-0000-0000-000000000011',digest=alias)
    raw=c.f.encode('wire','CHUNK',q);binding=c.sha(raw)
    events=[dict(node=own['node'],event='other')]
    events.extend([dict(node=own['node'],event=r.EVENTS[0],request=binding,bytes=base64.b64encode(raw).decode()),
                   dict(node=own['node'],event=r.EVENTS[1],request=binding,contents=r.references(own,alias)),
                   dict(node=own['node'],event=r.EVENTS[2],request=binding)])
    selected=frame('SELECTED',ballot=dict(counter=3,proposer=own['node'],incarnation=own['identity']['storage']))
    reader=c.Replay.__new__(c.Replay);reader.events=events;reader.windows=[own]
    reader.model=SimpleNamespace(root=state['root'],joining=joining['node'],states=[None]*9+[state],phases=[{}]*8+[dict(SELECTED=selected)])
    reader.confirmations={own['node']:dict(start=0,end=10,request=request,learner=joining)}
    bounds=[dict(eventIndex=i,node=own['node'],sequence=i,usage={}) for i in range(4)]
    return reader,bounds


def rewrite(reader,change):
    row=reader.events[1];_,q=r.transcript.wire(row['bytes']);change(q)
    raw=r.f.encode('wire','CHUNK',q);row['bytes']=base64.b64encode(raw).decode()
    for value in reader.events[1:]:value['request']=r.sha(raw)


class PublishedPrefixProbeTest(unittest.TestCase):
    def test_actual_proposer_original_manifest_and_alias_determine_expectation(self):
        reader,bounds=inputs();before=copy.deepcopy((reader.events,reader.windows,bounds));plan=r.derive(reader,bounds)
        self.assertEqual('node-2',plan[0]['node']);self.assertEqual(r.sha(reader.windows[0]['manifest']),plan[0]['binding'])
        self.assertEqual((4096,1,2,3),(plan[0]['bytes'],plan[0]['before'],plan[0]['through'],plan[0]['after']))
        self.assertEqual(before,(reader.events,reader.windows,bounds))

    def test_exact_original_inventory_includes_packet_alias_and_image_but_not_other_records(self):
        reader,_=inputs();items=reader.events[2]['contents']
        self.assertEqual(['APPLICATION','CAPSULE','CAPSULE'],sorted(v['kind'] for v in items))
        self.assertEqual(2,len({v['digest'] for v in items}));self.assertEqual(3,len({v['reference'] for v in items}))

    def test_missing_reordered_extra_or_backfilled_marker_is_rejected(self):
        for fault in ('missing','order','extra','fields'):
            reader,bounds=inputs()
            if fault=='missing':reader.events[3]['event']='other'
            elif fault=='order':reader.events[1],reader.events[2]=reader.events[2],reader.events[1]
            elif fault=='extra':reader.events.append(copy.deepcopy(reader.events[3]));bounds.append(bounds[-1])
            else:reader.events[3]['invented']=True
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original observations|observation shape'):r.derive(reader,bounds)

    def test_request_bytes_digest_and_each_original_correlation_are_required(self):
        for field in ('node','request'):
            reader,bounds=inputs();reader.events[2][field]='foreign'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'exact original call'):r.derive(reader,bounds)
        reader,bounds=inputs();reader.events[1]['bytes']='invalid'
        with self.assertRaises(ValueError):r.derive(reader,bounds)

    def test_only_original_initial_prefix_request_is_admitted(self):
        for change,reason in ((lambda q:q.update(sequence=2),'initial request'),
                              (lambda q:q['payload'].update(offset=1),'initial request'),
                              (lambda q:q['payload'].update(digest='f'*64),'progress prefix alias'),
                              (lambda q:q.update(view='f'*64),'original correlation'),
                              (lambda q:q['ballot'].update(counter=2),'original correlation')):
            reader,bounds=inputs();rewrite(reader,change)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):r.derive(reader,bounds)

    def test_foreign_learner_owner_root_or_cut_cannot_borrow_valid_permission(self):
        for fault in ('learner','owner','root','cut'):
            reader,bounds=inputs()
            if fault=='cut':reader.model.states[9]=dict(reader.model.states[9],cut={})
            else:
                def change(q):
                    if fault=='root':q['root']='f'*64
                    elif fault=='learner':q['sender']=copy.deepcopy(q['recipient'])
                    else:q['recipient']=copy.deepcopy(q['sender'])
                rewrite(reader,change)
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'original joint owner and learner'):r.derive(reader,bounds)

    def test_actual_generation_must_span_entire_call(self):
        for start,end in ((1,100),(0,3)):
            reader,bounds=inputs();reader.windows[0].update(start=start,end=end)
            with self.subTest(start=start),self.assertRaisesRegex(ValueError,'inactive current generation'):r.derive(reader,bounds)

    def test_permission_must_precede_call_and_survive_return_for_exact_learner_request(self):
        for fault in ('missing','start','end','learner','request'):
            reader,bounds=inputs();permit=reader.confirmations['node-2']
            if fault=='missing':reader.confirmations.clear()
            elif fault=='start':permit['start']=1
            elif fault=='end':permit['end']=3
            elif fault=='learner':permit['learner']=reader.windows[0]['identity']
            else:permit['request']=dict(permit['request'],number=2)
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'published learner original retention'):r.derive(reader,bounds)

    def test_reference_count_alias_digest_size_kind_and_order_are_exact(self):
        for fault in ('missing','alias','digest','bytes','kind','order'):
            reader,bounds=inputs();items=reader.events[2]['contents']
            if fault=='missing':items.pop()
            elif fault=='order':items.reverse()
            else:items[0]['reference' if fault=='alias' else fault]={'alias':'f'*64,'digest':'f'*64,'bytes':1,'kind':'RECORD'}[fault]
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'exact original reference inventory'):r.derive(reader,bounds)

    def test_boundaries_require_exact_node_index_type_and_live_body_interval(self):
        for fault in ('missing','node','index','bool','order','shape'):
            reader,bounds=inputs()
            if fault=='missing':bounds.pop()
            elif fault=='shape':bounds[2]=None
            else:bounds[2][{'node':'node','index':'eventIndex','bool':'sequence','order':'sequence'}[fault]]={'node':'node-1','index':1,'bool':True,'order':3}[fault]
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'boundaries|resource boundary|resource interval'):r.derive(reader,bounds)

    def test_manifest_identity_is_original_even_when_all_references_match(self):
        reader,bounds=inputs();reader.windows[0]['manifest']=frame('GENERATION',node='node-1',root=reader.model.root)
        with self.assertRaisesRegex(ValueError,'original generation identity'):r.derive(reader,bounds)

    def test_original_ownership_replay_preserves_narrow_scope_and_requires_cleanup(self):
        reader,bounds=inputs();traces,closes,plans=ownership();node='node-2';manifest=r.sha(reader.windows[0]['manifest'])
        traces={node:traces['node-1']};closes={node:closes['node-1']}
        for row in traces[node]['changes']:
            for v in row['added']+row['removed']:v['owner']=v['owner'].replace('c'*64,manifest)
        for row in closes[node]['rows']:row['owner']=row['owner'].replace('c'*64,manifest)
        for i,key in enumerate(('before','through','after'),1):bounds[i]['sequence']=plans[0][key]
        result=r.replay(traces,closes,reader,bounds)
        self.assertEqual('PASS',result['status']);self.assertTrue(result['originalPermissionWindowQualified'])
        self.assertFalse(result['fullBodyReadsQualified']);self.assertFalse(result['phase3Complete'])
        closes[node]['rows'].pop();renumber(closes[node])
        with self.assertRaisesRegex(ValueError,'incomplete probe cleanup'):r.replay(traces,closes,reader,bounds)

    def test_native_entry_requires_policy_and_original_admission_before_probe(self):
        for options in ({},{'export_ownership':True},{'export_ownership':True,'control_closes':True}):
            with self.subTest(options=options),self.assertRaisesRegex(ValueError,'published probe policy'):
                native.validate('/unused',published_probe=True,**options)
        with patch.object(native.collection,'inventory',return_value={}),patch.object(native.Path,'is_dir',return_value=True), \
             patch.object(native.publication,'validate',side_effect=ValueError('bad original')),patch.object(r,'derive') as derive:
            with self.assertRaisesRegex(ValueError,'bad original'):
                native.validate('/unused','5-REPLACE-required-four',published_probe=True,control_closes=True,export_ownership=True)
            derive.assert_not_called()


if __name__=='__main__':unittest.main()
