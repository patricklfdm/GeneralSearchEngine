"""Trusted root receiver. Only fixed metadata reads, private installation and self-check.

This source and its two dependencies arrive in the authenticated command, never
from the invoking user's writable staging area. No block backend is enabled.
"""
import base64
import os
from pathlib import Path
import pwd
import signal
import stat
import subprocess
import sys
import time
import urllib.request
from . import guest_delivery_receiver as r, guest_root_policy as policy


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('root metadata redirect')


def metadata(deadline):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    fields = dict(instanceId='id', sshKeys='attributes/ssh-keys',
                  blockProjectSshKeys='attributes/block-project-ssh-keys', enableOslogin='attributes/enable-oslogin')
    result = {}
    for name, suffix in fields.items():
        left = deadline-time.monotonic(); r.need(left > 0, 'root metadata deadline')
        request = urllib.request.Request('http://169.254.169.254/computeMetadata/v1/instance/'+suffix,
                                         headers={'Metadata-Flavor': 'Google'})
        with opener.open(request, timeout=min(2, left)) as response:
            r.need(response.status == 200 and response.headers.get('Metadata-Flavor') == 'Google', 'root metadata response')
            raw = response.read(4097); r.need(len(raw) <= 4096, 'root metadata bound')
            result[name] = raw.decode('ascii')
    return result


def directory(path):
    info = path.lstat()
    return dict(kind='directory' if stat.S_ISDIR(info.st_mode) else 'other', uid=info.st_uid, mode=stat.S_IMODE(info.st_mode))


def observe(value, budget, deadline, *, claims=True):
    policy.validate_plan(value)
    ids = dict(uid=os.getuid(), euid=os.geteuid(), gid=os.getgid(), egid=os.getegid())
    r.need(all(v == 0 for v in ids.values()), 'root effective identity')
    user = value['access']['user']
    try: account = pwd.getpwnam(user)
    except KeyError: raise ValueError('root invoking account missing') from None
    invoker = dict(user=os.environ.get('SUDO_USER'), uid=int(os.environ.get('SUDO_UID', '-1')),
                   gid=int(os.environ.get('SUDO_GID', '-1')))
    expected = dict(user=user, uid=account.pw_uid, gid=account.pw_gid)
    r.need(invoker == expected and account.pw_uid > 0 and account.pw_gid > 0, 'root invoking account')
    parent = Path(policy.PARENT)
    ancestors = [dict(path=str(p), **directory(p)) for p in reversed(parent.parents)]
    exists = parent.exists() or parent.is_symlink()
    observed = dict(planSha256=r.sha(r.canonical(value)), bootId=r.boot_identity(), ids=ids, account=expected,
        invoker=invoker, metadata=metadata(deadline), ancestors=ancestors,
        parent=dict(exists=True, **directory(parent)) if exists else dict(exists=False),
        claim=dict(state='ABSENT', planSha256=None, deadlineSha256=None))
    # Check ancestors before opening any claims below them.
    policy.assess(value, observed, budget, time.monotonic_ns())
    if exists and claims:
        root = r.location(parent, value['delivery'], 0); claim = root.with_name(root.name+'.claim')
        if claim.exists() or claim.is_symlink():
            r.owned(claim, 0, True)
            ticket = claim/'admission.json'
            observed['claim']['state'] = 'PARTIAL'
            if ticket.exists() or ticket.is_symlink():
                saved = r.decode(r.read(ticket, 0, 16384))
                r.need(set(saved) == {'plan', 'deadline', 'observation'} and saved['plan'] == value and saved['deadline'] == budget,
                       'root consumed admission identity')
                r.need(saved['observation']['account'] == expected, 'root retained account identity')
                answer = r.query(parent, value['delivery'], 0, budget=budget)
                observed['claim'] = dict(state=answer['state'] if answer['state'] in ('SUCCEEDED', 'FAILED') else 'PARTIAL',
                                        planSha256=r.sha(r.canonical(value)), deadlineSha256=r.sha(r.canonical(budget)))
        elif root.exists() or root.is_symlink():
            observed['claim']['state'] = 'PARTIAL'
    return observed


