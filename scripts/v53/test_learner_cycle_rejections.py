"""Small wire/refusal contracts; native originals supply physical authority."""
import base64
import copy
from pathlib import Path
import unittest
import uuid
from unittest.mock import patch
from . import learner_cycle_rejections as r


class LearnerCycleRejectionsTest(unittest.TestCase):
    def setUp(self):
        sample=next(row['value'] for row in r.f.generate()['fixtures'] if row['name']=='FUTURE_RETENTION_INTENT')
        self.expected={};self.wire=[];self.events=[];self.failures=[]
        for i in range(1,17):
            request=copy.deepcopy(sample);request['sequence']=2;request['trace']=str(uuid.UUID(int=i))
            request['recipient']=dict(request['sender'],node='node-2',storage=str(uuid.UUID(int=2)))
            request['payload']['peer']=request['recipient'];request['payload']['certificate']=f'{i:064x}'
            ack=dict(intent=r.e.digest(r.f.canonical(request['payload'])),storage='FUTURE',revision=i,digest=f'{i+16:064x}')
            third=dict(request['sender'],node='node-3',storage=str(uuid.UUID(int=3)))
            self.expected[i]=dict({k:v for k,v in request.items() if k!='trace'},ack=ack,third=third)
            self.add(request,dict(request,sender=request['recipient'],recipient=request['sender'],payload=ack))
            rejected=dict(request,recipient=third,sequence=3)
            failure=dict(node='node-3',kind='FUTURE_RETENTION_INTENT',failure=r.FAILURE,
                         request=r.e.digest(r.f.encode('wire','FUTURE_RETENTION_INTENT',rejected)))
            self.failures.extend([failure.copy() for _ in range(3)])

    def add(self,request,response):
        q=r.f.encode('wire','FUTURE_RETENTION_INTENT',request);a=r.f.encode('wire','FUTURE_RETENTION_ACK',response)
        self.wire.append(dict(request=base64.b64encode(q).decode(),response=base64.b64encode(a).decode(),withheld=False))
        self.events.append(dict(node='node-2',event='WIRE_RESPONSE',request=r.e.digest(q),response=r.e.digest(a)))

    def check(self):
        values={'wire.json':self.wire,'events.json':self.events,'failures.json':self.failures}
        with patch.object(r.d,'read',side_effect=lambda path:values[path.name]):return r.validate(Path('/synthetic'),self.expected)

    def test_zero_and_all_48_exact_refusals_are_not_quorum_acknowledgements(self):
        self.assertEqual(dict(recordingSlots=16,unselectedRefusals=48),self.check())
        self.failures=[];self.assertEqual(dict(recordingSlots=16,unselectedRefusals=0),self.check())

    def test_foreign_owner_kind_reason_request_and_shape_still_fail(self):
        original=copy.deepcopy(self.failures)
        for change in ({'node':'node-2'},{'kind':'PROOF'},{'failure':'java.io.IOException: disk failure'},
                       {'request':'f'*64},{'request':None},{'extra':True}):
            self.failures=copy.deepcopy(original);self.failures[0].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^learner cycles native failures$'):self.check()

    def test_total_bound_cannot_replace_per_request_bound(self):
        self.failures=self.failures[:1]*4
        with self.assertRaisesRegex(ValueError,'^learner cycles native failure retries$'):self.check()
        self.failures=self.failures[:1]*49
        with self.assertRaisesRegex(ValueError,'^learner cycles native failures$'):self.check()

    def test_changed_request_or_ack_cannot_supply_rejection_authority(self):
        original=copy.deepcopy(self.wire)
        for field in ('ballot','sender','selection','ack','withheld'):
            self.wire=copy.deepcopy(original);row=self.wire[0]
            if field=='withheld':row['withheld']=True
            else:
                key='response' if field=='ack' else 'request';kind='FUTURE_RETENTION_ACK' if key=='response' else 'FUTURE_RETENTION_INTENT'
                value=r.f.decode(base64.b64decode(row[key]),'wire',kind)
                if field=='ballot':value['ballot']['counter']+=1
                elif field=='sender':value['sender']['storage']=str(uuid.UUID(int=4))
                else:value['payload']['intent' if field=='ack' else 'selection']='f'*64
                row[key]=base64.b64encode(r.f.encode('wire',kind,value)).decode()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^learner cycles exact recording exchange$'):self.check()

    def test_missing_successful_recording_or_response_event_rejects(self):
        self.events.pop()
        with self.assertRaisesRegex(ValueError,'^learner cycles recording response event$'):self.check()
        self.wire.pop()
        with self.assertRaisesRegex(ValueError,'^learner cycles complete recording exchanges$'):self.check()

    def test_identical_ack_retry_is_bounded_and_cannot_change_trace(self):
        request=r.f.decode(base64.b64decode(self.wire[0]['request']),'wire','FUTURE_RETENTION_INTENT')
        response=r.f.decode(base64.b64decode(self.wire[0]['response']),'wire','FUTURE_RETENTION_ACK')
        self.add(request,response);self.add(request,response);self.check()
        self.add(request,response)
        with self.assertRaisesRegex(ValueError,'^learner cycles identical recording retries$'):self.check()
        self.wire.pop();self.events.pop();request['trace']=response['trace']=str(uuid.UUID(int=30))
        self.wire.pop();self.events.pop();self.add(request,response)
        with self.assertRaisesRegex(ValueError,'^learner cycles identical recording retries$'):self.check()

    def test_another_slot_cannot_reuse_a_trace_or_add_a_certificate(self):
        request=r.f.decode(base64.b64decode(self.wire[1]['request']),'wire','FUTURE_RETENTION_INTENT')
        response=r.f.decode(base64.b64decode(self.wire[1]['response']),'wire','FUTURE_RETENTION_ACK')
        self.wire.pop(1);self.events.pop(1);request['trace']=response['trace']=str(uuid.UUID(int=1));self.add(request,response)
        with self.assertRaisesRegex(ValueError,'^learner cycles distinct recording traces$'):self.check()
        self.wire.pop();self.events.pop();request['payload']['certificate']='f'*64;self.add(request,response)
        with self.assertRaisesRegex(ValueError,'^learner cycles recording original slot$'):self.check()


if __name__=='__main__':unittest.main()
