"""Generate inactive workflow proposals outside .github/workflows; never deploy."""
import argparse
from pathlib import Path
from . import cloud_cleanup_entry as entry, cloud_identity_setup as identities, cloud_preflight as p
from . import performance_model as m
from .remote_command import read, write_once


def render(cfg, trigger):
    m.need(trigger in entry.TRIGGERS, 'cleanup workflow trigger')
    selected = identities.proposal(cfg)['identities'][trigger]
    event = ("  schedule:\n    - cron: '7,22,37,52 * * * *'\n" if trigger == 'schedule' else
             '  workflow_dispatch:\n')
    return ('''# Inactive proposal. Native credentials and reconciliation are not enabled.
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
            --source "$GITHUB_SHA" --output target/v51-cleanup

      - name: Require separately reviewed native activation
        run: python -m scripts.v51.cloud_cleanup_entry activation-check --output target/v51-cleanup

      # No auth action, id-token permission, enable flag or live reconciliation.
      - name: Report cleanup entry and activation boundary
        if: ${{ always() }}
        run: |
          if [[ -f target/v51-cleanup/summary.md ]]; then
            cat target/v51-cleanup/summary.md >> "$GITHUB_STEP_SUMMARY"
          else
            printf '%s\\n' 'V5.1 cleanup entry binding failed; no cloud credentials were acquired.' >> "$GITHUB_STEP_SUMMARY"
          fi

      - name: Retain cleanup entry diagnostics
        if: ${{ always() }}
        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4
        with:
          name: v51-cleanup-'''+trigger+'''-${{ github.run_id }}-${{ github.run_attempt }}
          path: target/v51-cleanup
          if-no-files-found: warn
          retention-days: 14
''')


def write(output, cfg):
    output = Path(output)
    # A generator must not install a schedule even when given an unfortunate path.
    m.need('.github' not in output.resolve().parts, 'workflow proposal cannot target .github')
    value = identities.proposal(cfg)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for trigger in entry.TRIGGERS:
        selected = value['identities'][trigger]
        filename = Path(selected['workflow']).name
        text = render(cfg, trigger); (output/filename).write_text(text)
        rows.append(dict(trigger=trigger, file=filename, intendedWorkflow=selected['workflow'],
                         sha256=m.sha(text.encode()), environment=selected['environment'],
                         serviceAccount=selected['serviceAccount'], provider=selected['provider']))
    receipt = dict(schema='gse-v51-cleanup-workflow-proposal-v1', configurationSha256=value['configurationSha256'],
                   status='PROPOSAL_ONLY', deployed=False, activationAllowed=False, cleanupReady=False,
                   paidCloud=False, fullRemoteQualification=False, entries=rows)
    write_once(output/'receipt.json', receipt)
    (output/'REVIEW.md').write_text(
        '# Native cleanup workflow proposal\n\n'
        'These files are not installed. Both stop at activation-check before any cloud credential or request. '
        'Do not deploy them as an operational watchdog: neither can reclaim live resources yet.\n\n'
        'Manual and scheduled entries have separate frozen workflows/environments/WIF identities and share '
        'one concurrency group. Concurrency is advisory; retained lease generations and exact resource IDs '
        'remain cleanup authority. Manual dispatch has no force, request, bucket, age or resource override.\n\n'
        'Organization/folder policy reads are optional; unavailable inheritance remains an unassessed limitation, not a reason to add privileges. '
        'Before readiness, qualify actual workflow-identity required permissions and forbidden-action probes. '
        'Before activation, review disabled identity application/readback, exact OIDC claims '
        'and environment approval, credential acquisition, native transport, provider reconciliation, '
        'operation-history availability and retained readiness evidence. Removing the stop alone does not '
        'enable cleanup: no auth action or live reconciliation command is present. '
        'Cleanup must remain independent of paid admission and current CI success, while recovering retained '
        'older-source requests from their own authority.\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); print(m.canonical(write(args.output, read(p.CONFIG))).decode())
