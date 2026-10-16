"""One detached local receiver history under a stable command claim; no GCP."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
from . import remote_command as commands,remote_slots as slots,remote_runtime_qualification as bridge
from . import cloud_suite as suite,measurement_runtime as runtime,measurement_bundle as bundle
from .evidence import need

ROOT=Path(__file__).resolve().parents[2]


def source():
    return runtime.build.binding(ROOT,subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())


def validate_local_owner(owner,expected):
    commands.validate_binding(owner)
    selection=owner['selection'];bound=selection['binding']
    need(all(bound[k]==expected[k] for k in ('source','checkoutSha256')),'owned local history source drift')
    profile=selection['member']['profiles'][owner['history']]
    need(selection['member']['name']=='experiment' and profile['family']=='UNTIMED' and profile['measurement'] is False,
         'owned local history only supports untimed qualification')
    need(owner['node']=='node-1','owned local history coordinator')
    return profile['mode']


def execute_local(root,value):
    root=commands.directory(root);owner=commands.read(root/'binding.json',commands.REQUEST_BYTES)
    store=commands.CommandStore(root,owner);slots.validate(value,owner)
    need(value['command']=='execute-history','owned local history command')
    expected=source();mode=validate_local_owner(owner,expected)
    def handler(kind,payload,checkpoint):
        checkpoint()
        result=bridge.smoke(root/'history',mode,expected)
        need(source()==expected,'owned local history source changed during execution')
        commands.write_once(root/'history-result.json',result,commands.RESPONSE_BYTES)
        # Cancellation preserves this original result; it cannot cause a new history.
        return dict(status='PASS',execution='local-receiver-history-only',resultSha256=bundle.sha_file(root/'history-result.json'),
                    mode=mode,history=owner['history'],reads=result['result']['reads'],updates=result['result']['updates'],
                    qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
    return slots.execute(store,value,handler)


def run(output):
    root=Path(output).resolve();root.mkdir(parents=True,exist_ok=False)
    original=source();children=[];streams=[];started=time.time()
    receipt=dict(schema='gse-v52-owned-history-qualification-v1',status='FAIL',sourceBinding=original,
                 execution='local-detached-receiver-history-only',syntheticSelection=True,qualifiedMeasurement=False,
                 fullRemoteQualification=False,paidCloud=False,engineWorkloadExecuted=False,executionRequested=False)
    try:
        # This proves the local control path. Physical artifact identity is retained
        # by bridge.smoke; these zero selection fields grant no package admission.
        fixture=dict(source=original['source'],checkoutSha256=original['checkoutSha256'],sequence=uuid.uuid4().hex,
                     suiteSha256=suite.PLAN_SHA,programSha256=suite.model.PLAN_SHA,buildManifestSha256='0'*64,
                     packageSha256='0'*64,controlsManifestSha256=suite.load()['controlsManifestSha256'])
        selected=suite.selection(fixture,'experiment',uuid.uuid4().hex)
        history='candidate-minimum-untimed-smoke'
        owner=commands.binding(selected,history,'node-1',commands.boot_id(),uuid.uuid4().hex)
        store=commands.CommandStore(root/'guest',owner,create=True);value=slots.request(owner,'execute-history')
        def spawn(request,label):
            path=root/(label+'.request.json');commands.write_once(path,request,commands.REQUEST_BYTES)
            stdout=(root/(label+'.stdout')).open('xb');stderr=(root/(label+'.stderr')).open('xb');streams.extend((stdout,stderr))
            child=subprocess.Popen([sys.executable,'-m','scripts.v52.remote_owned_history','--worker',store.root,'--request',path],
                                   cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True)
            children.append(child);return child
        warnings=[]
        class LostConnection:
            submits=0
            queries=0
            def submit(self,request,deadline):
                self.submits+=1
                receipt.update(executionRequested=True,engineWorkloadExecuted=None)
                spawn(request,'original');raise ConnectionError('lost initial submit response')
            def query(self,request,deadline):self.queries+=1;return store.query(request)
        transport=LostConnection()
        result=commands.submit_and_observe(transport,value,owner,warn=lambda:warnings.append(dict(at=time.time(),kind='soft-time-budget')))
        need(result['state']=='SUCCEEDED','owned local history failed: '+json.dumps(result))
        need(transport.submits==1,'owned local history resubmitted')
        physical_path=store.root/'history-result.json';physical=commands.read(physical_path,commands.RESPONSE_BYTES)
        need(result['result']['resultSha256']==bundle.sha_file(physical_path) and physical['status']=='PASS','owned local result binding')
        before=bundle.sha_file(physical_path);topology=bundle.sha_file(store.root/'history/evidence/remote-topology.json')
        duplicate=spawn(value,'duplicate');need(duplicate.wait(timeout=10)==0,'owned duplicate process failed')
        repeated=commands.read(root/'duplicate.request.reply.json')
        need(repeated==result and bundle.sha_file(physical_path)==before and
             bundle.sha_file(store.root/'history/evidence/remote-topology.json')==topology,'owned duplicate changed original history')
        need(len(list((store.root/'commands').iterdir()))==1,'owned duplicate created another claim')
        # The semantic identity gate rejects a fresh ID for the same history too.
        alternate=('0' if value['commandId'][0]!='0' else '1')+value['commandId'][1:]
        try:slots.execute(store,dict(value,commandId=alternate),lambda *a:need(False,'unexpected history replay'))
        except ValueError as error:need(str(error)=='remote changed semantic command identity','unrelated fresh-ID rejection')
        else:raise ValueError('owned history accepted alternate command ID')
        processes=commands.read(store.root/'history/evidence/processes.json',64<<10)
        need(len(processes)==3 and all(p['exitCode']==0 for p in processes),'owned original JVM cleanup')
        need(source()==original,'owned qualification final source drift')
        receipt.update(status='PASS',engineWorkloadExecuted=True,submits=1,queries=transport.queries,warnings=warnings,
                       duplicateReceiptEqual=True,alternateCommandIdRejected=True,originalJvmCount=3,
                       originalReads=physical['result']['reads'],originalUpdates=physical['result']['updates'],
                       negativesPerLocation=len(physical['result']['negatives']),resultSha256=before,
                       archiveSha256=physical['archiveSha256'],commandResult=result)
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        cleanup=[]
        for child in children:
            interrupted=False
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                interrupted=True;child.send_signal(signal.SIGINT)
                try:child.wait(timeout=45)
                except subprocess.TimeoutExpired:
                    # Only a still-owned child session can reach this fallback.
                    if child.poll() is None:os.killpg(child.pid,signal.SIGKILL)
                    child.wait(timeout=5)
            cleanup.append(dict(pid=child.pid,exitCode=child.returncode,reaped=True,interruptedCleanup=interrupted))
        for stream in streams:stream.close()
        receipt['processCleanup']=cleanup;receipt['elapsedSeconds']=round(time.time()-started,3)
        if any(p['interruptedCleanup'] or p['exitCode']!=0 for p in cleanup):receipt['status']='FAIL'
        commands.write_once(root/'receipt.json',receipt)
    need(receipt['status']=='PASS','owned history cleanup failed');return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',nargs='?');p.add_argument('--worker');p.add_argument('--request');a=p.parse_args()
    if a.worker:
        need(a.request and not a.output,'owned worker arguments')
        value=commands.read(a.request,commands.REQUEST_BYTES)
        commands.write_once(Path(a.request).with_suffix('.reply.json'),execute_local(a.worker,value))
    else:
        need(a.output and not a.request,'owned qualification arguments');run(a.output)
