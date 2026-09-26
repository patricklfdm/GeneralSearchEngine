"""Shared pure root policy, also sent as trusted controller code before payload import."""
import base64
from pathlib import PurePosixPath
import re
from . import guest_delivery_receiver as receiver

m = receiver
PARENT = '/var/lib/gse-v51-helper'
EXECUTION = 'offline-root-admission-only'


def access(value):
    m.need(type(value) is dict and set(value) == {'attempt', 'user', 'publicKey'} and
           isinstance(value['attempt'], str) and re.fullmatch('[0-9a-f]{32}', value['attempt']) and
           value['user'] == 'gse-'+value['attempt'][:24], 'root attempt account')
    key = value['publicKey']
    m.need(isinstance(key, str) and re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', key), 'root public key')
    raw = base64.b64decode(key.split()[1], validate=True)
    m.need(len(raw) == 51 and raw[:19] == b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20', 'root key encoding')
    return value


def validate_plan(value):
    m.need(type(value) is dict and set(value) == {'schema', 'execution', 'requestSha256', 'providerFactsSha256',
        'delivery', 'access', 'destination', 'allowedActions', 'paidCloud', 'privilegedExecution',
        'nativeWritesEnabled', 'fullRemoteQualification'}, 'root plan fields')
    m.need(value['schema'] == 'gse-v51-root-admission-plan-v1' and value['execution'] == EXECUTION,
           'root plan scope')
    for key in ('paidCloud', 'privilegedExecution', 'nativeWritesEnabled', 'fullRemoteQualification'):
        m.need(value[key] is False, 'root plan execution disabled')
    for key in ('requestSha256', 'providerFactsSha256'):
        m.need(isinstance(value[key], str) and re.fullmatch('[0-9a-f]{64}', value[key]), 'root plan digest')
    desc = receiver.descriptor(value['delivery']); account_access = access(value['access']); binding = desc['binding']
    m.need(account_access['attempt'] == binding['attempt'] and m.sha(m.canonical(account_access)) == desc['guestAccessSha256'],
           'root plan access identity')
    m.need(value['destination'] == PARENT+'/'+binding['attempt']+'-'+binding['node'] and
           value['allowedActions'] == ['install', 'query', 'check'], 'root plan path/actions')
    return value


def assess(value, observed, budget, now_nanos):
    """Reject unsafe modeled observations. Never grants a native execution route."""
    validate_plan(value); desc = value['delivery']; receiver.validate_budget(budget, desc)
    m.need(type(now_nanos) is int and budget['sample']['sampledNanos'] <= now_nanos < budget['expiresNanos'],
           'root admission original deadline')
    m.need(type(observed) is dict and set(observed) == {'planSha256', 'bootId', 'ids', 'account', 'invoker',
           'metadata', 'ancestors', 'parent', 'claim'}, 'root observation fields')
    m.need(observed['planSha256'] == m.sha(m.canonical(value)) and observed['bootId'] == budget['sample']['bootId'],
           'root observation plan/boot')
    ids = observed['ids']
    m.need(type(ids) is dict and set(ids) == {'uid', 'euid', 'gid', 'egid'} and
           all(type(v) is int and v == 0 for v in ids.values()), 'root effective identity')
    account, invoker = observed['account'], observed['invoker']
    m.need(type(account) is dict and set(account) == {'user', 'uid', 'gid'} and
           account['user'] == value['access']['user'] and
           all(type(account[k]) is int and 0 < account[k] < 2**32-1 for k in ('uid', 'gid')) and
           type(invoker) is dict and invoker == account and
           all(type(invoker[k]) is int for k in ('uid', 'gid')), 'root invoking account')
    access = value['access']
    m.need(observed['metadata'] == {'instanceId': desc['instanceId'], 'sshKeys': access['user']+':'+access['publicKey'],
           'blockProjectSshKeys': 'TRUE', 'enableOslogin': 'FALSE'}, 'root metadata identity')
    ancestors = observed['ancestors']
    expected = [str(p) for p in reversed(PurePosixPath(PARENT).parents)]
    m.need(type(ancestors) is list and len(ancestors) == len(expected), 'root ancestor inventory')
    for row, path in zip(ancestors, expected):
        m.need(type(row) is dict and set(row) == {'path', 'kind', 'uid', 'mode'} and row['path'] == path and
               row['kind'] == 'directory' and type(row['uid']) is int and row['uid'] == 0 and
               type(row['mode']) is int and 0 <= row['mode'] <= 0o7777 and row['mode'] & 0o022 == 0,
               'root ancestor ownership/mode')
    parent = observed['parent']
    m.need(parent == {'exists': False} or type(parent) is dict and
           set(parent) == {'exists', 'kind', 'uid', 'mode'} and parent['exists'] is True and
           parent['kind'] == 'directory' and type(parent['uid']) is int and parent['uid'] == 0 and
           type(parent['mode']) is int and parent['mode'] == 0o700, 'root private parent')
    m.need(type(parent['exists']) is bool, 'root parent boolean')
    claim = observed['claim']
    m.need(type(claim) is dict and set(claim) == {'state', 'planSha256', 'deadlineSha256'}, 'root claim fields')
    if claim['state'] == 'ABSENT':
        m.need(claim['planSha256'] is None and claim['deadlineSha256'] is None, 'root absent claim identity')
        decision = 'INSTALL_ONCE'
    else:
        m.need(claim['state'] in ('PARTIAL', 'SUCCEEDED', 'FAILED'), 'root claim state')
        if claim['state'] == 'PARTIAL':
            decision = 'FAIL_UNCERTAIN'
        else:
            m.need(claim['planSha256'] == m.sha(m.canonical(value)) and
                   claim['deadlineSha256'] == m.sha(m.canonical(budget)), 'root retained claim binding')
            decision = 'QUERY_ONLY'
        m.need(parent['exists'] is True, 'root claim without parent')
    return dict(schema='gse-v51-root-admission-assessment-v1', execution=EXECUTION, status='PASS', decision=decision,
                planSha256=m.sha(m.canonical(value)), deadlineSha256=m.sha(m.canonical(budget)),
                paidCloud=False, privilegedExecution=False, nativeWritesEnabled=False, fullRemoteQualification=False)
