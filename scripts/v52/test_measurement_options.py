import base64
import copy
import unittest
from . import measurement_options as o,measurement_history as h,measurement_samples as samples,token
from .test_measurement_history import fixture,event
from .test_measurement_samples import window_input


class MeasurementOptionsTest(unittest.TestCase):
    def test_closed_defaults_and_five_wait_capacity_variants(self):
        default=o.parameters();self.assertEqual((64,5000,9600),tuple(default[k] for k in ('pendingLimit','waitTimeoutMillis','operationTimeoutMillis')))
        for wait in (0,1000,5000):self.assertEqual(wait,o.parameters('M02',wait=wait)['waitTimeoutMillis'])
        for pending in (4,65):
            value=o.parameters('M03',wait=60000,pending=pending);self.assertEqual(120000,value['operationTimeoutMillis'])
            self.assertEqual(pending,value['pendingLimit'])
        for family,pending,wait in (('M01',65,5000),('M02',4,1000),('M02',64,60000),('M03',64,60000),('M03',65,5000),('other',64,5000)):
            with self.subTest(family=family,pending=pending,wait=wait),self.assertRaisesRegex(ValueError,'undeclared read'):
                o.parameters(family,wait=wait,pending=pending)

    def test_bool_float_extra_fields_and_operation_override_reject(self):
        for change in (lambda v:v.__setitem__('waitTimeoutMillis',True),lambda v:v.__setitem__('pendingLimit',64.0),
                       lambda v:v.__setitem__('extra',1),lambda v:v.__setitem__('operationTimeoutMillis',120000)):
            value=o.parameters();change(value)
            with self.assertRaisesRegex(ValueError,'parameter shape|undeclared read'):o.validate(value)

    def test_zero_progress_rejection_requires_explicit_profile_and_original_zero_wait_invocation(self):
        data=fixture(rejected='PROGRESS_NOT_REACHED');traces,processes,history=data
        minimum=base64.b64encode(token.encode(dict(version=1,groupId='00000000-0000-0000-0000-000000000001',
            historyId='00000000-0000-0000-0000-000000000002',manifestDigest='aa'*32,index=10))).decode()
        history[0]['minimum']=minimum;history[0]['outcome']='REJECTED';history[0]['response']['outcome']='REJECTED'
        for row in traces['node-1']:
            if row['event'] in ('CLIENT_RECEIVED','CLIENT_INVOKE'):row['minimum']=minimum
            if 'policy' in row:row['policy']='AT_LEAST_INDEX'
            if 'preparing' in row:row['preparing']=False
            if row['event']=='REPLICA_READ_INVOKED':row.update(minimum=minimum,waitTimeoutMillis=0)
            if row['event']=='CLIENT_FAILURE':row['outcome']='REJECTED'
        kwargs=dict(minimum_wait_millis=0,allow_progress_not_reached=True)
        result=h.validate(*data,'candidate-minimum',**kwargs);self.assertEqual({'PROGRESS_NOT_REACHED':1},result['reasons']['read'])
        self.assertEqual({'REJECTED':1},result['outcomes']['read'])
        with self.assertRaisesRegex(ValueError,'undeclared zero-wait'):h.validate(*data,'candidate-minimum',minimum_wait_millis=0)
        for change,reason in (
            (lambda d:event(d[0],'REPLICA_READ_INVOKED').__setitem__('waitTimeoutMillis',1000),'options changed'),
            (lambda d:d[2][0]['response'].__setitem__('answer',{}),'response binding'),
            (lambda d:event(d[0],'REPLICA_READ_INVOKED').__setitem__('event','REMOVED'),'ownership transition after response')):
            bad=copy.deepcopy(data);change(bad)
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):h.validate(*bad,'candidate-minimum',**kwargs)
        with self.assertRaisesRegex(ValueError,'wait profile'):h.validate(*data,'candidate-minimum',minimum_wait_millis=1000,allow_progress_not_reached=True)

    def test_positive_wait_mismatch_is_detected_before_classification(self):
        data=fixture(rejected='DEADLINE_EXCEEDED')
        # The original strong setup still uses zero options; changing the declared
        # minimum default never rewrites that already observed strong invocation.
        h.validate(*data,'candidate-explicit-strong',minimum_wait_millis=1000)
        for wait in (-1,True,1001):
            with self.assertRaisesRegex(ValueError,'wait profile'):h.validate(*data,'candidate-explicit-strong',minimum_wait_millis=wait)

    def test_resource_windows_use_declared_pending_bound_not_m01_default(self):
        for pending in (4,65):
            data=window_input()
            for row in data[0]:row['queues']['admissionAvailable']=pending
            for call in data[2]:call['response']['sample']['queues']['admissionAvailable']=pending
            result=samples.windows(*data,pending_limit=pending);self.assertEqual(8,result['wholeSession']['samples'])
            if pending==65:
                with self.assertRaisesRegex(ValueError,'admission bound'):samples.windows(*data)


if __name__=='__main__':unittest.main()
