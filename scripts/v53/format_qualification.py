"""Independently decode every Java 1.3 byte fixture. Syntax evidence only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from . import format_fixture as independent
from .foundation import need, save

ROOT=Path(__file__).resolve().parents[2]


def validate_java(value):
    expected=independent.generate()['fixtures']
    need(value['schema']=='gse-v53-java-format-output-v1' and len(value['fixtures'])==45, 'Java fixture inventory')
    rows={(r['family'],r['name']):r for r in value['fixtures']}
    need(len(rows)==45 and set(rows)=={(r['family'],r['name']) for r in expected}, 'Java fixture kinds')
    for original in expected:
        row=rows[(original['family'],original['name'])]
        need(set(row)=={'family','name','hex','sha256'}, 'Java fixture fields')
        data=bytes.fromhex(row['hex'])
        need(hashlib.sha256(data).hexdigest()==row['sha256']==original['sha256'] and row['hex']==original['hex'], 'Java fixture byte drift')
        need(independent.decode(data,row['family'],row['name'])==original['value'], 'independent decode')
    return dict(status='PASS',syntaxFixtures=45,runtimeEnabled=False,authorityEvidence=False)


def run(output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-format-qualification-v1',status='RUNNING',runtimeEnabled=False,authorityEvidence=False)
    try:
        production=ROOT/'general-search-engine-replication/src/main/resources/replication/membership-format-v13.json'
        need(production.read_bytes()==independent.canonical(independent.catalog()), 'production schema drift')
        test_fixture=ROOT/'general-search-engine-replication/src/test/resources/replication/v53/byte-fixtures.json'
        need(test_fixture.read_bytes()==(ROOT/'docs/v5x/v5.3/byte-fixtures.json').read_bytes(), 'test fixture copy drift')
        cp=os.pathsep.join(str(ROOT/p) for p in ('target/general-search-engine-5.3.0-SNAPSHOT.jar',
            'general-search-engine-replication/target/general-search-engine-replication-5.3.0-SNAPSHOT.jar',
            'general-search-engine-replication/target/test-classes'))
        result=subprocess.run(['java','-cp',cp,'io.github.patricklfdm.generalsearch.replication.V53FormatWorker',str(output/'java.json')],
                              cwd=ROOT,capture_output=True,text=True,timeout=60)
        (output/'java.stdout').write_text(result.stdout);(output/'java.stderr').write_text(result.stderr)
        need(result.returncode==0,'Java byte producer: '+result.stderr[-2000:])
        validation=validate_java(json.loads((output/'java.json').read_text()));save(output/'validation.json',validation)
        receipt.update(status='PASS',syntaxFixtures=45,catalogSha256=hashlib.sha256(independent.CATALOG.read_bytes()).hexdigest(),
                       outputSha256=hashlib.sha256((output/'java.json').read_bytes()).hexdigest())
    except BaseException as error:
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:save(output/'receipt.json',receipt)
    print(json.dumps(validation));return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();run(a.output)
