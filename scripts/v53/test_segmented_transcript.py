"""Deferred decoded/content views; conditional fixtures are not native evidence."""
import base64
import copy
import hashlib
from pathlib import Path
import unittest
from uuid import UUID
from . import connection_transcript as connections
from . import joining_transcript as transcript
from . import segmented_transcript as deferred
from . import joining_export_evidence as exports
from . import test_connection_transcript as sockets
from . import test_wire_archive as archive


def trace(data=b'original payload',*,repetitions=2,chunk_bytes=7,change=None):
    template,wire,ids,root=sockets.trace();_,header=connections.wire(wire[0]['request'])
    events=[];wires=[]
    for repetition in range(repetitions):
        tid=str(UUID(int=2000+repetition));trace_id=str(UUID(int=1000+repetition));digest=hashlib.sha256(data).hexdigest()
        frames=[('CHUNK','SOURCE_OFFER',dict(id=tid,action='REQUEST',offset=0,digest=digest,bytes=''),
                 dict(id=tid,digest=digest,bytes=len(data),kind='APPLICATION'))]
        for at in range(0,len(data),chunk_bytes):
            part=data[at:at+chunk_bytes]
            frames.append(('CHUNK','CHUNK',dict(id=tid,action='REQUEST',offset=at,digest=digest,bytes=''),
                dict(id=tid,action='DATA',offset=at,digest=hashlib.sha256(part).hexdigest(),bytes=base64.b64encode(part).decode())))
        frames.append(('TRANSFER_COMMIT','TRANSFER_COMMIT',dict(id=tid,digest=digest),dict(id=tid,digest=digest)))
        if change:change(frames)
        for sequence,(kind,answer,request,response) in enumerate(frames,1):
            q=dict(header,trace=trace_id,sequence=sequence,payload=request)
            a=dict(q,sender=q['recipient'],recipient=q['sender'],payload=response)
            qr=connections.f.encode('wire',kind,q);ar=connections.f.encode('wire',answer,a)
            encoded=[base64.b64encode(raw).decode() for raw in (qr,ar)];qh,ah=[hashlib.sha256(raw).hexdigest() for raw in (qr,ar)]
            at=len(wires)
            for row in template:
                row=copy.deepcopy(row);client=row['event'] in (connections.SEND,connections.DELIVER)
                row['connection']['id']=str(UUID(int=10000+at*2+(0 if client else 1)))
                row.update(request=qh,kind=kind)
                if 'bytes' in row:row['bytes']=encoded[0]
                if 'response' in row:row.update(response=ah,responseKind=answer)
                events.append(row)
            wires.append(dict(request=encoded[0],response=encoded[1],withheld=False,connection=copy.deepcopy(events[-2]['connection'])))
    return events,wires,ids,root


