"""Attempt SSH access and fail-closed data-volume planning. No disk mutation runner."""
import base64
import os
from pathlib import Path
import re
import subprocess
from . import performance_model as m, remote_command as c


def ed25519(value):
    m.need(isinstance(value, str) and re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', value), 'Ed25519 public key')
    raw = base64.b64decode(value.split()[1], validate=True)
    m.need(len(raw) == 51 and raw[:19] == b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x20', 'Ed25519 key encoding')
    return value


def access(value):
    m.need(type(value) is dict and set(value) == {'attempt', 'user', 'publicKey'} and
           re.fullmatch('[0-9a-f]{32}', value['attempt']) and value['user'] == 'gse-'+value['attempt'][:24], 'attempt SSH access')
    ed25519(value['publicKey']); return value


def generate(directory, attempt):
    m.need(isinstance(attempt, str) and re.fullmatch('[0-9a-f]{32}', attempt), 'SSH attempt')
    directory = Path(directory); c.directory(directory.parent); directory.mkdir(mode=0o700)
    key = directory/'identity'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', '', '-f', str(key)], check=True, timeout=10, stdout=subprocess.DEVNULL)
    m.need(key.stat().st_uid == os.getuid() and key.stat().st_mode & 0o077 == 0, 'private SSH key permissions')
    result = access(dict(attempt=attempt, user='gse-'+attempt[:24], publicKey=(directory/'identity.pub').read_text().strip()))
    c.write_once(directory/'access.json', result)
    return result  # Never return private key bytes or include them in an evidence bundle.


def check_private_key(path, value):
    """Verify the owned key corresponds to this request's public access descriptor."""
    access(value); path = Path(path)
    c.directory(path.parent)
    m.need(path.is_absolute() and path.is_file() and not path.is_symlink() and
           path.stat().st_uid == os.getuid() and path.stat().st_mode & 0o077 == 0 and
           path.stat().st_size <= 4096, 'SSH owned private key')
    result = subprocess.run(['ssh-keygen', '-y', '-P', '', '-f', str(path)], stdin=subprocess.DEVNULL,
                            capture_output=True, check=True, timeout=10)
    m.need(ed25519(result.stdout.decode().strip()) == value['publicKey'], 'SSH private/public key mismatch')


def metadata(value):
    access(value)
    return [dict(key='block-project-ssh-keys', value='TRUE'), dict(key='enable-oslogin', value='FALSE'),
            dict(key='enable-guest-attributes', value='TRUE'), dict(key='ssh-keys', value=value['user']+':'+value['publicKey'])]


def host_key(response):
    m.need(response.get('queryPath') == 'hostkeys/', 'SSH host-key query scope')
    items = response.get('queryValue', {}).get('items', [])
    m.need(type(items) is list and len(items) <= 10, 'SSH host-key entries')
    selected = [v for v in items if v.get('namespace') == 'hostkeys' and v.get('key') == 'ssh-ed25519']
    m.need(len(selected) == 1, 'missing/duplicate SSH host key')
    # The guest agent publishes the base64 wire key in the value field.
    return ed25519('ssh-ed25519 '+selected[0]['value'])


def pin(path, identity, public_key):
    m.need(isinstance(identity, str) and re.fullmatch('[1-9][0-9]{0,19}', identity), 'SSH instance ID')
    ed25519(public_key); path = Path(path); c.directory(path.parent)
    with os.fdopen(os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600), 'w') as out:
        out.write('gse-v51-'+identity+' '+public_key+'\n'); out.flush(); os.fsync(out.fileno())
    c.sync_directory(path.parent)


def volume_plan(provider, observed, user):
    """Consumes checked provider facts and an explicit blank-device observation.

    This pure plan is not evidence that lsblk/wipefs/findmnt ran on a real VM.
    Live observation, privileged execution and post-mount verification stay closed.
    """
    m.need(set(provider) == {'instanceId', 'diskId', 'node', 'sizeGiB', 'attempt'}, 'volume provider fields')
    for key in ('instanceId', 'diskId'):
        m.need(isinstance(provider[key], str) and re.fullmatch('[1-9][0-9]{0,19}', provider[key]), 'volume numeric identity')
    m.need(type(provider['node']) is int and provider['node'] in (1,2,3) and provider['sizeGiB'] == 100 and
           re.fullmatch('[0-9a-f]{32}', provider['attempt']) and user == 'gse-'+provider['attempt'][:24], 'volume owner/shape')
    m.need(set(observed) == {'instanceId', 'device', 'resolved', 'type', 'sizeBytes', 'readOnly', 'mounted', 'signatures', 'children', 'bootDevice', 'targetEmpty'}, 'volume observation fields')
    device = '/dev/disk/by-id/google-gse-data-'+str(provider['node'])
    m.need(observed['instanceId'] == provider['instanceId'] and observed['device'] == device and
           re.fullmatch(r'/dev/(sd[a-z]+|nvme[0-9]+n[0-9]+)', observed['resolved']) and
           observed['resolved'] != observed['bootDevice'], 'volume guest identity/device')
    m.need(observed['type'] == 'disk' and type(observed['sizeBytes']) is int and observed['sizeBytes'] == 100*(1<<30) and
           observed['readOnly'] is False and observed['mounted'] is False and observed['targetEmpty'] is True and
           observed['signatures'] == [] and observed['children'] == [], 'volume not an empty dedicated data disk')
    mount = '/mnt/gse-v51'; label = 'gse-'+provider['attempt'][:12]
    return dict(schema='gse-v51-guest-volume-plan-v1', execution='offline-guest-setup-plan', paidCloud=False,
        provider=provider, observationSha256=m.sha(m.canonical(observed)), device=device, mount=mount,
        commands=[['mkfs.ext4', '-L', label, device], ['mount', '-o', 'nodev,nosuid', device, mount], ['chown', user+':'+user, mount]])
