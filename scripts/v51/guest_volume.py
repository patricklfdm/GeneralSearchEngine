"""Linux disk observations and a one-shot startup executor; live writes stay closed.

The injected executor is qualified with an independent block-device model. Linux
reads are implemented, but Linux mutations are deliberately unavailable until the
paid runner and privileged guest delivery have their own admission boundary.
"""
from pathlib import Path
import os
import pwd
import re
import stat
import time
from . import guest_setup as setup, performance_model as m, remote_command as c

MOUNT = '/mnt/gse-v51'
LSBLK = ['lsblk', '--json', '--bytes', '--paths', '--list', '--all', '--output',
         'NAME,TYPE,SIZE,RO,MAJ:MIN,PKNAME,MOUNTPOINTS,FSTYPE,LABEL,UUID']
FINDMNT = ['findmnt', '--json', '--list', '--output', 'SOURCE,TARGET,FSTYPE,OPTIONS,MAJ:MIN']


def device_name(value):
    m.need(isinstance(value, str) and re.fullmatch(r'/dev/(sd[a-z]+|nvme[0-9]+n[0-9]+)', value), 'guest whole device path')
    return value


class Linux:
    """Read-only native backend. Never fall back to executing a write argv."""
    offline = False
    clock = staticmethod(time.monotonic)

    def run(self, argv, deadline):
        from .guest_transport import process
        allowed = (argv == LSBLK or argv == FINDMNT or
                   (len(argv) == 3 and argv[:2] == ['readlink', '-e'] and
                    re.fullmatch('/dev/disk/by-id/google-gse-(boot|data)-[123]', argv[2])) or
                   (len(argv) == 6 and argv[:5] == ['wipefs', '--no-act', '--json', '--output', 'TYPE,OFFSET'] and device_name(argv[5])) or
                   argv == ['curl', '--fail', '--silent', '--show-error', '--noproxy', '*', '--header', 'Metadata-Flavor: Google',
                            'http://metadata.google.internal/computeMetadata/v1/instance/id'])
        m.need(allowed, 'live guest volume mutation disabled')
        return process(argv, b'', deadline, maximum=65536)

    def target(self):
        path = Path(MOUNT)
        for parent in path.parents:
            value = parent.lstat()
            m.need(stat.S_ISDIR(value.st_mode) and value.st_uid == 0 and value.st_mode & 0o022 == 0, 'guest mount parent')
        if not path.exists() and not path.is_symlink():
            return dict(exists=False, directory=False, symlink=False, empty=True, uid=None, gid=None, mode=None)
        value = path.lstat()
        directory = stat.S_ISDIR(value.st_mode)
        return dict(exists=True, directory=directory, symlink=stat.S_ISLNK(value.st_mode),
                    empty=directory and next(path.iterdir(), None) is None,
                    uid=value.st_uid, gid=value.st_gid, mode=stat.S_IMODE(value.st_mode))

    def user(self, name):
        value = pwd.getpwnam(name)
        m.need(value.pw_uid > 0 and value.pw_gid > 0, 'guest unprivileged owner')
        return value.pw_uid, value.pw_gid


def observe(backend, provider, deadline):
    """Collect raw bounded command output; no caller-supplied 'blank disk' flag."""
    m.need(backend.clock() < deadline, 'volume original deadline')
    node = provider['node']
    m.need(type(node) is int and node in (1, 2, 3), 'volume node')
    def run(argv):
        m.need(backend.clock() < deadline, 'volume original deadline')
        value = backend.run(argv, deadline)
        m.need(isinstance(value, bytes) and len(value) <= 65536 and backend.clock() < deadline, 'volume response/deadline')
        return value
    instance = run(['curl', '--fail', '--silent', '--show-error', '--noproxy', '*', '--header', 'Metadata-Flavor: Google',
                    'http://metadata.google.internal/computeMetadata/v1/instance/id']).decode().strip()
    data = '/dev/disk/by-id/google-gse-data-'+str(node)
    boot = '/dev/disk/by-id/google-gse-boot-'+str(node)
    resolved = device_name(run(['readlink', '-e', data]).decode().strip())
    boot_device = device_name(run(['readlink', '-e', boot]).decode().strip())
    result = dict(instanceId=instance, device=data, resolved=resolved, bootDevice=boot_device,
        lsblk=m.strict_json(run(LSBLK)), findmnt=m.strict_json(run(FINDMNT)),
        wipefs=m.strict_json(run(['wipefs', '--no-act', '--json', '--output', 'TYPE,OFFSET', resolved])),
        target=backend.target())
    # A changed by-id mapping during inspection cannot become a formatting plan.
    m.need(run(['readlink', '-e', data]).decode().strip() == resolved and
           run(['readlink', '-e', boot]).decode().strip() == boot_device, 'volume device mapping changed')
    return result


