"""Controller schedules with original futures and virtual time, not protocol proof."""
import base64
from concurrent.futures import Future
import json
from pathlib import Path
import tempfile
import unittest
from . import measurement_minimum as m,measurement_model as model,token


class World:
    def __init__(self,case,*,fault=None):
        self.case=case;self.plan=m.profile(case);self.fault=fault;self.now=10_000_000_000
        self.leader='node-2';self.index=7;self.sequence=1;self.history=[];self.pending=[];self.reads=[];self.admissions={n:0 for n in ('node-1','node-2','node-3')}
        self.token=base64.b64encode(token.encode(dict(version=1,groupId='00000000-0000-0000-0000-000000000001',
            historyId='00000000-0000-0000-0000-000000000002',manifestDigest='ab'*32,index=self.index))).decode()
        self.workers={node:Consumer(self,node) for node in self.admissions}
    def clock(self):self.now+=1;return self.now
    def sleep(self,seconds):self.now+=round(seconds*1e9)
    def finish(self,future,call,outcome='SUCCESS',**extra):
        response=dict(opId=call['opId'],kind=call['kind'],outcome=outcome,**extra)
        call.update(endNanos=self.clock(),response=response,outcome=outcome);future.set_result(response)
    def run(self,root):return m.observe(root,self.workers,self.history,self.case,clock=self.clock,sleep=self.sleep)


class Consumer:
    def __init__(self,world,node):self.world=world;self.node=node;self.serial=0
    def call(self,kind,**values):
        result=self.submit(kind,**values)[1].result()
        if result['outcome']!='SUCCESS':raise ValueError('injected public failure')
        return result
    def submit(self,kind,**values):
        w=self.world;self.serial+=1;identity=self.node+'-'+str(self.serial);future=Future()
        read=kind=='read' and not values.get('setupToken')
        if read and w.fault=='disconnect' and len(w.reads)==2:raise OSError('injected disconnect')
        call=dict(opId=identity,node=self.node,kind=kind,startNanos=w.clock(),**values);w.history.append(call)
        if read:
            w.reads.append(call);excess=len(w.reads)>w.plan['readCount']
            if excess:
                w.finish(future,call,'NOT_APPLICABLE' if w.fault!='accept-excess' else 'SUCCESS',reasonCode='CAPACITY_EXCEEDED')
            elif w.fault=='early-rejection':w.finish(future,call,'NOT_APPLICABLE',reasonCode='NOT_READY')
            else:
                w.admissions[self.node]+=1
                if w.plan['relation']!='above':w.finish(future,call)
                elif not w.plan['parameters']['waitTimeoutMillis']:w.finish(future,call,'REJECTED',reasonCode='PROGRESS_NOT_REACHED')
                elif w.fault=='settled-waiter':w.finish(future,call,'NOT_APPLICABLE',reasonCode='DEADLINE_EXCEEDED')
                else:w.pending.append((future,call))
            return identity,future
        extra={}
        if kind=='update':
            w.sequence+=1
            if w.sequence==5:
                w.index+=1
                for f,c in w.pending:w.finish(f,c)
                w.pending=[]
                if w.fault=='write-failure':w.finish(future,call,'INDETERMINATE',reasonCode='QUORUM_UNAVAILABLE');return identity,future
        elif kind=='read':extra=dict(token=w.token,sequence=4)
        elif kind=='status':
            extra=dict(state='LEADER_READY' if self.node==w.leader else 'FOLLOWER',publishedIndex=w.index,sequence=w.sequence)
            if w.fault=='changed-role' and w.sequence==4 and self.node=='node-3':extra['state']='LEADER_READY'
            if w.fault=='unplanned-progress' and w.reads:extra['publishedIndex']+=1
        elif kind=='probe':
            count=len(w.pending) if self.node in (w.leader,'node-3') else 0
            if self.node!=('node-2' if w.plan['family']=='M03' else 'node-3'):count=0
            p=w.plan['parameters']['pendingLimit']
            extra=dict(queues=dict(readAdmissionsObserved=w.admissions[self.node],recoveryFloorObserved=0 if w.fault=='missing-floor' else w.index,
                readsOwned=count,readsWaiting=count,readsAlarms=count,readsCaptured=0,readsSettling=0,readsMarker=0,admissionAvailable=p-count))
            if w.fault=='missing-reserve' and count:extra['queues']['admissionAvailable']=0
        w.finish(future,call,**extra);return identity,future


