"""Review-only single-disk plan; execution uses the separate exact-request driver."""
import argparse
from pathlib import Path
from . import cloud_authority as a, cloud_preflight as p
from . import cloud_cleanup_deployment as deployment, performance_model as m, remote_command as c

SCHEMA = 'gse-v51-cleanup-fixture-review-v1'
BOUNDARY = dict(applied=False, paidCloud=False, cleanupReady=False, paidAdmission=False,
                fullRemoteQualification=False, objectPermissionsQualified=False)
CASES = ('active', 'grace', 'expired-disk', 'lost-insert-response', 'missing-context',
         'reused-name', 'delete-denied', 'generation-conflict')


def plan(cfg, source):
    a.digest(source, 40)
    return dict(schema=SCHEMA, status='REVIEW_ONLY', source=source,
        configurationSha256=p.configuration(cfg),
        workflowSha256=m.sha(deployment.render(cfg, 'manual').encode()),
        resource=dict(kind='disk', purpose='data', node=1, sizeGiB=100,
                      diskType=cfg['provider']['diskType'], zone=cfg['provider']['zone'],
                      maximumCount=1, instances=0, firewalls=0, bootDisks=0),
        authority=dict(resourceInventory='unchanged-native-13-row-inventory',
                       attemptedRows=['n1-data'], requestMember='experiment',
                       sequence='new-dedicated-qualification-sequence',
                       completionStatus='FAIL', engineWorkloadExecuted=False,
                       leaseSeconds=5400, graceSeconds=1080, backdatingAllowed=False,
                       leaseKey=a.LEASE, ledgerKey=a.LEDGER, ledgerResetAllowed=False),
        actors=dict(prepare='separately-approved-operator', reconcile='manual-workflow-identity',
                    observe='independent-read-only-collector', scheduledEnabled=False, runnerEnabled=False),
        stages=[dict(case='active', elapsedMinimum=0, elapsedMaximumExclusive=5400, expected='WAITING'),
                dict(case='grace', elapsedMinimum=5400, elapsedMaximumExclusive=6480, expected='WAITING'),
                dict(case='expired-disk', elapsedMinimum=6480, expected='PASS',
                     minimumPreviouslyPresentResources=1, attemptedResources=1)],
        objectProbes=dict(execution='IMPLEMENTED_NOT_QUALIFIED', identity='manual',
            cases=['attempt-canary-create-read', 'attempt-canary-overwrite-denied',
                   'attempt-canary-delete-denied', 'outside-canary-read-write-delete-denied'],
            destructiveTarget='none', existingCanaryRequired=True,
            writeDeletePrecondition='ifGenerationMatch=0', expectedDenial=403,
            inconclusiveStatuses=[400, 401, 404, 409, 412, 429, 500, 503],
            verifyUnchangedGenerationAndBytes=True, realProbeDriverAvailable=True),
        budget=dict(proposedReservationMicrousd=1_000_000, cumulativeCeilingMicrousd=a.MAXIMUM_BUDGET_MICROUSD,
                    currency='USD', priceQualified=False,
                    regionalPriceRequired='us-west4/pd-balanced', retentionDays=30,
                    includes=['disk-until-confirmed-absence', 'control-and-canary-objects',
                              'evidence-retention', 'requests', 'actions', 'failure-overhang'],
                    hardProviderSpendingCap=False, remainingLedgerBudgetRequired=True),
        prerequisites=['protected-source-and-workflow-bytes', 'fresh-manual-configuration-readback',
            'operator-availability-through-expiry-and-grace', 'fresh-empty-lease-and-no-pending-attempt',
            'reviewed-regional-prices-and-bounded-request-inventory', 'exact-fixture-request-approval',
            'fresh-real-request-time-and-unique-attempt-sequence', 'fixture-manifest-bundle-digest',
            'public-SSH-format-binding-with-no-VM-or-private-key-distribution',
            'CAS-lease-and-ledger-before-durable-create-intent', 'once-only-original-operation',
            'actual-identity-object-probe-driver-and-approval', 'provider-audit-evidence'],
        offlineCases=list(CASES), **BOUNDARY)


