"""Source-bound public declaration scaffold; never claims an enabled runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
import zipfile

from scripts.build_coordinates import current
from scripts.ci_v51_bundle import binding

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 'gse-v53-declaration-foundation-v1'
JARS = ('target/general-search-engine-5.3.0-SNAPSHOT.jar',
        'general-search-engine-replication/target/general-search-engine-replication-5.3.0-SNAPSHOT.jar')


def need(value, message):
    if not value: raise ValueError(message)


def digest(data): return hashlib.sha256(data).hexdigest()
def save(path, value): path.write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')


def jar(path, role):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 * 1024 * 1024, 'missing/linked/oversized JAR')
    module = ROOT if role == 'core' else ROOT/'general-search-engine-replication'
    sources = [module/'pom.xml', *sorted((module/'src/main').rglob('*'))]
    need(all(p.stat().st_mtime_ns <= path.stat().st_mtime_ns for p in sources if p.is_file()), 'stale JAR')
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        need(len(names) == len(set(names)), 'duplicate JAR member')
        manifest = archive.read('META-INF/MANIFEST.MF').decode('utf-8')
        need('Implementation-Version: 5.3.0-SNAPSHOT' in manifest.splitlines(), 'JAR coordinate')
        expected = 'io/github/patricklfdm/generalsearch/' + ('engine/SearchEngine.class' if role == 'core' else 'replication/MembershipSearchEngines.class')
        need(expected in names, 'JAR role')
    return dict(path=str(path.relative_to(ROOT)), sha256=digest(path.read_bytes()), size=path.stat().st_size,
                sources={str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sources if p.is_file()})


def validate(receipt):
    need(receipt['schema'] == SCHEMA and receipt['status'] == 'PASS', 'foundation status')
    need(receipt['runtimeEnabled'] is False and receipt['physicalMembershipEvidence'] is False, 'scaffold promoted to runtime')
    need(receipt['source']['source'] and len(receipt['source']['checkoutSha256']) == 64, 'source binding')
    need([r['path'] for r in receipt['jars']] == list(JARS), 'JAR roles')
    need(len(receipt['cases']) == 3, 'declaration case inventory')
    for case, count in zip(receipt['cases'], (3, 4, 5)):
        need(case['members'] == count and case['exitCode'] == 0 and case['createdFiles'] == [], 'declaration process result')
        need(case['result'] == dict(status='PASS', execution='disabled-public-declarations', protocol='gse-replication/1.3', members=count, runtimeEnabled=False), 'public result')
    need(all(len(row['sha256']) == 64 and row['size'] > 0 for row in receipt['jars']), 'JAR hashes')
    return dict(status='PASS', freshProcesses=3, runtimeEnabled=False, physicalMembershipEvidence=False)


def replay(output, expected_source):
    """Portable artifact/stdio replay. This checks declarations, never runtime safety."""
    output = Path(output)
    receipt = json.loads((output/'receipt.json').read_text())
    result = validate(receipt)
    need(receipt['source'] == expected_source, 'declaration source binding')
    inventory = receipt['files']
    actual = {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}
    need(not any(p.is_symlink() for p in output.rglob('*')), 'linked declaration evidence')
    need(actual == set(inventory) | {'receipt.json', 'validation.json'}, 'declaration file inventory')
    for name, expected in inventory.items():
        path = output/name
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'declaration path')
        need(digest(path.read_bytes()) == expected, 'declaration file hash: '+name)
    for row in receipt['jars']:
        retained = output/'jars'/Path(row['path']).name
        need(retained.stat().st_size == row['size'] and digest(retained.read_bytes()) == row['sha256'], 'retained JAR identity')
    for case in receipt['cases']:
        name = 'process-'+str(case['members'])
        need(json.loads((output/(name+'.stdout')).read_text()) == case['result'], 'public stdout mismatch')
        origins = dict(line.split('=', 1) for line in (output/(name+'.stderr')).read_text().splitlines()
                       if line.startswith(('coreSource=', 'replicationSource=')))
        need(origins == receipt['originalOrigins'], 'public retained code origin')
    for name, sha in receipt['consumerClasses'].items():
        need(inventory.get('classes/'+name) == sha, 'retained consumer class')
    need(json.loads((output/'validation.json').read_text()) == result, 'declaration validation summary')
    return result


def run(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='RUNNING', runtimeEnabled=False, physicalMembershipEvidence=False, cases=[])
    started = time.monotonic()
    def command(label, args):
        result = subprocess.run(list(map(str, args)), cwd=ROOT, capture_output=True, text=True, timeout=60)
        (output/(label+'.stdout')).write_text(result.stdout); (output/(label+'.stderr')).write_text(result.stderr)
        need(result.returncode == 0, label+' failed: '+result.stderr[-3000:]); return result
    try:
        need(current() == '5.3.0-SNAPSHOT', 'V5.3 declaration coordinate')
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        receipt['source'] = binding(ROOT, source)
        receipt['jars'] = [jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))]
        (output/'jars').mkdir()
        for path in JARS: shutil.copyfile(ROOT/path, output/'jars'/Path(path).name)
        receipt['originalOrigins'] = {key: (ROOT/path).as_uri().replace('file:///', 'file:/')
                                      for key, path in zip(('coreSource', 'replicationSource'), JARS)}
        for module in ('pom.xml', 'reactor/pom.xml', 'general-search-engine-replication/pom.xml',
                       'general-search-engine-processor/pom.xml', 'examples/travel-search/pom.xml'):
            need(ET.parse(ROOT/module).getroot().findtext('{*}version') == current(), 'module coordinate: '+module)
        consumers = sorted((ROOT/'compatibility').glob('*-style-consumer/pom.xml'))
        need({p.parent.name for p in consumers} == {v+'-style-consumer' for v in ('v1', 'v2', 'v3', 'v4', 'v5', 'v51', 'v52', 'v53')}, 'consumer inventory')
        for pom in consumers: need(ET.parse(pom).getroot().findtext('{*}properties/{*}gse.version') == current(), 'consumer coordinate')
        classes = output/'classes'; classes.mkdir()
        sources = sorted((ROOT/'compatibility/v53-style-consumer/src/main/java').rglob('*.java'))
        cp = os.pathsep.join(str(ROOT/p) for p in JARS)
        command('compile-public-consumer', ['javac', '--release', '21', '-cp', cp, '-d', classes, *sources])
        receipt['consumerSources'] = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sources}
        receipt['consumerClasses'] = {str(p.relative_to(classes)): digest(p.read_bytes()) for p in sorted(classes.rglob('*.class'))}
        for count in (3, 4, 5):
            directory = output/f'absent-{count}'
            result = command(f'process-{count}', ['java', '-cp', str(classes)+os.pathsep+cp, 'fixture.V53StyleConsumer', directory, count])
            origins = dict(line.split('=', 1) for line in result.stderr.splitlines() if line.startswith(('coreSource=', 'replicationSource=')))
            need(origins == receipt['originalOrigins'], 'public process code origin')
            created = sorted(str(p.relative_to(directory)) for p in directory.rglob('*')) if directory.exists() else []
            need(not directory.exists(), 'disabled entry created storage')
            receipt['cases'].append(dict(members=count, exitCode=result.returncode, createdFiles=created, result=json.loads(result.stdout)))
        need(binding(ROOT, source) == receipt['source'], 'source changed during declaration qualification')
        need([jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))] == receipt['jars'], 'JAR changed during qualification')
        receipt['status'] = 'PASS'
        receipt['files'] = {str(p.relative_to(output)): digest(p.read_bytes()) for p in sorted(output.rglob('*')) if p.is_file()}
        save(output/'validation.json', validate(receipt)); save(output/'receipt.json', receipt)
        replay(output, receipt['source'])
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error)))
        raise
    finally:
        receipt['elapsedSeconds'] = round(time.monotonic()-started, 3); save(output/'receipt.json', receipt)
    print(json.dumps(validate(receipt), sort_keys=True)); return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args(); run(args.output)
