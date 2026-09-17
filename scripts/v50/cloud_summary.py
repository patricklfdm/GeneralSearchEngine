"""Render V5 Actions summaries from bounded local receipts, without cloud access."""
import argparse
from datetime import datetime, timezone
import html
import os
from pathlib import Path
import time
from .cloud_common import plan, read, sha, canonical
from .cloud_workload_plan import read_plan


def cell(value):
    text = '—' if value is None else str(value)
    text = html.escape(' '.join(text.split())[:2200], quote=True)
    for char in '|`*[]_': text = text.replace(char, f'&#{ord(char)};')
    return text


def utc(value):
    try: return datetime.fromtimestamp(int(value), timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (TypeError, ValueError, OSError, OverflowError): return '—'


def usd(value):
    return f'USD {value / 1_000_000:.2f}' if type(value) is int else 'Not recorded'


def render(root, *, mode, profile='admission-probe', job_status='unknown', env=None, now=None):
    root = Path(root); env = os.environ if env is None else env
    now = int(time.time()) if now is None else now
    warnings = []
    def load(name, expected=dict):
        path = root / name
        if not path.exists(): return expected()
        try:
            value = read(path, 16 << 20)
            if not isinstance(value, expected): raise ValueError('wrong document type')
            return value
        except (ValueError, OSError, TypeError):
            warnings.append('Unreadable receipt: ' + name); return expected()
    state = load('evidence/lifecycle.json') or load('evidence/completion.json')
    review = load('prepared/review.json')
    preflight = load('prepared/preflight.json') or load('preflight.json') or load('evidence/preflight.json')
    req = state.get('request') or load('prepared/request.json')
    cleanup = load('reconciliation/reconciliation.json') or load('cleanup/reconciliation.json')
    cleanup = cleanup or load('reconciliation/cleanup.json') or load('cleanup/cleanup.json')
    cleanup_identity = load('identity.json')
    req = req or cleanup.get('request') or {}
    approval = load('evidence/approval.json') or load('admission.json')
    matrix = load('evidence/matrix.json')
    entry = load('evidence/entry-error.json') or load('prepared/entry-error.json') or load('cleanup/entry-error.json') or load('reconciliation/entry-error.json')
    profile = req.get('profile', profile)
    p = plan(); workload = read_plan()
    status = (state.get('status') if mode == 'run' else cleanup.get('status') if mode in ('reconcile', 'expired-cleanup')
              else matrix.get('status') if mode == 'fake' else review.get('status') or preflight.get('status'))
    status = status or ('PLAN ONLY' if mode == 'plan' and job_status == 'success' else 'No result receipt')
    if entry or job_status in ('failure', 'cancelled'): status = job_status.upper() if job_status != 'unknown' else 'FAIL'
    lines = ['# V5.0 replication — ' + cell(mode), '', '**Result: ' + cell(status) + '**', '']
    def table(title, headers, rows):
        lines.extend(['## ' + title, '', '| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'])
        lines.extend('| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows)
        lines.append('')
    table('Run identity', ['Field', 'Value'], [
        ('Execution mode', mode), ('Actions job status before summary', job_status),
        ('Actions run / attempt', env.get('GITHUB_RUN_ID', 'local') + ' / ' + env.get('GITHUB_RUN_ATTEMPT', '1')),
        ('Source commit', req.get('source') or preflight.get('source') or env.get('GITHUB_SHA')),
        ('Profile / repetition', profile + ' / ' + str(req.get('repetition', env.get('REPETITION', '1')))),
        ('Sequence', req.get('sequence') or env.get('SEQUENCE')),
        ('Prepared run / attempt', str(req.get('runId') or env.get('PREPARED_RUN', '—')) + ' / ' + str(req.get('attempt', '—'))),
        ('Owner', req.get('owner')), ('Runtime started / finished', utc(state.get('startedAt')) + ' / ' + utc(state.get('finishedAt')))])
    table('Planned infrastructure', ['Field', 'Value'], [
        ('Project / zone', p['project'] + ' / ' + p['zone']),
        ('Voters / machine / provisioning', f"{p['voters']} concurrent / {p['machineType']} / STANDARD"),
        ('Peak quota', f"{p['voters'] * p['vcpusPerVoter']} vCPU / 450 GiB disks"),
        ('Disks per voter', f"{p['bootDiskGiB']} GiB boot + {p['dataDiskGiB']} GiB data / {p['diskType']} / ext4"),
        ('Network', f"private replication TCP {p['port']}; SSH via IAP; no external IP / VM service account"),
        ('Image / ID', p['image'] + ' / ' + p['imageId']),
        ('Java / gcloud', p['runtimeJava'] + ' / ' + p['gcloudVersion']),
        ('VM watchdog / cleanup reserve', f"{p['maximumTopologySeconds']} s / {p['cleanupReserveSeconds']} s"),
        ('Evidence bucket', 'gs://' + p['bucket'] + '/' + p['evidencePrefix']),
        ('Actions artifacts', '14 days; v50-prepared for prepare, v50-runner-<run>-<attempt> for runner, v50-cleanup-<run>-<attempt> for cleanup')])
    if profile in workload['profiles']:
        selected = workload['profiles'][profile]
        table('Frozen workload plan', ['Field', 'Value'], [
            ('Corpus / indexes', f"{workload['corpusDocuments']} documents / " + ', '.join(workload['application']['indexes'])),
            ('Published control', workload['publishedControl']['artifact']),
            ('JVM', ' '.join(workload['jvmArguments'])),
            ('Windows', ' → '.join(workload['workload']['windows'])),
            ('Healthy interval / sustained interval', f"{workload['workload']['healthyIntervalNanos'] / 1e6:g} ms / {workload['workload']['sustainedIntervalNanos'] / 1e6:g} ms"),
            ('Warmup / sustained lanes', f"{workload['workload']['warmupSeconds']} s / {workload['workload']['sustainedLanes']}"),
            ('Topology allowance', str(sum(selected['reservationsSeconds'])) + ' s'),
            ('Allowances: setup / control / candidate warmup and window control / cells / retention / cleanup',
             ' / '.join(str(v) + ' s' for v in selected['reservationsSeconds'])),
            ('Sequence order', 'experiment → failure-drill → canonical 1 → canonical 2 → canonical 3')])
        actual = {c.get('name'): c for c in load('evidence/runtime/cells.json', list) if isinstance(c, dict)}
        rows = []
        for spec in selected['cells']:
            observed = actual.get(spec['name'], {})
            duration = ((observed['finishedNanos'] - observed['startedNanos']) / 1e9
                        if all(type(observed.get(k)) is int for k in ('finishedNanos', 'startedNanos')) else None)
            outcome = observed.get('status', 'Not executed')
            if outcome == 'RUNNING' and status in ('FAIL', 'FAILURE', 'CANCELLED'): outcome = 'Interrupted'
            rows.append((spec['name'], spec['seconds'], outcome, f'{duration:.3f}' if duration is not None else '—',
                         f"{observed['controlOverheadNanos'] / 1e9:.3f}" if type(observed.get('controlOverheadNanos')) is int else '—'))
        table('Scenario results', ['Cell', 'Planned seconds', 'Observed status', 'Elapsed seconds', 'Control overhead seconds'], rows)
    if preflight or review:
        expires = preflight.get('expiresAt', review.get('expiresAt'))
        remaining = max(0, expires - now) if type(expires) is int else None
        github = preflight.get('observations', {}).get('github', {})
        table('Preparation and preflight', ['Field', 'Value'], [
            ('Receipt status when collected', preflight.get('status')), ('Review status', review.get('status')),
            ('Observed / expires', utc(preflight.get('observedAt')) + ' / ' + utc(expires)),
            ('Admission time remaining at summary generation', str(remaining) + ' s' if remaining is not None else 'Unknown'),
            ('Exact-source CI run / conclusion', str(github.get('ciRun', '—')) + ' / ' + str(github.get('ciConclusion', '—'))),
            ('Scheduled cleanup run / conclusion', str(github.get('cleanup', {}).get('run', '—')) + ' / ' + str(github.get('cleanup', {}).get('conclusion', '—'))),
            ('Request SHA-256 (confirmation)', sha(canonical(req)) if req else review.get('requestSha256')),
            ('Preflight SHA-256', sha(canonical(preflight)) if preflight else review.get('preflightSha256')),
            ('Bundle SHA-256', req.get('bundleSha256'))])
        lines.extend(['The 900-second admission window includes dispatch, environment approval and runner startup. '
                      'A READY receipt alone does not authorize a paid run.', ''])
    observed_budget = preflight.get('observations', {}).get('budget', {})
    budget = state.get('budgetReservation') or observed_budget
    reservations = budget.get('reservations')
    reserved = (sum(r['maximumCostMicrousd'] for r in reservations)
                if isinstance(reservations, list) and all(isinstance(r, dict) and type(r.get('maximumCostMicrousd')) is int for r in reservations) else None)
    table('Budget and cleanup', ['Field', 'Value'], [
        ('Complete budget ceiling', usd(p['maximumSequenceCostMicrousd'])),
        ('This request approved maximum', usd(approval.get('maximumCostMicrousd'))),
        ('Cumulative reservation observed', usd(reserved)),
        ('Remaining reservation capacity', usd(p['maximumSequenceCostMicrousd'] - reserved) if reserved is not None else 'Unknown'),
        ('Reservation written by this run', 'Yes' if state.get('budgetReservation') else 'Not recorded'),
        ('Actual billed cost', 'Not collected; reservations are not billing'),
        ('Cleanup result', state.get('cleanup', {}).get('status') or cleanup.get('status') or 'Not recorded'),
        ('Lease released by this runner', 'Yes' if state.get('leaseReleased') else 'Not recorded'),
        ('Active lease reported by cleanup', cleanup.get('activeLease')),
        ('Cleanup identity / verification', str(cleanup_identity.get('principal', '—')) + ' / ' + str(cleanup_identity.get('status', 'Not recorded'))),
        ('Retained lease expiry', utc(cleanup.get('expiresAt'))),
        ('Evidence retention', state.get('retention', 'Not recorded'))])
    if state.get('resources'):
        checks = {v.get('name'): v for v in state.get('cleanup', {}).get('checks', [])}
        rows = []
        for r in state['resources']:
            creation = 'Not attempted' if not r.get('attempted') else 'Rejected' if r.get('insertRejected') else 'ID observed' if r.get('id') else 'Unresolved'
            absent = checks.get(r.get('name'), {}).get('absent')
            rows.append((r.get('name'), r.get('kind'), creation, r.get('id'), 'Absent' if absent is True else 'Unresolved / remaining' if absent is False else 'Not checked'))
        table('Resource lifecycle', ['Name', 'Kind', 'Creation', 'Observed ID', 'Cleanup'], rows)
    blockers = list(dict.fromkeys(preflight.get('blockers', []) + review.get('blockers', [])))
    failures = state.get('errors', []) + cleanup.get('errors', []) + ([entry] if entry else [])
    if blockers or failures or warnings:
        rows = [('Preflight', 'BLOCKED', v) for v in blockers]
        rows += [(v.get('phase', v.get('name', 'Entry')), v.get('type', 'Error'), v.get('message', v.get('error'))) for v in failures]
        rows += [('Summary', 'Incomplete evidence', v) for v in warnings]
        table('Failure details', ['Phase / resource', 'Type', 'Reason'], rows)
    if matrix:
        lines.extend(['Fake execution result: **' + cell(matrix.get('status')) + '**. No real-cloud performance claim.', ''])
    if mode == 'prepare':
        lines.extend(['Next: review v50-prepared, then use its exact request digest and cost approval for a manual run. '
                      'Approve the run environment before the receipt expires.', ''])
    if mode == 'run' and state.get('sequenceReservation') and state.get('status') == 'FAIL':
        lines.extend(['This sequence member failed. Its reservation is retained. Resolve any held lease, '
                      'then prepare a new sequence with the updated budget balance.', ''])
    lines.extend(['Summary generated: ' + utc(now) + '. Artifact receipts remain the detailed evidence.', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--mode', required=True)
    parser.add_argument('--profile', default='admission-probe')
    parser.add_argument('--job-status', default='unknown')
    parser.add_argument('--github-step-summary', type=Path)
    args = parser.parse_args()
    summary = render(args.root, mode=args.mode, profile=args.profile, job_status=args.job_status)
    args.root.mkdir(parents=True, exist_ok=True)
    (args.root / 'summary.md').write_text(summary, encoding='utf-8')
    if args.github_step_summary:
        with args.github_step_summary.open('a', encoding='utf-8') as stream: stream.write(summary)


if __name__ == '__main__': main()
