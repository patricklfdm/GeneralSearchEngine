"""Concurrent cut ownership negatives; synthetic bytes are never runtime evidence."""
import copy
import base64
import zlib
from pathlib import Path
import tempfile
import sys
import unittest
from . import performance_fixtures as fixture, performance_projection as projection
from . import performance_plan as plan, performance_model as m, cloud_workload_contract as contract
from . import format_inspector as f, remote_rich_evidence as evidence
from .remote_rich_physical import Calls


class ConcurrentCutTest(unittest.TestCase):
    def sample(self):
        # An old read stays pinned while another read captures the updated document.
        program=[contract.call('GET',[1],0),contract.call('UPDATE',[1],0),
                 contract.call('GET',[1],1),dict(operation='NO_OP',payload=b'')]
        fixture_data=fixture.generate(plan.load(),program=program)
        projected=projection.project_cloud(fixture_data['manifest'],fixture_data['genesis'],fixture_data['votes'])
        snapshots={i:f.contextual_frame(raw,'SNAPSHOT',projected['manifest']) for i,raw in enumerate(fixture_data['snapshots'],1)}
        published={i:(snapshots[i],order) for i,order in ((2,4),(3,11),(4,14),(5,24))}
        votes={}
        for i,order in ((2,3),(3,9),(4,13),(5,23)):
            proof=f.contextual_frame(projection.raw(snapshots[i]['terminalProof']),'PROOF',projected['manifest'])
            votes[proof['epoch'],proof['incarnation'],i,proof['entryDigest']]=order
        promise=(2,fixture.fixtures.UUID)
        calls=[]
        for n,(call,index) in enumerate(zip(program[:3],(2,3,4))):
            answer=None if call['operation']=='UPDATE' else m.display(projected['states'][index].documents[1])
            calls.append(dict(opId=str(n),operation=call['operation'],keys=[1],payloadSha256=m.sha(call['payload']),
                              outcome='SUCCESS',node='node-1',pid=42,answer=answer,answerSha256=m.sha(m.canonical(answer)),afterSequence=999))
        events=[]
        def event(name,order,**values):events.append(dict(event=name,order=order,pid=42,**values))
        def invoke(n,order):event('CLIENT_INVOKE',order,opId=str(n),command='call',operation=calls[n]['operation'])
        def capture(name,order,index,read_id=None):
            values=dict(epoch=2,index=index,sequence=snapshots[index]['applicationSequence'])
            if read_id is not None:values['readId']=read_id
            event(name,order,**values)
        def result(n,order):event('CLIENT_RESULT',order,opId=str(n),command='call',outcome='SUCCESS',call=calls[n])
        invoke(0,1);event('PUBLIC_READ_INVOKE',2,readId=11,opId='0')
        capture('READ_CAPTURE_VALIDATED',6,2,11);capture('READ_CAPTURED',7,2,11)
        invoke(1,8);invoke(2,9);event('PUBLIC_READ_INVOKE',10,readId=12,opId='2')
        result(1,12);capture('READ_CAPTURE_VALIDATED',16,4,12);capture('READ_CAPTURED',17,4,12)
        capture('READ_RELEASED',18,4,12);result(2,19)
        capture('READ_RELEASED',20,2,11);result(0,21)
        event('CLIENT_INVOKE',22,command='backup',opId='backup')
        capture('READ_CAPTURE_VALIDATED',26,5);capture('READ_CAPTURED',27,5);capture('READ_RELEASED',28,5)
        event('CLIENT_RESULT',29,command='backup',opId='backup',outcome='SUCCESS',sequence=5)
        return calls,events,projected,published,votes,promise

    def verify(self,sample):
        calls,events,projected,published,votes,promise=sample
        audit=Calls(calls)
        for row in events:audit.event('node-1',row,projected,published,votes,promise)
        audit.finish();return audit

    def test_overlapping_reads_keep_distinct_cuts_and_out_of_order_replies(self):
        audit=self.verify(self.sample())
        self.assertEqual(3,len(audit.read_barriers))
        self.assertEqual(1,len(audit.mutations))

    def test_after_sequence_is_not_used_as_concurrent_read_cut(self):
        # Both diagnostic values are deliberately 999; actual answers use 4 and 5.
        sample=self.sample();self.assertEqual([999]*3,[c['afterSequence'] for c in sample[0]])
        self.verify(sample)

    def test_changed_read_owner_reuse_and_missing_observations_are_rejected(self):
        edits=[('PUBLIC_READ_INVOKE','opId','2'),('PUBLIC_READ_INVOKE','readId',12),
               ('READ_CAPTURED','readId',999),('READ_CAPTURED','sequence',999),
               ('READ_CAPTURED','index',4),('READ_RELEASED','index',2),
               ('CLIENT_RESULT','outcome','INDETERMINATE')]
        for event,key,value in edits:
            with self.subTest(event=event,key=key):
                sample=self.sample();next(r for r in sample[1] if r['event']==event)[key]=value
                with self.assertRaises((ValueError,KeyError)):self.verify(sample)
        for name in ('PUBLIC_READ_INVOKE','READ_CAPTURE_VALIDATED','READ_CAPTURED','READ_RELEASED','CLIENT_RESULT'):
            with self.subTest(missing=name):
                sample=self.sample();sample[1].remove(next(r for r in sample[1] if r['event']==name))
                with self.assertRaises((ValueError,KeyError)):self.verify(sample)

    def test_resealed_answer_from_other_cut_still_fails(self):
        sample=self.sample();old,new=sample[0][0],sample[0][2]
        self.assertNotEqual(old['answer'],new['answer'])
        old.update(answer=new['answer'],answerSha256=new['answerSha256'])
        with self.assertRaisesRegex(ValueError,'exact concurrent captured cut'):self.verify(sample)

    def test_barrier_before_invocation_and_fenced_capture_fail(self):
        sample=self.sample();key=next(k for k in sample[4] if k[2]==2);sample[4][key]=0
        with self.assertRaisesRegex(ValueError,'pre-invocation'):self.verify(sample)
        sample=list(self.sample());sample[-1]=(3,fixture.fixtures.UUID)
        with self.assertRaisesRegex(ValueError,'changed promise'):self.verify(sample)

    def test_response_before_release_and_missing_auxiliary_cut_fail(self):
        sample=self.sample();next(r for r in sample[1] if r['event']=='READ_RELEASED')['order']=100
        with self.assertRaisesRegex(ValueError,'release'):self.verify(sample)
        sample=self.sample();sample[1][:]=[r for r in sample[1] if r['order']<22]
        with self.assertRaisesRegex(ValueError,'accounting'):self.verify(sample)

    def test_cloud_path_does_not_expand_local_projection_limit(self):
        sample=self.sample()
        generated=fixture.generate(plan.load(),program=[dict(operation='NO_OP',payload=b'')]*200)
        with self.assertRaisesRegex(ValueError,'slot bound'):
            projection.project(generated['manifest'],generated['genesis'],generated['votes'],maximum_slots=512)
        report=projection.project_cloud(generated['manifest'],generated['genesis'],generated['votes'])
        self.assertEqual(201,len(report['chosen']))


