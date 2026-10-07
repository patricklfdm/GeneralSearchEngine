"""Reviewed four-cell Runner allocation inside the native v2 topology lease.

Approval freshness gates the first mutation. It is not the already-admitted
preparation lifetime. Canonical/failure-drill allocation remains frozen.
"""
from . import cloud_workload_contract as contract, performance_model as m
from .native_experiment_timing import PROFILE, PREPARATION_SECONDS, STAGES, LEASE_SECONDS, GRACE_SECONDS

APPROVAL_SECONDS = 900


def allocation():
    plan = contract.load()
    cells = plan['presets']['experiment']['cells']
    m.need(cells == ['healthy', 'leader-loss', 'maintenance', 'no-quorum'], 'Runner timing cell scope')
    limits = dict(STAGES)
    allocated = sum(limits.values())
    m.need(allocated == 12000 <= LEASE_SECONDS, 'Runner allocation exceeds lease')
    return dict(profile=PROFILE, approvalSeconds=APPROVAL_SECONDS, limitsSeconds=limits,
                leaseSeconds=LEASE_SECONDS, operationGraceSeconds=GRACE_SECONDS,
                allocatedSeconds=allocated, unallocatedSeconds=LEASE_SECONDS-allocated)


def validate(value):
    m.need(value == allocation(), 'Runner timing allocation changed')
    return value
