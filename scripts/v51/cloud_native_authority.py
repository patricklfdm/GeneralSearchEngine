"""Native record formats, sharing invariants with the isolated fake domain.

These records are data, not paid admission. No fake record is migrated/relabelled.
The paid runner remains closed. The network cleanup adapter has a separate tag.
"""
from functools import wraps
from . import cloud_authority as a

EXECUTION = 'gcp-v51-owned-control'
ADAPTER_EXECUTION = 'offline-v51-native-control'
CLEANUP_EXECUTION = 'gcp-v51-native-cleanup'
PAID_CLOUD = True  # Original attempt intent; offline replay receipts remain false.
COMPLETION_SCHEMA = 'gse-v51-native-completion-v1'
CONTEXT_SCHEMA = 'gse-v51-native-cleanup-context-v1'
PREFIX, LEASE, LEDGER, SUITE = a.PREFIX, a.LEASE, a.LEDGER, a.SUITE


def _native(function):
    @wraps(function)
    def call(*args, **kwargs):
        # A caller cannot override this facade's domain with keyword arguments.
        return function(*args, **kwargs, domain='native')
    return call


request = _native(a.request)
validate_request = _native(a.validate_request)
empty_ledger = _native(a.empty_ledger)
inspect_ledger = _native(a.inspect_ledger)
reserve = _native(a.reserve)
finish = _native(a.finish)
resources = _native(a.resources)
lease = _native(a.lease)
validate_lease = _native(a.validate_lease)