class SegmentedTranscriptTest(unittest.TestCase):
    def capture(self,**kwargs):
        data=trace(**kwargs);helper=archive.WireArchiveTest();helper.setUp();self.addCleanup(helper.doCleanups)
        helper.original({'wire.json':data[1]});reader=helper.open().read('wire.json')
        return data,reader,helper

    def test_deferred_exchanges_match_list_and_do_not_retain_returned_mutations(self):
        data,reader,_=self.capture();expected=connections.replay(*data)
        result=connections.replay(data[0],reader,*data[2:]);self.assertEqual(expected,result)
        row=result['rows'][1];self.assertIsInstance(row,deferred.Exchange)
        mutated=row['response'];mutated['payload']['bytes']='changed'
        self.assertEqual(expected['rows'][1]['response'],row['response'])
        changed=copy.deepcopy(row);changed['delivered']=999
        self.assertNotEqual(999,row['delivered']);self.assertIs(row.source,changed.source)
        with self.assertRaisesRegex(ValueError,'immutable frame'):row['request']={}

    def test_content_reassembles_exact_bytes_without_changing_session_bindings(self):
        for payload in (b'x',b'abcdefghijklmnopqrstuvwxyz'):
            with self.subTest(payload=payload):
                data,reader,_=self.capture(data=payload)
                original=connections.replay(*data)['rows'];rows=connections.replay(data[0],reader,*data[2:])['rows']
                expected=[];actual=[]
                self.assertEqual(transcript.transfers(original,contents=expected),transcript.transfers(rows,contents=actual))
                self.assertEqual(expected,actual);self.assertEqual(2,len(actual))
                self.assertTrue(all(type(v) is deferred.Content for v in actual))
                copied=copy.deepcopy(actual)
                for value in copied:
                    self.assertEqual(payload,value['raw'])
                    exports.exact([value],[(value['offer']['request']['payload']['digest'],payload,'APPLICATION')],'content differs')
                self.assertEqual(exports.sessions(expected),exports.sessions(actual))

    def test_connection_lookup_reads_positions_and_preserves_legacy_values(self):
        data,reader,_=self.capture();old=deferred.by_connection(data[1]);view=deferred.by_connection(reader)
        self.assertEqual(old,view);self.assertTrue(all(type(v) is int for v in view.positions.values()))
        key=next(iter(view));value=view[key];value['response']='changed'
        self.assertEqual(old[key],view[key])
        with self.assertRaises(KeyError):view['absent']

    def test_retained_original_tampering_rejects_frame_content_and_lookup(self):
        data,reader,helper=self.capture();rows=connections.replay(data[0],reader,*data[2:])['rows'];contents=[]
        transcript.transfers(rows,contents=contents);lookup=deferred.by_connection(reader)
        path=next((helper.root/'segmented-wire/wire/segments').iterdir())
        original=path.read_bytes();path.write_bytes(original[:-1]+b' ')
        for read in (lambda:rows[1]['response'],lambda:contents[0]['raw'],lambda:lookup[next(iter(lookup))]):
            with self.assertRaisesRegex(ValueError,'segmented evidence'):read()

    def test_changed_frame_binding_or_content_digest_cannot_be_used(self):
        data,reader,_=self.capture();rows=connections.replay(data[0],reader,*data[2:])['rows'];contents=[]
        transcript.transfers(rows,contents=contents)
        bad=copy.deepcopy(rows[0]);bad['requestHash']='0'*64
        with self.assertRaisesRegex(ValueError,'frame binding'):bad['request']
        content=copy.deepcopy(contents[0]);content.digest='0'*64
        with self.assertRaisesRegex(ValueError,'changed content'):content['raw']

    def test_missing_commit_bad_chunk_and_bad_final_digest_remain_failures(self):
        cases=[(lambda rows:rows.pop(),'incomplete transfer'),
               (lambda rows:rows[1][3].update(offset=1),'exact transfer chunk'),
               (lambda rows:rows[0][3].update(digest='0'*64),'exact transfer chunk')]
        for change,reason in cases:
            with self.subTest(reason=reason):
                data,reader,_=self.capture(repetitions=1,change=change)
                rows=connections.replay(data[0],reader,*data[2:])['rows'];contents=[]
                with self.assertRaisesRegex(ValueError,reason):transcript.transfers(rows,contents=contents)
                self.assertEqual([],contents)

    def test_no_content_views_created_for_counter_only_replay(self):
        from unittest.mock import patch
        data,reader,_=self.capture();rows=connections.replay(data[0],reader,*data[2:])['rows']
        with patch.object(deferred,'Content') as content:
            result=transcript.transfers(rows)
            self.assertEqual(2,result['committedTransfers']);content.assert_not_called()

    def test_view_cannot_mix_separately_captured_originals(self):
        data,one,_=self.capture();_,two,_=self.capture()
        first=connections.replay(data[0],one,*data[2:])['rows'];other=connections.replay(data[0],two,*data[2:])['rows']
        mixed=[first[0],other[1],*first[2:]]
        with self.assertRaisesRegex(ValueError,'transfer ownership'):transcript.transfers(mixed,contents=[])

    def test_identical_commit_retry_keeps_one_deferred_completed_content(self):
        events,wires,ids,root=trace(repetitions=1)
        repeated=copy.deepcopy(events[-4:]);wire=copy.deepcopy(wires[-1])
        for row in repeated:
            client=row['event'] in (connections.SEND,connections.DELIVER)
            row['connection']['id']=str(UUID(int=90000+(0 if client else 1)))
        wire['connection']=copy.deepcopy(repeated[-2]['connection'])
        events+=repeated;wires.append(wire)
        helper=archive.WireArchiveTest();helper.setUp();self.addCleanup(helper.doCleanups)
        helper.original({'wire.json':wires});reader=helper.open().read('wire.json')
        observed=connections.replay(events,reader,ids,root)['rows'];contents=[]
        result=transcript.transfers(observed,contents=contents)
        self.assertEqual(1,result['exactTransferRetries']);self.assertEqual(1,result['committedTransfers'])
        self.assertEqual(1,len(contents));self.assertEqual(b'original payload',contents[0]['raw'])

    def test_native_source_accounting_uses_same_original_request_and_response_sizes(self):
        from . import test_native_source_resources as native
        data=native.discovery_probe();expected=native.r.replay(*data)
        helper=archive.WireArchiveTest();helper.setUp();self.addCleanup(helper.doCleanups)
        helper.original({'wire.json':data[1]});reader=helper.open().read('wire.json')
        self.assertEqual(expected,native.r.replay(data[0],reader,*data[2:]))


if __name__=='__main__':unittest.main()
