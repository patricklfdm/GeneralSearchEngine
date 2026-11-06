import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import control_close_evidence as r
from . import control_close_negatives as negatives
from .test_transport_resource_evidence import recount
from .test_resource_transitions import charge


def fixture(completed=False):
    nonce='00000000-0000-0000-0000-000000000001';binding='a'*64
    names=['transfer-service-'+nonce,'transfer-trace-'+binding+'-'+nonce,'source-session-'+binding+'-'+nonce,'source-response-'+'b'*64+'-'+nonce]
    charges=[charge('CONTROL',name,1024) for name in names]
    rows=[dict(event='START',added=[],removed=[])]
    rows += [dict(event='RESERVE',added=[v],removed=[]) for v in charges]
    rows += [dict(event='RELEASE',added=[],removed=[v]) for v in reversed(charges)]
    def mark(event,kind,resource,children=()):return dict(event=event,owner=names[kind],resourceSequence=resource,children=[names[i] for i in children])
    observed=([mark('BEGIN',2,4,[3]),mark('RETURNED',2,6),mark('BEGIN',0,6,[1]),mark('BEGIN',1,6)] if completed else
              [mark('BEGIN',0,4,[1]),mark('BEGIN',1,4,[2]),mark('BEGIN',2,4,[3]),mark('RETURNED',2,6)])
    observed += [mark('RETURNED',1,7),mark('RETURNED',0,8)]
    calls={}
    for i,v in enumerate(observed):
        v['sequence']=i
        if v['event']=='BEGIN':calls[v['owner']]=i
        v['call']=calls[v['owner']]
    closes=dict(schema='gse-v53-control-close-observations-v1',maximum=65536,observations=len(observed),truncated=False,failed=False,rows=observed)
    events=[dict(node='node-1',event='SOURCE_SERVICE_CLOSE_'+v) for v in ('BEGIN','RETURNED')]
    return {'node-1':recount(rows)},{'node-1':closes},events,[dict(sequence=6 if completed else 4),dict(sequence=8)]


