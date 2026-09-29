"""Actual packaged CLI/guest/JVM qualification on one host, never cloud acceptance."""
import argparse
import ctypes
import os
from pathlib import Path
import socket
import signal
import time
import uuid
from scripts import ci_v51_bundle as build
from . import cloud_package as package, cloud_guest as guest, guest_transport as transport
from . import remote_command as command, remote_collection as collection, remote_schedule as schedule, performance_model as m
from . import guest_evidence


def run(output, bundle, source, *, isolated=False, allow_sudo=False, delivery=None, healthy=False, physical=False, backup=False):
    m.need(not backup or physical,'backup requires physical evidence')
    m.need(not physical or healthy,'physical evidence requires healthy scope')
    m.need(not (isolated and delivery), 'SSH service and mount-view qualification are separate gates')
    root, bundle = Path(output).resolve(), Path(bundle).resolve(); root.mkdir(parents=True, exist_ok=False, mode=0o700)
    packaged = bundle/'package'; manifest = package.verify(packaged, source)
    m.need(manifest['buildBinding'] == build.binding(Path(__file__).resolve().parents[2], source), 'guest qualification checkout/build mismatch')
    packed = package.read(bundle/'receipt.json')
    m.need(packed['status'] == 'PASS' and packed['source'] == source and
           m.sha((bundle/'guest.tar.gz').read_bytes()) == packed['archiveSha256'], 'guest qualified package receipt')
    manifest_bytes = (packaged/'manifest.json').read_bytes()
    (root/'package-manifest.json').write_bytes(manifest_bytes)
    # Reap detached services after their short-lived launch CLI exits.
    m.need(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'guest qualification subreaper')
    results, services, transcripts = [], [], {}; deadline = time.monotonic()+840
    receipt = dict(schema='gse-v51-guest-qualification-v1', status='FAIL', execution=guest.EXECUTION,
        filesystem='independent-mount-views' if isolated else 'shared-local', source=source, buildBinding=manifest['buildBinding'], bundleSha256=packed['archiveSha256'],
        paidCloud=False, fullRemoteQualification=False, engineWorkloadExecuted=True, cases=results)
    def execute(client, name, payload, lost=False, until=None):
        value = command.request(client.config['binding'], uuid.uuid4().hex, name, payload)
        until = min(deadline,time.monotonic()+120,until if until is not None else deadline)
        identity = m.sha(m.canonical(client.config))
        retained = root/'controller'/identity/value['commandId']; retained.mkdir(parents=True,mode=0o700)
        command.write_once(retained/'request.json',dict(config=client.config,request=value))
        class Drop:
            submits, queries = 0, 0
            def submit(self, request, end):
                self.submits += 1; answer = client.submit(request, end)
                if lost: raise ConnectionError('qualification discarded the original submit reply')
                return answer
            def query(self, request, end): self.queries += 1; return client.query(request, end)
        connection = Drop()
        result = command.submit_and_observe(connection, value, until)
        command.write_once(retained/'receipt.json',result)
        transcripts.setdefault(identity,[]).append(dict(request=value,receipt=result))
        return value, result, dict(submits=connection.submits, queries=connection.queries)
    try:
        for mode in package.MODES:
            cell = root/mode; cell.mkdir(); sockets = [socket.socket() for _ in range(3)]
            try:
                hosts = ['127.0.0.2', '127.0.0.3', '127.0.0.4']; ports = []
                for sock, host in zip(sockets, hosts): sock.bind((host, 0)); ports.append(sock.getsockname()[1])
                group, attempt, clients = str(uuid.uuid4()), uuid.uuid4().hex, []
                configs = []
                for n in range(1, 2 if mode == package.MODES[0] else 4):
                    cfg = dict(schema='gse-v51-guest-service-v1', execution=guest.EXECUTION,
                        binding=command.binding(source, packed['archiveSha256'], attempt, 'node-'+str(n)),
                        packageManifestSha256=m.sha((packaged/'manifest.json').read_bytes()), root=str(cell), mode=mode,
                        hosts=hosts, ports=ports, groupId=group)
                    configs.append(cfg)
                packages = {cfg['binding']['node']: delivery.install(cfg, min(deadline,time.monotonic()+120)) if delivery else packaged for cfg in configs}
                views = None
                if isolated:
                    from . import guest_isolation
                    views = guest_isolation.Views(root/'views'/mode, cell, allow_sudo)
                    guest_isolation.prepare(views, packaged, configs, min(deadline, time.monotonic()+120))
                for cfg in configs:
                    base = packages[cfg['binding']['node']]
                    client = delivery.client(cfg) if delivery else (views.client(base, cfg) if isolated else transport.Local(base, cfg))
                    started = client.start(min(deadline, time.monotonic()+30))
                    m.need(started['state'] == 'LAUNCHED', 'guest startup claim'); services.append((client, started['pid']))
                    until = min(deadline, time.monotonic()+30)
                    while True:
                        observed = client.ready(until)
                        if observed['ready'] is not None:
                            m.need(observed['ready']['pid'] == started['pid'] and observed['ready']['configSha256'] == m.sha(m.canonical(cfg)), 'guest ready identity'); break
                        m.need(time.monotonic() < until, 'guest service startup timeout'); time.sleep(.05)
                    clients.append(client)
                if not isolated:
                    _, answer, _ = execute(clients[0], 'prepare-cell', {})
                    m.need(answer['state'] == 'SUCCEEDED', 'guest prepare: '+str(answer))
            finally:
                for sock in sockets: sock.close()
            for client in clients:
                _, answer, _ = execute(client, 'start-voter', {})
                m.need(answer['state'] == 'SUCCEEDED', 'guest JVM start: '+str(answer))
            active = clients[0]
            if mode == package.MODES[1]:
                _, answer, _ = execute(active, 'fault', dict(action='activate'))
                m.need(answer['state'] == 'SUCCEEDED', 'configured guest activation')
            if mode == package.MODES[2]:
                until = min(deadline, time.monotonic()+30); active = None
                while active is None:
                    for client in clients:
                        _, answer, _ = execute(client, 'fault', dict(action='status'))
                        m.need(answer['state'] == 'SUCCEEDED', 'automatic guest status')
                        if answer['result']['status']['state'] == 'LEADER_READY': active = client; break
                    m.need(time.monotonic() < until, 'automatic guest startup deadline')
            specs=schedule.windows('healthy','experiment')[:None if healthy else 1]
            for spec in specs:
                if healthy:
                    for client in clients:
                        if client is not active:
                            _,configured,_=execute(client,'fault',dict(action='configure',window=spec['window']))
                            m.need(configured['state']=='SUCCEEDED','guest passive configure')
                value, answer, counts = execute(active, 'window', dict(cell='healthy', preset='experiment', window=spec['window']), lost=True)
                m.need(answer['state'] == 'SUCCEEDED' and counts['submits'] == 1 and counts['queries'] > 0, 'guest lost-reply window: '+str(answer))
                m.need(answer['result']['calls'] == len(spec['calls']), 'guest frozen window count')
            expected = len(specs[0]['calls'])
            _, bad, _ = execute(active, 'collect', {})
            m.need(bad['state'] == 'FAILED' and 'stopped JVM' in bad['error']['message'], 'live JVM collection accepted')
            physical_mode=physical and mode in package.MODES[1:]
            if physical_mode:
                if backup:
                    _,backed,_=execute(active,'backup',{},lost=True)
                    m.need(backed['state']=='SUCCEEDED','guest backup command')
                from . import guest_physical_evidence
                def status(client,end):
                    _,answer,_=execute(client,'fault',dict(action='status'),until=end)
                    m.need(answer['state']=='SUCCEEDED','guest final status command')
                    return answer['result']['status']
                guest_physical_evidence.converge(clients,active,status,deadline,mode=mode)
            for client in clients:
                _, stopped, _ = execute(client, 'stop-voter', dict(forced=False))
                m.need(stopped['state'] == 'SUCCEEDED', 'guest clean stop: '+str(stopped))
            if backup and physical_mode:
                _,restored,_=execute(active,'restore-backup',{},lost=True)
                m.need(restored['state']=='SUCCEEDED','guest restore command')
            old = active.submit(value, min(deadline, time.monotonic()+20)); m.need(old == answer, 'terminal command was replayed')
            members = []; physical_members=[]
            for client in clients:
                _, collected, _ = execute(client, 'collect', dict(physical=True,backup=True) if backup and physical_mode and client is active else ({'physical':True} if physical_mode else {}))
                m.need(collected['state'] == 'SUCCEEDED', 'guest collection: '+str(collected))
                parts = collected['result']; binding = m.sha(m.canonical(client.config['binding']))
                collection.validate_manifest(parts, binding)
                download = cell/('download-'+client.config['binding']['node']); download.mkdir()
                command.write_once(download/'parts.json', parts)
                for i, part in enumerate(parts['parts']):
                    raw = client.part(part['name'], part['bytes'], min(deadline, time.monotonic()+30))
                    if mode == package.MODES[2] and client is active and i == 0:
                        failed = cell/'interrupted-download'; failed.mkdir()
                        try: collection.receive_part(failed, part, (raw[p:min(p+(1<<20),len(raw)-1)] for p in range(0,len(raw)-1,1<<20)))
                        except ValueError: pass
                        else: raise ValueError('truncated guest part accepted')
                        m.need((failed/(part['name']+'.partial')).exists(), 'lost partial download evidence')
                    collection.receive_part(download, part, (raw[p:p+(1<<20)] for p in range(0,len(raw),1<<20)))
                replay = cell/('replay-'+client.config['binding']['node'])
                checked = collection.unpack(download, replay, binding)
                node = 'local' if mode == package.MODES[0] else client.config['binding']['node']
                controller = dict(config=client.config,packageRoot=str(client.base),active=client is active,
                    transcript=transcripts[m.sha(m.canonical(client.config))])
                command.write_once(cell/('controller-'+client.config['binding']['node']+'.json'),controller)
                validated = guest_evidence.validate(replay,client.config,manifest_bytes,client.base,
                    controller['transcript'],active=controller['active'],healthy=healthy,physical=physical_mode,backup=backup and physical_mode and client is active)
                command.write_once(cell/('validation-'+client.config['binding']['node']+'.json'),validated)
                members.append(dict(node=node,calls=validated['calls'],journals=validated['journals'],collection=checked,validation=validated))
                physical_members.append(dict(root=replay,controller=controller))
            physical_result=None
            if physical_mode:
                physical_result=guest_physical_evidence.validate(physical_members,manifest_bytes,backup=backup)
                command.write_once(cell/'physical.json',physical_result)
            row = dict(mode=mode, status='PASS', warmupCalls=expected, healthyWindows=healthy,
                calls=sum(len(s['calls']) for s in specs),transport=counts, members=members,physical=physical_result)
            results.append(row); print(m.canonical(row).decode(), flush=True)
        receipt['status'] = 'PASS'
    except BaseException as error:
        receipt['failure'] = dict(type=type(error).__name__, message=str(error)[:3000]); raise
    finally:
        errors = []
        for client, pid in services:
            try:
                until = time.monotonic()+30; client.shutdown(until)
                while True:
                    state = client.ready(until)
                    if state['closed'] is not None:
                        break
                    m.need(time.monotonic() < until, 'guest service close deadline'); time.sleep(.05)
                while True:
                    waited, status = os.waitpid(pid, os.WNOHANG)
                    if waited: break
                    m.need(time.monotonic() < until, 'guest service reap deadline'); time.sleep(.05)
                m.need(os.waitstatus_to_exitcode(status) == 0, 'guest service exit status')
                m.need(state['closed']['status'] == 'PASS' and state['closed']['jvmStopped'], 'guest service close failure')
            except BaseException as error: errors.append(str(error))
        receipt['cleanupErrors'] = errors
        if errors: receipt['status'] = 'FAIL'
        command.write_once(root/'receipt.json', receipt)
    m.need(receipt['status'] == 'PASS', 'guest service qualification failed'); return receipt


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source',required=True);p.add_argument('--isolated',action='store_true');p.add_argument('--allow-sudo-namespace',action='store_true');p.add_argument('--healthy',action='store_true')
    p.add_argument('--physical',action='store_true');p.add_argument('--backup',action='store_true')
    a=p.parse_args()
    def terminate(*_): raise TimeoutError('guest qualification terminated')
    signal.signal(signal.SIGTERM, terminate)
    run(a.output,a.bundle,a.source,isolated=a.isolated,allow_sudo=a.allow_sudo_namespace,healthy=a.healthy,physical=a.physical,backup=a.backup)
