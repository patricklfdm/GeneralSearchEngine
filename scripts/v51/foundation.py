"""One evidence-bound foundation gate; no runtime execution or paid cloud."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from . import cloud_plan, controls, explore, fixtures, process_harness, performance_foundation

ROOT=Path(__file__).resolve().parents[2]


def command(args,log):
    with log.open('wb') as output:
        result=subprocess.run(args,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,timeout=120)
    if result.returncode:raise ValueError(f'command failed ({result.returncode}); see {log}')


def artifact(path):
    if not path.is_file() or path.is_symlink():raise ValueError('missing artifact '+str(path))
    with zipfile.ZipFile(path) as jar:
        if b'Implementation-Version: 5.1.0-SNAPSHOT' not in jar.read('META-INF/MANIFEST.MF'):raise ValueError('stale artifact version')
        if any('/V51' in n or 'scripts/v51/' in n or 'replication/v51/' in n or 'fixture/v51/' in n for n in jar.namelist()):raise ValueError('foundation fixture leaked into product')
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def run(output,control_directory):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    changed=subprocess.check_output(['git','diff','--binary','HEAD'],cwd=ROOT)
    (output/'source.diff').write_bytes(changed)
    extra=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
    untracked={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in extra if (ROOT/p).is_file()}
    record=dict(schema='gse-v51-foundation-receipt-v1',source=source,diffSha256=hashlib.sha256(changed).hexdigest(),
                untrackedSha256=untracked,execution='independent-foundation-only',runtimeExecuted=False,paidCloud=False,status='FAIL')
    try:
        ns={'m':'http://maven.apache.org/POM/4.0.0'}
        for p in ['pom.xml','general-search-engine-replication/pom.xml','general-search-engine-processor/pom.xml','reactor/pom.xml','examples/travel-search/pom.xml']:
            if ET.parse(ROOT/p).getroot().findtext('m:version',namespaces=ns)!='5.1.0-SNAPSHOT':raise ValueError('version '+p)
        for p in ROOT.glob('compatibility/v*-style-consumer/pom.xml'):
            if ET.parse(p).getroot().findtext('m:properties/m:gse.version',namespaces=ns)!='5.1.0-SNAPSHOT':raise ValueError('consumer version '+str(p))
        record['formats']=fixtures.validate()
        record['model']=explore.run(output/'model')
        process=process_harness.run(output/'process')
        record['process']=dict(status=process['status'],cases=len(process['cases']),execution=process['execution'])
        record['cloud']=cloud_plan.qualify(source)
        (output/'fake-cloud.json').write_text(json.dumps(record['cloud'],indent=2)+'\n')
        record['controls']=controls.resolve(control_directory)
        published=Path(control_directory).resolve()
        core=ROOT/'target/general-search-engine-5.1.0-SNAPSHOT.jar'
        replication=ROOT/'general-search-engine-replication/target/general-search-engine-replication-5.1.0-SNAPSHOT.jar'
        record['artifacts']=[artifact(core),artifact(replication)]
        record['richWorkload']=performance_foundation.run(output/'rich-workload',control_directory,core)
        classes=output/'consumer-classes';classes.mkdir()
        classpath=str(core)+':'+str(replication)
        java=ROOT/'scripts/v51/java'
        command(['javac','-cp',classpath,'-d',str(classes),str(java/'AutomaticConsumer.java'),str(java/'PublishedApiCheck.java')],output/'consumer-compile.log')
        command(['java','-cp',str(classes)+':'+classpath,'fixture.v51.AutomaticConsumer',str(output/'guard')],output/'consumer.log')
        command(['java','-cp',str(classes),'fixture.v51.PublishedApiCheck',str(published/'general-search-engine-5.0.0.jar'),
                 str(published/'general-search-engine-replication-5.0.0.jar'),str(core),str(replication)],output/'published-api.log')
        legacy=output/'legacy-classes';legacy.mkdir()
        old_cp=str(published/'general-search-engine-5.0.0.jar')+':'+str(published/'general-search-engine-replication-5.0.0.jar')
        legacy_source=ROOT/'compatibility/v5-style-consumer/src/main/java/fixture'
        command(['javac','-cp',old_cp,'-d',str(legacy),str(legacy_source/'V5StyleConsumer.java'),str(legacy_source/'V5Document.java'),str(java/'LegacyRunner.java')],output/'legacy-compile.log')
        command(['java','-cp',str(legacy)+':'+classpath,'fixture.v51.LegacyRunner',str(output/'legacy-no-io')],output/'legacy.log')
        record['publicConsumer']={'status':'PASS','stoppedHandle':'executed','offlineBootstrap':'executed','fullLifecycle':'compile-only','legacyBinary':'published-5.0-to-current'}
        record['status']='PASS'
    except Exception as error:
        record['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        (output/'receipt.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--controls',type=Path,default=ROOT/'target/v51-controls');a=p.parse_args()
    r=run(a.output,a.controls);print(json.dumps({k:r[k] for k in ('status','execution','runtimeExecuted','paidCloud')}))
