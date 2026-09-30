"""Bound native cleanup entry points. Live activation remains unavailable.

GitHub context checks are not authentication. Only offline HTTP qualification is
executable here; reviewed WIF/IAM and native transport activation remain separate.
"""
import argparse
import html
import os
from pathlib import Path
import re
import subprocess
from . import cloud_authority as a, cloud_ci as ci, cloud_identity_setup as identities
from . import cloud_preflight as preflight, cloud_native_cleanup as cleanup, performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-cleanup-entry-v1'
TRIGGERS = ('manual', 'schedule')


def identity(cfg, env, *, trigger, source, checkout):
    """Bind the fixed entry, selected configuration and actually checked-out source."""
    m.need(trigger in TRIGGERS, 'cleanup entry trigger')
    a.digest(source, 40)
    selected = identities.proposal(cfg)['identities'][trigger]
    claims = selected['claims']
    expected = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=ci.REPOSITORY,
                    GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID), GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),
                    GITHUB_EVENT_NAME=claims['event_name'], GITHUB_REF=claims['ref'],
                    GITHUB_WORKFLOW_REF=claims['workflow_ref'], GITHUB_WORKFLOW_SHA=source,
                    GITHUB_SHA=source, GITHUB_JOB='cleanup', CLEANUP_ENVIRONMENT=selected['environment'])
    m.need(all(env.get(k) == v for k, v in expected.items()), 'cleanup entry context mismatch')
    m.need(checkout == source, 'cleanup checkout source mismatch')
    numbers = []
    for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        value = env.get(key)
        m.need(isinstance(value, str) and re.fullmatch('[1-9][0-9]{0,19}', value) is not None,
               'cleanup run identity')
        numbers.append(int(value))
    return dict(schema=SCHEMA, trigger=trigger, event=claims['event_name'], source=source,
                runId=numbers[0], runAttempt=numbers[1], workflow=selected['workflow'],
                environment=selected['environment'], serviceAccount=selected['serviceAccount'],
                provider=selected['provider'], configurationSha256=preflight.configuration(cfg),
                identityAuthenticated=False, activationAllowed=False, cleanupReady=False,
                paidCloud=False, fullRemoteQualification=False)


def validate_run(binding, observation):
    """Cross-check a sampled GitHub run attempt; do not require green CI to clean up."""
    m.need(type(observation) is dict, 'cleanup run observation missing')
    for key in ('repository', 'head_repository'):
        repo = observation[key]
        m.need(repo['id'] == ci.REPOSITORY_ID and repo['full_name'] == ci.REPOSITORY and
               repo['owner']['id'] == ci.OWNER_ID, 'cleanup run repository identity')
    m.need(type(observation['id']) is int and type(observation['run_attempt']) is int and
           observation['id'] == binding['runId'] and observation['run_attempt'] == binding['runAttempt'] and
           observation['head_sha'] == binding['source'] and observation['head_branch'] == 'master' and
           observation['path'] == binding['workflow'] and observation['event'] == binding['event'] and
           observation['status'] == 'in_progress' and observation['conclusion'] is None,
           'cleanup run attempt/source/entry mismatch')
    return binding


def collect_run(binding, get=ci.github):
    # Latest and explicit attempt must agree: an old attempt cannot reuse a new
    # attempt's observation. Recheck after collection to detect an intervening rerun.
    path = 'actions/runs/'+str(binding['runId'])
    before = get(path)
    attempt = get(path+'/attempts/'+str(binding['runAttempt']))
    after = get(path)
    for value in (before, attempt, after): validate_run(binding, value)
    return attempt


def execute(cfg, env, observation, api, output, *, trigger, source, checkout, now):
    binding = identity(cfg, env, trigger=trigger, source=source, checkout=checkout)
    validate_run(binding, observation)
    # This guard precedes credentials, transport, and creation of output files.
    m.need(api.offline is True, 'native cleanup activation unavailable')
    a.integer(now, 1)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_once(output/'binding.json', binding)
    try:
        result = cleanup.reconcile(cfg['provider'], api, output/'reconciliation', trigger=trigger, now=now)
        receipt = dict(binding, status=result['status'], execution='offline-native-cleanup-entry',
                       checkedAt=now, reconciliation=result)
    except Exception as error:
        # No arbitrary provider exception text, token, URL or response is retained.
        receipt = dict(binding, status='FAIL', execution='offline-native-cleanup-entry',
                       checkedAt=now, failure=dict(phase='reconciliation', type=type(error).__name__))
    write_once(output/'receipt.json', receipt)
    (output/'summary.md').write_text(summary(receipt))
    return receipt


