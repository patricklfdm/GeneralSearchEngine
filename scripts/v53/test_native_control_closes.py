import copy
import tempfile
import unittest
from unittest.mock import patch
from . import native_control_closes as r
from . import native_control_close_negatives as negatives
from . import native_resource_evidence as accounting
from .test_control_close_evidence import fixture as one
from .test_transport_resource_evidence import recount
from .test_resource_transitions import charge


def concurrent():
    nonce='00000000-0000-0000-0000-000000000001'
    names=['transfer-service-'+nonce,'transfer-trace-'+'a'*64+'-'+nonce,'source-session-'+'a'*64+'-'+nonce,
           'source-response-'+'c'*64+'-'+nonce,'transfer-trace-'+'b'*64+'-'+nonce,
           'source-session-'+'b'*64+'-'+nonce,'source-response-'+'d'*64+'-'+nonce]
    charges=[charge('CONTROL',name,1024) for name in names];rows=[dict(event='START',added=[],removed=[])]
    rows += [dict(event='RESERVE',added=[v],removed=[]) for v in charges]
    rows += [dict(event='RELEASE',added=[],removed=[charges[i]]) for i in (3,6,5,2,1,4,0)]
    close_rows=[];calls={}
    for name,event,at,children in [(2,'BEGIN',7,[3]),(5,'BEGIN',8,[6]),(5,'RETURNED',10,[]),(2,'RETURNED',11,[]),
                                    (0,'BEGIN',11,[1,4]),(1,'BEGIN',11,[]),(1,'RETURNED',12,[]),
                                    (4,'BEGIN',12,[]),(4,'RETURNED',13,[]),(0,'RETURNED',14,[])]:
        seq=len(close_rows)
        if event=='BEGIN':calls[name]=seq
        close_rows.append(dict(sequence=seq,event=event,call=calls[name],resourceSequence=at,owner=names[name],children=sorted(names[i] for i in children)))
    closes=dict(schema='gse-v53-control-close-observations-v1',maximum=65536,observations=len(close_rows),truncated=False,failed=False,rows=close_rows)
    key=lambda i:('node-1',names[i])
    bindings={key(3):(key(2),key(1)),key(6):(key(5),key(4))}
    return {'node-1':recount(rows)},{'node-1':closes},bindings


class NativeControlClosesTest(unittest.TestCase):
    def test_overlapping_sessions_keep_original_response_owners(self):
        result=r.bind(*concurrent());self.assertEqual(2,result['sessions']);self.assertEqual(5,result['cleanupIntervals'])
        self.assertEqual(1,result['services']);self.assertFalse(result['listenerDrainQualified']);self.assertFalse(result['phase3Complete'])

    def test_another_live_response_cannot_replace_the_original(self):
        traces,closes,bindings=concurrent();rows=closes['node-1']['rows']
        rows[0]['children']=list(rows[1]['children'])
        self.assertEqual('PASS',r.close.replay(traces,closes)['status']) # Accounting/nesting alone is insufficient.
        with self.assertRaisesRegex(ValueError,'complete original response inventory'):r.bind(traces,closes,bindings)

    def test_missing_response_is_refused_even_when_every_lease_releases(self):
        traces,closes,bindings=concurrent();closes['node-1']['rows'][0]['children']=[]
        self.assertEqual(0,traces['node-1']['current']['leases'])
        with self.assertRaisesRegex(ValueError,'complete original response inventory'):r.bind(traces,closes,bindings)

    def test_trace_must_match_the_original_exchange_not_only_an_existing_scope(self):
        traces,closes,bindings=concurrent();a,b=bindings
        bindings[a]=(bindings[a][0],bindings[b][1])
        with self.assertRaisesRegex(ValueError,'exact original trace'):r.bind(traces,closes,bindings)

    def test_unbound_or_foreign_original_sessions_cannot_qualify(self):
        for mode in ('missing','foreign','wrong-role'):
            traces,closes,bindings=concurrent();a,b=bindings
            if mode=='missing':del bindings[a]
            elif mode=='foreign':bindings[a]=(('node-2',bindings[a][0][1]),bindings[a][1])
            else:bindings[a]=(bindings[a][1],bindings[a][0])
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.bind(traces,closes,bindings)

    def test_joining_service_uses_its_own_trace_scope(self):
        traces,closes,*_=one();names={name:name.replace('transfer-service-','joining-checkpoint-service-').replace('transfer-trace-','joining-checkpoint-trace-')
                                    for row in traces['node-1']['changes'] for v in row['added'] for name in [v['owner']]}
        for row in traces['node-1']['changes']:
            for v in row['added']+row['removed']:v['owner']=names[v['owner']]
        for row in closes['node-1']['rows']:
            row['owner']=names[row['owner']];row['children']=sorted(names[n] for n in row['children'])
        lives,_,_=r.source.scan(traces);key=lambda role:next(k for k,v in lives.items() if v['role']==role)
        bindings={key('source-response'):(key('source-session'),key('joining-checkpoint-trace'))}
        self.assertEqual(1,r.bind(traces,closes,bindings)['joiningCheckpointServices'])

    def test_all_declared_native_close_negatives_are_specific(self):
        result=negatives.replay(*concurrent());self.assertEqual(len(negatives.NEGATIVES),len(result['negatives']))

    def test_invalid_original_never_counts_as_negative_success(self):
        with patch.object(r,'bind',side_effect=ValueError('bad original')),patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'bad original'):negatives.replay(*concurrent())
            mutate.assert_not_called()

    def test_native_close_replay_first_requires_complete_original_source_evidence(self):
        with patch.object(r.source,'replay',side_effect=ValueError('bad original source')),patch.object(r,'bind') as bind:
            with self.assertRaisesRegex(ValueError,'bad original source'):r.replay([],[],{},[],{},'a'*64,{})
            bind.assert_not_called()

    def test_binding_output_cannot_be_preseeded_with_claimed_authority(self):
        for bindings in ({'claimed':'source'},[],True):
            with self.subTest(bindings=bindings),self.assertRaisesRegex(ValueError,'empty binding output'):
                r.source.replay([],[],{},[],{},'a'*64,bindings=bindings)

    def test_strict_native_mode_refuses_historical_zero_usage_without_sidecar(self):
        with tempfile.TemporaryDirectory() as root,self.assertRaisesRegex(ValueError,'missing control close observations'):
            accounting.validate(root,control_closes=True)


if __name__=='__main__':unittest.main()
