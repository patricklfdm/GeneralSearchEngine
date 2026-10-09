"""Offline full-preset review: no credentials, provider calls or admission token.

The selected member is checked against the existing native ledger rules in a
discarded copy. Review binds the proposed timing and remaining sequence quotes;
it cannot manufacture a new-format request, lease, approval or PASS completion.
"""
from copy import deepcopy
from pathlib import Path
import time
from . import cloud_authority as a, cloud_native_authority as n, cloud_prices, native_preset_timing as full
from . import cloud_runner_admission as admission, cloud_runner_timing as experiment
from . import cloud_workload_contract as workload, performance_model as m, remote_command as c

PLAN = Path(__file__).resolve().parents[2]/'docs/v5x/v5.1/native-preset-timing-review.json'
PLAN_SHA256 = 'f201a52a96b6451f068090f0f8b6999f15c774fa9ae41ec60182f2329c214670'
SCHEMA = 'gse-v51-native-preset-review-v1'
FLAGS = dict(paidCloud=False, paidAdmission=False, dispatchEnabled=False,
             resourcesCreated=False, engineWorkloadExecuted=False, fullRemoteQualification=False)
INPUTS = {'configuration', 'artifacts', 'guestAccess', 'prices', 'baseline',
          'sequence', 'member', 'order', 'maximumCostsMicrousd'}


def load():
    m.need(PLAN.is_file() and not PLAN.is_symlink() and PLAN.stat().st_size <= 65536, 'preset timing file')
    raw = PLAN.read_bytes()
    m.need(m.sha(raw) == PLAN_SHA256, 'preset timing plan drift')
    value = m.strict_json(raw)
    m.need(value['dispatchEnabled'] is False and value['workloadSha256'] == workload.PLAN_SHA256,
           'preset timing workload/domain')
    return value


def selection(member):
    m.need(type(member) is str and member in a.ORDERS['experiment-first'], 'preset review member')
    repetition = int(member[-1]) if member.startswith('canonical-') else None
    return ('canonical' if repetition else member), repetition


def allocation(member):
    preset, repetition = selection(member)
    frozen = workload.load()
    cells = frozen['presets']['failureDrill' if preset == 'failure-drill' else preset]['cells']
    if preset == 'experiment':
        from . import native_experiment_timing as native
        result = experiment.allocation()
        result.update(cells=cells, retentionReserveSeconds=None, healthyModeSeconds=native.CONTROLS['mode'],
                      commandGuardSeconds=15000, terminationGraceSeconds=60,
                      jobMinutes=270, jobOverheadReserveSeconds=1140)
    else:
        result = deepcopy(load()['profiles'][preset])
        m.need(result['cells'] == cells, 'preset timing cell coverage')
        result['approvalSeconds'] = experiment.APPROVAL_SECONDS
        result['allocatedSeconds'] = sum(result['limitsSeconds'].values())
        result['unallocatedSeconds'] = result['leaseSeconds']-result['allocatedSeconds']
    limits = result['limitsSeconds']
    m.need(set(limits) == set(cells)|{'preparation', 'validation-retention', 'cleanup', 'control'},
           'preset timing stage coverage')
    for seconds in limits.values(): a.integer(seconds, 1, 21600)
    m.need(result['allocatedSeconds'] <= result['leaseSeconds'] and
           (result['retentionReserveSeconds'] is None or
            result['retentionReserveSeconds'] < limits['validation-retention']) and
           result['leaseSeconds'] < result['commandGuardSeconds'] and
           result['commandGuardSeconds']+result['terminationGraceSeconds']+
           result['jobOverheadReserveSeconds'] == result['jobMinutes']*60 <= 21600,
           'preset timing enclosing budgets')
    result['priceCoverageSeconds'] = limits['preparation']+result['leaseSeconds']+result['operationGraceSeconds']
    result.update(preset=preset, repetition=repetition,
                  controlNode=None if preset == 'failure-drill' else 'node-'+str(repetition or 1))
    return result