def execute_integrated(cfg, env, observation, credentials, transport, auth_transport, output, *,
                       trigger, source, checkout, now, clock, wall):
    """Same reconciliation, with the bound credential exchange and provider HTTP.

    Both transports must be offline until separately reviewed activation. Context
    and transport checks precede credentials, network traffic and local output.
    """
    from .cloud_cleanup_credentials import Credentials
    from .cloud_http import Api
    binding = identity(cfg, env, trigger=trigger, source=source, checkout=checkout)
    validate_run(binding, observation)
    m.need(transport.offline is True and auth_transport.offline is True, 'native cleanup activation unavailable')
    tokens = Credentials(binding, env, credentials, transport=auth_transport, clock=clock, wall=wall)
    api = Api(transport=transport, tokens=tokens, clock=clock)
    result = execute(cfg, env, observation, api, output, trigger=trigger, source=source, checkout=checkout, now=now)
    return result


def blocked(output, *, binding=None):
    value = dict(binding or {}, schema=SCHEMA, status='BLOCKED', execution='native-cleanup-not-activated',
                 reason='Native cleanup transport and credential activation are not qualified.',
                 identityAuthenticated=False, activationAllowed=False, cleanupReady=False,
                 paidCloud=False, fullRemoteQualification=False)
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    write_once(output/'receipt.json', value)
    (output/'summary.md').write_text(summary(value))
    return value


def summary(value):
    def cell(v): return html.escape(str(v)).replace('|', '&#124;').replace('\n', ' ')
    rows = [('Status', value['status']), ('Execution', value['execution'])]
    for label, key in (('Trigger', 'trigger'), ('Event', 'event'), ('Source', 'source'), ('Run', 'runId'),
                       ('Attempt', 'runAttempt'), ('Workflow', 'workflow'), ('Environment', 'environment'),
                       ('Service account', 'serviceAccount'), ('WIF provider', 'provider'),
                       ('Configuration SHA-256', 'configurationSha256')):
        if key in value: rows.append((label, value[key]))
    result = value.get('reconciliation', {})
    for label, key in (('Active lease', 'activeLease'), ('Lease released', 'leaseReleased')):
        if key in result: rows.append((label, result[key]))
    rows += [('Live activation allowed', False), ('Cleanup readiness established', False), ('Paid cloud executed', False)]
    return ('# V5.1 cleanup entry\n\n| Parameter | Value |\n| --- | --- |\n'+
            ''.join('| '+cell(k)+' | '+cell(v)+' |\n' for k,v in rows)+
            '\n'+cell(value.get('reason', 'Offline qualification only; context matching is not authentication.'))+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('identity')
    check.add_argument('--trigger', choices=TRIGGERS, required=True)
    check.add_argument('--source', required=True)
    check.add_argument('--output', type=Path, required=True)
    stop = sub.add_parser('activation-check'); stop.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'activation-check':
        binding_path = args.output/'binding.json'
        value = blocked(args.output, binding=read(binding_path) if binding_path.is_file() else None)
    else:
        cfg = read(preflight.CONFIG)
        checkout = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        value = identity(cfg, os.environ, trigger=args.trigger, source=args.source, checkout=checkout)
        observation = collect_run(value)
        args.output.mkdir(parents=True, exist_ok=False)
        write_once(args.output/'binding.json', value)
        # Retain only the fields used in comparison, never the event/environment dump.
        keys = ('id', 'run_attempt', 'head_sha', 'head_branch', 'path', 'event', 'status', 'conclusion')
        write_once(args.output/'run.json', {key:observation[key] for key in keys})
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            for key in ('provider', 'serviceAccount'): output.write(key+'='+value[key]+'\n')
        value = dict(value, status='CONTEXT_MATCH')
    print(m.canonical(value).decode())
    return 2 if value['status'] == 'BLOCKED' else 0


if __name__ == '__main__': raise SystemExit(main())
