"""Review-only cleanup deployment package and read-only activation-state audit.

No apply, copy-to-workflows, enable, dispatch or reconcile command is executed.
The earlier disabled proposal and its strict staged audit remain unchanged.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import re
import subprocess
import time
from . import cloud_cleanup_entry as entry, cloud_identity_setup as setup
from . import cloud_identity_audit as audit, cloud_preflight as preflight
from . import cloud_ci as ci, performance_model as m, remote_command as c

STATES = {'staged': (), 'manual': ('manual',), 'cleanup': ('manual', 'schedule')}
SCHEMA = 'gse-v51-cleanup-deployment-review-v1'
BOUNDARY = dict(activationAllowed=False, effectiveIamQualified=False, cleanupReady=False,
                paidAdmission=False, paidCloud=False, fullRemoteQualification=False)


def render(cfg, trigger):
    m.need(trigger in entry.TRIGGERS, 'cleanup workflow trigger')
    selected = setup.proposal(cfg)['identities'][trigger]
    event = ("  schedule:\n    - cron: '7,22,37,52 * * * *'\n" if trigger == 'schedule' else
             '  workflow_dispatch:\n')
    text = '''# Generated cleanup entry; dispatch and environment approval remain manual.
name: V5.1 '''+('Scheduled' if trigger == 'schedule' else 'Manual')+''' Cleanup

on:
'''+event+'''
permissions:
  contents: read
  actions: read

concurrency:
  group: v51-native-cleanup
  cancel-in-progress: false

jobs:
  cleanup:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    environment: '''+selected['environment']+'''
    permissions:
      contents: read
      actions: read
      id-token: write
    env:
      GH_TOKEN: ${{ github.token }}
      CLEANUP_ENVIRONMENT: '''+selected['environment']+'''
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
        with:
          ref: ${{ github.sha }}
          persist-credentials: false

      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Bind cleanup entry and exact run attempt
        id: identity
        run: |
          python -m scripts.v51.cloud_cleanup_entry identity --trigger '''+trigger+''' \\
            --source "$GITHUB_SHA" --output target/v51-cleanup/identity

      - name: Authenticate exact cleanup identity
        uses: google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3
        with:
          workload_identity_provider: ${{ steps.identity.outputs.provider }}
          service_account: ${{ steps.identity.outputs.serviceAccount }}
          create_credentials_file: true
          export_environment_variables: true
          cleanup_credentials: true

      - name: Check actual cleanup permissions without cloud mutations
        run: |
          python -m scripts.v51.cloud_permissions --role '''+trigger+''' --source "$GITHUB_SHA" \\
            --output target/v51-cleanup/permissions

      - name: Reconcile retained expired lease
        run: |
          python -m scripts.v51.cloud_cleanup_entry reconcile --trigger '''+trigger+''' \\
            --source "$GITHUB_SHA" --output target/v51-cleanup/reconciliation

      - name: Report cleanup result
        if: ${{ always() }}
        run: |
          if [[ -f target/v51-cleanup/permissions/summary.md ]]; then
            cat target/v51-cleanup/permissions/summary.md >> "$GITHUB_STEP_SUMMARY"
          fi
          if [[ -f target/v51-cleanup/reconciliation/summary.md ]]; then
            cat target/v51-cleanup/reconciliation/summary.md >> "$GITHUB_STEP_SUMMARY"
          else
            printf '%s\\n' 'V5.1 cleanup stopped before a reconciliation receipt; inspect entry/auth step results. Cleanup readiness is not established.' >> "$GITHUB_STEP_SUMMARY"
          fi

      - name: Retain cleanup diagnostics
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: v51-cleanup-'''+trigger+'''-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-cleanup
          if-no-files-found: warn
          retention-days: 14
'''

    return probe_steps(text) if trigger=='manual' else text


def probe_steps(text):
    """Add the optional, exact-request canary entry to the manual workflow."""
    text=text.replace('  workflow_dispatch:\n','''  workflow_dispatch:
    inputs:
      object_probe_request:
        description: 'Optional approved single-disk request SHA-256; creates one fixed canary'
        required: false
        default: ''
        type: string
''',1)
    marker='      - name: Reconcile retained expired lease\n'
    text=text.replace(marker,'''      - name: Probe approved cleanup object scope
        if: ${{ inputs.object_probe_request != '' }}
        env:
          OBJECT_PROBE_REQUEST: ${{ inputs.object_probe_request }}
        run: |
          python -m scripts.v51.cloud_object_probes run --request "$OBJECT_PROBE_REQUEST" \\
            --source "$GITHUB_SHA" --output target/v51-cleanup/object-probes

'''+marker,1)
    marker='          if [[ -f target/v51-cleanup/permissions/summary.md ]]; then\n'
    return text.replace(marker,'''          if [[ -f target/v51-cleanup/object-probes/summary.md ]]; then
            cat target/v51-cleanup/object-probes/summary.md >> "$GITHUB_STEP_SUMMARY"
          fi
'''+marker,1)


def commands(cfg):
    """Structured operator plans; deliberately no executor or IAM-grant commands."""
    wanted = setup.proposal(cfg); result = {}
    project = '--project='+wanted['project']
    for key in ('manual', 'schedule'):
        identity = wanted['identities'][key]
        account = ['gcloud', 'iam', 'service-accounts']
        pool = ['gcloud', 'iam', 'workload-identity-pools', 'update', identity['name'],
                project, '--location=global']
        provider = ['gcloud', 'iam', 'workload-identity-pools', 'providers', 'update-oidc', 'github',
                    project, '--location=global', '--workload-identity-pool='+identity['name']]
        result[key] = dict(
            enable=[[*provider, '--no-disabled'], [*pool, '--no-disabled'],
                    [*account, 'enable', identity['serviceAccount'], project]],
            disable=[[*account, 'disable', identity['serviceAccount'], project],
                     [*provider, '--disabled'], [*pool, '--disabled']])
    return result


def review_text(source):
    return '''# Cleanup deployment review — NOT APPLIED

Review base: `'''+source+'''`. The deployed checkout must be the separately
reviewed master merge containing these exact workflow bytes and the accepted
cleanup implementation. Regenerate/review after relevant source or IAM drift.

This package contains two runnable workflow proposals and structured enable /
disable command lists. Nothing installs or executes them. Do not run a command
list wholesale: each request is submitted once, followed by state inspection;
stop on failure or ambiguity. The runner stays disabled in every reviewed state.

## Preconditions and order

1. Protected CI must accept the implementation and this proposal. Check this
   package against the trusted configuration/source with the validator. Obtain
   separate operator approval for deployment and the exact two cleanup identities.
2. Collect fresh explicit identity/grant/environment observations, including
   exact project/bucket/account bindings and role contents. Missing, denied or
   mismatched required observations still block this review. Organization/folder
   policy reads are optional: retain unavailable reads as an unassessed limitation,
   never as an empty policy. Do not add organization roles or read permissions to
   the observer, runner or cleanup identities for this review. Credential exchange
   or positive provider calls alone do not prove absence of extra privileges.
3. Deploy the exact workflow files in a separately reviewed change while all
   three identities remain disabled. Confirm the protected master bytes and exact
   workflow paths. A schedule may start and fail authentication in this state;
   that is not a working watchdog and does not establish cleanup readiness.
4. After approval and fresh staged readback, enable only manual provider, pool,
   then account. Inspect each requested state; do not replay an ambiguous update.
   Use readback --state manual to check all three identities, trust, roles,
   grants and environments. Scheduled and runner credentials must stay disabled.
5. The operator dispatches manual cleanup on master and approves its environment.
   The workflow first runs the bound project/bucket permission precheck. Missing
   required or returned forbidden permissions block reconciliation. PRECHECK_PASS
   is diagnostic only: bucket tests cannot establish object-name conditions, and
   no object testIamPermissions endpoint exists. Object-scope and conditional IAP
   qualification remain separate; never broaden grants to satisfy a bucket test.
   Retain actual OIDC/STS/impersonation/provider results without secrets. Before
   treating either identity as ready, verify required access and forbidden-action
   probes using that workflow's actual service account. Required permission denial,
   inconclusive probes or forbidden access block readiness. Never use an operator's
   own access or another identity's success as proof. A no-lease PASS tests only
   the empty path. Independently qualify active/grace WAITING,
   expired exact-ID deletion, ownership/operation ambiguity, generation conflicts,
   failure retention and failed charges with a separately reviewed bounded fixture.
   This package does not create a fixture, reserve budget or allocate resources.
6. Enable schedule provider, pool, then account only after the preceding review.
   Use readback --state cleanup; retain a real scheduled run and separately
   establish readiness. Both triggers share the same reconciler and advisory
   concurrency group; a waiting manual run can delay the schedule. Approve or
   cancel abandoned waiting runs. Do not treat scheduler/concurrency timing as a
   guarantee: lease CAS, expiry/grace and exact IDs remain deletion authority.

## Stop / rollback

Disable the affected service account first, then its provider and pool, using
commands.json. Roll back schedule to the manual state or both cleanup identities
to staged; collect fresh readback. Do not enable the runner, delete resources,
change grants, reset the ledger, release a lease, or erase failed evidence as
part of rollback. Provider disabling alone does not revoke existing credentials;
account/pool disablement and independent observations matter. Revocation may
propagate asynchronously. A successful disable request is not absence evidence
for resources and does not finish a cleanup already in progress.

## Evidence boundaries

All package/audit readiness, activation, effective-IAM and paid flags remain false.
The effectiveIamQualified=false field retains the comprehensive-audit limitation;
it is not a standalone ancestor-policy-read gate. Actual-identity required and
forbidden permission checks and real cleanup qualification remain prerequisites.
A configuration match is not an authorization, authenticated provider test or
working-watchdog receipt. Runtime PASS/WAITING has the same qualification limit.
No paid runner path is deployed or enabled. Resource expiry, budgets, ownership,
exact IDs, terminal evidence and admission rules are unchanged.
'''


def payloads(cfg, source):
    m.need(isinstance(source, str) and re.fullmatch('[0-9a-f]{40}', source), 'review source SHA')
    wanted = setup.proposal(cfg)
    files = {Path(wanted['identities'][key]['workflow']).name: render(cfg, key).encode()
             for key in entry.TRIGGERS}
    files['commands.json'] = m.canonical(commands(cfg))+b'\n'
    files['REVIEW.md'] = review_text(source).encode()
    return files


def manifest(cfg, source, files):
    return dict(schema=SCHEMA, status='REVIEW_ONLY', source=source,
                configurationSha256=preflight.configuration(cfg), deployed=False, applied=False,
                files={name:m.sha(data) for name, data in files.items()}, **BOUNDARY)


def write(output, cfg, source):
    output = Path(output)
    m.need('.github' not in output.resolve().parts, 'deployment proposal cannot target .github')
    files = payloads(cfg, source); value = manifest(cfg, source, files)
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items(): (output/name).write_bytes(data)
    c.write_once(output/'review.json', value)
    return value


def validate(output, cfg, source):
    """Compare to trusted generator/config/source, not only self-reported hashes."""
    output = Path(output); files = payloads(cfg, source)
    m.need(not output.is_symlink() and output.is_dir(), 'review package directory')
    m.need({p.name for p in output.iterdir()} == set(files) | {'review.json'}, 'review package inventory')
    for name, expected in files.items():
        path = output/name
        m.need(not path.is_symlink() and path.is_file() and path.read_bytes() == expected,
               'review payload drift: '+name)
    path = output/'review.json'
    m.need(not path.is_symlink() and path.is_file(), 'review manifest file')
    expected = manifest(cfg, source, files)
    m.need(c.read(path) == expected, 'review manifest drift')
    return expected


def evaluate(cfg, state, value, *, now):
    """Validate all nine enable bits before reusing the strict staged policy audit."""
    m.need(state in STATES, 'cleanup deployment state')
    normalized = deepcopy(value); states = {}; failure = None
    try:
        observations = normalized['observations']
        for key in ('runner', 'manual', 'schedule'):
            disabled = key not in STATES[state]
            providers = observations[key+':providers']
            m.need(type(providers) is list and len(providers) == 1, 'provider inventory')
            objects = (observations[key+':account'], observations[key+':pool'], providers[0])
            states[key] = []
            for obj in objects:
                # Google JSON responses may omit a default false boolean.
                actual = obj.get('disabled', False)
                m.need(type(actual) is bool and actual is disabled, 'unexpected enable state: '+key)
                states[key].append(actual)
                obj['disabled'] = True
    except (ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        failure = dict(status='BLOCKED', reason=str(error)[:200])
    result = audit.evaluate(cfg, 'staged', normalized if failure is None else value, now=now)
    result['checks']['enableState'] = failure or dict(status='PASS')
    result.update(schema='gse-v51-cleanup-deployment-audit-v1', mode=state, observedDisabled=states,
                  status='CONFIGURATION_MATCH' if all(v['status']=='PASS' for v in result['checks'].values()) else 'BLOCKED',
                  limitations=[preflight.IAM_LIMITATION,
                               'Matching enabled state does not authorize activation or establish cleanup/paid readiness.'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('generate', 'validate'):
        p = sub.add_parser(command); p.add_argument('--output', type=Path, required=True)
        p.add_argument('--source', required=True)
    p = sub.add_parser('readback'); p.add_argument('--state', choices=STATES, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); cfg = c.read(preflight.CONFIG)
    if args.command == 'readback':
        args.output.mkdir(parents=True, exist_ok=False)
        observations = audit.collect(cfg, 'staged'); c.write_once(args.output/'observations.json', observations)
        result = evaluate(cfg, args.state, observations, now=int(time.time()))
        result['execution'] = 'read-only-cleanup-deployment-audit'
        result['source'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ci.ROOT, text=True).strip()
        c.write_once(args.output/'receipt.json', result)
    else:
        fn = write if args.command == 'generate' else validate
        result = fn(args.output, cfg, args.source)
    print(m.canonical(result).decode())
    return 2 if result['status'] == 'BLOCKED' else 0


if __name__ == '__main__': raise SystemExit(main())
