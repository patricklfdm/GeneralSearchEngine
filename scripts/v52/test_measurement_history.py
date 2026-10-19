"""Adversarial lifecycle fixtures; these are not physical authority evidence."""
import copy
import unittest
from . import measurement_history as h


def fixture(*,rejected=None,admitted=True,invocation=True,release_first=False):
    processes=[dict(node=f'node-{i}',pid=i,generation=1,exitCode=0) for i in (1,2,3)]
    request=dict(opId='read-1',kind='read',query=dict(kind='get',id=1))
    traces={p['node']:[] for p in processes};ordinal=0
    def row(event,**data):
        nonlocal ordinal
        ordinal+=1
        value=dict(node='node-1',pid=1,generation=1,order=ordinal,localNanos=ordinal*100,
                   groupId='group',manifestDigest='digest',event=event,**data)
        traces['node-1'].append(value);return value
    row('CLIENT_RECEIVED',**request)
    client_rejected=rejected=='RejectedExecutionException'
    if not client_rejected:row('CLIENT_INVOKE',**request)
    invocation=invocation and not client_rejected
    if invocation:row('REPLICA_READ_INVOKED',opId='read-1',readId=1,policy='LEADER_STRONG',minimum='',waitTimeoutMillis=0,deadlineNanos=500)
    admitted=admitted and invocation
    common=dict(readId=1,policy='LEADER_STRONG',deadlineNanos=500,barrierEpoch=1,barrierIndex=1,
                preparing=False,cancelled=False,completionReturned=False,cancelling=0,marker=0,highWater=1)
    if admitted:row('REPLICA_READ_ADMITTED',**dict(common,preparing=True),phase='QUEUED',owned=1,waiting=1,captured=0,settling=0,alarms=1)
    if not rejected:
        for event in ('REPLICA_READ_CAPTURE_VALIDATED','REPLICA_READ_CAPTURED'):
            row(event,**common,phase='CAPTURED',owned=1,waiting=0,captured=1,settling=0,alarms=0,index=1,sequence=1)
        row('CLIENT_CALLBACK_BEGIN',opId='read-1',sequence=1);row('CLIENT_CALLBACK_END',opId='read-1',sequence=1)
        row('REPLICA_READ_RELEASED',**common,phase='CAPTURED',owned=1,waiting=0,captured=1,settling=0,alarms=0,index=1,sequence=1)
    if admitted:row('REPLICA_READ_SETTLING',**common,phase='SETTLING',owned=1,waiting=0,captured=0,settling=1,alarms=0)
    def release():
        if admitted:row('REPLICA_READ_OWNERSHIP_RELEASED',**dict(common,completionReturned=True),phase='SETTLING',owned=0,waiting=0,captured=0,settling=0,alarms=0)
    if release_first:release()
    outcome='SUCCESS' if not rejected else 'VALIDATION_FAILURE' if client_rejected else 'NOT_APPLICABLE'
    response=dict(opId='read-1',kind='read',outcome=outcome,receivedNanos=90,apiStartNanos=90 if client_rejected else 190,apiEndNanos=(ordinal+1)*100-1)
    if rejected:response.update(reasonCode=rejected,reason='fixture rejection '+rejected)
    else:response.update(answer=dict(id=1,value='fixture'))
    row('CLIENT_SUCCESS' if not rejected else 'CLIENT_FAILURE',**response)
    if not release_first:release()
    queues=dict(admissionAvailable=64,readsOwned=0,readsWaiting=0,readsCaptured=0,readsSettling=0,readsAlarms=0,readsMarker=0,readsHighWater=int(admitted))
    row('CLIENT_IDLE',queues=queues);row('CLOSED')
    for p in processes[1:]:
        traces[p['node']]=[dict(p,order=i,localNanos=i*100,event=event,groupId='group',manifestDigest='digest',**values)
            for i,event,values in ((1,'CLIENT_IDLE',dict(queues=dict(queues,readsHighWater=0))),(2,'CLOSED',{}))]
    history=[dict(request,node='node-1',pid=1,generation=1,startNanos=1,endNanos=10000,outcome=outcome,response=response)]
    return traces,processes,history


