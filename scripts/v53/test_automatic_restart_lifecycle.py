"""Synthetic attachment tests do not stand in for the native two-campaign run."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_restart_lifecycle as m


def fixture():
    f=m.f;cat=f.catalog();ack=f.sample(cat['wire']['PUBLISH_ACK']['schema'],cat['types'])
    ack['sender']['node']='node-1';ack['recipient']=dict(ack['sender']);ack['sequence']=1
    def ready(trace):
        ack['trace']=trace;raw=f.encode('wire','PUBLISH_ACK',ack)
        return dict(node='node-1',event='ROUND_BEFORE_READY',record=m.h.digest(raw),bytes=base64.b64encode(raw).decode())
    events=[dict(node='node-1',event='BOOT'),dict(node='node-1',event='ROUND_INSTALLED'),
            ready('00000000-0000-0000-0000-000000000001'),dict(node='node-2',event='ALLOCATOR_FORCED'),
            dict(node='node-1',event='WIRE_RESPONSE'),dict(node='node-1',event='ROUND_INSTALLED'),
            ready('00000000-0000-0000-0000-000000000002'),dict(node='node-1',event='ROUND_SLOT_COMPLETE')]
    rows=[]
    def row(at,after,event,state,rounds,detail=''):
        rows.append(dict(node='node-1',ordinal=len(rows)+1,nanoTime=at,afterEvent=after,event=event,state=state,rounds=rounds,
                         pending=0,originalStarted=30,detail=detail))
    row(30,0,'START','STARTING',0);row(31,0,'ROUND_BEGIN','STARTING',1)
    row(250,2,'READY','READY',1,events[2]['record']);row(380,3,'LOSS','READY',1,'HIGHER_BALLOT')
    row(381,3,'RESTART','RESTARTING',1);row(382,3,'SESSION_CLOSED','RESTARTING',1)
    row(383,3,'SESSION_OPENED','RESTARTING',1);row(384,3,'ROUND_BEGIN','RESTARTING',2)
    row(650,6,'READY','READY',2,events[6]['record'])
    for at,event,detail in [(850,'CLOSE',''),(851,'SESSION_CLOSED',''),(852,'TERMINATED','DRAINED'),(853,'DRAINED','')]:
        row(at,7,event,'CLOSED',2,detail)
    capture=dict(schema=m.SCHEMA,firstEvent=1,prefixSha256=m.h.digest(f.canonical(events[:1])),attachedNanos=10,
        events=[dict(index=i,nanoTime=100*i,sha256=m.h.digest(f.canonical(e))) for i,e in enumerate(events) if i],
        opened=dict(node='node-1',afterEvent=0,nanoTime=20,budgetNanos=m.BUDGET),
        requests=[dict(node='node-1',afterEvent=3,nanoTime=350,request=base64.b64encode(b'original fence').decode())],
        captureFailure='',observationFailure='',producerPassed=True,ownerDrained=True,resourceLeases=[0,0,0],
        eventsSha256=m.h.digest(f.canonical(events)),planSha256=m.h.digest(b'plan'))
    return events,capture,rows


def bind(events,capture,rows):
    return m.attachment(events,capture,rows,m.h.digest(m.f.canonical(events)),m.h.digest(b'plan'))


def write(root,events,capture,rows):
    raw=root/'raw';raw.mkdir();sidecar=root/'sidecar';sidecar.mkdir()
    (raw/'events.json').write_bytes(m.f.canonical(events));(raw/'original-plan.gsbp').write_bytes(b'plan')
    (raw/'fence-request.gsw').write_bytes(b'original fence')
    (sidecar/m.CAPTURE).write_bytes(m.f.canonical(capture));(sidecar/m.OBSERVATIONS).write_bytes(m.f.canonical(rows))
    return raw,sidecar


class AutomaticRestartLifecycleTest(unittest.TestCase):
    def test_two_real_anchors_keep_original_deadline_and_fresh_barrier(self):
        events,capture,rows=fixture();before=copy.deepcopy((events,capture,rows));result=bind(events,capture,rows)
        self.assertEqual([2,6],result['state']['readyCallbacks']);self.assertEqual(['HIGHER_BALLOT'],result['state']['losses'])
        self.assertEqual(30,result['originalStarted']);self.assertEqual(2,result['state']['rounds'])
        self.assertEqual(before,(events,capture,rows))

    def test_all_declared_attachment_negatives_have_exact_reasons(self):
        for name,reason in m.NEGATIVES.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                events,capture,rows=fixture();raw,sidecar=write(Path(temp),events,capture,rows)
                with patch.object(m.current,'validate',return_value={'status':'PASS'}):
                    m.validate(raw,sidecar);original=m.h.inventory(raw);m.mutate(sidecar,name,events=events)
                    with self.assertRaisesRegex(ValueError,'^'+reason+'$'):m.validate(raw,sidecar)
                    self.assertEqual(original,m.h.inventory(raw))

    def test_original_physical_network_failure_stops_before_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            raw,sidecar=write(Path(temp),*fixture())
            with patch.object(m.current,'validate',side_effect=ValueError('bad original')),patch.object(m,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify(raw,sidecar)
                mutate.assert_not_called()

    def test_unrelated_negative_or_accepted_mutation_cannot_count_as_rejection(self):
        for bad,reason in ((ValueError('other error'),'unrelated restart lifecycle negative'),({},'accepted mutation')):
            with self.subTest(reason=reason),tempfile.TemporaryDirectory() as temp:
                raw,sidecar=write(Path(temp),*fixture())
                with patch.object(m,'validate',side_effect=[{},bad]),patch.object(m,'mutate'):
                    with self.assertRaisesRegex(ValueError,reason):m.qualify(raw,sidecar)

    def test_unknown_or_linked_attachment_is_never_lifecycle_proof(self):
        for mode in ('extra','link','missing'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temp:
                raw,sidecar=write(Path(temp),*fixture())
                if mode=='extra':(sidecar/'extra').write_bytes(b'unexplained')
                elif mode=='link':(sidecar/'link').symlink_to(sidecar/m.CAPTURE)
                else:(sidecar/m.OBSERVATIONS).unlink()
                with patch.object(m.current,'validate') as physical:
                    with self.assertRaises(ValueError):m.validate(raw,sidecar)
                    physical.assert_not_called()

    def test_other_trace_and_unobserved_prefix_cannot_be_substituted(self):
        for mode in ('removed','reordered','boolean','prefix'):
            events,capture,rows=fixture()
            if mode=='removed':events.pop()
            elif mode=='reordered':events[1],events[3]=events[3],events[1]
            elif mode=='boolean':capture['firstEvent']=True
            else:events[0]['event']='OTHER'
            with self.subTest(mode=mode),self.assertRaises(ValueError):bind(events,capture,rows)

    def test_clock_anchor_and_observation_counter_bounds(self):
        for change in (dict(afterEvent=True),dict(afterEvent=8),dict(nanoTime=0),dict(rounds=True),dict(pending=65),
                       dict(originalStarted=True),dict(ordinal=True),dict(node='node-2')):
            events,capture,rows=fixture();rows[0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):bind(events,capture,rows)

    def test_native_new_round_must_follow_session_replacement(self):
        events,capture,rows=fixture();second=next(v for v in rows if v['event']=='ROUND_BEGIN' and v['rounds']==2)
        # Move only its actual anchor past installation while retaining valid clocks.
        second.update(afterEvent=5,nanoTime=550)
        with self.assertRaisesRegex(ValueError,'new session before native reactivation'):bind(events,capture,rows)

    def test_legacy_node_open_contract_remains_required_by_default(self):
        events,_,rows=fixture()
        with self.assertRaisesRegex(ValueError,'start before node open'):m.lifecycle.owner(events,rows)
        with self.assertRaisesRegex(ValueError,'start before observed construction'):m.lifecycle.owner(events,rows,opened_after=True)

    def test_last_data_completion_cannot_use_cleanup_deadline_exemption(self):
        events,capture,rows=fixture();capture['events'][-1]['nanoTime']+=m.BUDGET
        for row in rows:
            if row['event'] in ('CLOSE','SESSION_CLOSED','TERMINATED','DRAINED') and row['afterEvent']==7:row['nanoTime']+=m.BUDGET
        with self.assertRaisesRegex(ValueError,'original operation deadline'):bind(events,capture,rows)


if __name__=='__main__':unittest.main()
