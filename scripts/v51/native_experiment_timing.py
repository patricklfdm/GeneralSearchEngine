"""Reviewed first-run headroom; fixed ceilings, never a wire-supplied timeout.

Native request v2 selects these limits; v3 delegates to its closed member
allocation below. Legacy leases keep their original
expiry, and canonical measurement parameters are not changed by this profile.
"""
PROFILE = 'owned-experiment-v2'
REQUEST_SCHEMA = 'gse-v51-native-request-v2'
PREPARATION_SECONDS = 3600
LEASE_SECONDS = 14400
GRACE_SECONDS = 1800
# VM maxRunDuration starts at allocation, which can be late in preparation.
PRICE_COVERAGE_SECONDS = PREPARATION_SECONDS + LEASE_SECONDS + GRACE_SECONDS
STAGES = {'preparation': PREPARATION_SECONDS, 'healthy': 2700,
          'leader-loss': 600, 'maintenance': 900, 'no-quorum': 600,
          'validation-retention': 1800, 'cleanup': 900, 'control': 900}
CONTROLS = {'mode': 900, 'activation': 180, 'convergence': 180,
            'service-stop': 180, 'rejoin': 180, 'progress': 300,
            'isolation': 180, 'pin': 300, 'hold-controller': 120}
EXCHANGE_SECONDS = 120
CONNECTION_SECONDS = 900
COMMAND_SECONDS = 180
MAX_TRANSIENT_FAILURES = 3
MAX_UNCERTAIN_REPLIES = 3
MAX_QUERIES = 256


def selected(request):
    from . import native_preset_timing as full
    return (request.get('schema') == REQUEST_SCHEMA and request.get('timingProfile') == PROFILE) or full.selected(request)


def control(request, name, legacy):
    from . import native_preset_timing as full
    if full.selected(request) and name=='mode':return full.validate(request)['healthyModeSeconds']
    return CONTROLS[name] if selected(request) else legacy


def cell(request, name):
    if selected(request):return allocation(request)['limitsSeconds'][name]
    from . import cloud_workload_contract as contract
    return {cell['name']:cell['seconds'] for cell in contract.load()['cells']}[name]


def allocation(request):
    from . import native_preset_timing as full
    if full.selected(request):return full.validate(request)
    return dict(profile=PROFILE, limitsSeconds=dict(STAGES), leaseSeconds=LEASE_SECONDS,
                operationGraceSeconds=GRACE_SECONDS, priceCoverageSeconds=PRICE_COVERAGE_SECONDS)