class TraceDictionaryTest(unittest.TestCase):
    def encoded(self,raw):
        return {'$gseString':dict(sha256=m.sha(raw),bytes=len(raw),zlib=base64.b64encode(zlib.compress(raw)).decode())}

    def test_original_bytes_and_repeated_reference_are_identical(self):
        from .remote_trace import Decoder
        raw=('snapshot-'*1000).encode();first=self.encoded(raw);later={'$gseString':dict(ref=m.sha(raw))};decoder=Decoder()
        for encoded in (first,later):
            self.assertEqual(raw.decode(),decoder.row(encoded,len(m.canonical(encoded))))
        reordered=dict(a=later,z=first)
        self.assertEqual(dict(a=raw.decode(),z=raw.decode()),Decoder().row(reordered,len(m.canonical(reordered))))

    def test_missing_duplicate_hash_trailing_data_and_expansion_are_rejected(self):
        from .remote_trace import Decoder
        raw=b'x'*10000;original=self.encoded(raw)
        with self.assertRaises(ValueError):Decoder().row({'$gseString':dict(ref=m.sha(raw))},100)
        decoder=Decoder();decoder.row(original,len(m.canonical(original)))
        with self.assertRaises(ValueError):decoder.row(original,len(m.canonical(original)))
        for key,value in [('bytes',1),('bytes',5<<20),('sha256','a'*64),
                          ('zlib',base64.b64encode(zlib.compress(raw)+b'trailing').decode())]:
            changed=copy.deepcopy(original);changed['$gseString'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):Decoder().row(changed,len(m.canonical(changed)))
        encoded=self.encoded(b'x'*(3<<20));decoder=Decoder();decoder.row(encoded,len(m.canonical(encoded)))
        repeated=[{'$gseString':dict(ref=m.sha(b'x'*(3<<20)))}]*2
        with self.assertRaisesRegex(ValueError,'row bound'):decoder.row(repeated,len(m.canonical(repeated)))
        with self.assertRaisesRegex(ValueError,'expansion budget'):Decoder([1]).row({'data':'too long'},20)
        oversized=[self.encoded(b'x'*(3<<20)),self.encoded(b'y'*(3<<20))]
        with self.assertRaisesRegex(ValueError,'row bound'):Decoder().row(oversized,len(m.canonical(oversized)))