def review_text():
    return '''# Single-disk cleanup fixture — REVIEW ONLY

No cloud commands or native control records are executed by this package.
The operator's prior approval covers the manual identity and workflow only.
This fixture, object probes and its proposed USD 1 reservation need separate
review after current regional prices and exact request bytes are available.

## Sequence

1. Protect/merge the implementation; refresh source, configuration and empty
   lease/ledger observations. Do not overwrite a lease or a pending reservation.
2. Prepare a fresh native request with a separate sequence/attempt and a digest
   of the qualification manifest, not a claimed engine workload bundle. Keep the
   native public SSH format binding; no VM or SSH private-key distribution is needed.
3. Reserve the reviewed cost without resetting prior charges. Keep all 13 native
   inventory rows but mark only n1-data attempted, durably before its insert.
   Retain the exact configuration/context and the original deterministic requestId.
4. Create one existing-shape 100 GiB pd-balanced data disk. Resolve the original
   operation and numeric ID; never blindly replay an ambiguous create request.
5. Bracket operator-triggered manual runs with independent observations: active
   WAITING before 5400 seconds, grace WAITING from 5400 to 6480, then expired
   cleanup at or after 6480. Actual wall time must elapse; never shorten or backdate
   the lease. The minimum wait is 108 minutes and does not bound scheduler delay.
6. The successful cleanup must independently show one previously present disk,
   original-operation/numeric-ID absence, retained FAIL completion with no workload,
   unchanged reserved charge, correct terminal ledger append and lease release.
   Keep provider principal/operation audit evidence. A zero-resource PASS is insufficient.

## Object permission probes

The separate cloud_object_probes driver uses the manual workflow's optional
object_probe_request input after exact fixture approval. Use dedicated canaries;
never completion/context or
other retained evidence as destructive targets. Establish the canary's existence,
generation and contents, and independently verify they are unchanged afterward.
Guard overwrite/delete attempts with ifGenerationMatch=0. Only an authenticated
403 can qualify the specified denial; 412 is a precondition result, not IAM proof.
Unavailable, malformed or other responses block that case. Stop on unexpected
success; retain all evidence and inspect state. Do not broaden permissions.

## Cost and recovery

The cumulative ledger ceiling is USD 200; all previous charges remain recorded.
USD 1 is a proposed ledger reservation, not a current quote, payment approval or
provider spending cap. Verify us-west4 disk pricing plus requests, retention,
Actions and failure overhang before allocation. Disk charges continue until
absence is confirmed; do not promise an unattended deadline while schedule is
disabled. The operator must remain available through cleanup or postpone creation.
If cleanup fails, preserve the lease, original operations, evidence and charges;
inspect and reconcile the same authority. Do not clear control objects or delete
by name. There is no force-delete or rollback-to-empty-ledger operation.

## Boundaries

The local matrix tests native-format records through an offline HTTP model. It
does not establish Google IAM, real operation behavior, expiry passage or deletion.
Real name reuse, ambiguous operations, generation conflicts, failure recovery,
instance/firewall cleanup and scheduled identity coverage remain pending.
The separate cloud_fixture_driver requires a clean protected source, current
prices/state/configuration, the reviewed operator and exact fixture confirmation.
This review package never invokes it or dispatches a workflow. Live execution and
its evidence remain separate; the paid runner stays closed.
'''


def payloads(cfg, source):
    return {'plan.json':m.canonical(plan(cfg, source))+b'\n', 'REVIEW.md':review_text().encode()}


def manifest(cfg, source, files):
    return dict(schema=SCHEMA, status='REVIEW_ONLY', source=source,
                configurationSha256=p.configuration(cfg),
                files={name:m.sha(data) for name,data in files.items()}, **BOUNDARY)


def write(output, cfg, source):
    output=Path(output)
    m.need('.github' not in output.resolve().parts, 'fixture review cannot target .github')
    files=payloads(cfg, source); result=manifest(cfg, source, files)
    output.mkdir(parents=True, exist_ok=False)
    for name,data in files.items(): (output/name).write_bytes(data)
    c.write_once(output/'review.json', result)
    return result


def validate(output, cfg, source):
    output=Path(output); files=payloads(cfg, source)
    m.need(not output.is_symlink() and output.is_dir(), 'fixture review directory')
    m.need({f.name for f in output.iterdir()}==set(files)|{'review.json'}, 'fixture review inventory')
    for name,data in files.items():
        path=output/name
        m.need(not path.is_symlink() and path.is_file() and path.read_bytes()==data,
               'fixture review payload drift: '+name)
    path=output/'review.json'
    m.need(not path.is_symlink() and path.is_file(), 'fixture review manifest')
    expected=manifest(cfg, source, files)
    m.need(c.read(path)==expected, 'fixture review manifest drift')
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('generate','validate'))
    parser.add_argument('--source', required=True); parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    result=(write if args.command=='generate' else validate)(args.output,c.read(p.CONFIG),args.source)
    print(m.canonical(result).decode())


if __name__=='__main__': main()
