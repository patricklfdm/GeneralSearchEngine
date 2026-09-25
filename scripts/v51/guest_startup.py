"""Owned-controller startup bridge, offline adapters only until paid admission."""
from pathlib import Path
from . import cloud_authority as a, performance_model as m, remote_command as c
from .guest_setup import pin, check_private_key
from .guest_transport import ssh_args


class Prepare:
    execution = a.EXECUTION

    def __init__(self, provider, transport, key, output):
        m.need(provider.api.offline is True and transport.offline is True, 'live guest startup disabled')
        m.need(provider.guest_access is not None, 'startup needs request-bound access')
        self.provider, self.transport, self.key, self.root = provider, transport, Path(key).absolute(), Path(output)
        check_private_key(self.key, provider.guest_access)

    def prepare(self, req, lease, deadline):
        m.need(req == self.provider.req and lease['request'] == req, 'startup request mismatch')
        c.directory(self.root.parent); self.root.mkdir(mode=0o700); c.sync_directory(self.root.parent)
        digest = a.validate_request(req)
        c.write_once(self.root/'claim.json', dict(requestSha256=digest, lease=lease))
        result = dict(schema='gse-v51-guest-startup-v1', status='RUNNING', execution=a.EXECUTION,
                      paidCloud=False, fullRemoteQualification=False, requestSha256=digest, guests=[])
        seconds = deadline/10**9
        try:
            facts = [self.provider.guest_facts(lease, node, deadline=seconds) for node in (1, 2, 3)]
            m.need(len({v['privateIp'] for v in facts}) == 3 and
                   len({v['provider']['instanceId'] for v in facts}) == 3 and
                   len({identity for v in facts for identity in (v['bootDiskId'], v['provider']['diskId'])}) == 6, 'startup distinct topology')
            c.write_once(self.root/'facts.json', facts)
            targets, pins = [], []
            for item in facts:
                node = item['provider']['node']; identity = item['provider']['instanceId']
                spec = next(r['spec'] for r in lease['resources'] if r['spec']['kind'] == 'instance' and r['spec']['node'] == node)
                host = self.provider.guest_host_key(spec, identity, deadline=seconds)
                known = (self.root/('known-host-'+str(node))).absolute(); pin(known, identity, host['publicKey'])
                target = dict(project=item['project'], zone=item['zone'], instance=item['instance'], instanceId=identity,
                              user=self.provider.guest_access['user'], key=str(self.key), knownHosts=str(known))
                # Exercise the same exact pin/credential/argv validation as native IAP SSH.
                ssh_args(target, ['true'])
                targets.append(target); pins.append(dict(node=node, **host))
            c.write_once(self.root/'host-pins.json', pins)
            for item, target in zip(facts, targets):
                node = item['provider']['node']
                def recheck(item=item, node=node):
                    m.need(self.provider.guest_facts(lease, node, deadline=seconds) == item, 'startup provider drift')
                recheck()
                guest = self.transport.prepare(item, target, self.root/('node-'+str(node)), seconds, recheck=recheck)
                m.need(set(guest) == {'schema', 'status', 'paidCloud', 'provider', 'commands', 'volume'} and
                       guest['schema'] == 'gse-v51-volume-startup-v1' and guest['status'] == 'PASS' and
                       guest['paidCloud'] is False and guest['provider'] == item['provider'], 'startup guest result')
                result['guests'].append(guest)
            m.need([self.provider.guest_facts(lease, node, deadline=seconds) for node in (1, 2, 3)] == facts,
                   'startup final provider drift')
            result['status'] = 'PASS'
        except (Exception, KeyboardInterrupt) as error:
            result.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)[:2000]))
            raise
        finally:
            c.write_once(self.root/'receipt.json', result)
        return result

    def retention_files(self):
        # Only closed generated diagnostics. Private SSH key material is elsewhere.
        if self.root.is_dir():
            allowed = {'claim.json', 'facts.json', 'host-pins.json', 'receipt.json'} | {f'node-{node}/{name}.json'
                for node in (1, 2, 3) for name in ('claim', 'before', 'plan', 'after', 'receipt', *('intent-'+str(i) for i in range(5)))}
            paths = sorted(self.root.rglob('*.json'))
            m.need(len(paths) <= len(allowed), 'startup retention inventory')
            for path in paths:
                c.directory(path.parent)
                name = path.relative_to(self.root).as_posix()
                m.need(name in allowed and path.is_file() and not path.is_symlink() and path.stat().st_size <= 262144, 'startup retention file')
                yield name, path.read_bytes()
