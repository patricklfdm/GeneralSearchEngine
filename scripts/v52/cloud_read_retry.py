"""Bounded retries for explicitly read-only exchanges; never replay mutations.

Callers retain the original deadline and revalidate authority on each attempt.
Exhaustion is terminal to outer retry loops; diagnostics contain no request data.
"""
import json
import math
import time
from scripts.v51 import cloud_http as http

ATTEMPTS = 3
STATUSES = frozenset((408, 429, 500, 502, 503, 504))
SCOPES = frozenset(('provider-read', 'preflight-read', 'evidence-read',
                    'credential-oidc', 'credential-sts', 'credential-impersonation'))
REASONS = frozenset(('connection', 'timeout', 'deadline')) | frozenset('http-'+str(s) for s in STATUSES)
STOPS = frozenset(('attempt-limit', 'deadline'))
CODES = frozenset(('V52_READ_RETRIES_EXHAUSTED', 'V52_READ_DEADLINE'))


class ReadError(ConnectionError):
    retryable = False
    def __init__(self, scope, attempts, reason, stop):
        if scope not in SCOPES or type(attempts) is not int or not 0 <= attempts <= ATTEMPTS or \
                reason not in REASONS or stop not in STOPS:
            raise ValueError('invalid read retry diagnostic')
        self.code = 'V52_READ_DEADLINE' if stop == 'deadline' else 'V52_READ_RETRIES_EXHAUSTED'
        self.detail = dict(code=self.code, scope=scope, attempts=attempts, reason=reason, stop=stop)
        super().__init__(self.code)


def reason(error):
    if getattr(error, 'retryable', True) is False: return None
    if type(error) is TimeoutError: return 'timeout'
    if type(error) is ConnectionError: return 'connection'
    if type(error) is http.ApiError and error.status in STATUSES: return 'http-'+str(error.status)
    return None


def public_failure(value):
    detail = value.get('readRetry') if type(value) is dict else None
    if type(detail) is not dict or set(detail) != {'code', 'scope', 'attempts', 'reason', 'stop'}: return {}
    try: checked = ReadError(detail['scope'], detail['attempts'], detail['reason'], detail['stop'])
    except (TypeError, ValueError): return {}
    return dict(readRetry=checked.detail) if checked.detail == detail else {}


def failure(error):
    return public_failure(dict(readRetry=error.detail)) if type(error) is ReadError else {}


def progress(value):
    try: print(json.dumps(dict(stage='cloud-read-retry', **value), separators=(',', ':')), flush=True)
    except (OSError, ValueError): pass  # Logging cannot replace the original failure.


def run(call, *, deadline, clock, scope, classify=reason):
    if scope not in SCOPES or type(deadline) not in (int, float) or not math.isfinite(deadline):
        raise ValueError('invalid read retry scope/deadline')
    for attempt in range(1, ATTEMPTS+1):
        if clock() >= deadline: raise ReadError(scope, attempt-1, 'deadline', 'deadline')
        try: return call()
        except Exception as error:
            why = classify(error)
            if why is None: raise
            if why not in REASONS: raise ValueError('invalid read retry classification') from None
            delay = .25 * attempt
            stop = 'attempt-limit' if attempt == ATTEMPTS else 'deadline' if deadline-clock() <= delay else None
            progress(dict(scope=scope, attempt=attempt, reason=why, retry=stop is None, stop=stop))
            if stop is not None: raise ReadError(scope, attempt, why, stop) from None
            time.sleep(delay)


class Api(http.Api):
    """V5.2 reads only. Existing GET-401 refresh and mutation semantics remain."""
    read_scope = 'provider-read'
    def call(self, method, url, body=None, *, deadline, **kwargs):
        original = super().call
        if method != 'GET': return original(method, url, body, deadline=deadline, **kwargs)
        # The full call repeats authorization and scoped policy checks. An inner
        # exhausted read is terminal, so nested owner reads cannot multiply it.
        return run(lambda: original(method, url, body, deadline=deadline, **kwargs),
                   deadline=deadline, clock=self.clock, scope=self.read_scope)
