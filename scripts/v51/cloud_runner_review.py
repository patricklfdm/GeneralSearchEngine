"""Review-only runner permission-entry package and explicit identity readback.

Enable/disable commands are data for separately approved operator execution.
This module cannot apply them, dispatch workflows or allocate resources.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import time
from . import cloud_authority as a, cloud_ci as ci, cloud_preflight as p
from . import cloud_cleanup_deployment as cleanup, cloud_identity_audit as audit
from . import cloud_identity_setup as identities, cloud_permissions as permissions, performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-runner-review-v1'
OBSERVER_WORKFLOW_SHA256 = 'da5dc893a3044f32dc9a21d12e38ca89b4b58a30c7abf9dbe9ff46dd5f5cf59c'
INPUT = '''    inputs:
      check_runner_permissions:
        description: 'Also check the separately enabled runner identity; no resource allocation'
        type: boolean
        required: false
        default: false
'''
JOB = r'''
  run:
    name: Runner permission precheck (no allocation)
    needs: observations
    if: ${{ inputs.check_runner_permissions == true }}
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    environment: v51-cloud-benchmark
    permissions:
      contents: read
      actions: read
      id-token: write
    env:
      GH_TOKEN: ${{ github.token }}
      PERMISSION_ENVIRONMENT: v51-cloud-benchmark
      RUNNER_PERMISSION_PRECHECK: ${{ inputs.check_runner_permissions }}
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
        with:
          ref: ${{ github.sha }}
          persist-credentials: false

      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Download this attempt's observer evidence
        uses: actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4
        with:
          name: v51-preflight-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-runner-precheck/preflight

      - name: Bind runner identity to fresh same-run observer evidence
        id: identity
        run: |
          python -m scripts.v51.cloud_runner_precheck identity --source "$GITHUB_SHA" \
            --preflight target/v51-runner-precheck/preflight --output target/v51-runner-precheck/identity

      - name: Authenticate exact runner identity for permission queries
        uses: google-github-actions/auth@7c6bc770dae815cd3e89ee6cdf493a5fab2cc093 # v3
        with:
          workload_identity_provider: ${{ steps.identity.outputs.provider }}
          service_account: ${{ steps.identity.outputs.serviceAccount }}
          create_credentials_file: true
          export_environment_variables: true
          cleanup_credentials: true

      - name: Check actual runner permissions without cloud mutations
        run: |
          python -m scripts.v51.cloud_permissions --role runner --source "$GITHUB_SHA" \
            --output target/v51-runner-precheck/permissions

      - name: Report runner permission diagnostics
        if: ${{ always() }}
        run: |
          if [[ -f target/v51-runner-precheck/permissions/summary.md ]]; then
            cat target/v51-runner-precheck/permissions/summary.md >> "$GITHUB_STEP_SUMMARY"
          fi
          python -m scripts.v51.cloud_runner_precheck report --source "$GITHUB_SHA" \
            --preflight target/v51-runner-precheck/preflight --output target/v51-runner-precheck \
            --github-step-summary "$GITHUB_STEP_SUMMARY"

      - name: Retain runner precheck evidence including failures
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: v51-runner-precheck-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-runner-precheck
          if-no-files-found: warn
          retention-days: 14
'''


def workflow(raw=None):
    raw = (ci.ROOT/a.RUNNER_WORKFLOW).read_text() if raw is None else raw
    m.need(raw.endswith(JOB) and raw.count(INPUT) == 1, 'runner workflow entry drift')
    base = raw[:-len(JOB)].replace(INPUT, '', 1)
    m.need(m.sha(base.encode()) == OBSERVER_WORKFLOW_SHA256, 'observer workflow drift')
    return raw.encode()


def text(source):
    return f'''# Runner permission precheck review — NOT APPLIED

Review source: `{source}`. Regenerate against the protected merge before approval.
This package adds an optional diagnostic job at the existing runner workflow,
environment and trust scope. Default observer-only dispatch remains available.

## Scope and sequence

1. Accept this source and exact workflow through protected CI. Run fresh manual
   cleanup on that master; schedule qualification is optional.
2. Collect `cloud_runner_review readback --state disabled` using operator reads.
   All 33 explicit observations / 17 groups must match; manual stays enabled and
   schedule may stay fully enabled or fully disabled. Missing ancestor IAM reads
   remain unassessed, not a new organization-permission requirement.
3. Review these exact runner-only commands and obtain separate enablement approval.
   Execute provider, pool, then account once each, with independent readback after
   every request. Stop and inspect ambiguity rather than replaying a mutation.
   Do not change roles, grants, trust, environments, cleanup identities or budget.
4. Collect `readback --state enabled`; compare with the original observations.
   Only the three runner enable bits may change. A matching configuration is not
   effective IAM qualification, actual workflow credentials or paid admission.
5. The operator dispatches V5.1 Read-only Preflight on master with
   `check_runner_permissions=true` and approves the existing environment gates.
   Its observer job must finish first. The runner job checks the same run/attempt,
   source, complete raw preflight and recent manual artifact before authentication.
   If approval delays exceed evidence freshness, run a new complete dispatch;
   do not rerun only a failed runner job using an earlier attempt's artifacts.
6. Retain native credential/permission receipts. PRECHECK_PASS covers diagnostic
   project/bucket permissions only; actual object conditions, resources, IAP,
   native engine wiring, retention/prices and paid-request approval remain open.

## Authority boundary and rollback

Enabling the runner permits its existing project-wide Compute and conditional
storage/IAP roles to be assumed by the exact reviewed workflow/environment.
Observer and runner jobs share those WIF claims; job ID/input selection is a
workflow control, not an IAM separation. Review the entire protected workflow.
The fixed diagnostic client offers only project POST / bucket GET permission
queries. It cannot allocate resources or mutate the ledger. PRECHECK_PASS does
not authorize future paid execution. No paid runner entry is exposed here.

Rollback commands disable account, provider and pool, preserving manual cleanup
and schedule state. Inspect each result and collect disabled-state readback;
revocation propagation/in-flight credentials require independent observation.
Never delete resources or reset retained charges as part of identity rollback.
All commands in this directory are review data; this generator executes none.
'''


def payloads(cfg, source):
    a.digest(source, 40);p.configuration(cfg)
    return {'v51-replication-evidence.yml':workflow(),
            'commands.json':m.canonical(dict(runner=cleanup.identity_commands(cfg,'runner')))+b'\n',
            'REVIEW.md':text(source).encode()}


def manifest(cfg, source, files):
    return dict(schema=SCHEMA,status='REVIEW_ONLY',source=source,configurationSha256=p.configuration(cfg),
                applied=False,files={name:m.sha(raw) for name,raw in files.items()},**permissions.BOUNDARY)


def generate(cfg, source, output):
    root=Path(output);m.need('.github' not in root.resolve().parts,'review cannot target .github')
    files=payloads(cfg,source);root.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():(root/name).write_bytes(raw)
    result=manifest(cfg,source,files);write_once(root/'review.json',result);return result


def validate(cfg, source, output):
    root=Path(output);files=payloads(cfg,source)
    m.need({v.name for v in root.iterdir()} == set(files)|{'review.json'},'runner review inventory drift')
    m.need(all(not v.is_symlink() and v.is_file() for v in root.iterdir()),'runner review non-file')
    m.need(all((root/name).read_bytes()==raw for name,raw in files.items()),'runner review payload drift')
    expected=manifest(cfg,source,files);m.need(read(root/'review.json')==expected,'runner review manifest drift')
    return expected


def evaluate(cfg, state, value, *, now):
    m.need(state in ('disabled','enabled'),'runner readback state')
    normalized=deepcopy(value);states={};failure=None
    try:
        o=normalized['observations']
        for key in ('runner','manual','schedule'):
            providers=o[key+':providers'];m.need(type(providers) is list and len(providers)==1,'provider inventory')
            objects=(o[key+':account'],o[key+':pool'],providers[0])
            bits=[v.get('disabled',False) for v in objects]
            m.need(all(type(v) is bool for v in bits) and len(set(bits))==1,'mixed or invalid identity enable state')
            if key!='schedule':m.need(bits[0] is (state=='disabled' if key=='runner' else False),'unexpected enable state: '+key)
            states[key]=bits
            for obj in objects:obj['disabled']=True
    except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:failure=dict(status='BLOCKED',reason=str(error)[:180])
    result=audit.evaluate(cfg,'staged',normalized if failure is None else value,now=now)
    result['checks']['enableState']=failure or dict(status='PASS')
    result.update(schema='gse-v51-runner-configuration-review-v1',mode=state,observedDisabled=states,
                  status='CONFIGURATION_MATCH' if all(v['status']=='PASS' for v in result['checks'].values()) else 'BLOCKED',
                  **permissions.BOUNDARY)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('generate','validate','readback'))
    parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--state',choices=('disabled','enabled'));args=parser.parse_args()
    cfg=read(p.CONFIG);a.digest(args.source,40)
    m.need(subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()==args.source,'review source must match checkout')
    if args.action=='readback':
        m.need(args.state is not None,'runner readback state required')
        args.output.mkdir(parents=True,exist_ok=False);observed=audit.collect(cfg,'staged')
        write_once(args.output/'observations.json',observed)
        value=evaluate(cfg,args.state,observed,now=int(time.time()));value.update(source=args.source,execution='read-only-runner-configuration')
        write_once(args.output/'receipt.json',value)
    else:value=(generate if args.action=='generate' else validate)(cfg,args.source,args.output)
    print(m.canonical(value).decode())
    if value['status']=='BLOCKED':raise SystemExit(2)


if __name__=='__main__':main()