def event(traces,name):return next(row for row in traces['node-1'] if row['event']==name)


class MeasurementHistoryTest(unittest.TestCase):
    def check(self,data):return h.validate(*data,'candidate-explicit-strong')

    def test_complete_callback_and_permit_lifetime_in_both_completion_orders(self):
        # Completion can return before the consumer attaches whenComplete.
        for first in (False,True):
            result=self.check(fixture(release_first=first))
            self.assertEqual({'SUCCESS':1},result['outcomes']['read'])
            self.assertEqual(dict(admitted=1,highWater=1,ownedAtClose=0),result['resources']['node-1'])
            self.assertFalse(result['qualifiedMeasurement'])

    def test_realistic_rejection_paths_do_not_become_success(self):
        for reason,admitted,invocation in (('NOT_READY',False,False),('CAPACITY_EXCEEDED',False,True),
                                         ('DEADLINE_EXCEEDED',True,True),('STALE_EPOCH',True,True),
                                         ('RejectedExecutionException',False,False)):
            with self.subTest(reason=reason):
                result=self.check(fixture(rejected=reason,admitted=admitted,invocation=invocation))
                self.assertNotIn('SUCCESS',result['outcomes']['read'])
                expected='CLIENT_REJECTED' if reason=='RejectedExecutionException' else reason
                self.assertEqual({expected:1},result['reasons']['read'])

    def test_all_transient_reasons_are_observations_not_unproven_causal_claims(self):
        for reason in h.TRANSIENT:
            result=self.check(fixture(rejected=reason,admitted=False,invocation=False))
            self.assertEqual({reason:1},result['reasons']['read'])

    def test_duplicate_controller_call_cannot_be_hidden_by_a_dictionary(self):
        data=fixture();data[2].append(copy.deepcopy(data[2][0]))
        with self.assertRaisesRegex(ValueError,'duplicate/invalid operation'):self.check(data)

    def test_omitted_call_or_unknown_wire_call_rejects(self):
        data=fixture();data[2].clear()
        with self.assertRaisesRegex(ValueError,'unrecorded/late'):self.check(data)

    def test_duplicate_api_invocation_is_not_a_business_retry(self):
        data=fixture();rows=data[0]['node-1'];second=copy.deepcopy(event(data[0],'CLIENT_INVOKE'))
        second['order']=3;second['localNanos']=300
        for row in rows[2:]:row['order']+=1;row['localNanos']+=100
        rows.insert(2,second)
        with self.assertRaisesRegex(ValueError,'duplicate/unreceived invocation'):self.check(data)

    def test_missing_receive_invoke_response_and_close_reject(self):
        for name in ('CLIENT_RECEIVED','CLIENT_INVOKE','CLIENT_SUCCESS','CLOSED'):
            with self.subTest(event=name):
                data=fixture();event(data[0],name)['event']='REMOVED'
                with self.assertRaises(ValueError):self.check(data)

    def test_failed_read_cannot_carry_answer_or_expose_callback(self):
        data=fixture(rejected='NOT_READY',admitted=False,invocation=False)
        response=event(data[0],'CLIENT_FAILURE');response['answer']={};data[2][0]['response']['answer']={}
        with self.assertRaisesRegex(ValueError,'failed call carried result'):self.check(data)
        data=fixture();response=event(data[0],'CLIENT_SUCCESS');response['event']='CLIENT_FAILURE';response.pop('answer')
        response.update(outcome='NOT_APPLICABLE',reasonCode='NOT_READY',reason='changed')
        data[2][0].update(outcome='NOT_APPLICABLE',response={k:v for k,v in response.items() if k not in h.trace.META})
        with self.assertRaisesRegex(ValueError,'rejected read exposed view'):self.check(data)

    def test_fatal_or_unknown_error_is_not_an_ordinary_measurement_rejection(self):
        for reason in ('STORAGE_FAILURE','CLOSED','INTEGRITY_FAILURE','INVALID_TOKEN','ViewBug'):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,'undeclared read failure'):
                self.check(fixture(rejected=reason,admitted=False,invocation=False))

    def test_deadline_failure_must_not_precede_observed_deadline(self):
        data=fixture(rejected='DEADLINE_EXCEEDED',admitted=False)
        event(data[0],'REPLICA_READ_INVOKED')['deadlineNanos']=100000
        with self.assertRaisesRegex(ValueError,'before deadline'):self.check(data)

    def test_pending_or_crashed_process_requires_different_qualification(self):
        data=fixture();data[2][0]['outcome']='PENDING'
        with self.assertRaisesRegex(ValueError,'incomplete controller'):self.check(data)
        data=fixture();data[1][0]['exitCode']=-9
        with self.assertRaisesRegex(ValueError,'clean processes'):self.check(data)

    def test_missing_reordered_or_early_ownership_release_rejects(self):
        for name,key,value,reason in (
                ('REPLICA_READ_ADMITTED','event','REMOVED','without queued ownership'),
                ('REPLICA_READ_OWNERSHIP_RELEASED','completionReturned',False,'premature ownership'),
                ('REPLICA_READ_OWNERSHIP_RELEASED','preparing',True,'premature ownership'),
                ('REPLICA_READ_OWNERSHIP_RELEASED','event','REMOVED','incomplete idle'),
                ('REPLICA_READ_RELEASED','event','REMOVED','settling before view release')):
            with self.subTest(name=name,key=key):
                data=fixture();event(data[0],name)[key]=value
                with self.assertRaisesRegex(ValueError,reason):self.check(data)

    def test_atomic_counts_alarms_peak_and_final_counter_presence_are_checked(self):
        for name,key,value in (
                ('REPLICA_READ_ADMITTED','owned',2),('REPLICA_READ_CAPTURE_VALIDATED','alarms',1),
                ('REPLICA_READ_SETTLING','highWater',2),('REPLICA_READ_SETTLING','captured',1),
                ('REPLICA_READ_ADMITTED','marker',2),('REPLICA_READ_ADMITTED','owned',True)):
            with self.subTest(name=name,key=key):
                data=fixture();event(data[0],name)[key]=value
                with self.assertRaisesRegex(ValueError,'accounting differs'):self.check(data)
        data=fixture();event(data[0],'CLIENT_IDLE')['queues'].pop('readsOwned')
        with self.assertRaisesRegex(ValueError,'counters missing'):self.check(data)

    def test_nonatomic_hook_counts_do_not_pretend_to_be_atomic_cuts(self):
        data=fixture()
        # A different request can admit/settle between counts() and trace.write().
        for name in ('REPLICA_READ_CAPTURED','REPLICA_READ_RELEASED'):event(data[0],name)['owned']=2
        self.check(data)

    def test_wrong_policy_duplicate_runtime_call_and_changed_request_reject(self):
        for name,key,value,reason in (
                ('REPLICA_READ_INVOKED','policy','STALE_ALLOWED','policy/options'),
                ('REPLICA_READ_INVOKED','waitTimeoutMillis',5000,'policy/options'),
                ('CLIENT_INVOKE','query',dict(kind='get',id=2),'request differs'),
                ('REPLICA_READ_SETTLING','deadlineNanos',9999,'changed request')):
            with self.subTest(name=name,key=key):
                data=fixture();event(data[0],name)[key]=value
                with self.assertRaisesRegex(ValueError,reason):self.check(data)

    def test_mutation_failure_classification_is_not_a_claim_of_rollback(self):
        for outcome in ('NOT_SUBMITTED','INDETERMINATE'):
            response=dict(outcome=outcome,reasonCode='QUORUM_UNAVAILABLE',reason='fixture')
            self.assertEqual('QUORUM_UNAVAILABLE',h.failure(dict(kind='update'),response,None,False,False,'candidate-stale'))
        with self.assertRaisesRegex(ValueError,'mutation/control'):
            h.failure(dict(kind='update'),dict(outcome='NOT_APPLICABLE',reasonCode='NOT_READY',reason='fixture'),None,False,False,'candidate-stale')


if __name__=='__main__':unittest.main()