class StartupCleanupTest(unittest.TestCase):
    def test_failed_startup_before_reply_thread_still_reaps_child(self):
        from .remote_workload import Run
        from .remote_jvm import Worker
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=Run(root,plan.load())
            with self.assertRaises(TypeError):
                Worker(run,root,'node-1',[sys.executable,'-c',"import time; print('null', flush=True); time.sleep(60)"])
            worker=run.workers[0]
            worker.stop(failed=True)
            self.assertIsNotNone(worker.proc.poll())
            self.assertEqual('reaped',evidence.old.read(root/'node-1-process.json')['cleanup'])


class SegmentedEvidenceTest(unittest.TestCase):
    def test_frozen_schedule_survives_json_serialization(self):
        from . import remote_schedule,remote_schedule_evidence
        spec=remote_schedule.windows('healthy','experiment')[0]
        events=[];state=remote_schedule.WindowState(spec,100,events.append)
        for call in spec['calls']:
            due=100+call['dueMillis']*10**6
            state.offer(call,due);state.invoke(call['ordinal'],due);state.complete(call['ordinal'],due+1,dict(outcome='SUCCESS'))
        result=state.finish(100+spec['durationNanos'])
        self.assertEqual('PASS',remote_schedule_evidence.validate(m.strict_json(m.canonical(spec)),events,result)['status'])

    def test_gzip_segments_keep_rows_and_reject_truncation_mixing_and_expansion(self):
        import gzip
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'trace.jsonl.gz'
            path.write_bytes(gzip.compress(b'{"order":1}\n'))
            part=root/'trace-part0001.jsonl.gz';part.write_bytes(gzip.compress(b'{"order":2}\n'))
            self.assertEqual([1,2],[r['order'] for r in evidence.lines(root,'trace')])
            (root/'trace.jsonl').write_bytes(b'{"order":9}\n')
            with self.assertRaisesRegex(ValueError,'mixed'):evidence.lines(root,'trace')
            (root/'trace.jsonl').unlink();part.unlink()
            original=path.read_bytes();path.write_bytes(original[:-1])
            with self.assertRaises((EOFError,OSError,ValueError)):evidence.lines(root,'trace')
            bad=bytearray(original);bad[-8]^=1;path.write_bytes(bad)
            with self.assertRaises((OSError,ValueError)):evidence.lines(root,'trace')
            path.write_bytes(gzip.compress(b'"'+b'x'*(4<<20)+b'"\n'))
            with self.assertRaisesRegex(ValueError,'expansion'):evidence.lines(root,'trace')
            # Each row fits, but the decompressed member does not.
            line=b'{"data":"'+b'x'*(1<<20)+b'"}\n'
            with gzip.open(path,'wb') as out:
                for _ in range(33):out.write(line)
            with self.assertRaisesRegex(ValueError,'expansion'):evidence.lines(root,'trace')

    def test_ordered_segments_and_torn_or_missing_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'trace.jsonl').write_bytes(b'{"order":1}\n')
            (root/'trace-part0001.jsonl').write_bytes(b'{"order":2}\n')
            self.assertEqual([1,2],[r['order'] for r in evidence.lines(root,'trace')])
            (root/'trace-part0001.jsonl').rename(root/'trace-part0002.jsonl')
            with self.assertRaises(ValueError):evidence.lines(root,'trace')
            (root/'trace-part0002.jsonl').unlink();(root/'trace.jsonl').write_bytes(b'{"order":1}')
            with self.assertRaises(ValueError):evidence.lines(root,'trace')