def perform(action, value, token, stream):
    policy.validate_plan(value); desc = value['delivery']
    r.need(action in ('clock', 'install', 'query', 'check'), 'root action')
    if action == 'clock':
        sample = r.clock_sample(desc, token)
        temporary = dict(schema='gse-v51-helper-deadline-v1', sample=sample,
                         expiresNanos=sample['sampledNanos']+5*10**9)
        # Clock probes inspect the context but do not query an existing claim
        # against a fresh ticket. A fresh clock cannot authorize its reuse.
        observed = observe_context(value, temporary)
        return dict(schema='gse-v51-root-transport-v1', planSha256=r.sha(r.canonical(value)),
                    rootUid=observed['ids']['euid'], answer=r.clock_sample(desc, token))
    budget = r.validate_budget(r.decode(base64.b64decode(token, validate=True)), desc)
    deadline = r.guest_deadline(budget, desc)
    observed = observe(value, budget, deadline)
    decision = policy.assess(value, observed, budget, time.monotonic_ns())['decision']
    parent = Path(policy.PARENT)
    if decision == 'INSTALL_ONCE' and action == 'install':
        try: parent.mkdir(mode=0o700)
        except FileExistsError: pass
        r.need(directory(parent) == dict(kind='directory', uid=0, mode=0o700), 'root private parent')
        root = r.location(parent, desc, 0); claim = root.with_name(root.name+'.claim')
        try: claim.mkdir(mode=0o700)
        except FileExistsError:
            answer = r.envelope(desc, 'UNCERTAIN')
        else:
            r.sync(parent)
            # Claim precedes payload consumption. A crash at any subsequent point
            # is queried, never an invitation to install again.
            r.publish(claim/'admission.json', dict(plan=value, deadline=budget, observation=observed))
            answer = r.install(parent, desc, 0, stream, deadline, budget=budget)
    elif decision == 'QUERY_ONLY': answer = r.query(parent, desc, 0, budget=budget)
    else: answer = r.envelope(desc, 'NOT_FOUND' if decision == 'INSTALL_ONCE' else 'UNCERTAIN')
    if action == 'check':
        r.need(answer['state'] == 'SUCCEEDED', 'root helper unavailable')
        root = r.location(parent, desc, 0)
        result = subprocess.run([sys.executable, '-I', str(root/'files/helper.py')], stdin=subprocess.DEVNULL,
                                capture_output=True, check=True, timeout=max(.001, deadline-time.monotonic()))
        r.need(len(result.stdout) <= 4096 and len(result.stderr) <= 4096 and
               r.decode(result.stdout) == dict(status='PASS', nativeWritesEnabled=False), 'root helper check')
        r.need(r.query(parent, desc, 0, budget=budget) == answer, 'root helper changed after check')
    r.guest_deadline(budget, desc)
    return dict(schema='gse-v51-root-transport-v1', planSha256=r.sha(r.canonical(value)), rootUid=0,
                answer=dict(schema='gse-v51-helper-transport-v1', deadlineSha256=r.sha(r.canonical(budget)), receipt=answer))


def observe_context(value, budget):
    # The clock probe must validate the very same context without consulting a
    # retained claim using its temporary (non-authoritative) deadline.
    return observe(value, budget, budget['expiresNanos']/10**9, claims=False)


def main():
    action, encoded, token = sys.argv[1:]
    r.need(len(encoded) <= 16384 and len(token) <= 4096, 'root request bound')
    value = r.decode(base64.b64decode(encoded, validate=True))
    seconds = 5 if action == 'clock' else r.guest_deadline(r.decode(base64.b64decode(token, validate=True)), value['delivery'])-time.monotonic()
    def expired(*_): raise TimeoutError('root original deadline')
    signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, max(.001, seconds))
    try: print(r.canonical(perform(action, value, token, sys.stdin.buffer)).decode(), flush=True)
    finally: signal.setitimer(signal.ITIMER_REAL, 0)
