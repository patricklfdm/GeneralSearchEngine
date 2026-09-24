"""One controller clock and disjoint charging of the frozen topology lease."""
from contextlib import contextmanager
import time
from . import cloud_workload_contract as contract, performance_model as m


class Budget:
    def __init__(self, *, clock=time.monotonic_ns, emit=lambda row: None):
        plan = contract.load()
        self.limits = {cell['name']: cell['seconds'] * 10**9 for cell in plan['cells']}
        self.limits.update({name: plan['budgets'][key] * 10**9 for name, key in (
            ('preparation', 'preparationSeconds'), ('control', 'controlOverheadSeconds'),
            ('validation-retention', 'validationRetentionSeconds'), ('cleanup', 'cleanupSeconds'))})
        self.lease = plan['budgets']['leaseSeconds'] * 10**9
        self.clock, self.emit = clock, emit
        self.start = self.cursor = clock()
        self.spent = {name: 0 for name in self.limits}
        self.used, self.rows, self.active = set(), [], None

    def _charge(self, name, end):
        m.need(type(end) is int and end >= self.cursor, 'controller clock moved backwards')
        row = dict(category=name, startNanos=self.cursor, endNanos=end, elapsedNanos=end-self.cursor)
        self.spent[name] += row['elapsedNanos']
        self.cursor = end
        row['withinBudget'] = self.spent[name] <= self.limits[name] and end-self.start <= self.lease
        self.rows.append(row)
        self.emit(row)
        return row['withinBudget']

    @contextmanager
    def stage(self, name):
        m.need(name in self.limits and name != 'control' and self.active is None, 'budget stage/nesting')
        m.need(name not in self.used, 'stage cannot restart its deadline')
        gap_ok = self._charge('control', self.clock())
        # Cleanup must still be attempted after an overrun; accounting reports FAIL.
        m.need(gap_ok or name == 'cleanup', 'control/lease budget exceeded')
        self.used.add(name)
        self.active = name
        stage_deadline = self.cursor + self.limits[name]
        reserve = 0 if name == 'cleanup' else self.limits['cleanup']
        deadline = min(stage_deadline, self.start+self.lease-reserve)
        try:
            yield deadline
        finally:
            self.active = None
            ok = self._charge(name, self.clock())
            m.need(ok, 'budget exceeded: ' + name)

    def finish(self):
        m.need(self.active is None, 'unfinished budget stage')
        self._charge('control', self.clock())
        elapsed = self.cursor-self.start
        m.need(sum(self.spent.values()) == elapsed, 'uncharged controller time')
        ok = all(row['withinBudget'] for row in self.rows) and elapsed <= self.lease
        return dict(status='PASS' if ok else 'FAIL', clock='controller-monotonic',
                    elapsedNanos=elapsed, spentNanos=self.spent.copy(), intervals=self.rows.copy())
