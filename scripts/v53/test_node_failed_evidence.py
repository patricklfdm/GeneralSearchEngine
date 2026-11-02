import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_failed_evidence as m


class NodeFailedEvidenceTest(unittest.TestCase):
    def scope_record(self):
        ballot=dict(counter=4)
        value=dict(guard='DEADLINE',firstEnd='NONE',ballot=ballot,startedNanos=100,limitNanos=180_000_000_000,
            elapsedNanos=180_000_000_001,clockEvaluated=True)
        return dict(schema='gse-v53-node-process-diagnostic-v1',authority=False,role='worker',phase='client-await',life=2,
            serviceBudgetNanos=180_000_000_000,failure=[dict(type=m.INACTIVE,message=m.REASON,scopeFailure=value)]),ballot

    def check_scope(self,record,ballot):
        with patch.object(Path,'read_bytes',return_value=b'selected'),patch.object(m.f,'decode',return_value=dict(ballot=ballot)):
            return m.scope_failure('v53NodeProcessDiagnostic='+m.f.canonical(record).decode(),Path('unused'))

    def test_scope_snapshot_requires_the_actual_rejecting_condition(self):
        record,ballot=self.scope_record();value=record['failure'][0]['scopeFailure']
        self.assertEqual(value,self.check_scope(record,ballot))
        for guard,elapsed in [('CLOCK_BACKWARDS',-1),('DEADLINE',180_000_000_000)]:
            value.update(guard=guard,elapsedNanos=elapsed);self.check_scope(record,ballot)
        value.update(guard='SCOPE_ENDED',firstEnd='EXPIRED',clockEvaluated=False);value.pop('elapsedNanos')
        self.check_scope(record,ballot)
        value['firstEnd']='NONE'
        with self.assertRaisesRegex(ValueError,'rejecting closed state'):self.check_scope(record,ballot)

    def test_scope_snapshot_cannot_change_original_ballot_or_invent_deadline(self):
        record,ballot=self.scope_record();value=record['failure'][0]['scopeFailure'];value['elapsedNanos']=179_999_999_999
        with self.assertRaisesRegex(ValueError,'rejecting clock value'):self.check_scope(record,ballot)
        value['elapsedNanos']=180_000_000_000;value['ballot']=dict(counter=5)
        with self.assertRaisesRegex(ValueError,'original ballot'):self.check_scope(record,ballot)
        value['ballot']=ballot;record['authority']=True
        with self.assertRaisesRegex(ValueError,'diagnostic scope'):self.check_scope(record,ballot)

    def fixture(self,root):
        (root/'process').mkdir()
        rows=[dict(life=life,pid=100+life,started=dict(life=life,pid=100+life,mode='halt'),exit=73 if life==1 else 1) for life in (1,2)]
        rows[0].update(lockHeldBeforeDeath=True,lockReleasedAfterDeath=True)
        value=dict(mode='halt',cut='ACCEPT_RENAMED',children=rows,status='FAIL',powerLoss=False,phase3Complete=False)
        (root/'process/result.json').write_text(json.dumps(value))
        error='Caused by: java.lang.IllegalArgumentException: '+m.REASON+'\n\tat MembershipActivationEndpoint$Scope.check(Example.java:1)\n\tat MembershipRoundDriver.publish(Example.java:2)\n'
        (root/'process/life-2.stderr').write_text(error)
        return value

    def test_failure_observation_never_establishes_exact_guard_cause(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);value=self.fixture(root);result,rows,error=m.failure(root)
            self.assertEqual(value,result);self.assertEqual([73,1],[v['exit'] for v in rows]);self.assertFalse(error['rootCauseEstablished'])

    def test_success_clean_exit_drain_and_missing_error_cannot_be_failure_evidence(self):
        for change in ('status','exit','drain','same-pid','lock','error','stack'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);value=self.fixture(root)
                if change=='status':value['status']='PARTIAL'
                elif change=='exit':value['children'][1]['exit']=0
                elif change=='drain':value['children'][1]['drained']=True
                elif change=='same-pid':value['children'][1]['pid']=101
                elif change=='lock':value['children'][0].pop('lockHeldBeforeDeath')
                elif change=='error':(root/'process/life-2.stderr').write_bytes(b'')
                else:(root/'process/life-2.stderr').write_text('different failure\n')
                (root/'process/result.json').write_text(json.dumps(value))
                with self.assertRaises(ValueError):m.failure(root)

    def test_wrong_producer_is_rejected_before_physical_interpretation(self):
        with patch.object(m.p.process,'inventory'),patch.object(m.history,'inventory'), \
                patch.object(m,'failure',side_effect=ValueError('wrong producer')),patch.object(m.current,'physical') as physical:
            with self.assertRaisesRegex(ValueError,'wrong producer'):m.inspect('unused')
            physical.assert_not_called()

    def test_invalid_original_cannot_count_as_successful_negative_rejection(self):
        with patch.object(m,'inspect',side_effect=ValueError('invalid original')),patch.object(m.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.qualify('unused')
            copied.assert_not_called()

    def test_successful_qualification_still_requires_closed_lifecycle(self):
        with patch.object(m.p,'_lifecycle',return_value='ok') as replay:
            self.assertEqual('ok',m.p.lifecycle('root','ACCEPT_RENAMED',reconciled=True))
            replay.assert_called_once_with('root','ACCEPT_RENAMED',reconciled=True,closed=True)
        with patch.object(m.p.process,'_observations',return_value='ok') as replay:
            self.assertEqual('ok',m.p.process.observations('root',[],cut='ACCEPT_RENAMED',reconciled=True))
            replay.assert_called_once_with('root',[],cut='ACCEPT_RENAMED',reconciled=True,failed=False)

    def test_diagnostic_cli_retains_nonzero_failure_exit(self):
        result=dict(status='FAIL',diagnosticReplay='PASS',nativeQualification=False)
        with patch('sys.argv',['inspect','original','--output','result.json']),patch.object(m,'inspect',return_value=result), \
                patch.object(m.history,'save') as save,patch('builtins.print'):
            with self.assertRaises(SystemExit) as stopped:m.main()
            self.assertEqual(2,stopped.exception.code);save.assert_called_once_with(Path('result.json'),result)

    def test_diagnostic_output_cannot_overwrite_originals(self):
        with patch('sys.argv',['inspect','original','--output','original/process/result.json']),patch.object(m,'inspect') as inspect:
            with self.assertRaisesRegex(ValueError,'output outside originals'):m.main()
            inspect.assert_not_called()


if __name__=='__main__':unittest.main()
