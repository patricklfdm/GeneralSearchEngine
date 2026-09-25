"""Independent block-state/HTTP fixtures. Never opens a host disk or network."""
from copy import deepcopy
from pathlib import Path
from . import cloud_authority as a, cloud_gcp as g, cloud_http_fake as f, guest_volume as v, guest_setup as s, performance_model as m


class Block:
    offline = True

    def __init__(self, provider, clock, fault=None):
        self.provider, self.timer, self.fault = deepcopy(provider), clock, fault
        self.exists, self.formatted, self.attached, self.uid, self.gid, self.mode = False, False, False, 0, 0, 0o755
        self.commands, self.formats, self.alias_reads = [], 0, 0
        self.resolved = '/dev/sdb'

    def clock(self): return self.timer.seconds()
    def user(self, name):
        m.need(name == 'gse-'+self.provider['attempt'][:24], 'model owner')
        return 1001, 1001
    def target(self):
        return dict(exists=self.exists, directory=self.exists, symlink=False, empty=not self.formatted,
                    uid=self.uid if self.exists else None, gid=self.gid if self.exists else None, mode=self.mode if self.exists else None)
    def blocks(self):
        def row(name, kind, size, number, parent=None, mounts=None):
            return dict(name=name, type=kind, size=size, ro=False, **{'maj:min':number}, pkname=parent,
                        mountpoints=mounts or [None], fstype=None, label=None, uuid=None)
        boot = row('/dev/sda', 'disk', 50 << 30, '8:0')
        root = row('/dev/sda1', 'part', (50 << 30)-4096, '8:1', '/dev/sda', ['/'])
        data = row('/dev/sdb', 'disk', 100 << 30, '8:16', mounts=[v.MOUNT] if self.attached else None)
        if self.formatted:
            data.update(fstype='ext4', label='gse-'+self.provider['attempt'][:12], uuid='12345678-1234-1234-1234-123456789abc')
        return dict(blockdevices=[boot, root, data])
    def mounts(self):
        rows = [dict(source='/dev/sda1', target='/', fstype='ext4', options='rw,relatime', **{'maj:min':'8:1'})]
        if self.attached:
            rows.append(dict(source='/dev/sdb', target=v.MOUNT, fstype='ext4', options='rw,nodev,nosuid', **{'maj:min':'8:16'}))
            if self.fault == 'wrong-mount': rows[-1]['maj:min'] = '8:0'
        return dict(filesystems=rows)
    def run(self, argv, deadline):
        m.need(self.clock() < deadline, 'model deadline')
        self.commands.append(deepcopy(argv)); self.timer.sleep(.001)
        if argv[0] == 'curl': return self.provider['instanceId'].encode()
        if argv[:2] == ['readlink', '-e']:
            if 'data-' in argv[2]:
                self.alias_reads += 1
                if self.fault == 'alias-drift' and self.alias_reads > 1: return b'/dev/sdc\n'
                return b'/dev/sda\n' if self.fault == 'boot-device' else self.resolved.encode()+b'\n'
            return b'/dev/sda\n'
        if argv == v.LSBLK: return m.canonical(self.blocks())
        if argv == v.FINDMNT: return m.canonical(self.mounts())
        if argv[:5] == ['wipefs', '--no-act', '--json', '--output', 'TYPE,OFFSET'] and argv[5] in ('/dev/sda', '/dev/sdb'):
            return m.canonical(dict(signatures=[dict(type='ext4', offset='0x438')] if self.formatted or self.fault == 'used-disk' else []))
        if self.fault == 'deadline': self.timer.sleep(601); raise TimeoutError('injected original startup deadline')
        if argv == ['mkdir', '-m', '0755', v.MOUNT]:
            m.need(not self.exists, 'model target exists'); self.exists = True
        elif argv == ['mkfs.ext4', '-L', 'gse-'+self.provider['attempt'][:12], '/dev/sdb']:
            m.need(not self.formatted and not self.attached, 'model destructive reformat'); self.formatted = True; self.formats += 1
            if self.fault == 'lost-format-reply': raise ConnectionError('injected lost format reply')
        elif argv == ['mount', '-t', 'ext4', '-o', 'nodev,nosuid', '/dev/sdb', v.MOUNT]:
            m.need(self.exists and self.formatted and not self.attached, 'model mount preconditions'); self.attached = True
            if self.fault == 'lost-mount-reply': raise ConnectionError('injected lost mount reply')
        elif argv == ['chown', '1001:1001', v.MOUNT]: self.uid = self.gid = 1001
        elif argv == ['chmod', '0700', v.MOUNT]: self.mode = 0o700
        else: raise ValueError('unmodeled guest command: '+str(argv))
        return b''


class Transport:
    offline = True
    def __init__(self, clock, fault=None): self.clock, self.fault, self.blocks = clock, fault, []
    def prepare(self, facts, target, output, deadline, *, recheck):
        m.need(target['instanceId'] == facts['provider']['instanceId'], 'model pinned target')
        block = Block(facts['provider'], self.clock, self.fault if facts['provider']['node'] == 2 else None)
        self.blocks.append(block)
        return v.prepare(output, facts['provider'], target['user'], block, deadline, recheck=recheck)


def fixture(private, fault=None):
    req, pre, approval, clock, http, store, old = f.fixture()
    access = s.generate(Path(private), req['attempt'])
    req.update(schema='gse-v51-cloud-request-v2', guestAccessSha256=m.sha(m.canonical(access)))
    pre['requestSha256'] = a.validate_request(req)
    approval.update(requestSha256=a.validate_request(req), preflightSha256=m.sha(m.canonical(pre)))
    provider = g.Compute(old.config, req, old.api, guest_access=access, sleep=clock.sleep)
    drifted = False
    def hook(method, path, query, body):
        nonlocal drifted
        if method != 'GET': return None
        if path.path.endswith('/getGuestAttributes'):
            return http.reply(dict(queryPath='hostkeys/', queryValue=dict(items=[dict(namespace='hostkeys', key='ssh-ed25519', value=access['publicKey'].split()[1])])))
        collection, identity = path.path.rsplit('/', 1)
        match = next(((key, val) for key, val in http.resources.items() if key.rsplit('/', 1)[0] == collection and (key == path.path or val['id'] == identity)), None)
        if match is None: return None
        key, value = match; value = deepcopy(value)
        if '/instances/' in key:
            value['status'] = 'RUNNING'; node = int(value['name'][-1]); value['networkInterfaces'][0]['networkIP'] = '10.0.0.'+str(node)
        elif '/disks/' in key:
            value['status'] = 'READY'; vm_name = value['name'].rsplit('-', 1)[0]
            vm_key = key.split('/disks/')[0]+'/instances/'+vm_name
            value['users'] = ['https://compute.googleapis.com'+vm_key] if vm_key in http.resources else []
            if fault == 'disk-id-drift' and not drifted and len(http.resources) == 13 and value['name'].endswith('n2-data') and identity.isdecimal():
                value['id'] = '999999'; drifted = True
        return http.reply(value)
    http.hook = hook
    return req, pre, approval, clock, http, store, provider, Transport(clock, fault)
