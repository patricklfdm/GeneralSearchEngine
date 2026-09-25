"""Actual packaged CLI/guest/JVM qualification on one host, never cloud acceptance."""
import argparse
import ctypes
import gzip
import json
import os
from pathlib import Path
import socket
import signal
import time
import uuid
from scripts import ci_v51_bundle as build
from . import cloud_package as package, cloud_guest as guest, guest_transport as transport
from . import remote_command as command, remote_collection as collection, remote_schedule as schedule, performance_model as m


def run(output, bundle, source):
    root, bundle = Path(output).resolve(), Path(bundle).resolve(); root.mkdir(parents=True, exist_ok=False)
    packaged = bundle/'package'; manifest = package.verify(packaged, source)
    m.need(manifest['buildBinding'] == build.binding(Path(__file__).resolve().parents[2], source), 'guest qualification checkout/build mismatch')
    packed = package.read(bundle/'receipt.json')
    m.need(packed['status'] == 'PASS' and packed['source'] == source and
           m.sha((bundle/'guest.tar.gz').read_bytes()) == packed['archiveSha256'], 'guest qualified package receipt')
    # Reap detached services after their short-lived launch CLI exits.
    m.need(ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) == 0, 'guest qualification subreaper')
    results, services = [], []; deadline = time.monotonic()+840
    receipt = dict(schema='gse-v51-guest-qualification-v1', status='FAIL', execution=guest.EXECUTION,
        source=source, buildBinding=manifest['buildBinding'], bundleSha256=packed['archiveSha256'],
        paidCloud=False, fullRemoteQualification=False, engineWorkloadExecuted=True, cases=results)
    def execute(client, name, payload, lost=False):
        value = command.request(client.config['binding'], uuid.uuid4().hex, name, payload)
        class Drop:
            submits, queries = 0, 0
            def submit(self, request, end):
                self.submits += 1; answer = client.submit(request, end)
                if lost: raise ConnectionError('qualification discarded the original submit reply')
                return answer
            def query(self, request, end): self.queries += 1; return client.query(request, end)
        connection = Drop()
        result = command.submit_and_observe(connection, value, min(deadline, time.monotonic()+120))
        return value, result, dict(submits=connection.submits, queries=connection.queries)
    try:
        for mode in package.MODES:
            cell = root/mode; cell.mkdir(); sockets = [socket.socket() for _ in range(3)]
            try:
                hosts = ['127.0.0.2', '127.0.0.3', '127.0.0.4']; ports = []
                for sock, host in zip(sockets, hosts): sock.bind((host, 0)); ports.append(sock.getsockname()[1])
                group, attempt, clients = str(uuid.uuid4()), uuid.uuid4().hex, []
                for n in range(1, 2 if mode == package.MODES[0] else 4):
                    cfg = dict(schema='gse-v51-guest-service-v1', execution=guest.EXECUTION,
                        binding=command.binding(source, packed['archiveSha256'], attempt, 'node-'+str(n)),
                        packageManifestSha256=m.sha((packaged/'manifest.json').read_bytes()), root=str(cell), mode=mode,
                        hosts=hosts, ports=ports, groupId=group)
                    client = transport.Local(packaged, cfg); started = client.start(min(deadline, time.monotonic()+30))
                    m.need(started['state'] == 'LAUNCHED', 'guest startup claim'); services.append((client, started['pid']))
                    until = min(deadline, time.monotonic()+30)
                    while True:
                        observed = client.ready(until)
                        if observed['ready'] is not None:
                            m.need(observed['ready']['pid'] == started['pid'] and observed['ready']['configSha256'] == m.sha(m.canonical(cfg)), 'guest ready identity'); break
                        m.need(time.monotonic() < until, 'guest service startup timeout'); time.sleep(.05)
                    clients.append(client)
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
            value, answer, counts = execute(active, 'window', dict(cell='healthy', preset='experiment', window='warmup'), lost=True)
            m.need(answer['state'] == 'SUCCEEDED' and counts['submits'] == 1 and counts['queries'] > 0, 'guest lost-reply window: '+str(answer))
            expected = len(schedule.windows('healthy', 'experiment')[0]['calls'])
            m.need(answer['result']['calls'] == expected, 'guest frozen warmup count')
            _, bad, _ = execute(active, 'collect', {})
            m.need(bad['state'] == 'FAILED' and 'stopped JVM' in bad['error']['message'], 'live JVM collection accepted')
            for client in clients:
                _, stopped, _ = execute(client, 'stop-voter', dict(forced=False))
                m.need(stopped['state'] == 'SUCCEEDED', 'guest clean stop: '+str(stopped))
            old = active.submit(value, min(deadline, time.monotonic()+20)); m.need(old == answer, 'terminal command was replayed')
            members = []
            for client in clients:
                _, collected, _ = execute(client, 'collect', {})
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
                exchanges = command.read(replay/(node+'-exchanges.json'))
                calls = [r for r in exchanges if r['request']['command'] == 'call']
                m.need(len(calls) == (expected if client is active else 0) and all(r['outcome'] == 'SUCCESS' for r in calls), 'guest actual call count/outcomes')
                journals = {}
                for kind in ('results', 'samples') if mode == package.MODES[0] else ('results', 'samples', 'trace'):
                    paths = sorted(replay.glob(node+'-'+kind+'*.jsonl.gz'))
                    m.need(paths, 'missing closed guest journal: '+kind)
                    # Consume gzip trailers and JSON rows; complete semantic and physical
                    # replay remains the later full integration gate.
                    count = 0
                    for path in paths:
                        with gzip.open(path, 'rb') as stream:
                            for line in stream: m.strict_json(line); count += 1
                    journals[kind] = count; m.need(count > 0, 'empty guest journal: '+kind)
                stopped = command.read(replay/(node+'-stop.json'))
                m.need(stopped['readerReaped'] and stopped['exitCode'] == 0 and not stopped['forced'], 'guest shutdown evidence')
                members.append(dict(node=node, calls=len(calls), journals=journals, collection=checked))
            row = dict(mode=mode, status='PASS', warmupCalls=expected, transport=counts, members=members)
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
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--bundle',type=Path,required=True);p.add_argument('--source',required=True)
    a=p.parse_args()
    def terminate(*_): raise TimeoutError('guest qualification terminated')
    signal.signal(signal.SIGTERM, terminate)
    run(a.output,a.bundle,a.source)
