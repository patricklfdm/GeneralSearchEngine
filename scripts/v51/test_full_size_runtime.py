"""Adversarial public-history tests. Synthetic records are not execution evidence."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import full_size_runtime_evidence as e, performance_fixtures as fixtures, cloud_workload_contract as cloud


class FullSizeRuntimeTest(unittest.TestCase):
    def test_all_boundary_mutations_stay_in_frozen_rich_corpus(self):
        from .full_size_runtime import mutation
        observed=[]
        for ordinal in range(1,512):
            args=mutation(ordinal);doc=e.m.document(args['key'],args['revision'])
            self.assertEqual(doc,e.m.decode_document(e.m.encode_document(doc)))
            observed.append((args['key'],args['revision']))
        self.assertEqual(511,len(set(observed)))
        for ordinal in (0,512):
            with self.assertRaises(ValueError):mutation(ordinal)

    def sample(self):
        program=[cloud.call('UPDATE',[1],0),cloud.call('GET',[1],0),cloud.call('UPDATE',[2],0)]
        fixture=fixtures.generate(e.plan.load(),program=program)
        projected=e.projection.project_cloud(fixture['manifest'],fixture['genesis'],fixture['votes'])
        snapshots={i:e.fmt.inspect(raw,'SNAPSHOT') for i,raw in enumerate(fixture['snapshots'],1)}
        published={2:(snapshots[2],3),3:(snapshots[3],7)}
        proof=e.fmt.inspect(e.raw(snapshots[3]['terminalProof']),'PROOF')
        votes={(proof['epoch'],proof['incarnation'],3,proof['entryDigest']):6}
        promise=(proof['epoch'],proof['incarnation'])
        history=[dict(opId='write',kind='update',node='node-1',generation=1,pid=42,startNanos=0,endNanos=100,outcome='SUCCESS',key=1,revision=1),
                 dict(opId='read',kind='read',node='node-1',generation=1,pid=42,startNanos=0,endNanos=100,outcome='SUCCESS',documents=e.documents(projected['states'][3])),
                 dict(opId='crash',kind='update',node='node-1',generation=1,pid=42,startNanos=0,endNanos=None,outcome='PENDING',disconnectNanos=100,key=2,revision=1)]
        rows=[]
        def row(event,order,**values):rows.append(dict(event=event,order=order,localNanos=order,node='node-1',pid=42,generation=1,**values))
        def invoke(index,order):row('CLIENT_INVOKE',order,**{k:v for k,v in history[index].items() if k in ('opId','kind','key','revision')})
        invoke(0,1);row('CLIENT_RESULT',4,opId='write',kind='update',outcome='SUCCESS')
        invoke(1,5);row('PUBLIC_READ_INVOKE',5.5,opId='read',readId=1)
        for event,order in [('READ_CAPTURE_VALIDATED',8),('READ_CAPTURED',9),('READ_RELEASED',10)]:
            row(event,order,readId=1,index=3,epoch=proof['epoch'],sequence=snapshots[3]['applicationSequence'])
        row('CLIENT_RESULT',11,opId='read',kind='read',outcome='SUCCESS',documents=history[1]['documents'])
        invoke(2,12)
        return history,rows,projected,published,votes,promise

    def audit(self,sample):
        history,rows,projected,published,votes,promise=sample
        calls=e.Calls(history,{'uncertainOpId':'crash'})
        for row in rows:calls.event('node-1',row,projected,published,votes,promise)
        calls.finish();return calls

    def test_chosen_crash_has_no_fabricated_success(self):
        audit=self.audit(self.sample());self.assertEqual(2,len(audit.mutations));self.assertEqual(1,len(audit.read_barriers))
        sample=self.sample();sample[0][-1]['outcome']='SUCCESS'
        with self.assertRaisesRegex(ValueError,'invented crash response'):self.audit(sample)

    def test_resealed_controller_and_worker_answer_from_other_cut_fails(self):
        sample=self.sample();wrong=e.documents(sample[2]['states'][4]);self.assertNotEqual(wrong,sample[0][1]['documents'])
        sample[0][1]['documents']=wrong;next(r for r in sample[1] if r['event']=='CLIENT_RESULT' and r['kind']=='read')['documents']=wrong
        with self.assertRaisesRegex(ValueError,'captured answer'):self.audit(sample)

    def test_missing_release_stale_capture_and_old_barrier_fail(self):
        sample=self.sample();sample[1][:]=[r for r in sample[1] if r['event']!='READ_RELEASED']
        with self.assertRaisesRegex(ValueError,'before read release'):self.audit(sample)
        sample=list(self.sample());sample[-1]=(99,sample[-1][1])
        with self.assertRaisesRegex(ValueError,'stale capture'):self.audit(sample)
        sample=self.sample();sample[4][next(iter(sample[4]))]=1
        with self.assertRaisesRegex(ValueError,'fresh read barrier'):self.audit(sample)

    def test_reordered_write_missing_invocation_and_changed_release_fail(self):
        for event,field,value,reason in [('CLIENT_RESULT','order',2,'before own publication'),
                ('PUBLIC_READ_INVOKE','opId','write','read identity'),('READ_RELEASED','index',4,'changed read release')]:
            with self.subTest(event=event):
                sample=self.sample();next(r for r in sample[1] if r['event']==event)[field]=value
                with self.assertRaisesRegex(ValueError,reason):self.audit(sample)

    def test_read_ids_are_scoped_to_original_process_generation(self):
        sample=self.sample();self.audit(sample)
        for row in sample[1]:
            if row['event']=='READ_RELEASED':row['generation']=2
        with self.assertRaisesRegex(ValueError,'unowned release'):self.audit(sample)

    def test_refused_reads_still_consume_the_auxiliary_attempt_budget(self):
        sample=self.sample();history=sample[0]
        for i in range(8):history.append(dict(history[1],opId='refused-'+str(i),outcome='NOT_APPLICABLE'))
        with self.assertRaisesRegex(ValueError,'auxiliary read attempt bound'):e.Calls(history,{'uncertainOpId':'crash'})

    def test_whole_transfer_includes_pre_offer_work_and_requires_probe(self):
        # Synthetic codec stand-ins isolate the clock/range algorithm, not execution evidence.
        encode=lambda value:base64.b64encode(e.m.canonical(value)).decode()
        image=b'x'*64;snapshot=base64.b64encode(b'snapshot').decode()
        offer=dict(transferId='transfer',imageBytes=len(image),imageDigest=image[16:48].hex(),response=False)
        chunk=dict(transferId='transfer',offset=0,maxChunkBytes=4096,chunk=base64.b64encode(image).decode(),action='DATA')
        install=dict(transferId='transfer',imageDigest=offer['imageDigest'],response=False)
        def message(kind,payload):return dict(recipient='node-2',type=kind,payload=payload,epoch=2,incarnationId='epoch',traceId='trace',proposer='node-1')
        def event(kind,payload,time,response=None):
            row=dict(event='REQUEST' if response is None else 'RECEIVED',pid=1,localNanos=time,request=encode(message(kind,payload)))
            if response is not None:row['frame']=encode(message(kind,response))
            return row
        rows=[event('AUTHORITY_STATUS_PROBE',{},0),event('SNAPSHOT_OFFER',offer,1_000_000_000),
              event('SNAPSHOT_CHUNK',chunk,2_000_000_000,dict(chunk,action='ACK',chunk='')),
              event('REJOIN_INSTALL',install,3_000_000_000,dict(install,response=True))]
        traces={'node-1':rows,'node-2':[dict(event='REJOIN_INSTALLED',transferId='transfer',snapshot=snapshot)]}
        with patch.object(e.fmt,'wire',side_effect=lambda data,_:e.m.strict_json(data)), \
             patch.object(e.fmt,'contextual_frame',return_value={'snapshot':snapshot}), \
             patch.object(e.fmt,'inspect',return_value={'anchors':[None]*512}):
            self.assertEqual(2_000_000_000,e.transfer(traces,{},'node-2')['elapsedNanos'])
            rows[0]['localNanos']=-7_000_000_000
            with self.assertRaisesRegex(ValueError,'whole transfer deadline'):e.transfer(traces,{},'node-2')
            rows.pop(0)
            with self.assertRaisesRegex(ValueError,'without authority probe'):e.transfer(traces,{},'node-2')

    def test_invalid_original_cannot_be_accepted_as_negative_evidence(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')):
            with self.assertRaisesRegex(ValueError,'invalid original'):e.negatives('/unused')

    def test_relocation_inventory_is_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'member').write_bytes(b'x')
            with self.assertRaises((FileNotFoundError,ValueError)):e.remote.EvidenceLocation(root,'/original')


if __name__=='__main__':unittest.main()
