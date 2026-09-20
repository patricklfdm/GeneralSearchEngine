"""Public JAR consumer, published V4.4 import and independently inspected JVM cuts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import struct
import tarfile
import time
import xml.etree.ElementTree as ET
from . import bootstrap_inspector as oracle, controls
from .storage_inspector import inventory
from scripts.v50 import admission_format as application_format
from scripts.v50.offline_harness import CORE, REPLICATION

ROOT=Path(__file__).resolve().parents[2]
PACKAGE='io.github.patricklfdm.generalsearch.'
CUTS=('AUTO_BOOTSTRAP_PREPARING','AUTO_BOOTSTRAP_PREPARED','AUTO_BOOTSTRAP_COMMITTING',
      'AUTO_BOOTSTRAP_COMMITTED','AUTO_SEAL_0_RENAMED')


def run(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='public-offline-bootstrap',publicRuntime=False,paidCloud=False,cases=[])
    def command(args,name,timeout=60):
        result=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=timeout,cwd=ROOT)
        (output/(name+'.stdout')).write_text(result.stdout); (output/(name+'.stderr')).write_text(result.stderr)
        oracle.f.need(result.returncode==0,f'{name} failed: {result.stderr[-2000:]}'); return result
    try:
        receipt['source']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        paths=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
        receipt['sourceInventorySha256']=oracle.sha(oracle.canonical({p:oracle.sha((ROOT/p).read_bytes()) for p in sorted(set(paths)) if p and (ROOT/p).is_file()}))
        receipt['jars']={p.name:oracle.sha(p.read_bytes()) for p in (CORE,REPLICATION)}
        module=ROOT/'general-search-engine-replication'
        oracle.f.need(all(p.stat().st_mtime_ns<=REPLICATION.stat().st_mtime_ns for p in (module/'src/main').rglob('*') if p.is_file()),'package current production sources first')
        report=module/'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.V51BootstrapTest.xml'
        suite=ET.parse(report).getroot(); oracle.f.need(int(suite.attrib['tests'])>=10 and all(int(suite.attrib.get(k,0))==0 for k in ('errors','failures','skipped')),'bootstrap Java regressions')
        oracle.f.need((module/'src/test/java/io/github/patricklfdm/generalsearch/replication/V51BootstrapTest.java').stat().st_mtime_ns<=report.stat().st_mtime_ns,'bootstrap Java report predates tests')
        receipt['javaTests']=dict(tests=int(suite.attrib['tests']),sha256=oracle.sha(report.read_bytes()))
        source=module/'src/test/java/io/github/patricklfdm/generalsearch/admission'
        consumer=output/'consumer'; consumer.mkdir(); workers=output/'workers'; workers.mkdir(); control_classes=output/'control'; control_classes.mkdir()
        jars=os.pathsep.join(map(str,(CORE,REPLICATION)))
        command(['javac','--release','21','-proc:none','-cp',jars,'-d',consumer,source/'OfflineApplication.java',source/'AutomaticOfflineConsumer.java'],'compile-consumer')
        command(['javac','--release','21','-proc:none','-cp',jars+os.pathsep+str(consumer),'-d',workers,
                 source.parent/'replication/V51BootstrapWorker.java'],'compile-worker')
        cp=os.pathsep.join(map(str,(CORE,REPLICATION,consumer,workers)))
        def args(root,action,source='-'): return ['java','-cp',cp,PACKAGE+'admission.AutomaticOfflineConsumer',root,action,source]
        def crash(root,action,cut,mode,name):
            out=output/(name+'.stdout'); err=output/(name+'.stderr')
            with out.open('w') as stdout,err.open('w') as stderr:
                proc=subprocess.Popen(list(map(str,['java','-cp',cp,PACKAGE+'replication.V51BootstrapWorker',root,action,'-',cut,mode])),stdout=stdout,stderr=stderr,cwd=ROOT)
                try:
                    deadline=time.monotonic()+45
                    while 'BARRIER ' not in out.read_text() and proc.poll() is None and time.monotonic()<deadline: time.sleep(.02)
                    oracle.f.need(f'BARRIER {proc.pid} {cut}' in out.read_text(),'missing real process barrier '+name)
                    if mode=='kill': proc.kill()
                    code=proc.wait(timeout=10); oracle.f.need(code==(-9 if mode=='kill' else 71),'unexpected crash exit')
                finally:
                    if proc.poll() is None: proc.kill(); proc.wait(timeout=10)
            before=inventory(root)
            archive=output/(name+'-pre-reopen.tar.gz')
            with tarfile.open(archive,'w:gz') as tar: tar.add(root,arcname='raw')
            with tarfile.open(archive) as tar:
                archived={m.name.removeprefix('raw/'):dict(size=m.size,sha256=oracle.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
            oracle.f.need(archived==before,'pre-reopen archive differs')
            return dict(pid=proc.pid,exitCode=code,mode=mode,cut=cut,archiveSha256=oracle.sha(archive.read_bytes()))
        healthy=output/'healthy'; healthy.mkdir(); command(args(healthy,'apply'),'healthy-apply')
        receipt['cases'].append(dict(name='empty',oracle=oracle.inspect(healthy,True)))
        # Mutate one input at a time, preserving the exact source paths; the oracle must reject each.
        negatives=0
        for relative in ('operation/operation.gsr','operation/bootstrap-binding.gsr','node-1/bootstrap-seal.gsr','node-2/genesis.gsr'):
            path=healthy/relative; original=path.read_bytes(); path.write_bytes(original[:-1])
            try:
                try: oracle.inspect(healthy,True)
                except (ValueError,KeyError,IndexError): negatives+=1
                else: raise ValueError('oracle admitted corrupted '+relative)
            finally: path.write_bytes(original)
        # A valid frame checksum must not conceal the wrong decision order.
        path=healthy/'operation/operation.gsr'; original=path.read_bytes()
        size=struct.unpack('>i',original[12:16])[0]; row=oracle.f.inspect(original[:48+size],'DECISION')
        row['state']='COMMITTING'; body=oracle.canonical(row); header=original[:12]+struct.pack('>i',len(body))
        path.write_bytes(header+bytes.fromhex(oracle.sha(header+body))+body+original[48+size:])
        try:
            try: oracle.inspect(healthy,True)
            except ValueError: negatives+=1
            else: raise ValueError('oracle admitted rechecksummed premature decision')
        finally: path.write_bytes(original)
        receipt['oracleNegatives']=negatives
        for mode in ('halt','kill'):
            for i,cut in enumerate(CUTS):
                name=f'{mode}-{i}'; root=output/name; root.mkdir(); result=crash(root,'apply',cut,mode,name)
                result['preReopen']=oracle.inspect(root)
                command(args(root,'resume'),name+'-resume'); result['oracle']=oracle.inspect(root,True)
                receipt['cases'].append(dict(name=name,**result))
            name=mode+'-cleanup'; root=output/name; root.mkdir()
            crash(root,'apply','AUTO_BOOTSTRAP_PREPARED',mode,name+'-prepared')
            result=crash(root,'cleanup','AUTO_BOOTSTRAP_CLEANUP_DELETE_2',mode,name)
            command(args(root,'cleanup'),name+'-resume')
            oracle.f.need(not (root/'operation').exists() and not any((root/f'node-{i}').exists() for i in (1,2,3)),'cleanup leftovers')
            receipt['cases'].append(dict(name=name,**result,cleanup='PASS'))
        controls.resolve(ROOT/'target/v51-controls'); control=ROOT/'target/v51-controls/general-search-engine-4.4.0.jar'
        receipt['publishedControlSha256']=oracle.sha(control.read_bytes())
        control_cp=os.pathsep.join(map(str,(control,REPLICATION,consumer,control_classes)))
        command(['javac','--release','21','-proc:none','-cp',control_cp,'-d',control_classes,
                 *[source/(n+'.java') for n in ('AdmissionJson','AdmissionSemanticModel','PublicRuntimeWorkload','AdmissionV44Control')]],'compile-v44')
        for minor in (0,1,2):
            root=output/f'import-{minor}'; root.mkdir()
            made=command(['java','-cp',control_cp,PACKAGE+'admission.AdmissionV44Control','simple-source',root,str(minor)],f'v44-{minor}')
            oracle.f.need('controlSource='+str(control) in made.stderr.splitlines(),'control loaded wrong artifact')
            expected=json.loads(made.stdout); before=inventory(root/'source')
            command(args(root,'apply',root/'source'),f'import-{minor}'); result=oracle.inspect(root,True)
            genesis=oracle.f.inspect((root/'node-1/genesis.gsr').read_bytes(),'GENESIS')
            indexes,docs=application_format.application(oracle.raw(genesis['application']))
            oracle.f.need(len(indexes)==1 and json.loads(indexes[0])==dict(analyzer='',field='value',kind='equality')
                          and docs==[(bytes.fromhex('00000003'),b'3:shared'),(bytes.fromhex('00000001'),b'1:shared')],'imported active indexes/document order/values')
            oracle.f.need(result['sequence']==expected['sequence'] and genesis['historyId']!=expected['history'] and before==inventory(root/'source'),'published V4.4 import changed source/history/sequence')
            receipt['cases'].append(dict(name=f'published-v44-{minor}',oracle=result))
        receipt['status']='PASS'
    except Exception as error:
        receipt['error']=dict(type=type(error).__name__,message=str(error)); raise
    finally: (output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('output'); args=parser.parse_args(); result=run(args.output)
    print(json.dumps(dict(status=result['status'],cases=len(result['cases']),execution=result['execution'],publicRuntime=False)))
