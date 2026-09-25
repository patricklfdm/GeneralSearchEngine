"""One-time source distribution and local public bootstrap; never runtime state repair.

Only the prepare-cell handler exports the source, before any voter is started. The controller
must supply the independently retained descriptor digest to the receiving guest.
A partial install consumes its destination; it cannot be overwritten or resumed.
"""
import argparse
from copy import deepcopy
import os
from pathlib import Path
import sys
from . import performance_model as m, remote_command as c, remote_collection as parts
from . import cloud_package as package

SCHEMA = 'gse-v51-guest-bootstrap-v1'
TOPOLOGY = ('hosts.txt', 'ports.txt', 'group-id.txt')
SOURCE = ('gse-backup-manifest', 'gse-backup-checkpoint', 'gse-backup-metadata')
COMMON = {'manifest.gsr', 'proofs.gsr', 'genesis.gsr', 'bootstrap-seal.gsr', 'storage-ready.gsr',
          'promises.gsr', 'node.gsr', 'bootstrap-prepared.gsr', 'replica.lock'}
CLAIM, READY = '.bootstrap-claim.json', '.bootstrap-ready.json'


LOCAL_CLAIM, LOCAL_READY = '.bootstrap-local-claim.json', '.bootstrap-local-ready.json'


def expected_files(config):
    if config['mode'] == package.MODES[0]: m.need(config['binding']['node'] == 'node-1', 'local bootstrap node')
    return {*TOPOLOGY, *('source/'+n for n in SOURCE)}


def authority_files(config):
    if config['mode'] == package.MODES[0]: return set()
    return COMMON | ({'accepted.gsr', 'bootstrap-binding.gsr'} if config['mode'] == package.MODES[2] else {'entries.gsr'})


def topology(root, config):
    for name, text in zip(TOPOLOGY, ('\n'.join(config['hosts'])+'\n', '\n'.join(map(str, config['ports']))+'\n', config['groupId']+'\n')):
        path = root/name
        m.need(path.is_file() and not path.is_symlink() and path.read_bytes() == text.encode(), 'bootstrap topology differs')


def export(root, target, config):
    from .cloud_guest import validate
    validate(config); root, target = c.directory(root), Path(target)
    m.need(str(root) == config['root'], 'bootstrap sealed path')
    m.need(not list(root.glob('*-jvm.json')) and not list(root.glob('*-results*')) and not (root/'store').exists(), 'bootstrap already used')
    topology(root, config)
    # Only a verified immutable source backup crosses hosts. Public bootstrap
    # seals also bind filesystem identity and must be produced on the receiver.
    wanted = expected_files(config)
    m.need(not any((root/('node-'+str(n))).exists() for n in (1,2,3)), 'bootstrap authority cannot be distributed')
    m.need({p.name for p in (root/'source').iterdir()} == set(SOURCE), 'bootstrap source inventory')
    for name in wanted:
        path = root/name; c.directory(path.parent)
        m.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 << 20, 'bootstrap source type/bound')
    target.mkdir(mode=0o700); raw = target/'raw'; raw.mkdir()
    before = {}
    for name in sorted(wanted):
        path = root/name; data = path.read_bytes(); before[name] = dict(bytes=len(data), sha256=m.sha(data))
        out = raw/name; out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(data)
    m.need(sum(v['bytes'] for v in before.values()) <= 64 << 20, 'bootstrap total bound')
    manifest = parts.pack(raw, target/'parts', m.sha(m.canonical(config)))
    m.need(all(m.sha((root/n).read_bytes()) == v['sha256'] for n, v in before.items()), 'bootstrap changed during export')
    value = dict(schema=SCHEMA, config=deepcopy(config), files=before, partsSha256=m.sha(m.canonical(manifest)))
    c.write_once(target/'bootstrap.json', value)
    return dict(node=config['binding']['node'], descriptorSha256=m.sha(m.canonical(value)))


def descriptor(folder, digest, config):
    from .cloud_guest import validate
    validate(config); value = c.read(folder/'bootstrap.json')
    m.need(m.sha(m.canonical(value)) == digest, 'bootstrap descriptor digest')
    m.need(set(value) == {'schema', 'config', 'files', 'partsSha256'} and value['schema'] == SCHEMA and value['config'] == config, 'bootstrap exact identity/path')
    files = value['files']; m.need(set(files) == expected_files(config), 'bootstrap member scope')
    m.need(sum(v['bytes'] for v in files.values()) <= 64 << 20, 'bootstrap total bound')
    manifest = c.read(folder/'parts/parts.json')
    m.need(m.sha(m.canonical(manifest)) == value['partsSha256'], 'bootstrap parts binding')
    parts.validate_manifest(manifest, m.sha(m.canonical(config)))
    return value