def topology(raw, provider):
    m.need(raw['instanceId'] == provider['instanceId'], 'volume guest instance changed')
    m.need(raw['device'] == '/dev/disk/by-id/google-gse-data-'+str(provider['node']), 'volume device alias')
    disk, boot = device_name(raw['resolved']), device_name(raw['bootDevice'])
    m.need(disk != boot, 'volume is boot disk')
    rows = raw['lsblk']['blockdevices']
    m.need(type(rows) is list and 2 <= len(rows) <= 128 and
           len({v['name'] for v in rows}) == len(rows) and len({v['maj:min'] for v in rows}) == len(rows), 'volume block inventory')
    devices = {v['name']: v for v in rows}
    m.need(disk in devices and boot in devices, 'volume/boot missing from inventory')
    for row in rows:
        m.need(not row.get('children') and re.fullmatch(r'[0-9]+:[0-9]+', row['maj:min']) and
               type(row['mountpoints']) is list, 'volume block topology')
    data = devices[disk]
    m.need(data['type'] == 'disk' and data['pkname'] is None and data['ro'] is False and
           type(data['size']) is int and data['size'] == provider['sizeGiB']*(1 << 30) and
           not any(v['pkname'] == disk for v in rows), 'volume not a dedicated writable whole disk')
    mounts = raw['findmnt']['filesystems']
    m.need(type(mounts) is list and 1 <= len(mounts) <= 512, 'volume mount inventory')
    roots = [v for v in mounts if v['target'] == '/']
    m.need(len(roots) == 1, 'volume root mount')
    root = next((v for v in rows if v['maj:min'] == roots[0]['maj:min']), None)
    seen = set()
    while root is not None and root['pkname'] is not None:
        m.need(root['name'] not in seen, 'volume boot ancestry cycle')
        seen.add(root['name']); root = devices.get(root['pkname'])
    m.need(root is not None and root['name'] == boot and root['type'] == 'disk', 'volume boot ancestry')
    target = raw['target']
    m.need(not target['symlink'] and (not target['exists'] or target['directory']), 'volume mount target type')
    return data, mounts


def blank(raw, provider, user):
    data, mounts = topology(raw, provider)
    target = raw['target']
    m.need(not target['exists'] or (target['uid'] == 0 and target['mode'] & 0o022 == 0), 'volume mount target ownership')
    m.need(not any(v['target'] == MOUNT or v['target'].startswith(MOUNT+'/') for v in mounts), 'volume existing target mount')
    m.need(not data['fstype'] and not data['label'] and not data['uuid'], 'volume existing filesystem')
    return setup.volume_plan(provider, dict(instanceId=raw['instanceId'], device=raw['device'], resolved=raw['resolved'],
        type=data['type'], sizeBytes=data['size'], readOnly=data['ro'], bootDevice=raw['bootDevice'],
        mounted=any(v['maj:min'] == data['maj:min'] for v in mounts) or any(data['mountpoints']),
        children=[], signatures=raw['wipefs']['signatures'], targetEmpty=target['empty']), user)