class NegativeReplayLocationTest(unittest.TestCase):
    """Synthetic history isolates relocation and original-before-mutation checks."""
    def setUp(self):
        import json
        from . import fixtures, remote_collection
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'download';self.root.mkdir()
        self.original=Path('/unavailable-rich-negative-run/raw')
        self.cell='read-heavy-candidate-v5.1-automatic'
        self.directory=self.root/self.cell;self.directory.mkdir()
        frames,wires,_=fixtures.generate()
        for node in ('node-1','node-2','node-3'):
            authority=self.directory/node;authority.mkdir();(authority/'manifest.gsr').write_bytes(frames['MANIFEST'])
        self.calls=[dict(node='node-1',opId='read',operation='GET',outcome='SUCCESS')]
        self.traces={'node-1':[
            dict(event='PUBLIC_READ_INVOKE',opId='read',readId=1),
            dict(event='READ_CAPTURED',readId=1,sequence=4),
            dict(event='READ_RELEASED',readId=1,index=2),
            dict(event='FORCE',kind='PROOF'),
            dict(event='RECEIVED',frame=fixtures.B64(wires['COMMIT_PROOF_ACK'])),
            dict(event='CLIENT_RESULT',opId='read',call=self.calls[0])],
            'node-2':[dict(event='START')],'node-3':[dict(event='START')]}
        (self.directory/'calls.json').write_text(json.dumps(self.calls))
        for node,rows in self.traces.items():
            (self.directory/(node+'-trace.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (self.root/'execution.json').write_text(json.dumps(dict(adapters={
            'candidate':dict(artifacts=[dict(path=str(self.original/'artifacts/candidate.jar'))])})))
        (self.root/remote_collection.INDEX).write_bytes(m.canonical(remote_collection.inventory(self.root)))

    def audit(self,directory,calls,traces,*,evidence_location=None,cloud_calls=None):
        from . import storage_inspector as storage
        inspect=evidence_location.inspect if evidence_location else storage.inspect
        for node in traces:inspect(directory/node)
        if calls!=self.calls or traces!=self.traces:raise ValueError('synthetic changed history')

    def sealed(self,directory,maximum_bytes,maximum_frame,admitted_path):
        m.need(admitted_path==self.original/self.cell/Path(directory).name,'copied/stale seal path')
        return {}

    def test_relocated_negatives_use_original_sealed_paths_for_baseline_and_mutations(self):
        from unittest.mock import patch
        from . import remote_rich_negatives as negatives, storage_inspector as storage
        with patch.object(storage,'_inspect',side_effect=self.sealed) as inspect, \
                patch.object(negatives.physical,'automatic',side_effect=self.audit) as audit:
            result=negatives.verify(self.root)
        self.assertEqual(11,audit.call_count)
        self.assertEqual(33,inspect.call_count)
        self.assertEqual(10,len(result))
        self.assertEqual({'synthetic changed history'},{row['reason'] for row in result})
        self.assertEqual({'REJECTED'},{row['status'] for row in result})

    def test_bad_original_cannot_be_counted_as_ten_successful_rejections(self):
        from unittest.mock import patch
        from . import remote_rich_negatives as negatives
        with patch.object(negatives.physical,'automatic',side_effect=ValueError('invalid original authority')) as audit:
            with self.assertRaisesRegex(ValueError,'invalid original authority'):negatives.verify(self.root)
        self.assertEqual(1,audit.call_count)

    def test_relocated_negatives_reject_missing_or_changed_inventory_before_mutations(self):
        from unittest.mock import patch
        from . import remote_rich_negatives as negatives, remote_collection
        index=self.root/remote_collection.INDEX;original=index.read_bytes();index.unlink()
        with patch.object(negatives.physical,'automatic') as audit:
            with self.assertRaises((ValueError,FileNotFoundError)):negatives.verify(self.root)
            audit.assert_not_called()
        index.write_bytes(original)
        (self.directory/'node-1/manifest.gsr').write_bytes(b'changed')
        with patch.object(negatives.physical,'automatic') as audit:
            with self.assertRaisesRegex(ValueError,'relocated rich inventory differs'):negatives.verify(self.root)
            audit.assert_not_called()


if __name__=='__main__':unittest.main()
