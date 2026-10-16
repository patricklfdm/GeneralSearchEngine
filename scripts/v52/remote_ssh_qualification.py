"""One real local engine history controlled through pinned OpenSSH channels."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import signal
import tempfile
import time
import uuid
from scripts.v51.guest_ssh_qualification import Server
from scripts.v51.guest_transport import ProcessError
from . import remote_host as host,remote_ssh as ssh,remote_command as c,remote_slots as slots
from . import remote_owned_history as owned,measurement_bundle as bundle,cloud_suite as suite
from .evidence import need


def run(output):
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False,mode=0o700);source=owned.source()
    receipt=dict(status='FAIL',execution='loopback-openssh-history-only',sourceBinding=source,
                 syntheticSelection=True,qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False,
                 executionRequested=False,engineWorkloadExecuted=False,cases=[])
    endpoint=None;executor=None
    try:
        # Keys and control sockets never enter the retained artifact directory.
        # sshd StrictModes also checks ancestors of AuthorizedKeysFile: /tmp's
        # world-writable ancestor is unsuitable even when its child is 0700.
        with tempfile.TemporaryDirectory(prefix='v52-ssh-keys-',dir=host.ROOT/'target') as private,Server(private,root) as server:
            alias='gse-v52-'+uuid.uuid4().hex;known=Path(private)/'v52-known'
            known.write_text(alias+' '+server.host['publicKey']+'\n');known.chmod(0o600)
            target=dict(host='127.0.0.1',port=server.port,user=server.user,key=str(Path(private)/'client/identity'),knownHosts=str(known),alias=alias)
            receipt.update(tools=server.versions,hostKeySha256=host.digest(server.host['publicKey'].encode()))
            endpoint=ssh.Endpoint(target,host.ROOT);pin=endpoint.probe(root,time.monotonic()+30)
            fixture=dict(source=source['source'],checkoutSha256=source['checkoutSha256'],sequence=uuid.uuid4().hex,
                         suiteSha256=suite.PLAN_SHA,programSha256=suite.model.PLAN_SHA,buildManifestSha256='0'*64,
                         packageSha256='0'*64,controlsManifestSha256=suite.load()['controlsManifestSha256'])
            selected=suite.selection(fixture,'experiment',uuid.uuid4().hex)
            owner=c.binding(selected,'candidate-minimum-untimed-smoke','node-1',pin['bootId'],uuid.uuid4().hex)
            config=host.config(owner,root/'guest',pin);endpoint.bind(config)
            need(endpoint.prepare(time.monotonic()+30)==dict(state='PREPARED_NOT_EXECUTED'),'SSH preparation failed')
            receipt['configSha256']=host.sha(config);receipt['observedHost']=pin
            for label,code in (('host','HOST_CHANGED'),('source','SOURCE_CHANGED')):
                bad=deepcopy(config);bad['root']=str(root/('rejected-'+label))
                if label=='host':bad['host']['parentInode']+=1
                else:bad['owner']['selection']['binding']['checkoutSha256']='0'*64
                probe=ssh.Endpoint(target,host.ROOT)
                try:
                    probe.bind(bad)
                    try:probe.prepare(time.monotonic()+30)
                    except ssh.Rejected as error:need(error.code==code,'SSH wrong rejection category')
                    else:raise ValueError('SSH changed identity accepted')
                    need(not Path(bad['root']).exists(),'SSH rejected preparation wrote state')
                finally:probe.close()
                receipt['cases'].append(dict(case=label+'-drift',status='PASS',code=code))
            wrong=Path(private)/'wrong-known';wrong.write_text(alias+' '+server.access['publicKey']+'\n');wrong.chmod(0o600)
            for label,bad_target,code in (
                ('host-key',dict(target,knownHosts=str(wrong)),'SSH_HOST_KEY'),
                ('authentication',dict(target,key=str(Path(private)/'host/identity')),'SSH_AUTHENTICATION')):
                probe=ssh.Endpoint(bad_target,host.ROOT)
                try:
                    try:probe.probe(root,time.monotonic()+30)
                    except ProcessError as error:need(error.code==code and not error.retryable,'SSH wrong permanent category')
                    else:raise ValueError('SSH untrusted connection accepted')
                finally:probe.close()
                receipt['cases'].append(dict(case=label,status='PASS',code=code))
            value=slots.request(owner,'execute-history');last_report=time.monotonic();began=last_report
            class LostReply:
                submits=0
                queries=0
                def submit(self,request,deadline):
                    self.submits+=1;receipt.update(executionRequested=True,engineWorkloadExecuted=None)
                    endpoint.submit(request,deadline);endpoint.disconnect()
                    raise ConnectionError('qualification dropped original submit response')
                def query(self,request,deadline):
                    nonlocal last_report
                    self.queries+=1;answer=endpoint.query(request,deadline)
                    if time.monotonic()-last_report>=60:
                        last_report=time.monotonic();print(json.dumps(dict(stage='observe-original-ssh-history',state=answer['state'],
                            elapsedSeconds=round(last_report-began,1),submits=self.submits,queries=self.queries)),flush=True)
                    return answer
            transport=LostReply();warnings=[]
            result=c.submit_and_observe(transport,value,owner,warn=lambda:warnings.append('soft-time-budget'))
            need(result['state']=='SUCCEEDED' and transport.submits==1,'SSH original history failed')
            physical=root/'guest/store/history-result.json';history=c.read(physical,c.RESPONSE_BYTES)
            need(history['status']=='PASS' and result['result']['resultSha256']==bundle.sha_file(physical) and
                 (history['originalReads'],history['originalUpdates'])==(11,3),'SSH original physical history binding')
            launch_sha=bundle.sha_file(root/'guest/launch.json');result_sha=bundle.sha_file(physical)
            endpoint.disconnect();duplicate=endpoint.submit(value,time.monotonic()+30)
            need(duplicate==result and launch_sha==bundle.sha_file(root/'guest/launch.json') and result_sha==bundle.sha_file(physical),
                 'SSH duplicate changed original history')
            endpoint.prepare(time.monotonic()+30)
            need(endpoint.query(value,time.monotonic()+30)==result,'SSH repeated preparation erased original result')
            alternate=dict(value,commandId=('0' if value['commandId'][0]!='0' else '1')+value['commandId'][1:])
            try:endpoint.submit(alternate,time.monotonic()+30)
            except ValueError:pass
            else:raise ValueError('SSH alternate command identity accepted')
            until=time.monotonic()+10
            while True:
                state=endpoint.inspect(time.monotonic()+30)
                if state['exited'] is not None and not state['alive']:break
                need(time.monotonic()<until,'SSH original executor did not exit');time.sleep(.1)
            executor=state['executor']['process'];need(state['exited']['state']=='SUCCEEDED','SSH executor exit failed')
            processes=c.read(root/'guest/store/history/evidence/processes.json')
            need(len(processes)==3 and all(p['exitCode']==0 for p in processes),'SSH original JVM cleanup')
            need(len(list((root/'guest/store/commands').iterdir()))==1,'SSH duplicate created another claim')
            receipt['cases'].extend(dict(case=name,status='PASS') for name in
                ('lost-submit-response','fresh-connection-duplicate','alternate-id-rejection','prepare-after-completion','original-process-exit'))
            receipt.update(status='PASS',engineWorkloadExecuted=True,submits=1,queries=transport.queries,connections=endpoint.connections,warnings=warnings,
                originalReads=11,originalUpdates=3,negativesPerLocation=len(history['result']['negatives']),
                resultSha256=result_sha,launchSha256=launch_sha,commandResult=result,executor=executor,
                elapsedSeconds=round(time.monotonic()-began,3),originalJvmCount=3)
            need(owned.source()==source,'SSH qualification source changed')
    except BaseException as error:receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        if endpoint is not None:endpoint.close()
        # Qualification-only cleanup: inspect the exact locally created session,
        # never kill a PID from an unverified remote reply or another boot.
        path=root/'guest/executor.json';forced=False
        try:
            if path.exists():
                record=c.read(path);need(record['configSha256']==receipt['configSha256'],'SSH cleanup configuration changed')
                identity=record['process'];c.validate_process(identity,owner)
                if c.process_alive(identity):
                    need(os.getpgid(identity['pid'])==identity['pid'],'SSH cleanup original session changed')
                    os.killpg(identity['pid'],signal.SIGKILL);forced=True
                    until=time.monotonic()+5
                    while c.process_alive(identity) and time.monotonic()<until:time.sleep(.05)
                    need(not c.process_alive(identity),'SSH cleanup original executor remains active')
        except Exception as error:
            receipt.update(status='FAIL',cleanupFailure=dict(type=type(error).__name__,message=str(error)))
        receipt['forcedExecutorCleanup']=forced
        if forced:receipt['status']='FAIL'
        c.write_once(root/'receipt.json',receipt)
    need(receipt['status']=='PASS','SSH qualification cleanup failed');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();print(json.dumps(run(a.output)),flush=True)
