"""Guest-side, at-most-once command claims. This module grants no cloud admission.

The caller supplies a trusted handler, never an argv from an SSH request. A durable
claim precedes handler entry. Missing/partial receipts are uncertainty, not retry
permission. Query/cancel remain usable while the single executor holds its lock.
"""
import fcntl
import os
from pathlib import Path
import re
import stat
import time
from . import cloud_workload_contract as contract, performance_model as m

COMMANDS = frozenset(('prepare-cell', 'start-voter', 'window', 'fault', 'stop-voter', 'collect'))
RESPONSE_BYTES = 4 << 20
REQUEST_BYTES = 64 << 10


def directory(path):
    path = Path(path).absolute()
    m.need(all(not p.is_symlink() for p in (path, *path.parents)), 'remote directory symlink')
    m.need(path.is_dir(), 'remote directory absent')
    return path


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_once(path, value, maximum=RESPONSE_BYTES):
    """Publish forced bytes atomically without replacing an existing receipt.

    A crash leaves a .writing file and consumed claim. Concurrent polling sees
    either no receipt or the complete JSON, never a half-written response.
    """
    path = Path(path)
    data = m.canonical(value) + b'\n'
    m.need(len(data) <= maximum, 'remote receipt byte limit')
    if path.exists() or path.is_symlink():
        raise FileExistsError(str(path))
    temporary = path.with_name(path.name + '.writing')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    fd = os.open(temporary, flags, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.link(temporary, path, follow_symlinks=False)
    sync_directory(path.parent)
    temporary.unlink()
    sync_directory(path.parent)


def read(path, maximum=RESPONSE_BYTES):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        m.need(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'remote receipt file')
        data = stream.read(maximum + 1)
    m.need(len(data) <= maximum, 'remote receipt byte limit')
    return m.strict_json(data)


def binding(source, bundle_sha256, attempt, node):
    value = dict(schema='gse-v51-guest-binding-v1', source=source, bundleSha256=bundle_sha256,
                 attempt=attempt, node=node, workloadSha256=contract.PLAN_SHA256)
    validate_binding(value)
    return value


def validate_binding(value):
    m.need(set(value) == {'schema', 'source', 'bundleSha256', 'attempt', 'node', 'workloadSha256'}, 'guest binding fields')
    m.need(value['schema'] == 'gse-v51-guest-binding-v1' and value['workloadSha256'] == contract.PLAN_SHA256, 'guest suite binding')
    for key, size in (('source', 40), ('bundleSha256', 64), ('attempt', 32)):
        m.need(isinstance(value[key], str) and re.fullmatch('[0-9a-f]{%d}' % size, value[key]), 'guest identity ' + key)
    m.need(value['node'] in ('node-1', 'node-2', 'node-3'), 'guest node binding')


def request(owner, command_id, command, payload):
    value = dict(schema='gse-v51-guest-command-v1', bindingSha256=m.sha(m.canonical(owner)),
                 commandId=command_id, command=command, payload=payload)
    validate_request(value, owner)
    return value


def validate_request(value, owner):
    m.need(set(value) == {'schema', 'bindingSha256', 'commandId', 'command', 'payload'}, 'command fields')
    m.need(value['schema'] == 'gse-v51-guest-command-v1' and value['bindingSha256'] == m.sha(m.canonical(owner)), 'command binding')
    m.need(isinstance(value['commandId'], str) and re.fullmatch('[0-9a-f]{32}', value['commandId']), 'command identity')
    m.need(value['command'] in COMMANDS and isinstance(value['payload'], dict), 'command kind/payload')
    m.need(len(m.canonical(value)) <= REQUEST_BYTES, 'command byte limit')


class Cancelled(Exception):
    pass


class CommandStore:
    def __init__(self, root, owner, *, create=False):
        validate_binding(owner)
        self.root, self.owner = Path(root).absolute(), owner
        if create:
            directory(self.root.parent)
            self.root.mkdir(mode=0o700)
            sync_directory(self.root.parent)
            write_once(self.root / 'binding.json', owner)
            (self.root / 'commands').mkdir(mode=0o700)
            sync_directory(self.root)
        directory(self.root)
        m.need(read(self.root / 'binding.json') == owner, 'guest store ownership')
        directory(self.root / 'commands')

    def command_path(self, value):
        validate_request(value, self.owner)
        return self.root / 'commands' / value['commandId']

    def envelope(self, value, state, **fields):
        return dict(schema='gse-v51-command-receipt-v1', bindingSha256=value['bindingSha256'],
                    commandId=value['commandId'], requestSha256=m.sha(m.canonical(value)), state=state, **fields)

    def query(self, value):
        path = self.command_path(value)
        if not path.exists() and not path.is_symlink():
            return self.envelope(value, 'NOT_FOUND')
        directory(path)
        # A crash between mkdir and forced request leaves a permanent consumed ID.
        if not (path / 'request.json').exists():
            return self.envelope(value, 'UNCERTAIN', reason='claim without durable request')
        m.need(read(path / 'request.json', REQUEST_BYTES + 1) == value, 'command ID reused with different request')
        for name in ('terminal.json', 'started.json'):
            if (path / name).exists() or (path / name).is_symlink():
                result = read(path / name)
                m.need(all(result.get(k) == v for k, v in self.envelope(value, result.get('state')).items()), 'receipt identity')
                return result
        return self.envelope(value, 'UNCERTAIN', reason='claimed before handler entry')

    def cancelled(self, value):
        path = self.command_path(value) / 'cancel.json'
        if not path.exists() and not path.is_symlink():
            return False
        m.need(read(path) == self.envelope(value, 'CANCEL_REQUESTED'), 'cancel identity')
        return True

    def checkpoint(self, value):
        if self.cancelled(value):
            raise Cancelled('guest command cancelled; dispatched operations must retain their original outcomes')

    def cancel(self, value):
        result = self.query(value)
        m.need(result['state'] != 'NOT_FOUND', 'cannot cancel unknown command')
        if result['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            return result
        path = self.command_path(value) / 'cancel.json'
        try:
            write_once(path, self.envelope(value, 'CANCEL_REQUESTED'))
        except FileExistsError:
            m.need(self.cancelled(value), 'incomplete cancellation marker')
        return self.envelope(value, 'CANCEL_REQUESTED')

    def execute(self, value, handler):
        path = self.command_path(value)
        if path.exists() or path.is_symlink():
            return self.query(value)
        lock = os.open(self.root / 'executor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # This rejection is before a claim. The controller still never
                # resends after a lost response, even if that response was BUSY.
                return self.envelope(value, 'BUSY')
            if path.exists() or path.is_symlink():
                return self.query(value)
            m.need(len(list((self.root / 'commands').iterdir())) < 2000, 'guest command count bound')
            path.mkdir(mode=0o700)
            sync_directory(path.parent)
            write_once(path / 'request.json', value, REQUEST_BYTES + 1)
            process = dict(pid=os.getpid(), bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                           startTicks=Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
            started = time.monotonic_ns()
            write_once(path / 'started.json', self.envelope(value, 'RUNNING', process=process, startedNanos=started))
            try:
                self.checkpoint(value)
                answer = handler(value['command'], value['payload'], lambda: self.checkpoint(value))
                # A cancelled command is not relabelled successful because its last
                # operation raced with cancellation; the handler's result stays retained.
                state = 'CANCELLED' if self.cancelled(value) else 'SUCCEEDED'
                terminal = self.envelope(value, state, process=process, startedNanos=started,
                                         endedNanos=time.monotonic_ns(), result=answer)
                m.need(len(m.canonical(terminal)) + 1 <= RESPONSE_BYTES, 'remote result byte limit')
            except BaseException as error:
                terminal = self.envelope(value, 'CANCELLED' if isinstance(error, Cancelled) else 'FAILED',
                                         process=process, startedNanos=started, endedNanos=time.monotonic_ns(),
                                         error=dict(type=type(error).__name__, message=str(error)[:2000]))
            write_once(path / 'terminal.json', terminal)
            return terminal
        finally:
            os.close(lock)


def submit_and_observe(transport, value, deadline, *, clock=time.monotonic, sleep=time.sleep):
    """Submit exactly once, then only query. Transport implements submit/query.

    A fresh query connection may renew credentials. Lost responses do not restart
    deadlines, change request identities or authorize replay of mutations.
    """
    m.need(clock() < deadline, 'remote command deadline')
    expected = dict(bindingSha256=value['bindingSha256'], commandId=value['commandId'], requestSha256=m.sha(m.canonical(value)))
    result = None
    try:
        result = transport.submit(value, deadline)
    except (ConnectionError, TimeoutError):
        pass
    while True:
        if result is not None:
            m.need(all(result.get(k) == v for k, v in expected.items()) and result.get('schema') == 'gse-v51-command-receipt-v1', 'remote response identity')
            m.need(len(m.canonical(result)) <= RESPONSE_BYTES, 'remote response limit')
            if result['state'] in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'BUSY'):
                m.need(clock() <= deadline, 'late remote command receipt')
                return result
            m.need(result['state'] in ('RUNNING', 'UNCERTAIN', 'NOT_FOUND'), 'remote response state')
        remaining = deadline - clock()
        m.need(remaining > 0, 'remote command unresolved; never resubmit')
        sleep(min(.05, remaining))
        m.need(clock() < deadline, 'remote command unresolved; never resubmit')
        try:
            result = transport.query(value, deadline)
        except (ConnectionError, TimeoutError):
            result = None