def install(folder, digest, config):
    folder = c.directory(folder); value = descriptor(folder, digest, config)
    root = c.directory(config['root']); m.need(not list(root.iterdir()), 'bootstrap target consumed/nonempty')
    # mkdir is the exclusive install claim (write_once alone cannot serialize a
    # directory of writes). Leave it on every failure, including power loss.
    stage = root/'.bootstrap-install'; stage.mkdir(mode=0o700); c.sync_directory(root)
    c.write_once(root/CLAIM, dict(descriptorSha256=digest, config=config))
    parts.unpack(folder/'parts', stage/'raw', m.sha(m.canonical(config)))
    raw = stage/'raw'; index = c.read(raw/parts.INDEX)
    m.need(index == value['files'], 'bootstrap installed inventory differs')
    (raw/parts.INDEX).unlink(); topology(raw, config)
    for path in raw.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream: os.fsync(stream.fileno())
    for path in sorted((p for p in raw.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True): c.sync_directory(path)
    for path in raw.iterdir(): os.rename(path, root/path.name)
    raw.rmdir(); stage.rmdir(); c.sync_directory(root)
    c.write_once(root/READY, value)
    check_ready(root, config)
    return dict(status='PASS', node=config['binding']['node'], descriptorSha256=digest, files=len(index))


def check_ready(root, config, *, sealed=False):
    """Before first JVM launch, verify imported seed and locally sealed authority."""
    root = c.directory(root); value = c.read(root/READY); claim = c.read(root/CLAIM)
    m.need(value['schema'] == SCHEMA and value['config'] == config and claim == dict(descriptorSha256=m.sha(m.canonical(value)), config=config), 'bootstrap ready identity')
    m.need(set(value['files']) == expected_files(config), 'bootstrap ready members')
    allowed = {CLAIM, READY, 'agents', *TOPOLOGY, 'source'}
    if sealed:
        allowed.update((LOCAL_CLAIM, LOCAL_READY))
        local = c.read(root/LOCAL_READY)
        m.need(c.read(root/LOCAL_CLAIM) == dict(config=config, seedSha256=m.sha(m.canonical(value))) and local['config'] == config, 'local bootstrap identity')
        m.need(set(local['files']) == authority_files(config), 'local bootstrap file set')
        if config['mode'] != package.MODES[0]:
            node = config['binding']['node']; allowed.add(node)
            m.need(parts.inventory(root/node) == local['files'], 'local bootstrap changed')
            for name in ('manifest', 'genesis'):
                m.need(local['identity'][name+'Sha256'] == local['files'][name+'.gsr']['sha256'], 'local bootstrap group identity')
        m.need(local['identity']['sourceSha256'] == m.sha(m.canonical({k:v for k,v in value['files'].items() if k.startswith('source/')})), 'local bootstrap source identity')
    m.need({p.name for p in root.iterdir()} <= allowed, 'bootstrap unexpected root')
    actual = parts.inventory(root/'source')
    m.need({'source/'+k: v for k, v in actual.items()} == {k:v for k,v in value['files'].items() if k.startswith('source/')}, 'bootstrap ready inventory')
    topology(root, config)
    m.need(all((root/k).stat().st_size == v['bytes'] and m.sha((root/k).read_bytes()) == v['sha256'] for k,v in value['files'].items()), 'bootstrap ready bytes')
    return value


def seal(base, config):
    from .cloud_guest import Service
    root = c.directory(config['root']); value = check_ready(root, config)
    c.write_once(root/LOCAL_CLAIM, dict(config=config, seedSha256=m.sha(m.canonical(value))))
    service = Service(base, config); files = {}
    identity = dict(sourceSha256=m.sha(m.canonical({k:v for k,v in value['files'].items() if k.startswith('source/')})))
    if config['mode'] != package.MODES[0]:
        service.oneshot('local-bootstrap', service.java(config['mode'], root, 'setup', service.plan, root/'source'))
        node = config['binding']['node']; files = parts.inventory(root/node)
        m.need(set(files) == authority_files(config), 'public local bootstrap inventory')
        identity.update({name+'Sha256': files[name+'.gsr']['sha256'] for name in ('manifest', 'genesis')})
        # The public API prepares three offline voters. Keep only the assigned
        # one at a live path; retain the never-started sibling copies and operation
        # receipts as diagnostics. No authority bytes or seals are rewritten.
        archive = service.root/'unstarted-bootstrap'; archive.mkdir()
        for other in ('node-1', 'node-2', 'node-3', 'operation'):
            if other == node: continue
            os.rename(root/other, archive/other)
        c.sync_directory(archive); c.sync_directory(root)
    local = dict(config=config, files=files, identity=identity)
    c.write_once(root/LOCAL_READY, local); check_ready(root, config, sealed=True)
    return dict(status='PASS', node=config['binding']['node'], identity=identity)


def group_identity(rows, configs):
    m.need(len(rows) == len(configs) and [r['node'] for r in rows] == [v['binding']['node'] for v in configs] and
           all(r['status'] == 'PASS' for r in rows), 'local bootstrap member set')
    m.need(all(row['identity'] == rows[0]['identity'] for row in rows), 'local bootstrap manifest/genesis/source disagree')
    return rows[0]['identity']


def main(base, argv):
    from .cloud_guest import Service
    p = argparse.ArgumentParser(); p.add_argument('action', choices=('prepare', 'install', 'seal')); p.add_argument('--input'); p.add_argument('--digest'); a = p.parse_args(argv)
    config = m.strict_json(sys.stdin.buffer.read(c.REQUEST_BYTES+1))
    package.verify(base, config['binding']['source'])
    m.need(m.sha((base/'manifest.json').read_bytes()) == config['packageManifestSha256'], 'bootstrap package binding')
    if a.action == 'prepare':
        service = Service(base, config)
        value = c.request(config['binding'], m.sha(m.canonical(config))[:32], 'prepare-cell', dict(distribute=True))
        answer = service.store.execute(value, service.handler)
        m.need(answer['state'] == 'SUCCEEDED', 'bootstrap producer failed: '+str(answer))
    elif a.action == 'install': answer = install(Path(a.input), a.digest, config)
    else: answer = seal(base, config)
    print(m.canonical(answer).decode(), flush=True)
