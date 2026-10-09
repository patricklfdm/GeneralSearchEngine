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
RUNNER_JOB_NAME = 'Runner precheck and approved execution'
ORIGINAL_HEADER = '# Observation-only stage. No prepared run, paid execution or cleanup is exposed.\nname: V5.1 Read-only Preflight\n'
HEADER = '# Read-only by default. Storage and experiment require separate exact confirmation.\nname: V5.1 Preflight and Experiment Runner\n'
INPUT = '''    inputs:
      check_runner_permissions:
        description: 'Also check the separately enabled runner identity; no resource allocation'
        type: boolean
        required: false
        default: false
      runner_storage_request:
        description: 'Optional prepared storage plan SHA-256; empty keeps diagnostic-only mode'
        type: string
        required: false
        default: ''
      runner_storage_confirmation:
        description: 'Exact prepared manifest SHA-256; confirms a separate USD 1 Runner reservation'
        type: string
        required: false
        default: ''
      runner_experiment:
        description: 'off is diagnostic-only; prepare allocates nothing; run requires a reviewed plan'
        type: choice
        options: ['off', prepare, run]
        required: false
        default: 'off'
      runner_member:
        description: 'Exact member for both prepare and run; run must match the prepared plan'
        type: choice
        options: [experiment, failure-drill, canonical-1, canonical-2, canonical-3]
        required: false
        default: experiment
      runner_order:
        description: 'Immutable sequence order; failed canonical requires a new sequence'
        type: choice
        options: [experiment-first, canonical-first]
        required: false
        default: experiment-first
      runner_experiment_quote:
        description: 'prepare only; JSON with prices, maximumCostMicrousd and sequence (32 hex)'
        type: string
        required: false
        default: ''
      runner_prepared_run:
        description: 'run only; completed first-attempt preparation run ID on this exact master'
        type: string
        required: false
        default: ''
      runner_experiment_confirmation:
        description: 'run only; exact plan SHA-256 approves its reservation and 15-minute admission window'
        type: string
        required: false
        default: ''
'''
JOB = r'''
  run:
    name: Runner precheck and approved execution
    needs: observations
    if: ${{ inputs.check_runner_permissions == true || inputs.runner_storage_request != '' || inputs.runner_storage_confirmation != '' || inputs.runner_experiment != 'off' || inputs.runner_experiment_quote != '' || inputs.runner_prepared_run != '' || inputs.runner_experiment_confirmation != '' }}
    runs-on: ubuntu-24.04
    timeout-minutes: ${{ inputs.runner_experiment == 'run' && (startsWith(inputs.runner_member, 'canonical-') && 360 || inputs.runner_member == 'failure-drill' && 330 || 270) || 15 }}
    environment: v51-cloud-benchmark
    permissions:
      contents: read
      actions: read
      id-token: write
    env:
      GH_TOKEN: ${{ github.token }}
      PERMISSION_ENVIRONMENT: v51-cloud-benchmark
      RUNNER_PERMISSION_PRECHECK: ${{ inputs.check_runner_permissions }}
      RUNNER_STORAGE_REQUEST: ${{ inputs.runner_storage_request }}
      RUNNER_STORAGE_CONFIRMATION: ${{ inputs.runner_storage_confirmation }}
      RUNNER_EXPERIMENT: ${{ inputs.runner_experiment }}
      RUNNER_MEMBER: ${{ inputs.runner_member }}
      RUNNER_ORDER: ${{ inputs.runner_order }}
      RUNNER_EXPERIMENT_QUOTE: ${{ inputs.runner_experiment_quote }}
      RUNNER_PREPARED_RUN: ${{ inputs.runner_prepared_run }}
      RUNNER_EXPERIMENT_CONFIRMATION: ${{ inputs.runner_experiment_confirmation }}
    steps:
      - uses: actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803 # v6
        with:
          ref: ${{ github.sha }}
          persist-credentials: false

      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: '3.11'

      - name: Validate Runner selections before authentication
        run: |
          python -m scripts.v51.cloud_runner_storage_entry guard --source "$GITHUB_SHA"
          python -m scripts.v51.cloud_runner_entry guard --source "$GITHUB_SHA"

      - name: Set up pinned Java for original experiment build binding
        if: ${{ inputs.runner_experiment != 'off' }}
        uses: actions/setup-java@b6effb05e454b25005698d916606bdc6ffcbf961 # v5
        with:
          distribution: temurin
          java-version: '21.0.12+8.0.LTS'

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

      - name: Install pinned Cloud CLI for native IAP
        if: ${{ inputs.runner_experiment == 'run' }}
        uses: google-github-actions/setup-gcloud@aa5489c8933f4cc7a4f7d45035b3b1440c9c10db # v3
        with:
          version: '582.0.0'

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

      - name: Qualify exact approved Runner storage request (no allocation)
        if: ${{ success() && inputs.runner_storage_request != '' }}
        run: |
          python -m scripts.v51.cloud_runner_storage_entry run --source "$GITHUB_SHA" \
            --preflight target/v51-runner-precheck/preflight --precheck target/v51-runner-precheck \
            --output target/v51-runner-precheck/storage

      - name: Report Runner storage outcome including failures
        if: ${{ always() && inputs.runner_storage_request != '' }}
        run: |
          if [[ -f target/v51-runner-precheck/storage/summary.md ]]; then
            cat target/v51-runner-precheck/storage/summary.md >> "$GITHUB_STEP_SUMMARY"
          else
            echo 'Runner storage entry did not start; inspect the binding/precheck failure.' >> "$GITHUB_STEP_SUMMARY"
          fi

      - name: Prepare exact V5.1 experiment for review (no allocation)
        if: ${{ success() && inputs.runner_experiment == 'prepare' }}
        env:
          V51_EXPERIMENT_SSH_KEY: ${{ secrets.V51_EXPERIMENT_SSH_KEY }}
        run: |
          timeout --signal=TERM --kill-after=10s 600s python -m scripts.v51.cloud_runner_entry prepare --source "$GITHUB_SHA" \
            --preflight target/v51-runner-precheck/preflight --precheck target/v51-runner-precheck \
            --output target/v51-experiment

      - name: Retain public experiment preparation
        if: ${{ success() && inputs.runner_experiment == 'prepare' }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: v51-experiment-prepared-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-experiment/prepared
          if-no-files-found: error
          retention-days: 14

      - name: Run exact approved native V5.1 experiment
        if: ${{ success() && inputs.runner_experiment == 'run' }}
        env:
          V51_EXPERIMENT_SSH_KEY: ${{ secrets.V51_EXPERIMENT_SSH_KEY }}
        run: |
          case "$RUNNER_MEMBER" in
            experiment) guard_seconds=15000 ;;
            failure-drill) guard_seconds=16500 ;;
            canonical-1|canonical-2|canonical-3) guard_seconds=20100 ;;
            *) exit 2 ;;
          esac
          timeout --signal=TERM --kill-after=60s "${guard_seconds}s" python -m scripts.v51.cloud_runner_entry run --source "$GITHUB_SHA" \
            --preflight target/v51-runner-precheck/preflight --precheck target/v51-runner-precheck \
            --output target/v51-experiment

      - name: Report native experiment parameters and outcomes
        if: ${{ always() && inputs.runner_experiment != 'off' }}
        run: |
          python -m scripts.v51.cloud_runner_entry summary --output target/v51-experiment \
            --github-step-summary "$GITHUB_STEP_SUMMARY"

      - name: Retain native experiment evidence including failures
        if: ${{ always() && inputs.runner_experiment != 'off' }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: v51-experiment-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-experiment
          if-no-files-found: warn
          retention-days: 30

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
    m.need(raw.startswith(HEADER), 'runner workflow header drift')
    base = raw[:-len(JOB)].replace(INPUT, '', 1).replace(HEADER, ORIGINAL_HEADER, 1)
    m.need(m.sha(base.encode()) == OBSERVER_WORKFLOW_SHA256, 'observer workflow drift')
    return raw.encode()


def text(source):
    return f'''# V5.1 Runner workflow review — NOT EXECUTED

