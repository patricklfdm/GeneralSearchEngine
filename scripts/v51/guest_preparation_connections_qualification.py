"""Real loopback SSH preparation connections; no GCP, sudo or block devices."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from . import cloud_runner_iap as iap, cloud_http as h, guest_transport as transport
from . import guest_ssh_master as ssh, guest_ssh_qualification as qualification
from . import performance_model as m, remote_command as c


def run(output):
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v51-preparation-ssh-qualification-v1',status='FAIL',cases=[],
        execution='loopback-openssh-preparation',paidCloud=False,fullRemoteQualification=False,
        realSshExecuted=True,privilegedExecution=False,realBlockDeviceWritten=False)
    try:
        # sshd needs a non-world-writable ancestry for authorized_keys. Pool
        # sockets/tokens independently live in private, short-lived /tmp paths.
        with tempfile.TemporaryDirectory(prefix='v51-preparation-keys-',dir=qualification.ROOT/'target') as private,\
             qualification.Server(private,root) as server:
            target=server.endpoint(root).target
            args=transport.ssh_args
            def loopback(target,remote,**options):
                original=args(target,remote,**options)
                original=[v if not v.startswith('ProxyCommand=') else 'ProxyCommand=none' for v in original]
                return [*original[:-2],'-o','Hostname=127.0.0.1','-p',str(server.port),*original[-2:]]
            api=SimpleNamespace(offline=False,clock=time.monotonic,deadline=time.monotonic()+90,
                gate_open=True,state='done',failed=False,
                lease=dict(resources=[dict(id=str(i),spec=dict(kind='instance')) for i in (123,456,789)]))
            api.tokens=lambda _:h.AccessToken('local-not-a-cloud-token',api.deadline+100)
            def call(remote,data=b'',**options):
                return iap._network_exchange(api,target,remote,data,api.deadline,maximum=4096,**options)
            with patch.object(transport,'ssh_args',side_effect=loopback):
                with iap.preparation_connections(api,root/'parts.json'):
                    raw=(b'bounded-package-part'*(1048576//20+1))[:1048576]
                    expected=hashlib.sha256(raw).hexdigest().encode()+b'\n'
                    for _ in range(21):
                        answer=call(['python3','-c','import sys,hashlib;print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest())'],
                                    raw,request_maximum=1<<20)
                        m.need(answer==expected,'pooled binary part mismatch')
                    master=api._preparation_connections.active['123'];pid=master.process.pid
                record=c.read(root/'parts.json');m.need(record['guests']==[dict(instanceId='123',connections=1,commands=21,failures=0)],
                    'parts did not reuse one SSH connection')
                m.need(master.process is None and not master.path.parent.parent.exists(),'master/credentials survived preparation')
                receipt['cases'].append(dict(case='21-binary-parts-one-connection',status='PASS',processId=pid))

                claim=root/'claim'
                mutate=['python3','-c','import pathlib;pathlib.Path('+repr(str(claim))+').open("x").write("once");print("done")']
                original=transport.process
                def lost(args,*rest,**options):
                    result=original(args,*rest,**options)
                    if 'open(' in args[-1]:raise ConnectionError('synthetic lost reply')
                    return result
                with iap.preparation_connections(api,root/'lost-reply.json'):
                    with patch.object(transport,'process',side_effect=lost):
                        try:call(mutate)
                        except ConnectionError:pass
                        else:raise ValueError('lost reply accepted')
                        answer=call(['python3','-c','import pathlib;print(pathlib.Path('+repr(str(claim))+').read_text())'])
                        m.need(answer==b'once\n','original claim query')
                m.need(c.read(root/'lost-reply.json')['guests']==[dict(instanceId='123',connections=2,commands=2,failures=1)],
                    'lost reply caused command replay')
                receipt['cases'].append(dict(case='lost-reply-query-only-reconnect',status='PASS'))

                with iap.preparation_connections(api,root/'missing-socket.json'):
                    call(['true']);master=api._preparation_connections.active['123'];check=master.check
                    def disappear(deadline):check(deadline);master.path.unlink()
                    with patch.object(master,'check',side_effect=disappear):
                        try:call(['touch',str(root/'must-not-exist')])
                        except ConnectionError:pass
                        else:raise ValueError('silent SSH network fallback')
                    m.need(not (root/'must-not-exist').exists(),'command executed through fallback')
                receipt['cases'].append(dict(case='socket-race-no-network-fallback',status='PASS'))

                known=Path(target['knownHosts']);saved=known.read_bytes()
                wrong=qualification.setup.generate(Path(private)/'wrong','e'*32)
                known.write_text('gse-v51-123 '+wrong['publicKey']+'\n')
                try:
                    with iap.preparation_connections(api,root/'wrong-host.json'):
                        try:call(['touch',str(root/'must-not-exist')])
                        except ConnectionError:pass
                        else:raise ValueError('wrong pinned host accepted')
                finally:known.write_bytes(saved)
                m.need(not (root/'must-not-exist').exists(),'wrong-host command executed')
                receipt['cases'].append(dict(case='wrong-host-pin-rejected',status='PASS'))

                with iap.preparation_connections(api,root/'deadline.json'):
                    call(['true']);master=api._preparation_connections.active['123']
                    try:master.exchange(['touch',str(root/'must-not-exist')],b'',time.monotonic()-1)
                    except TimeoutError:pass
                    else:raise ValueError('expired channel admitted')
                    m.need(master.process is None,'expired master not closed')
                receipt['cases'].append(dict(case='expired-channel-closes-master',status='PASS'))
            receipt['tools']=server.versions
        receipt['status']='PASS'
    finally:c.write_once(root/'receipt.json',receipt)
    print(json.dumps(dict(status=receipt['status'],cases=len(receipt['cases']),paidCloud=False)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');run(parser.parse_args().output)