class MeasurementMinimumTest(unittest.TestCase):
    def test_all_eleven_exact_schedules_keep_original_requests_and_gates(self):
        for case in m.CASES:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);w=World(case);result=w.run(root);plan=w.plan
                self.assertEqual('OBSERVED',result['status']);self.assertFalse(result['qualifiedMeasurement']);self.assertFalse(result['paidCloud'])
                scenario=json.loads((root/'scenario.json').read_text());observed=json.loads((root/'observed.json').read_text())
                target='node-2' if plan['family']=='M03' else 'node-3';self.assertEqual(target,scenario['readTarget'])
                reads=plan['readCount']+(plan['family']=='M03');self.assertEqual(reads,len(w.reads));self.assertFalse(w.pending)
                self.assertEqual([model.query(i) for i in range(reads)],[c['query'] for c in w.reads])
                self.assertTrue(all(c['node']==target and c['minimum']==scenario['minimum'] for c in w.reads))
                decoded=token.decode(base64.b64decode(scenario['minimum']));self.assertEqual(7+{'below':-1,'equal':0,'above':1}[plan['relation']],decoded['index'])
                updates=[c for c in w.history if c['kind']=='update'];self.assertEqual(3+plan['releaseUpdate'],len(updates))
                self.assertEqual([c['document'] for c in model.program() if c['kind']=='update'][:len(updates)],[c['document'] for c in updates])
                if plan['releaseUpdate']:self.assertGreaterEqual(scenario['releaseOfferNanos']-scenario['gateNanos'],plan['releaseDelayNanos'])
                self.assertTrue(observed['drained']);self.assertEqual(0,observed['unobserved'])
                self.assertTrue(all(c['completionStatus']=='OBSERVED' and c['status']=='DISPATCHED' for c in observed['operations']))
                self.assertEqual(3,sum(c['kind']=='sample-start' for c in w.history));self.assertEqual(3,sum(c['kind']=='sample-stop' for c in w.history))

    def test_zero_wait_rejections_are_retained_and_do_not_trigger_progress_update(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('m02-above-0');w.run(directory)
            self.assertEqual({'PROGRESS_NOT_REACHED'},{c['response']['reasonCode'] for c in w.reads})
            self.assertEqual(3,sum(c['kind']=='update' for c in w.history))

    def test_saturation_requires_owned_waiters_and_the_reserved_slot(self):
        for fault,reason in [('settled-waiter','settled before full gate'),('missing-reserve','requests not admitted'),('accept-excess','excess was not rejected')]:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                w=World('m03-p4',fault=fault)
                with self.assertRaisesRegex(ValueError,reason):w.run(directory)
                self.assertEqual(3,sum(c['kind']=='update' for c in w.history))
                self.assertEqual('FAIL',json.loads((Path(directory)/'controller.json').read_text())['status'])

    def test_partial_submission_preserves_calls_and_undeclared_suffix_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('m02-above-5000',fault='disconnect')
            with self.assertRaisesRegex(OSError,'injected disconnect'):w.run(directory)
            rows=json.loads((Path(directory)/'observed.json').read_text())['operations']
            self.assertEqual(['DISPATCHED','DISPATCHED','DISPATCH_FAILED'],[c['status'] for c in rows[:3]])
            self.assertTrue(all(c['status']=='NOT_DISPATCHED' for c in rows[3:]));self.assertEqual(2,len(w.reads))

    def test_all_early_rejections_fail_fast_without_releasing_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('m02-above-1000',fault='early-rejection');start=w.now
            with self.assertRaisesRegex(ValueError,'all original calls completed'):w.run(directory)
            self.assertLess(w.now-start,1_000_000_000);self.assertEqual(30,len(w.reads))
            self.assertEqual(3,sum(c['kind']=='update' for c in w.history))

    def test_missing_floor_changed_role_and_unplanned_publication_reject(self):
        for fault,reason in [('missing-floor','baseline recovery floor'),('changed-role','prepared target changed'),('unplanned-progress','unplanned publication progress')]:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as directory:
                w=World('m02-above-1000',fault=fault)
                with self.assertRaisesRegex(ValueError,reason):w.run(directory)
                self.assertEqual(3,sum(c['kind']=='update' for c in w.history))
                self.assertLess(max(sum(c['node']==n for c in w.history) for n in w.workers),4096)

    def test_uncertain_writer_is_not_resubmitted(self):
        with tempfile.TemporaryDirectory() as directory:
            w=World('m03-p4',fault='write-failure')
            with self.assertRaisesRegex(ValueError,'reserved writer/waiter did not complete'):w.run(directory)
            rows=json.loads((Path(directory)/'observed.json').read_text())['operations']
            self.assertEqual('INDETERMINATE',rows[-1]['response']['outcome']);self.assertEqual(4,sum(c['kind']=='update' for c in w.history))

    def test_profile_and_derived_token_are_closed(self):
        for value in ('m02-above-10','m03-p64','M02',None):
            with self.assertRaisesRegex(ValueError,'minimum case'):m.profile(value)
        carried=World('m02-above-0').token
        for index,relation in [(True,'above'),(6,'above'),(7,'other')]:
            with self.assertRaisesRegex(ValueError,'baseline index/relation'):m.lower_bound(carried,index,relation)
        with self.assertRaisesRegex(ValueError,'INVALID_TOKEN'):m.lower_bound(carried,(1<<63)-1,'above')
        for relation in ('below','equal','above'):
            value=token.decode(base64.b64decode(m.lower_bound(carried,7,relation)));original=token.decode(base64.b64decode(carried))
            self.assertEqual({k:v for k,v in original.items() if k!='index'},{k:v for k,v in value.items() if k!='index'})


if __name__=='__main__':unittest.main()
