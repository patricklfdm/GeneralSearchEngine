"""Reviewed four-cell Runner allocation inside the existing topology lease.

Approval freshness gates the first mutation. It is not the already-admitted
preparation lifetime. Canonical/failure-drill allocation remains frozen.
"""
from . import cloud_workload_contract as contract, performance_model as m

PROFILE = 'owned-experiment-v1'
APPROVAL_SECONDS = 900
PREPARATION_SECONDS = 1800


def allocation():
    plan = contract.load(); budgets = plan['budgets']
    cells = plan['presets']['experiment']['cells']
    m.need(cells == ['healthy', 'leader-loss', 'maintenance', 'no-quorum'], 'Runner timing cell scope')
    limits = {v['name']: v['seconds'] for v in plan['cells'] if v['name'] in cells}
    limits.update(preparation=PREPARATION_SECONDS, control=budgets['controlOverheadSeconds'],
                  **{'validation-retention': budgets['validationRetentionSeconds'], 'cleanup': budgets['cleanupSeconds']})
    allocated = sum(limits.values())
    m.need(allocated == 4920 <= budgets['leaseSeconds'] == 5400, 'Runner allocation exceeds lease')
    return dict(profile=PROFILE, approvalSeconds=APPROVAL_SECONDS, limitsSeconds=limits,
                leaseSeconds=budgets['leaseSeconds'], operationGraceSeconds=budgets['operationGraceSeconds'],
                allocatedSeconds=allocated, unallocatedSeconds=budgets['leaseSeconds']-allocated)


def validate(value):
    m.need(value == allocation(), 'Runner timing allocation changed')
    return value
