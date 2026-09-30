"""Fresh-process qualification of both bound cleanup entries, without credentials."""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from . import cloud_cleanup_entry as e, cloud_cleanup_qualification as q, cloud_native_authority as n
from . import cloud_ci as ci, cloud_preflight as p, cloud_identity_setup as identities, cloud_cleanup_workflows as workflows
from . import performance_model as m
from .remote_command import read, write_once

SOURCE = 'c'*40  # Intentionally differs from the abandoned request's source.


def fixture(configuration, trigger):
    cfg = read(p.CONFIG)
    cfg['provider'] = deepcopy(configuration)
    cfg['observerServiceAccount'] = 'gse-v51-observer@'+configuration['project']+'.iam.gserviceaccount.com'
    selected = identities.proposal(cfg)['identities'][trigger]
    claims = selected['claims']
    env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=ci.REPOSITORY,
               GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID), GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),
               GITHUB_EVENT_NAME=claims['event_name'], GITHUB_REF=claims['ref'], GITHUB_SHA=SOURCE,
               GITHUB_WORKFLOW_REF=claims['workflow_ref'], GITHUB_WORKFLOW_SHA=SOURCE,
               GITHUB_JOB='cleanup', CLEANUP_ENVIRONMENT=selected['environment'],
               GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT='2')
    repo = dict(id=ci.REPOSITORY_ID, full_name=ci.REPOSITORY, owner=dict(id=ci.OWNER_ID))
    observation = dict(id=12345, run_attempt=2, repository=repo, head_repository=deepcopy(repo),
                       head_sha=SOURCE, head_branch='master', path=selected['workflow'],
                       event=claims['event_name'], status='in_progress', conclusion=None)
    return dict(configuration=cfg, env=env, observation=observation, trigger=trigger, source=SOURCE, checkout=SOURCE)


def replay(state, invocation, output, now, *, integrated=False):
    clock, http, api, _ = q.restore(state)
    arguments = dict(trigger=invocation['trigger'], source=invocation['source'], checkout=invocation['checkout'], now=now)
    if integrated:
        from . import cloud_cleanup_auth_fake as auth
        binding = e.identity(invocation['configuration'], invocation['env'], **{k:arguments[k] for k in ('trigger','source','checkout')})
        env, descriptor = auth.inputs(binding, invocation['env'])
        issuer, provider = auth.Issuer(binding, clock), auth.Provider(http)
        value = e.execute_integrated(invocation['configuration'], env, invocation['observation'], descriptor,
            provider, issuer, output, clock=clock.seconds, wall=clock.wall, **arguments)
        write_once(Path(output)/'credential-exchange.json', dict(stages=issuer.calls, providerCalls=provider.authorized_calls,
            execution='offline-credential-http', identityAuthenticated=False, effectiveIamQualified=False))
    else:
        value = e.execute(invocation['configuration'], invocation['env'], invocation['observation'], api, output, **arguments)
    write_once(Path(output)/'http.json', http.requests)
    write_once(Path(output)/'state.json', q.snapshot(http))
    return value


def qualify(output, *, integrated=False):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    workflows.write(output/'workflow-proposal', read(p.CONFIG))
    for case in q.CASES:
        state, now, _ = q.case_state(case, authority=n)
        paths = []
        for trigger in e.TRIGGERS:
            root = output/(case+'-'+trigger); root.mkdir()
            invocation = fixture(state['configuration'], trigger)
            write_once(root/'input.json', state); write_once(root/'invocation.json', invocation)
            command = [sys.executable, '-m', 'scripts.v51.cloud_cleanup_entry_qualification', 'offline-replay',
                       str(root/'input.json'), str(root/'invocation.json'), str(root/'replay'), '--now', str(now)]
            if integrated: command.append('--integrated')
            done = subprocess.run(command, capture_output=True, timeout=30)
            (root/'stdout').write_bytes(done.stdout); (root/'stderr').write_bytes(done.stderr)
            m.need(done.returncode == 0, 'bound cleanup process failed: '+case+'-'+trigger)
            result = read(root/'replay/receipt.json'); after = read(root/'replay/state.json'); calls = read(root/'replay/http.json')
            expected = ('WAITING' if case in ('active', 'grace') else 'PASS' if case in
                        ('no-lease', 'expired-schedule', 'expired-manual', 'empty-reservation', 'lost-insert-ack') else 'FAIL')
            m.need(result['status'] == expected and result['trigger'] == trigger and result['source'] == SOURCE,
                   'bound cleanup outcome/identity')
            m.need(all(result[key] is False for key in ('identityAuthenticated', 'activationAllowed', 'paidCloud', 'cleanupReady', 'fullRemoteQualification')),
                   'offline entry claimed native readiness')
            if integrated:
                exchange = read(root/'replay/credential-exchange.json')
                m.need([r['stage'] for r in exchange['stages']] == ['oidc','sts','impersonation'] and
                       exchange['providerCalls'] == len(calls) and not exchange['identityAuthenticated'], 'credential integration evidence')
            compute = [row for row in calls if row['path'].startswith('/compute/')]
            m.need(all(row['method'] != 'POST' for row in compute), 'entry allocated resources')
            m.need(all(row['path'].rsplit('/', 1)[-1].isdecimal() for row in compute if row['method'] == 'DELETE'),
                   'entry used name deletion')
            if case in ('no-lease', 'active', 'grace', 'missing-context', 'changed-context', 'missing-reservation'):
                m.need(after == state and all(row['method'] == 'GET' for row in calls), 'blocked entry mutated authority')
            if case not in ('no-lease', 'missing-reservation'):
                _, _, _, store = q.restore(after)
                total, attempts = n.inspect_ledger(store.get(n.LEDGER)[1])
                m.need(total == 1_000_000, 'entry reset charges')
                if expected == 'PASS':
                    m.need(not after['resources'] and store.get(n.LEASE) is None and all(v['status'] == 'FAIL' for v in attempts.values()),
                           'entry falsely accepted workload or released lease')
                else: m.need(store.get(n.LEASE) is not None, 'entry unsafe lease release')
            paths.append(compute)
            rows.append(dict(case=case, trigger=trigger, status='PASS', observed=expected, requests=len(calls)))
        m.need(paths[0] == paths[1], 'manual/scheduled compute reconciliation diverged')
    receipt = dict(schema='gse-v51-cleanup-entry-qualification-v1', status='PASS', execution='offline-native-cleanup-entry',
                   source=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                   dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True)),
                   inputs={p.name:m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('cloud_*.py'))},
                   integratedCredentials=integrated, paidCloud=False, cleanupReady=False, fullRemoteQualification=False, cases=rows)
    write_once(output/'receipt.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('qualify'); check.add_argument('output', type=Path)
    child = sub.add_parser('offline-replay'); child.add_argument('state', type=Path); child.add_argument('invocation', type=Path)
    child.add_argument('output', type=Path); child.add_argument('--now', type=int, required=True)
    check.add_argument('--integrated', action='store_true'); child.add_argument('--integrated', action='store_true')
    args = parser.parse_args()
    result = qualify(args.output, integrated=args.integrated) if args.command == 'qualify' else replay(read(args.state), read(args.invocation), args.output, args.now, integrated=args.integrated)
    print(m.canonical(dict(status=result['status'], execution=result['execution'], paidCloud=False)).decode())