def review(inputs, *, now):
    """Inspect supplied observations only. Their authenticity/freshness is not live-verified."""
    m.need(type(inputs) is dict and set(inputs) == INPUTS, 'preset review input fields')
    a.integer(now, 1)
    member, order = inputs['member'], inputs['order']
    selection(member)
    m.need(type(order) is str and order in a.ORDERS, 'preset review order')
    remaining = a.ORDERS[order][a.ORDERS[order].index(member):]
    quotes, maxima = inputs['prices'], inputs['maximumCostsMicrousd']
    m.need(type(quotes) is dict and type(maxima) is dict and
           set(quotes) == set(maxima) == set(remaining), 'preset review remaining quotes')
    # Reuse the existing shape/configuration/package/guest checks. This pure
    # constructor has no credentials or live effects. It does not attest CI.
    admission.plan(inputs['configuration'], inputs['artifacts'], inputs['guestAccess'],
                   quotes[member], None, sequence=inputs['sequence'], now=now,
                   maximum_cost=a.MAXIMUM_BUDGET_MICROUSD)
    proof, guest = inputs['artifacts'], inputs['guestAccess']
    req = n.request(proof['source'], proof['archiveSha256'],
                    admission.g.config(inputs['configuration']['provider']), inputs['sequence'],
                    guest['attempt'], member, now=now, order=order,
                    guest_access_sha256=m.sha(m.canonical(guest)),timing_profile=allocation(member)['profile'],
                    timing_plan_sha256=PLAN_SHA256)
    baseline = inputs['baseline']
    if baseline is not None:
        m.need(type(baseline) in (tuple, list) and len(baseline) == 2, 'preset review ledger observation')
        a.integer(baseline[0], 1)
    ledger = baseline[1] if baseline is not None else n.empty_ledger()
    previous, _ = n.inspect_ledger(ledger)
    rows = []
    for selected in remaining:
        timing = allocation(selected)
        cost = cloud_prices.estimate(quotes[selected], now, minimum_coverage_seconds=timing['priceCoverageSeconds'])
        maximum = a.integer(maxima[selected], 1, a.MAXIMUM_BUDGET_MICROUSD)
        m.need(cost <= maximum, 'preset review estimate exceeds reservation: '+selected)
        rows.append(dict(member=selected, timing=timing, estimatedCostMicrousd=cost, maximumCostMicrousd=maximum))
    # Enforces order, immutable sequence identity, global pending attempts,
    # consumed attempt IDs, failed-canonical blocking and cumulative costs.
    # Discard the simulated reservation; it is never written or returned.
    n.reserve(ledger, req, dict(previousCostMicrousd=previous, maximumCostMicrousd=maxima[member]))
    total = previous+sum(v['maximumCostMicrousd'] for v in rows)
    m.need(total <= a.MAXIMUM_BUDGET_MICROUSD, 'preset review remaining sequence exceeds ledger ceiling')
    return m.strict_json(m.canonical(dict(schema=SCHEMA, status='REVIEW_ONLY',
        inputs=deepcopy(inputs), reviewedAt=now,
        expiresAt=min(now+experiment.APPROVAL_SECONDS, *(v['expiresAt'] for v in quotes.values())),
        timingPlanSha256=PLAN_SHA256, members=rows, previousCostMicrousd=previous,
        remainingMaximumCostMicrousd=total-previous, projectedMaximumCostMicrousd=total,
        remainingHeadroomMicrousd=a.MAXIMUM_BUDGET_MICROUSD-total,
        observationsAuthenticated=False, **FLAGS)))


def validate(value, *, now):
    m.need(type(value) is dict and value.get('schema') == SCHEMA, 'preset review schema')
    expected = review(value['inputs'], now=value['reviewedAt'])
    m.need(m.canonical(value) == m.canonical(expected), 'preset review drift')
    a.integer(now, value['reviewedAt'])
    m.need(now < value['expiresAt'], 'preset review expired')
    return m.sha(m.canonical(value))


def summary(value):
    validate(value, now=value['reviewedAt'])
    def usd(amount): return f'{amount//1_000_000}.{amount%1_000_000:06d}'
    lines = ['# V5.1 native preset review', '',
             'Review only. Supplied observations have not been authenticated against current CI/provider state.', '',
             'This file is not a dispatch request or paid approval.', '',
             '| Member | Preparation | Lease | Priced lifetime | Estimate (USD) | Maximum (USD) |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for row in value['members']:
        t = row['timing']
        lines.append(f"| {row['member']} | {t['limitsSeconds']['preparation']} s | {t['leaseSeconds']} s | "
                     f"{t['priceCoverageSeconds']} s | {usd(row['estimatedCostMicrousd'])} | {usd(row['maximumCostMicrousd'])} |")
    lines += ['', f"Previously reserved: USD {usd(value['previousCostMicrousd'])}.",
              f"Projected total: USD {usd(value['projectedMaximumCostMicrousd'])}; "
              f"remaining headroom: USD {usd(value['remainingHeadroomMicrousd'])}.", '',
              'Failed-attempt charges remain included. New runs require fresh exact-source admission, prices and user confirmation.']
    return '\n'.join(lines)+'\n'


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('prepare'); create.add_argument('--inputs', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    check = commands.add_parser('validate'); check.add_argument('review', type=Path)
    args = parser.parse_args()
    if args.command == 'validate':
        digest = validate(c.read(args.review, maximum=4<<20), now=int(time.time()))
    else:
        value = review(c.read(args.inputs, maximum=4<<20), now=int(time.time()))
        digest = validate(value, now=int(time.time()))
        args.output.mkdir(parents=True, exist_ok=False)
        c.write_once(args.output/'review.json', value, maximum=4<<20)
        (args.output/'REVIEW.md').write_text(summary(value), encoding='utf-8')
    print(m.canonical(dict(status='REVIEW_ONLY', reviewSha256=digest, **FLAGS)).decode())


if __name__ == '__main__': main()
