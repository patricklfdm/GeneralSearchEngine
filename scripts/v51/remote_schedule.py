"""Issuing-guest fixed arrivals. Operation callbacks must use persistent local IPC.

This executor proves dispatch accounting only. GSE semantics, physical read cuts,
resource samples and cloud admission must be checked by the workload integration.
"""
from concurrent.futures import ThreadPoolExecutor, wait
from collections import defaultdict
import threading
import time
from . import cloud_workload_contract as contract, performance_model as m


def windows(cell, preset='canonical'):
    plan = contract.load()
    grouped = {}
    for ordinal, row in enumerate(contract.program(plan, cell, preset), 1):
        grouped.setdefault(row['window'], []).append(dict(row, ordinal=ordinal, payload=row['payload'].hex()))
    seconds = (plan['healthy']['windowSeconds'] if preset == 'canonical' else plan['presets']['experiment']['healthyWindowSeconds'])
    warmup = (plan['healthy']['warmupCalls'] if preset == 'canonical' else plan['presets']['experiment']['healthyWarmupCalls'])
    return [dict(schema='gse-v51-guest-window-v1', workloadSha256=contract.PLAN_SHA256,
                 cell=cell, preset=preset, window=name, calls=calls,
                 durationNanos=(warmup if name == 'warmup' else seconds if cell == 'healthy' else
                     plan['readHeavy' if cell == 'read-heavy' else 'sustained']['seconds'])*10**9,
                 lanes=1 if cell == 'healthy' else 4, latenessNanos=250_000_000,
                 burstSpreadNanos=0 if cell == 'healthy' else 10_000_000, drainNanos=10*10**9)
            for name, calls in grouped.items()]


class WindowState:
    """Same state machine used by real threads and deterministic clock tests."""
    def __init__(self, spec, start, emit):
        self.spec, self.start, self.emit = spec, start, emit
        self.busy, self.rows = {}, {}
        self.lock = threading.RLock()
        self.failed = False

    def offer(self, call, now, *, cancelled=False):
        with self.lock:
            ordinal, lane = call['ordinal'], call['lane']
            m.need(ordinal not in self.rows and 0 <= lane < self.spec['lanes'], 'duplicate arrival/lane')
            due = self.start+call['dueMillis']*10**6
            m.need(now >= due or cancelled or self.failed, 'early arrival')
            reason = ('CANCELLED' if cancelled else 'PRIOR_FAILURE' if self.failed else
                      'LATE' if now-due > self.spec['latenessNanos'] else 'LANE_BUSY' if lane in self.busy else None)
            row = dict(ordinal=ordinal, lane=lane, dueNanos=due, offeredNanos=now, state='RESERVED')
            if reason:
                row.update(state='NOT_DISPATCHED', reason=reason)
                self.failed = True
            else:
                self.busy[lane] = ordinal
            self.rows[ordinal] = row
            self.emit(dict(row))
            return reason is None

    def invoke(self, ordinal, now):
        with self.lock:
            row = self.rows[ordinal]
            m.need(row['state'] == 'RESERVED', 'unreserved invocation')
            if now-row['dueNanos'] > self.spec['latenessNanos']:
                row.update(state='NOT_DISPATCHED', reason='EXECUTOR_LATE', endedNanos=now)
                del self.busy[row['lane']]
                self.failed = True
                self.emit(dict(row))
                return False
            row.update(state='DISPATCHED', invokedNanos=now)
            self.emit(dict(row))
            return True

    def complete(self, ordinal, now, result):
        with self.lock:
            row = self.rows[ordinal]
            # A callback finishing after the drain deadline must not turn an
            # unfinished invocation into a successful window retrospectively.
            m.need(row['state'] in ('DISPATCHED', 'UNFINISHED'), 'completion without dispatch')
            m.need(now >= row['invokedNanos'], 'guest completion clock')
            late = row['state'] == 'UNFINISHED'
            row.update(state='LATE_RESULT' if late else 'COMPLETED', endedNanos=now, result=result)
            self.busy.pop(row['lane'], None)
            self.failed |= late or not isinstance(result, dict) or result.get('outcome') != 'SUCCESS'
            self.emit(dict(row))

    def finish(self, now):
        with self.lock:
            m.need(set(self.rows) == {v['ordinal'] for v in self.spec['calls']}, 'missing scheduled arrivals')
            for row in self.rows.values():
                if row['state'] in ('RESERVED', 'DISPATCHED'):
                    row.update(state='UNFINISHED')
                    self.failed = True
                    self.emit(dict(row))
            self.failed |= now < self.start+self.spec['durationNanos'] or now > self.start+self.spec['durationNanos']+self.spec['drainNanos']
            bursts = defaultdict(list)
            for row in self.rows.values():
                if 'invokedNanos' in row:
                    bursts[row['dueNanos']].append(row['invokedNanos'])
            if self.spec['lanes'] > 1:
                self.failed |= any(len(v) != self.spec['lanes'] or max(v)-min(v) > self.spec['burstSpreadNanos'] for v in bursts.values())
            return dict(status='FAIL' if self.failed else 'PASS', startedNanos=self.start, endedNanos=now,
                        scheduledEndNanos=self.start+self.spec['durationNanos'],
                        calls=[dict(v) for v in self.rows.values()])


def execute_window(cell, preset, name, operation, emit, cancelled=lambda: False):
    spec = next((v for v in windows(cell, preset) if v['window'] == name), None)
    m.need(spec is not None, 'unknown frozen window')
    return _execute(spec, operation, emit, cancelled)


def _execute(spec, operation, emit, cancelled):
    """Private short fixtures exercise this runner; public API has no time scaling."""
    executors = [ThreadPoolExecutor(max_workers=1, thread_name_prefix='guest-lane-'+str(i)) for i in range(spec['lanes'])]
    ready = threading.Barrier(spec['lanes']+1)
    futures = []
    state = None
    def invoke(call):
        if state.invoke(call['ordinal'], time.monotonic_ns()):
            try:
                result = operation(call)
            except BaseException as error:
                result = dict(outcome='FAILED', error=dict(type=type(error).__name__, message=str(error)[:2000]))
            state.complete(call['ordinal'], time.monotonic_ns(), result)
    try:
        for executor in executors:
            futures.append(executor.submit(ready.wait, 10))
        ready.wait(10)
        for future in futures:
            future.result()
        futures.clear()
        state = WindowState(spec, time.monotonic_ns(), emit)
        for call in spec['calls']:
            due = state.start+call['dueMillis']*10**6
            while time.monotonic_ns() < due and not state.failed and not cancelled():
                time.sleep(max(0, min(.05, (due-time.monotonic_ns())/1e9)))
            if state.offer(call, time.monotonic_ns(), cancelled=cancelled()):
                futures.append(executors[call['lane']].submit(invoke, call))
        end = state.start+spec['durationNanos']
        while time.monotonic_ns() < end and not state.failed and not cancelled():
            time.sleep(max(0, min(.05, (end-time.monotonic_ns())/1e9)))
        drain_end = min(end, time.monotonic_ns())+spec['drainNanos']
        wait(futures, timeout=max(0, (drain_end-time.monotonic_ns())/1e9))
        for future in futures:
            if future.done():
                future.result()  # observer failures cannot turn into a passing window
        return state.finish(time.monotonic_ns())
    finally:
        for executor in executors:
            executor.shutdown(wait=False, cancel_futures=True)
        # A hung callback is retained as UNFINISHED. The guest process supervisor
        # must enforce the cell deadline and reap the process, never replay calls.
