"""Source-bound declaration/disabled consumer/model gate. No automatic read runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zipfile
import xml.etree.ElementTree as ET
from scripts import ci_v51_bundle as build
from scripts.build_coordinates import current
from . import controls,evidence,model

ROOT=Path(__file__).resolve().parents[2]


def command(args,log,expected=0):
    result=subprocess.run([str(v) for v in args],cwd=ROOT,capture_output=True,timeout=120)
    log.write_bytes(result.stdout+result.stderr)
    if (result.returncode==0)!=(expected==0):raise ValueError('command exit '+str(result.returncode)+': '+str(log))
    return result


def run(output):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    record=dict(schema='gse-v52-foundation-receipt-v1',status='FAIL',runtimeReadsEnabled=False,paidCloud=False)
    try:
        source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        record['build']=build.binding(ROOT,source)
        record['run']=os.environ.get('GITHUB_RUN_ID','local');record['attempt']=int(os.environ.get('GITHUB_RUN_ATTEMPT','1'))
        record['dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT))
        version=current();core=ROOT/f'target/general-search-engine-{version}.jar'
        repl=ROOT/f'general-search-engine-replication/target/general-search-engine-replication-{version}.jar'
        for jar,module in ((core,ROOT),(repl,ROOT/'general-search-engine-replication')):
            inputs=[module/'pom.xml',*(module/'src/main').rglob('*')]
            build.need(jar.is_file() and not jar.is_symlink() and
                all(p.stat().st_mtime_ns<=jar.stat().st_mtime_ns for p in inputs if p.is_file()),'stale candidate build: '+jar.name)
        record['artifacts']={p.name:evidence.digest(p.read_bytes()) for p in (core,repl)}
        record['javaTests']={}
        for name in ('V52ReadTokenTest','V52PublicApiInventoryTest','V51PublicApiInventoryTest'):
            p=ROOT/build.REPORTS/f'TEST-io.github.patricklfdm.generalsearch.replication.{name}.xml'
            xml=ET.parse(p).getroot()
            build.need(int(xml.attrib['tests'])>0 and all(int(xml.attrib.get(k,'0'))==0 for k in ('errors','failures','skipped')),'required test '+name)
            record['javaTests'][name]=dict(tests=int(xml.attrib['tests']),sha256=evidence.digest(p.read_bytes()))
        record['controls']=controls.resolve(ROOT/'target/v52-controls')
        oldcp=os.pathsep.join(str(ROOT/'target/v52-controls'/f'{a}-5.1.0.jar') for a in ('general-search-engine','general-search-engine-replication'))
        cp=os.pathsep.join(map(str,(core,repl)));legacy=out/'legacy';legacy.mkdir();classes=out/'consumer';classes.mkdir()
        java=ROOT/'scripts/v52/java'
        command(['javac','-cp',oldcp,'-d',legacy,java/'LegacyGenerator.java'],out/'legacy-generator-compile.log')
        command(['java','-cp',str(legacy)+os.pathsep+oldcp,'fixture.v52.LegacyGenerator',legacy/'LegacyAutomatic.java'],out/'legacy-generator.log')
        command(['javac','-cp',oldcp,'-d',legacy,legacy/'LegacyAutomatic.java'],out/'legacy-compile.log')
        sources=sorted((ROOT/'compatibility/v52-style-consumer/src/main/java/fixture').glob('*.java'))
        command(['javac','-cp',cp,'-d',classes,*sources,java/'ReadConsumer.java',ROOT/'scripts/v51/java/PublishedApiCheck.java'],out/'consumer-compile.log')
        command(['java','-cp',str(classes)+os.pathsep+str(legacy)+os.pathsep+cp,'fixture.v52.ReadConsumer',out/'no-io'],out/'consumer.log')
        oldjars=[ROOT/'target/v52-controls'/f'{a}-5.1.0.jar' for a in ('general-search-engine','general-search-engine-replication')]
        command(['java','-cp',classes,'fixture.v51.PublishedApiCheck',*oldjars,core,repl],out/'published-api.log')
        record['consumer']=dict(status='PASS',legacyBinary='published-5.1-to-current',surface='seven-methods-compile-only',explicitRead='disabled')
        negative=[]
        for name,expression in [('paging','v.search((io.github.patricklfdm.generalsearch.search.SearchPageRequest<Object>)null)'),('mutation','v.add(new Object())')]:
            path=out/(name.capitalize()+'.java')
            path.write_text('import io.github.patricklfdm.generalsearch.replication.*; class '+name.capitalize()+' {void call(ReplicaReadView<Integer,Object> v) {'+expression+';}}')
            result=command(['javac','-cp',cp,'-d',classes,path],out/(name+'-compile.log'),expected=1)
            build.need(b'cannot find symbol' in result.stderr or b'no suitable method' in result.stderr,'unrelated negative compiler failure')
            negative.append(dict(case=name,status='REJECTED'))
        record['compileNegatives']=negative
        record['model']=model.run(out/'model.json')
        binding=dict(source=source,tree=record['build']['checkoutSha256'],artifacts=record['artifacts'],run=record['run'],attempt=record['attempt'],
                     process='synthetic-node-1-g1',seed=52,codec='synthetic-v1')
        raw=out/'synthetic';evidence.save(raw,evidence.fixture(binding));record['negatives']=evidence.negatives(raw,binding)
        archive=out/'synthetic.zip'
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for path in sorted(raw.iterdir()):z.write(path,path.name)
        relocated=out/'relocated';relocated.mkdir()
        with zipfile.ZipFile(archive) as z:
            build.need(set(z.namelist())=={'history.json','inventory.json'},'synthetic archive inventory')
            for name in z.namelist():(relocated/name).write_bytes(z.read(name))
        build.need(evidence.negatives(relocated,binding,str(raw))==record['negatives'],'relocation negative drift')
        record['syntheticBinding']=binding;record['status']='PASS'
    except Exception as error:
        record['error']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        record['elapsedSeconds']=round(time.monotonic()-started,3)
        record['origin']=str(out)
        record['files']={str(p.relative_to(out)):dict(bytes=p.stat().st_size,sha256=evidence.digest(p.read_bytes()))
                         for p in sorted(out.rglob('*')) if p.is_file() and p.name!='receipt.json'}
        (out/'receipt.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    r=run(a.output);print(json.dumps({k:r[k] for k in ('status','runtimeReadsEnabled','paidCloud')}))
