"""Artifact-bound V5.1 release preparation; no candidate freeze or publication."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from . import controls, native_set_review, remote_command as c, performance_model as m

ROOT = Path(__file__).resolve().parents[2]
NS = {'m': 'http://maven.apache.org/POM/4.0.0'}
ARTIFACTS = ('general-search-engine', 'general-search-engine-processor', 'general-search-engine-replication')


def version(root=ROOT):
    current = ET.parse(root/'pom.xml').getroot().findtext('m:version', namespaces=NS)
    m.need(current in ('5.1.0-SNAPSHOT', '5.1.0'), 'V5.1 preparation version')
    return current


def artifact_inventory(root, current):
    result = {}
    for artifact in ARTIFACTS:
        directory = root/'target' if artifact == ARTIFACTS[0] else root/artifact/'target'
        for suffix in ('', '-sources', '-javadoc'):
            path = directory/f'{artifact}-{current}{suffix}.jar'
            m.need(path.is_file() and not path.is_symlink(), 'missing preparation artifact: '+path.name)
            with zipfile.ZipFile(path) as jar:
                names = jar.namelist()
                m.need(len(names) == len(set(names)), 'duplicate JAR member')
                if not suffix:
                    manifest = jar.read('META-INF/MANIFEST.MF').decode().replace('\r', '')
                    m.need(re.findall(r'^Implementation-Version: (.+)$', manifest, re.M) == [current],
                           'preparation artifact version')
                m.need(not any(re.search(r'(^|/)(fixture|admission)/|/replication/v51/', name)
                               for name in names), 'preparation test asset leak')
            result[path.name] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(), bytes=path.stat().st_size)
    return result


def command(args, output):
    with output.open('xb') as log:
        result = subprocess.run([str(v) for v in args], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    m.need(result.returncode == 0, 'release preparation command failed; see '+str(output))


def run(output, control_directory):
    output = Path(output).absolute(); output.mkdir(parents=True, exist_ok=False)
    record = dict(schema='gse-v51-release-preparation-v1', status='FAIL', execution='offline-release-preparation',
                  candidateFrozen=False, publication=False, paidCloud=False)
    try:
        current = version(); record['version'] = current
        record['artifacts'] = artifact_inventory(ROOT, current)
        docs = ROOT/'docs/v5x/v5.1'
        baseline = native_set_review.entry(c.read(docs/'phase6-cloud-review.json'))
        m.need(c.read(docs/'cloud-benchmark-baselines.json') ==
               dict(schema=native_set_review.REGISTRY_SCHEMA, baselines=[baseline]), 'release preparation baseline')
        record['cloudBaseline'] = baseline
        record['controls'] = controls.resolve(control_directory)
        command(['java', '-version'], output/'java-version.log')
        command(['javac', '-version'], output/'javac-version.log')
        record['toolchain'] = {name: (output/(name+'-version.log')).read_text().strip()
                               for name in ('java', 'javac')}
        published = Path(control_directory).absolute()
        core = ROOT/'target'/f'{ARTIFACTS[0]}-{current}.jar'
        replication = ROOT/ARTIFACTS[2]/'target'/f'{ARTIFACTS[2]}-{current}.jar'
        classes = output/'api-classes'; classes.mkdir()
        helper = ROOT/'scripts/v51/java'
        command(['javac', '-d', classes, helper/'PublishedApiCheck.java'], output/'api-compile.log')
        command(['java', '-cp', classes, 'fixture.v51.PublishedApiCheck',
                 published/'general-search-engine-5.0.0.jar', published/'general-search-engine-replication-5.0.0.jar',
                 core, replication], output/'published-api.log')
        match = re.fullmatch(r'v51PublishedApi=PASS preservedDeclarations=(\d+) additiveDeclarations=(\d+)\s*',
                            (output/'published-api.log').read_text())
        m.need(match is not None and int(match[1]) > 0 and int(match[2]) > 0, 'release public API result')
        record['publishedApi'] = dict(preservedDeclarations=int(match[1]), additiveDeclarations=int(match[2]))
        legacy = output/'legacy-classes'; legacy.mkdir()
        old_cp = ':'.join(str(published/name) for name in
                          ('general-search-engine-5.0.0.jar', 'general-search-engine-replication-5.0.0.jar'))
        source = ROOT/'compatibility/v5-style-consumer/src/main/java/fixture'
        command(['javac', '-cp', old_cp, '-d', legacy, source/'V5Document.java', source/'V5StyleConsumer.java',
                 helper/'LegacyRunner.java'], output/'legacy-compile.log')
        command(['java', '-cp', ':'.join(map(str, (legacy, core, replication))), 'fixture.v51.LegacyRunner',
                 output/'unused-legacy-authority'], output/'legacy.log')
        m.need(not (output/'unused-legacy-authority').exists(), 'legacy stopped handle created authority')
        record['legacyBinary'] = 'compiled-with-published-5.0-run-with-current'
        m.need(record['artifacts'] == artifact_inventory(ROOT, current), 'artifacts changed during preparation')
        record['status'] = 'PASS'
    except Exception as error:
        record['failure'] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        c.write_once(output/'receipt.json', record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controls', type=Path, default=ROOT/'target/v51-published-controls')
    args = parser.parse_args(); result = run(args.output, args.controls)
    print(m.canonical({k: result[k] for k in ('status', 'version', 'publishedApi', 'candidateFrozen')}).decode())


if __name__ == '__main__': main()
