"""Reviewed first-run headroom; fixed ceilings, never a wire-supplied timeout.

Only native request v2 selects these limits. Legacy leases keep their original
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
    return (request.get('schema') == REQUEST_SCHEMA and
            request.get('timingProfile') == PROFILE)


def control(request, name, legacy):
    return CONTROLS[name] if selected(request) else legacy


def cell(request, name):
    return STAGES[name] if selected(request) else (900 if name == 'healthy' else 240 if name == 'maintenance' else 120)
