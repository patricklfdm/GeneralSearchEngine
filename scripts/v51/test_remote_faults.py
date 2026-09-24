"""Fault budget and conservative-outcome negatives, never labelled runtime proof."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_workload_contract as contract, performance_model as m
from . import remote_faults as workload, remote_fault_evidence as evidence


class RemoteFaultTest(unittest.TestCase):
    def test_large_values_fit_only_the_two_reviewed_exceptions(self):
        plan=contract.load();cells={c['name']:c for c in plan['cells']}
        for name,value_bytes,total in [('interrupted-transfer',4096,4100),('minority-capacity',20000,20004)]:
            docs=workload.documents(40,value_bytes)
            self.assertEqual([value_bytes]*2,[len(d['value'].encode()) for d in docs])
            self.assertEqual(total,cells[name]['maxEncodedDocumentBytes'])
            self.assertTrue(all(4+len(d['value'].encode())==total for d in docs))
        self.assertEqual({'interrupted-transfer','minority-capacity'},{c['name'] for c in plan['cells'] if 'maxEncodedDocumentBytes' in c})

    def test_fault_exceptions_cannot_leak_or_shrink_without_pin_check(self):
        for name,bound in [('healthy',4100),('interrupted-transfer',4096),('minority-capacity',20000),('minority-capacity',20005)]:
            value=copy.deepcopy(contract.load());next(c for c in value['cells'] if c['name']==name)['maxEncodedDocumentBytes']=bound
            with self.subTest(name=name,bound=bound),self.assertRaisesRegex(ValueError,'fault document exceptions'):contract.audit(value)
        value=copy.deepcopy(contract.load());next(c for c in value['cells'] if c['name']=='interrupted-transfer').pop('maxEncodedDocumentBytes')
        with self.assertRaisesRegex(ValueError,'fault document exceptions'):contract.audit(value)

    def test_declaration_covers_exact_twelve_and_never_reuses_mutation_keys(self):
        self.assertEqual(12,len(workload.CASES))
        for name in workload.CASES:
            declared=workload.declaration(name)
            self.assertEqual([f'call-{n:02d}' for n in range(1,25)],declared['operationIds'])
            tags=[s['tag'] for s in declared['seeds']]+declared['targetTags']+declared['progressTags']+[declared['refusalTag']]
            keys=[d['id'] for t in tags for d in workload.documents(t)]
            self.assertEqual(len(keys),len(set(keys)))
        with self.assertRaises(ValueError):workload.declaration('unreviewed')

    def test_only_exact_conservative_outcomes_allow_another_fresh_pair(self):
        for kind,outcome in [('read','NOT_APPLICABLE'),('addAll','NOT_SUBMITTED')]:
            for reason in workload.q.RECOVERY_REASONS:
                response=dict(kind=kind,outcome=outcome,reasonCode=reason)
                workload.availability(response,kind);evidence.accepted_outcome(response)
        for reason in workload.q.UNCERTAIN_RECOVERY_REASONS:
            response=dict(kind='addAll',outcome='INDETERMINATE',reasonCode=reason)
            workload.availability(response,'addAll');evidence.accepted_outcome(response)
        for outcome,reason in [('NOT_SUBMITTED','STORAGE_FAILURE'),('INDETERMINATE','NOT_LEADER'),('NOT_SUBMITTED','CAPACITY_EXCEEDED'),('NOT_SUBMITTED','CLOSED'),('NOT_SUBMITTED','INTEGRITY_FAILURE'),('VALIDATION_FAILURE','NOT_READY')]:
            response=dict(kind='addAll',outcome=outcome,reasonCode=reason)
            with self.subTest(response=response),self.assertRaises(ValueError):workload.availability(response,'addAll')
            with self.subTest(response=response),self.assertRaises(ValueError):evidence.accepted_outcome(response)
        workload.availability(dict(kind='read',outcome='NOT_APPLICABLE',reasonCode='CAPACITY_EXCEEDED'),'read',True)
        with self.assertRaises(ValueError):workload.availability(None,'read')
        with self.assertRaises(ValueError):evidence.accepted_outcome(dict(kind='read',outcome='PENDING'))

    def test_operation_cap_is_checked_before_any_worker_dispatch(self):
        class Run:pass
        with tempfile.TemporaryDirectory() as tmp:
            cell=workload.Cell(Run(),Path(tmp),'unused','leader-loss');cell.history=[{}]*24
            with self.assertRaisesRegex(ValueError,'public operation budget'):cell.send('node-1','addAll',documents=workload.documents(10))

    def test_nested_deadline_cannot_extend_original_cell(self):
        class Run:pass
        with tempfile.TemporaryDirectory() as tmp,patch.object(workload.time,'monotonic_ns',return_value=1000):
            cell=workload.Cell(Run(),Path(tmp),'unused','leader-loss')
            self.assertEqual(120,cell.remaining(999,deadline=1000+600*10**9))
            self.assertEqual(60,cell.remaining(999,deadline=1000+60*10**9))
            with patch.object(workload.time,'monotonic_ns',return_value=cell.deadline):
                with self.assertRaisesRegex(ValueError,'deadline'):cell.remaining(deadline=cell.deadline+60*10**9)

    def test_trace_reader_rejects_incomplete_duplicate_and_oversized_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for n,node in enumerate(workload.NODES,1):
                (root/(node+'-trace.jsonl')).write_bytes(m.canonical(dict(node=node,pid=n,generation=1,order=1,localNanos=1))+b'\n')
            self.assertEqual(set(workload.NODES),set(evidence.load_traces(root)))
            path=root/'node-1-trace.jsonl';original=path.read_bytes()
            for invalid in (original.rstrip(),b'{"node":"node-1","node":"node-1"}\n',b'x'*((4<<20)+1)):
                path.write_bytes(invalid)
                with self.assertRaises(ValueError):evidence.load_traces(root)
            with path.open('wb') as stream:stream.truncate((32<<20)+1)
            with self.assertRaisesRegex(ValueError,'member bound'):evidence.load_traces(root)

    def test_unknown_fault_never_creates_a_plan(self):
        with self.assertRaises(ValueError):workload.declaration('leader-loss-retry')


if __name__=='__main__':unittest.main()
