"""Bounded recovery for the exact native session claim, never workload replay."""
import time
from . import guest_transport as transport, performance_model as m

SECONDS = 120
EXCHANGE_SECONDS = 30
MAX_BEGINS = 3
MAX_FAILURES = 3
MAX_UNCERTAIN = 3
MAX_EXCHANGES = 8
DETAILS = {
    'SESSION_RECOVERY_DEADLINE': 'The bounded session recovery deadline expired.',
    'SESSION_RETRY_LIMIT': 'The session retry or exchange limit was reached.',
    'SESSION_UNCERTAIN': 'The original session claim remained uncertain; it was not replaced.',
    'SESSION_RESPONSE_INVALID': 'The session response did not match the exact expected state and identity.',
    'SESSION_REJECTED': 'A session identity, authority, provider or local validation check failed.',
    'SESSION_INTERRUPTED': 'Session initialization was interrupted.',
    'SESSION_EXCHANGE_TIMEOUT': 'The bounded session exchange timed out.',
    **transport.FAILURE_DETAILS,
}


class RecoveryError(ValueError):
    def __init__(self, code):
        m.need(code in DETAILS, 'unknown session recovery failure')
        self.code = code
        super().__init__(DETAILS[code])


def initialize(exchange, expected, deadline, report, *, clock=time.monotonic, sleep=time.sleep):
    """Query a lost reply first; only an exact NOT_FOUND permits the same begin.

    The receiver's atomic mkdir claims one immutable session. Concurrent or torn
    claims return UNCERTAIN; no recovery path deletes a claim or renews its clock.
    """
    start = clock(); end = min(deadline, start+SECONDS)
    report.update(status='FAIL',code='SESSION_INTERRUPTED',startNanos=int(start*1e9),deadlineNanos=int(end*1e9),
        limits=dict(seconds=SECONDS,exchangeSeconds=EXCHANGE_SECONDS,begins=MAX_BEGINS,
                    transientFailures=MAX_FAILURES,uncertain=MAX_UNCERTAIN,exchanges=MAX_EXCHANGES),events=[])
    begins = failures = uncertain = 0; action = 'begin'
    def fail(code):
        report['code'] = code
        raise RecoveryError(code) from None
    try:
        while True:
            if clock() >= end: fail('SESSION_RECOVERY_DEADLINE')
            if len(report['events']) >= MAX_EXCHANGES or action == 'begin' and begins >= MAX_BEGINS:
                fail('SESSION_RETRY_LIMIT')
            if action == 'begin': begins += 1
            until = min(end, clock()+EXCHANGE_SECONDS)
            row = dict(action=action,startNanos=int(clock()*1e9),deadlineNanos=int(until*1e9))
            report['events'].append(row)
            lost = False
            try:
                answer = exchange(action, until)
            except (transport.ProcessError,transport.ProcessRejected) as error:
                row.update(code=error.code,retryable=error.retryable)
                if not error.retryable: fail(error.code)
                lost = True; failures += 1
            except TimeoutError:
                row.update(code='SESSION_EXCHANGE_TIMEOUT',retryable=True)
                lost = True; failures += 1
            except Exception:
                row.update(code='SESSION_REJECTED',retryable=False)
                fail('SESSION_REJECTED')
            finally:
                row['endNanos'] = int(clock()*1e9)
            if clock() >= end: fail('SESSION_RECOVERY_DEADLINE')
            if failures >= MAX_FAILURES: fail('SESSION_RETRY_LIMIT')
            if not lost:
                if clock() > until: fail('SESSION_RECOVERY_DEADLINE')
                if answer == expected:
                    row['state'] = 'SUCCEEDED'; report.update(status='PASS',code=None)
                    return answer
                if answer not in ({'state':'NOT_FOUND'}, {'state':'UNCERTAIN'}):
                    row['code'] = 'SESSION_RESPONSE_INVALID'; fail('SESSION_RESPONSE_INVALID')
                row['state'] = answer['state']
                if answer['state'] == 'NOT_FOUND':
                    if action != 'query': fail('SESSION_RESPONSE_INVALID')
                    if begins >= MAX_BEGINS: fail('SESSION_RETRY_LIMIT')
                    action = 'begin'
                else:
                    uncertain += 1
                    if uncertain >= MAX_UNCERTAIN: fail('SESSION_UNCERTAIN')
                    action = 'query'
            else:
                action = 'query'
            # Bounded backoff also counts against the one original recovery clock.
            sleep(min(2**min(len(report['events'])-1,2), max(0,end-clock())))
    finally:
        report.update(endNanos=int(clock()*1e9),begins=begins,transientFailures=failures,uncertain=uncertain)
