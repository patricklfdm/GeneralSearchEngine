"""A completed response need not have released its single public admission permit."""
from concurrent.futures import Future
from contextlib import ExitStack
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from . import public_bounds_harness as bounds


class BoundsScheduleTest(unittest.TestCase):
    def run_document_case(self, delayed, *, reject_resumed=False):
        documents = []; calls = []; instances = []

        class Worker:
            def __init__(worker, root, node, cp, history, generation=1, **unused):
                worker.node = node; worker.history = history; worker.generation = generation
                worker.proc = SimpleNamespace(pid=100+len(instances))
                worker.ticks = 0; worker.reads = 0; instances.append(worker)

            def send(worker, kind, **values):
                calls.append((kind, values))
                result = dict(kind=kind, outcome='SUCCESS', **values)
                if kind == 'status':
                    result.update(state='LEADER_READY', pending=int(worker.ticks > 0))
                    worker.ticks = max(0, worker.ticks-1)
                else:
                    result['opId'] = str(len(calls)); point = None
                    if worker.ticks or (reject_resumed and kind == 'addAll' and values['documents'][0]['id'] == 30):
                        result.update(outcome='NOT_SUBMITTED' if kind == 'addAll' else 'NOT_APPLICABLE', reasonCode='CAPACITY_EXCEEDED')
                    elif kind == 'addAll':
                        if len(documents)+len(values['documents']) > 4:
                            result.update(outcome='NOT_SUBMITTED', reasonCode='CAPACITY_EXCEEDED'); point = 'rejection'
                        else:
                            documents.extend(values['documents']); point = 'write'
                    else:
                        worker.reads += 1; result['documents'] = list(documents)
                        point = 'seed-read' if worker.reads == 1 else 'recovery-read'
                    if point == delayed: worker.ticks = 2
                    worker.history.append(dict(result))
                future = Future(); future.set_result(result); return future

            def call(worker, kind, **values):
                result = worker.send(kind, **values).result()
                bounds.need(result['outcome'] == 'SUCCESS', 'public call failed: '+str(result)); return result

            def stop(worker): pass

        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            stack.enter_context(patch.object(bounds.q, 'Worker', Worker))
            stack.enter_context(patch.object(bounds, 'bootstrap'))
            stack.enter_context(patch.object(bounds.fault, 'leader', side_effect=lambda workers: next(iter(workers.items()))))
            stack.enter_context(patch.object(bounds.fault.time, 'sleep'))
            stack.enter_context(patch.object(bounds.recovery, 'archive', return_value={}))
            for obj, name, value in ((bounds.physical, 'traces_at', {}), (bounds.physical, 'physical', {}),
                                     (bounds.physical, 'negatives', []), (bounds.public_history, 'check', {}),
                                     (bounds.evidence, 'bounds', {}), (bounds.evidence, 'sequential_admission', {}),
                                     (bounds.evidence, 'negatives', [])):
                stack.enter_context(patch.object(obj, name, return_value=value))
            self.calls = calls
            return bounds.process_case(Path(temp)/'case', '', 'document-limit')

    def test_single_permit_drains_after_each_kind_of_completed_response(self):
        for delayed in ('write', 'seed-read', 'rejection', 'recovery-read'):
            with self.subTest(delayed=delayed):
                result = self.run_document_case(delayed)
                self.assertEqual('PASS', result['status'])
                writes = [v['documents'][0]['id'] for kind, v in self.calls if kind == 'addAll']
                self.assertEqual([10, 11, 90, 30], writes)
                self.assertEqual([10, 11, 30], [v['id'] for v in result['expected']])

    def test_unexpected_resumed_write_rejection_fails_without_replay(self):
        with self.assertRaisesRegex(ValueError, 'public call failed.*CAPACITY_EXCEEDED'):
            self.run_document_case('recovery-read', reject_resumed=True)
        self.assertEqual(1, sum(kind == 'addAll' and v['documents'][0]['id'] == 30 for kind, v in self.calls))

    def test_leaked_permit_times_out_without_application_calls(self):
        worker = Mock(call=Mock(return_value=dict(pending=1)))
        with patch.object(bounds.fault.time, 'monotonic', side_effect=[0, 0, 41]), patch.object(bounds.fault.time, 'sleep'):
            with self.assertRaisesRegex(ValueError, 'bounds admission did not drain'):
                bounds.await_admission_idle(worker)
        worker.call.assert_called_once_with('status')

    def test_status_failure_is_not_ignored(self):
        worker = Mock(call=Mock(side_effect=ValueError('public status disconnected')))
        with self.assertRaisesRegex(ValueError, 'status disconnected'): bounds.await_admission_idle(worker)
        worker.call.assert_called_once_with('status')