Review source: `{source}`. Regenerate after the protected merge before running.
The existing runner identity is enabled. This change adds explicit prepare/run
selections at the same workflow, master ref and environment; no IAM, WIF, role,
cleanup identity or budget change is required. The default remains read-only.
This generator neither dispatches a workflow nor applies the included commands.

## Entry review

- Review the entire installed workflow. Observer and runner jobs share WIF claims;
  job ID and input checks are workflow controls, not separate IAM identities.
- Preserve the original observer bytes, same-run raw evidence, manual cleanup,
  current exact-source CI and Runner permission checks. Schedule is optional.
- Storage remains separately selected and confirmed. It cannot run alongside
  experiment preparation/execution. Its two USD 1 stages retain their own charges.
- `runner_member` selects experiment, failure-drill or canonical-1/2/3;
  `runner_order` fixes experiment-first or canonical-first for the sequence.
  Prepare and run must select the same member/order on the same source/package.
- `runner_experiment=prepare` requires reviewed current prices, an explicit maximum
  reservation, sequence and the environment SSH secret. It only reads and builds a
  public plan from original CI artifacts. It makes no resource or ledger writes.
- Review the resulting plan, original artifacts, topology, estimate, prior charges,
  maximum reservation, 15-minute admission window and reviewed timing allocation.
  Preparation/lease ceilings are 3600/14400 seconds for experiment, 3600/16200
  for failure-drill and 5400/19800 for canonical. All work shares the original
  admitted lease; exact per-cell and retention limits are bound into the plan.
  Preparation is not paid approval.
- `runner_experiment=run` needs its preparation run ID and exact plan SHA-256, fresh
  same-run observations and environment approval. Only this selection calls the
  selected native preset. The digest confirms the entire original plan, including
  cost and expiry; it cannot change the plan or approve a different private key.
- A changed source, CI artifact, retained ledger, expired plan, missing permission,
  reused attempt, replaced secret or mixed selection blocks admission. Failed
  charges remain recorded; no retry/resume or budget reset is provided.

## SSH secret and operations

Use an unencrypted, empty-comment Ed25519 key in the protected environment secret
`V51_EXPERIMENT_SSH_KEY`. Keep the same key through preparation and its execution.
Only its public descriptor enters artifacts. The CLI removes the secret from its
subprocess environment, writes it under RUNNER_TEMP outside artifact roots, and
removes that temporary copy on exit. Do not upload a private key as a plan input.
Secret setup/removal, dispatch and approvals are separate operator actions; this
review does not perform them. Never rotate the key for an in-flight experiment.

The full procedure and result boundaries are in PHASE_6_NATIVE_RUNNER_ENTRY.md.
First accept this source with protected CI, then configure the secret, perform
fresh manual cleanup, prepare and review the exact plan, and manually dispatch
its run before expiry. Actual cloud execution remains unqualified until observed.

## Identity rollback

Runner enable/disable commands are retained for separately reviewed operations.
Do not repeat enablement for the already enabled deployment. If rollback is
required, disable only account/provider/pool in the prescribed order, observe each
outcome, then collect readback. Preserve manual cleanup, retained leases, evidence
and all charges. A request timeout is not permission to repeat a mutation.
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
