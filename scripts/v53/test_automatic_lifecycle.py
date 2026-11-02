"""Synthetic state transitions test the reader, never supply native proof."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import automatic_lifecycle as m


def fixture():
    f=m.p.f;cat=f.catalog();ack=f.sample(cat['wire']['PUBLISH_ACK']['schema'],cat['types'])
    ack['sender']['node']='node-1';ack['recipient']=dict(ack['sender']);ack['sequence']=1
    raw=f.encode('wire','PUBLISH_ACK',ack);digest=m.p.e.digest(raw)
    events=[dict(node='node-'+str(i),event='NODE_OPEN',nanoTime=i*10) for i in (1,2,3)]
    events.extend([dict(node='node-1',event='ROUND_BEFORE_READY',record=digest,bytes=base64.b64encode(raw).decode(),nanoTime=100),
                   dict(node='node-2',event='PROMISE_FORCED',nanoTime=200)])
    rows=[];indices=dict.fromkeys(m.p.c.NODES,0)
    def row(node,at,event,state,rounds,detail=''):
        indices[node]+=1
        rows.append(dict(node=node,ordinal=indices[node],event=event,state=state,rounds=rounds,pending=0,
            originalStarted={'node-1':35,'node-2':55,'node-3':65}[node],detail=detail,
            afterEvent=2 if at<100 else 3 if at<200 else 4,nanoTime=at))
    row('node-1',40,'START','STARTING',0);row('node-1',41,'ROUND_BEGIN','STARTING',1)
    row('node-1',42,'LOSS','STARTING',1,'HIGHER_BALLOT');row('node-1',43,'RESTART','RESTARTING',1)
    row('node-1',44,'SESSION_CLOSED','RESTARTING',1);row('node-1',45,'SESSION_OPENED','RESTARTING',1)
    row('node-1',46,'ROUND_BEGIN','RESTARTING',2);row('node-1',110,'READY','READY',2,digest)
    for node,start,close in [('node-2',60,205),('node-3',70,201),('node-1',None,210)]:
        if start:
            row(node,start,'START','STARTING',0);row(node,start+1,'ROUND_BEGIN','STARTING',1)
        rounds=2 if node=='node-1' else 1
        for i,(event,detail) in enumerate([('CLOSE',''),('SESSION_CLOSED',''),('TERMINATED','DRAINED'),('DRAINED','')]):
            row(node,close+i,event,'CLOSED',rounds,detail)
    return events,sorted(rows,key=lambda v:v['nanoTime'])


def check(events,rows):
    return [m.owner(events,values) for values in m.timeline(events,rows,m.p.c.NODES).values()]


class AutomaticLifecycleTest(unittest.TestCase):
    def test_original_state_chain_keeps_deadline_and_close_before_fresh_session(self):
        events,rows=fixture();before=copy.deepcopy((events,rows));result=check(events,rows)
        self.assertEqual(2,result[0]['rounds']);self.assertEqual(['HIGHER_BALLOT'],result[0]['losses'])
        self.assertEqual([3],result[0]['readyCallbacks']);self.assertTrue(all(v['drained'] for v in result))
        self.assertEqual(before,(events,rows))

    def test_missing_duplicate_or_boolean_ordinals_cannot_hide_observations(self):
        for mode in ('missing','duplicate','boolean'):
            events,rows=fixture()
            if mode=='missing':rows.pop(3)
            elif mode=='duplicate':rows.insert(1,dict(rows[0]))
            else:rows[0]['ordinal']=True
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'complete ordinal'):check(events,rows)

    def test_event_anchor_and_clocks_must_match_untouched_original_trace(self):
        for mode in ('early','late','boolean','past','reverse'):
            events,rows=fixture()
            if mode=='early':rows[0]['nanoTime']=29
            elif mode=='late':rows[0]['nanoTime']=101
            elif mode=='boolean':rows[0]['afterEvent']=True
            elif mode=='past':rows[0]['afterEvent']=len(events)
            else:rows[1]['afterEvent']=1
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'original event anchor'):check(events,rows)

    def test_clock_or_counter_cannot_be_renewed_on_restart(self):
        events,rows=fixture();next(v for v in rows if v['event']=='SESSION_OPENED')['originalStarted']+=1
        with self.assertRaisesRegex(ValueError,'renewed original deadline'):check(events,rows)
        events,rows=fixture();next(v for v in rows if v['event']=='SESSION_OPENED')['rounds']=2
        with self.assertRaisesRegex(ValueError,'exact state and round'):check(events,rows)

    def test_state_claim_is_not_authority_for_a_transition(self):
        events,rows=fixture();next(v for v in rows if v['event']=='RESTART')['state']='READY'
        with self.assertRaisesRegex(ValueError,'exact state and round'):check(events,rows)
        events,rows=fixture();next(v for v in rows if v['event']=='LOSS')['detail']='looks like higher ballot'
        with self.assertRaisesRegex(ValueError,'typed active loss'):check(events,rows)

    def test_fresh_session_cannot_precede_old_close(self):
        events,rows=fixture();a=next(v for v in rows if v['event']=='SESSION_OPENED');b=next(v for v in rows if v['event']=='SESSION_CLOSED')
        a['event'],b['event']=b['event'],a['event']
        with self.assertRaisesRegex(ValueError,'fresh session before old drain'):check(events,rows)

    def test_ready_requires_exact_original_barrier_not_diagnostic_state(self):
        events,rows=fixture();next(v for v in rows if v['event']=='READY')['detail']='f'*64
        with self.assertRaisesRegex(ValueError,'original ready callback'):check(events,rows)
        events,rows=fixture();events[3]['bytes']=base64.b64encode(b'forged completion').decode()
        with self.assertRaisesRegex(ValueError,'original event digest'):check(events,rows)

    def test_readiness_cannot_precede_a_round_or_survive_close(self):
        events,rows=fixture();ready=next(v for v in rows if v['event']=='READY')
        first=next(v for v in rows if v['event']=='ROUND_BEGIN');first.update(event='READY',state='READY',rounds=0,detail=ready['detail'])
        with self.assertRaisesRegex(ValueError,'ready without live round'):check(events,rows)
        events,rows=fixture();next(v for v in rows if v['event']=='RESTART')['event']='CLOSE'
        with self.assertRaisesRegex(ValueError,'exact state and round'):check(events,rows)

    def test_missing_termination_or_nonzero_pending_never_proves_drain(self):
        events,rows=fixture();next(v for v in rows if v['event']=='TERMINATED')['pending']=1
        with self.assertRaisesRegex(ValueError,'worker termination order'):check(events,rows)
        events,rows=fixture();term=next(v for v in rows if v['event']=='TERMINATED');term.update(event='DRAINED',detail='')
        with self.assertRaisesRegex(ValueError,'premature drain'):check(events,rows)

    def test_complete_node_set_and_strict_bounds_are_required(self):
        events,rows=fixture()
        with self.assertRaisesRegex(ValueError,'missing owner'):check(events,[v for v in rows if v['node']!='node-3'])
        for change in (dict(rounds=True),dict(rounds=4),dict(pending=65),dict(originalStarted=True)):
            changed=copy.deepcopy(rows);changed[0].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'bounded counters'):check(events,changed)

    def test_collection_does_not_claim_physical_or_loss_cause_qualification(self):
        events,rows=fixture()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,value in [('events.json',events),(m.FILE,rows),('drains.json',[
                dict(node=v,leases=0,failure='') for v in reversed(m.p.c.NODES)])]:
                (root/name).write_bytes(m.p.f.canonical(value))
            for name in ('failure.txt','close-failure.txt'):(root/name).write_bytes(b'')
            result=m.validate(root);self.assertEqual('PARTIAL',result['status'])
            for field in ('physicalNetworkQualified','lossCauseQualified','fullLifecycleQualified','phase3Complete'):
                self.assertFalse(result[field])
            (root/'close-failure.txt').write_text('observation unavailable')
            with self.assertRaisesRegex(ValueError,'execution or observation failure'):m.validate(root)

    def test_legacy_without_sidecar_cannot_become_lifecycle_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);events,_=fixture();(root/'events.json').write_bytes(m.p.f.canonical(events))
            with self.assertRaises((ValueError,FileNotFoundError)):m.validate(root)

    def test_invalid_original_never_counts_as_negative_coverage(self):
        with patch.object(m,'validate',side_effect=ValueError('original')),patch.object(m,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original$'):m.qualify('/original')
            mutate.assert_not_called()

    def test_negative_requires_exact_reason_and_protects_native_bytes(self):
        for error,reason in ((ValueError('another failure'),'unrelated automatic lifecycle negative'),({},'mutation accepted')):
            with self.subTest(reason=reason),patch.object(m,'validate',side_effect=[{},error]), \
                    patch.object(m.h,'inventory',return_value=dict(files={},directories=[])),patch.object(m.shutil,'copytree'),patch.object(m,'mutate'):
                with self.assertRaisesRegex(ValueError,reason):m.qualify('/original')


if __name__=='__main__':unittest.main()