def mounted(raw, provider, user, backend, before):
    data, mounts = topology(raw, provider)
    previous, _ = topology(before, provider)
    m.need(raw['resolved'] == before['resolved'] and raw['bootDevice'] == before['bootDevice'] and
           data['maj:min'] == previous['maj:min'], 'volume mounted identity changed')
    owned = [v for v in mounts if v['maj:min'] == data['maj:min'] or v['target'] == MOUNT or v['target'].startswith(MOUNT+'/')]
    m.need(len(owned) == 1 and owned[0]['target'] == MOUNT and owned[0]['maj:min'] == data['maj:min'] and
           owned[0]['fstype'] == 'ext4' and {'rw', 'nodev', 'nosuid'} <= set(owned[0]['options'].split(',')) and
           'ro' not in owned[0]['options'].split(','), 'volume mount verification')
    m.need(data['mountpoints'] == [MOUNT] and data['fstype'] == 'ext4' and
           data['label'] == 'gse-'+provider['attempt'][:12] and
           re.fullmatch('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', data['uuid'] or ''), 'volume filesystem verification')
    signatures = raw['wipefs']['signatures']
    m.need(len(signatures) == 1 and signatures[0]['type'] == 'ext4', 'volume filesystem signatures')
    uid, gid = backend.user(user)
    target = raw['target']
    m.need(target['exists'] and target['directory'] and target['uid'] == uid and target['gid'] == gid and
           target['mode'] == 0o700, 'volume mount ownership/mode')
    return dict(device=raw['resolved'], majorMinor=data['maj:min'], uuid=data['uuid'], mount=MOUNT, uid=uid, gid=gid)


def prepare(root, provider, user, backend, deadline, *, recheck):
    """Consume once before inspection/mutation; uncertainty is terminal for this path.

    No reconnect repeats format/mount. The controller may read the original receipt.
    Backend writes remain restricted to offline qualification for this slice.
    """
    m.need(backend.offline is True, 'live privileged guest startup disabled')
    root = Path(root); c.directory(root.parent); root.mkdir(mode=0o700); c.sync_directory(root.parent)
    c.write_once(root/'claim.json', dict(provider=provider, user=user))
    result = dict(schema='gse-v51-volume-startup-v1', status='RUNNING', paidCloud=False, provider=provider, commands=[])
    try:
        before = observe(backend, provider, deadline); c.write_once(root/'before.json', before)
        plan = blank(before, provider, user); c.write_once(root/'plan.json', plan)
        uid, gid = backend.user(user)
        m.need(type(uid) is int and type(gid) is int and uid > 0 and gid > 0, 'volume unprivileged owner')
        recheck()
        second = observe(backend, provider, deadline); blank(second, provider, user)
        m.need(second == before, 'volume changed before format')
        # Use the checked whole-device path; never follow the by-id link on writes.
        argv = [] if before['target']['exists'] else [['mkdir', '-m', '0755', MOUNT]]
        argv += [['mkfs.ext4', '-L', 'gse-'+provider['attempt'][:12], before['resolved']],
                 ['mount', '-t', 'ext4', '-o', 'nodev,nosuid', before['resolved'], MOUNT],
                 ['chown', str(uid)+':'+str(gid), MOUNT], ['chmod', '0700', MOUNT]]
        for index, command in enumerate(argv):
            m.need(backend.clock() < deadline, 'volume original deadline')
            c.write_once(root/('intent-'+str(index)+'.json'), dict(argv=command))
            backend.run(command, deadline)  # Never retry a write, including a lost reply.
            m.need(backend.clock() < deadline, 'volume original deadline')
            result['commands'].append(command)
        after = observe(backend, provider, deadline); c.write_once(root/'after.json', after)
        result['volume'] = mounted(after, provider, user, backend, before)
        recheck(); m.need(backend.clock() < deadline, 'volume original deadline')
        result['status'] = 'PASS'
    except (Exception, KeyboardInterrupt) as error:
        result.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)[:2000]))
        raise
    finally:
        c.write_once(root/'receipt.json', result)
    return result
