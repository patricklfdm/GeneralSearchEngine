"""Tail corruption must fail against the complete original transfer bytes."""
import base64
import unittest
from uuid import UUID

from . import queue_completion_evidence as q


def transcript(parts):
    basis=b'original-joint-basis';image=b''.join(parts);chunk=len(parts[0])
    basis_id=str(UUID(int=1));image_id=str(UUID(int=2))
    requests={};answers={};frames={};session={}

    def append(kind,transfer,content,reply_kind,*,data=None,offset=0):
        seq=len(session)+1;digest=q.queue.sha(content)
        p=dict(id=transfer,digest=digest)
        if kind=='CHUNK':p.update(action='REQUEST',offset=offset,bytes='')
        if reply_kind=='SOURCE_OFFER':
            reply=dict(id=transfer,digest=digest,bytes=len(content),kind='RECORD' if transfer==basis_id else 'APPLICATION')
        elif reply_kind=='CHUNK':
            reply=dict(id=transfer,action='DATA',offset=offset,digest=q.queue.sha(data),bytes=base64.b64encode(data).decode('ascii'))
        else:reply=dict(p)
        key='request-'+str(seq);answer='response-'+str(seq)
        session[seq]=key;requests[key]=(kind,dict(sender='reader',payload=p),0)
        answers[key]=answer;frames[answer]=(reply_kind,dict(payload=reply),0)

    append('CHUNK',basis_id,basis,'SOURCE_OFFER')
    append('CHUNK',basis_id,basis,'CHUNK',data=basis)
    append('TRANSFER_COMMIT',basis_id,basis,'TRANSFER_COMMIT')
    append('CHUNK',image_id,image,'SOURCE_OFFER')
    offset=0
    for data in parts:
        append('CHUNK',image_id,image,'CHUNK',data=data,offset=offset);offset+=len(data)
    append('TRANSFER_COMMIT',image_id,image,'TRANSFER_COMMIT')
    return session,requests,answers,frames,basis,image,chunk


class QueueCompletionChunksTest(unittest.TestCase):
    def value(self,chunks=5,last=17):
        return transcript([bytes([i])*4096 for i in range(chunks-1)]+[b'z'*last])

    def test_two_five_six_and_sixteen_chunk_transfers_include_short_or_exact_tail(self):
        for count in (2,5,6,16):
            for last in (1,17,4096):
                with self.subTest(count=count,last=last):q.replay_session(*self.value(count,last))

    def test_two_chunk_terminal_cannot_close_a_five_chunk_original(self):
        value=self.value();session,requests,answers,frames,*_=value
        session.pop(7);session.pop(8);session.pop(9)
        session[7]=session.pop(10) # The old producer committed after only two chunks.
        with self.assertRaisesRegex(ValueError,'^queue completion session sequence$'):q.replay_session(*value)

    def test_missing_extra_and_reordered_tail_requests_are_rejected(self):
        for mode in ('missing','extra','reordered'):
            value=self.value();session=value[0]
            if mode=='missing':session.pop(8)
            elif mode=='extra':session[11]=session[10]
            else:session[7],session[8]=session[8],session[7]
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'queue completion (session sequence|exact request)'):
                q.replay_session(*value)

    def test_late_tail_bytes_digest_offset_and_truncation_are_verified(self):
        for mode in ('bytes','digest','offset','truncated','empty','kind'):
            value=self.value();session,requests,answers,frames,*_=value
            key=answers[session[9]];kind,answer,size=frames[key];payload=answer['payload']
            if mode=='bytes':payload['bytes']=base64.b64encode(b'wrong').decode('ascii')
            elif mode=='digest':payload['digest']='0'*64
            elif mode=='offset':payload['offset']-=4096
            elif mode in ('truncated','empty'):
                data=b'z'*16 if mode=='truncated' else b''
                payload.update(bytes=base64.b64encode(data).decode('ascii'),digest=q.queue.sha(data))
            else:frames[key]=('TRANSFER_COMMIT',answer,size)
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'^queue completion original content$'):q.replay_session(*value)

    def test_terminal_cannot_switch_image_transfer_or_reader(self):
        for field in ('id','digest','sender'):
            value=self.value();session,requests,*_=value;request=requests[session[10]][1]
            if field=='sender':request[field]='another-reader'
            else:request['payload'][field]=str(UUID(int=3)) if field=='id' else '0'*64
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^queue completion exact request$'):q.replay_session(*value)

    def test_single_chunk_basis_scope_is_explicit(self):
        value=list(self.value());value[4]=b'basis'*(value[-1]+1)
        with self.assertRaisesRegex(ValueError,'^queue completion basis extent$'):q.replay_session(*value)

    def test_rehearsal_flags_cannot_select_formal_qualification(self):
        for rehearsal,multi in ((False,True),(1,False),(True,1)):
            with self.subTest(rehearsal=rehearsal,multi=multi),self.assertRaisesRegex(ValueError,'^queue completion replay profile$'):
                q.rehearsal_profile(rehearsal,multi)

    def test_multichunk_rehearsal_cannot_fill_the_formal_resource_slot(self):
        from . import queue_completion_run as run
        from .test_queue_completion_run import replay
        value=replay();value['original'].update(scope='multi-chunk-completion-rehearsal',
            capacityRefusals=0,queuePressureQualified=False)
        with self.assertRaisesRegex(ValueError,'^queue-completion admission original pressure and native completion$'):
            run.check_result(value,run.PROFILE)

    def test_invalid_chunk_extents_are_rejected(self):
        for image,chunk in ((b'x'*8192,True),(b'x'*8192,0),(b'x'*8192,4096.0),(b'x'*4096,4096)):
            with self.subTest(chunk=chunk),self.assertRaisesRegex(ValueError,'^queue completion image extent$'):
                q.image_commit_sequence(image,chunk)


if __name__=='__main__':unittest.main()
