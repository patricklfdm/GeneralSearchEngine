"""Synthetic 1.1 read/receipt tests; real JVM/SSH qualification is separate."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts.v50 import admission_format as f, admission_fixtures as fixture
from . import guest_configured_evidence as e, guest_physical_evidence as joint
from . import performance_model as m, performance_plan as plan, cloud_package as package
from . import test_guest_backup as backups


class ConfiguredReadTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        # Real framed 1.1 bytes, with a rich immutable seed but no mutations. This
        # intentionally tests prefix/read binding, not force quorum qualification.
        files=fixture.make(4);old=f.genesis(files['genesis.gsr']);state=m.initial(plan.load());n=fixture.number
        g=f.framed(16,n('H',1)+old['group']+f.blob(old['source'])+old['history']+n('q',4)+f.blob(state.application()))
        manifest=f.framed(1,f.text('gse-replicated')+n('HH',1,1)+f.text('gse-replication')+n('HH',1,1)+old['group']+
            f.text('phase6-local-v1')+n('q',1)+f.text('node-1')+n('i',3)+b''.join(f.text('node-'+str(i))+
            f.text('127.0.0.1')+n('iB',19100+i,1) for i in (1,2,3))+f.text('semantic-codec')+n('i',1)+
            f.text('semantic-schema')+n('i',1)+f.sha(f.canonical(sorted(f.application(state.application())[0])))+
            g[16:48]+old['history']+n('q',4))
        for i in (1,2,3):
            node='node-'+str(i);root=self.root/node;root.mkdir()
            (root/'genesis.gsr').write_bytes(g);(root/'manifest.gsr').write_bytes(manifest)
            for name,kind in [('entries',5),('proofs',6),('promises',4)]:
                (root/(name+'.gsr')).write_bytes(f.framed(3,manifest[16:48]+f.text(node)+n('H',kind)))
        request=dict(command='call',opId='node-1-g1-1',operation='GET',cycle=0)
        answer=state.answer('GET',0)
        response=dict(command='call',opId=request['opId'],pid=123,node='node-1',outcome='SUCCESS',
            call=dict(operation='GET',cycle=0,beforeSequence=4,afterSequence=4,answer=answer,answerSha256=m.sha(m.canonical(answer))))
        self.exchanges={node:[] for node in ('node-1','node-2','node-3')}
        self.exchanges['node-1']=[dict(request=request,response=deepcopy(response))]
        self.traces={node:[] for node in self.exchanges}
        self.traces['node-1']=[dict(request,event='CLIENT_INVOKE',pid=123,node='node-1',order=1,localNanos=1,window='warmup'),
            dict(response,event='CLIENT_RESULT',order=2,localNanos=2,window='warmup')]
    def validate(self):e.observations(self.root,self.traces,self.exchanges)
    def test_read_uses_published_seed_without_automatic_noop(self):self.validate()
    def test_original_bad_evidence_does_not_count_as_rejected_mutations(self):
        self.traces['node-1'].pop(0)
        with patch.object(e,'audit',wraps=e.audit) as audit:
            with self.assertRaisesRegex(ValueError,'without invocation'):e.qualify(self.root,[],self.traces,self.exchanges,final_sequence=4)
            self.assertEqual(audit.call_count,1)
    def test_resealed_read_answer_rejected_by_independent_bytes(self):
        for r in (self.traces['node-1'][1],self.exchanges['node-1'][0]['response']):
            r['call'].update(answer='changed',answerSha256=m.sha(m.canonical('changed')))
        with self.assertRaisesRegex(ValueError,'published prefix'):self.validate()
    def test_resealed_sequence_cannot_claim_unpublished_prefix(self):
        for r in (self.traces['node-1'][1],self.exchanges['node-1'][0]['response']):r['call']['afterSequence']=5
        with self.assertRaisesRegex(ValueError,'published sequence'):self.validate()
    def test_borrowed_original_response_rejected(self):
        self.traces['node-1'][1]['pid']=456
        with self.assertRaisesRegex(ValueError,'original result binding'):self.validate()
    def test_original_request_change_rejected(self):
        self.exchanges['node-1'][0]['request']['cycle']=1
        with self.assertRaisesRegex(ValueError,'original invocation binding'):self.validate()
    def test_resealed_failed_response_rejected(self):
        for r in (self.traces['node-1'][1],self.exchanges['node-1'][0]['response']):r['outcome']='FAILED'
        with self.assertRaisesRegex(ValueError,'unsuccessful original'):self.validate()
    def test_extra_or_missing_original_exchange_rejected(self):
        self.exchanges['node-1'].append(deepcopy(self.exchanges['node-1'][0]))
        with self.assertRaisesRegex(ValueError,'trace coverage'):self.validate()
    def test_unretained_force_rejected(self):
        self.traces['node-1'].insert(0,dict(event='FORCE',kind='PROOF',record='AA=='))
        with self.assertRaisesRegex(ValueError,'retained bytes'):self.validate()
    def test_duplicate_invocation_rejected(self):
        self.traces['node-1'].insert(1,deepcopy(self.traces['node-1'][0]))
        with self.assertRaisesRegex(ValueError,'overlapping'):self.validate()


class ConfiguredBackupLifecycleTest(backups.BackupLifecycleTest):
    def setUp(self):super().setUp();self.service.config['mode']=package.MODES[1]


class ConfiguredBackupEvidenceTest(unittest.TestCase):
    def test_configured_backup_binds_original_response_and_separate_published_restore(self):
        with tempfile.TemporaryDirectory() as folder:
            value=backups.BackupFixture(Path(folder)/'raw',mode=package.MODES[1]);value.render()
            self.assertEqual(value.validate()['backupRestore']['sequence'],76)
            value=backups.BackupFixture(Path(folder)/'bad-pid',mode=package.MODES[1])
            value.restored['process']['pid']=102;value.render()
            with self.assertRaisesRegex(ValueError,'restore process'):value.validate()
    def test_configured_convergence_requires_ready_and_keeps_original_deadline(self):
        seen=[]
        def status(node,end):seen.append((node,end));return dict(state='READY',provenIndex=73)
        joint.converge([1,2,3],1,status,10,mode=package.MODES[1],clock=lambda:0)
        self.assertEqual(seen,[(1,10),(2,10),(3,10)])
        with self.assertRaisesRegex(ValueError,'leader status'):
            joint.converge([1,2,3],1,status,10,clock=lambda:0)


if __name__=='__main__':unittest.main()
