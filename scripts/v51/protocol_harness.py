"""Fresh JVM kernel scenarios with real stores and independent causal evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from . import protocol_evidence as oracle, storage_inspector as storage
from .storage_harness import ROOT, need, save

SCENARIOS=('healthy','entry-chosen','hidden-proof','fenced','retry','restart')


def run(output):
    from scripts.v50.offline_harness import CORE, REPLICATION
    output=Path(output).resolve();need(not output.exists(),'fresh protocol evidence required');output.mkdir(parents=True)
    module=ROOT/'general-search-engine-replication';jars=[CORE,REPLICATION]
    need(all(j.is_file() for j in jars),'package current reactor first')
    for source in (module/'src/main').rglob('*.java'):
        need(source.stat().st_mtime_ns<=REPLICATION.stat().st_mtime_ns,'production JAR predates sources')
    report=module/'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.V51AutomaticProtocolTest.xml'
    suite=ET.parse(report).getroot();need(int(suite.attrib['tests'])>=21 and all(int(suite.attrib.get(k,0))==0 for k in ('failures','errors','skipped')),'protocol regression suite required')
    files=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    receipt=dict(schema='gse-v51-protocol-evidence-v1',status='RUNNING',execution='automatic-transition-kernel-only',publicRuntime=False,
                 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 sourceInventorySha256=storage.sha(storage.canonical({p:storage.sha((ROOT/p).read_bytes()) for p in sorted(set(files)) if p and (ROOT/p).is_file()})),
                 jars={j.name:storage.sha(j.read_bytes()) for j in jars},javaTests=int(suite.attrib['tests']),javaReportSha256=storage.sha(report.read_bytes()),cases=[])
    cp=os.pathsep.join(map(str,[*jars,module/'target/test-classes']))
    try:
        for scenario in SCENARIOS:
            root=output/scenario;command=['java','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V51ProtocolWorker',str(root),scenario]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120)
            (output/(scenario+'.stdout')).write_bytes(result.stdout);(output/(scenario+'.stderr')).write_bytes(result.stderr)
            need(result.returncode==0,scenario+': '+result.stderr.decode(errors='replace')[-2000:])
            checked=oracle.validate(root);receipt['cases'].append(checked);print(json.dumps(checked),flush=True)
        receipt['negatives']=oracle.negatives(output/'healthy');receipt['status']='PASS'
    finally:save(output/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');args=parser.parse_args();run(args.output)