class ControlCloseEvidenceTest(unittest.TestCase):
    def test_reusable_round_and_slot_labels_are_not_unique_cleanup_handles(self):
        data=fixture();rows=data[0]['node-1']['changes']
        for name in ('native-round-owner','native-slot-owner','slot-payload','round-input'):
            for _ in range(2):
                value=charge('CONTROL',name,10)
                rows.extend([dict(event='RESERVE',added=[value],removed=[]),dict(event='RELEASE',added=[],removed=[value])])
        data[0]['node-1']=recount(rows);result=r.replay(*data[:2])
        self.assertEqual(3,result['cleanupIntervals'])
        self.assertEqual(4,len(result['owners']['node-1']['lifetimes']))
        self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_reusable_protocol_label_cannot_supply_a_cleanup_parent_or_child(self):
        for parent in (False,True):
            data=fixture();value=charge('CONTROL','native-round-owner',10);rows=data[0]['node-1']['changes']
            rows.extend([dict(event='RESERVE',added=[value],removed=[]),dict(event='RELEASE',added=[],removed=[value])])
            data[0]['node-1']=recount(rows)
            data[1]['node-1']['rows'][0]['owner' if parent else 'children']='native-round-owner' if parent else ['native-round-owner']
            with self.subTest(parent=parent),self.assertRaises(ValueError):r.replay(*data[:2])

    def test_service_export_and_unknown_handle_reuse_still_fails(self):
        for name in ('transfer-service-reused','source-session-reused','source-export-reused','native-round-owner-extra','unknown-control'):
            data=fixture();rows=data[0]['node-1']['changes']
            for _ in range(2):
                value=charge('CONTROL',name,10)
                rows.extend([dict(event='RESERVE',added=[value],removed=[]),dict(event='RELEASE',added=[],removed=[value])])
            data[0]['node-1']=recount(rows)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'reused allocation'):r.replay(*data[:2])

    def test_actual_active_and_completed_intervals_have_different_nesting(self):
        for completed in (False,True):
            result=r.component(*fixture(completed));self.assertEqual(3,result['cleanupIntervals'])
            self.assertEqual(2 if completed else 3,result['childReferences']);self.assertFalse(result['phase3Complete'])

    def test_negatives_preserve_their_specific_obligations(self):
        for completed in (False,True):
            with self.subTest(completed=completed):self.assertEqual(len(negatives.NEGATIVES),len(negatives.replay(fixture(completed))))

    def test_zero_leases_cannot_replace_missing_normal_return(self):
        data=fixture();data[1]['node-1']['rows'].pop();data[1]['node-1']['observations']-=1
        self.assertEqual(0,data[0]['node-1']['current']['leases'])
        with self.assertRaisesRegex(ValueError,'complete cleanup intervals'):r.component(*data)

    def test_original_failure_is_not_a_negative_pass(self):
        with patch.object(r,'component',side_effect=ValueError('bad original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.replay(fixture())
            mutate.assert_not_called()

    def test_missing_budget_and_empty_observation_reject(self):
        data=fixture()
        with self.assertRaisesRegex(ValueError,'complete original budgets'):r.replay(data[0],{})
        data[1]['node-1'].update(rows=[],observations=0)
        with self.assertRaisesRegex(ValueError,'complete cleanup intervals'):r.replay(*data[:2])

    def test_extra_fields_and_booleans_cannot_downgrade_completeness(self):
        for change in (dict(extra=True),dict(observations=True),dict(maximum=True),dict(truncated=0),dict(failed=0)):
            data=fixture();data[1]['node-1'].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'complete bounded recorder'):r.replay(*data[:2])

    def test_parent_must_be_allocated_before_its_child(self):
        data=fixture();rows=data[0]['node-1']['changes'];rows[1],rows[2]=rows[2],rows[1];data[0]['node-1']=recount(rows)
        with self.assertRaisesRegex(ValueError,'parent allocation order'):r.component(*data)

    def test_session_must_keep_original_trace_binding(self):
        data=fixture();old=data[1]['node-1']['rows'][2]['owner'];new=old.replace('a'*64,'c'*64)
        for row in data[0]['node-1']['changes']:
            for v in row['added']+row['removed']:
                if v['owner']==old:v['owner']=new
        for row in data[1]['node-1']['rows']:
            if row['owner']==old:row['owner']=new
            row['children']=[new if v==old else v for v in row['children']]
        with self.assertRaisesRegex(ValueError,'original trace session'):r.component(*data)

    def test_capture_is_bound_to_original_identity_event_and_resource_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/r.DIRECTORY;directory.mkdir();raw=r.a.collection.snapshot.f.canonical(fixture()[1]['node-1']);(directory/'node-1.json').write_bytes(raw)
            original=dict(root='a'*64,eventsSha256='b'*64,owners=[dict(identity=dict(node='node-1'),path='node-1.json',sha256='c'*64)])
            index=dict(schema='gse-v53-control-close-capture-v1',root=original['root'],eventsSha256=original['eventsSha256'],
                       owners=[dict(identity=dict(node='node-1'),path='node-1.json',sha256=hashlib.sha256(raw).hexdigest(),resourceSha256='c'*64)])
            def save(value):(directory/'index.json').write_bytes(r.a.collection.snapshot.f.canonical(value))
            save(index);self.assertEqual({'node-1'},set(r.load(root,original)))
            for name in ('root','eventsSha256','resourceSha256','identity','sha256','path'):
                bad=copy.deepcopy(index)
                if name in ('root','eventsSha256'):bad[name]='f'*64
                else:bad['owners'][0][name]=dict(node='node-2') if name=='identity' else 'bad'
                save(bad)
                with self.subTest(name=name),self.assertRaises(ValueError):r.load(root,original)
            save(index);(directory/'extra').write_text('extra')
            with self.assertRaisesRegex(ValueError,'capture inventory'):r.load(root,original)

    def test_missing_original_sidecar_is_not_inferred_from_zero_usage(self):
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'missing original capture'):r.load(temp,{})


if __name__=='__main__':unittest.main()
