"""V5.2 packaging and published compatibility, without publication or cloud execution."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from . import controls, release_baseline as b
from .evidence import digest, encoded, need, strict

ROOT = b.ROOT
ARTIFACTS = ('general-search-engine', 'general-search-engine-processor', 'general-search-engine-replication')
PACKAGE = 'io/github/patricklfdm/generalsearch/'
MARKERS = ('engine/SearchEngine', 'processor/SearchFieldsProcessor', 'replication/ReplicaReadToken')
MODULES = ('io.github.patricklfdm.generalsearch', 'io.github.patricklfdm.generalsearch.processor',
           'io.github.patricklfdm.generalsearch.replication')
SERVICE = 'META-INF/services/javax.annotation.processing.Processor'
PROCESSOR = 'io.github.patricklfdm.generalsearch.processor.SearchFieldsProcessor'


def artifact_inventory(root, version):
    result = {}
    for artifact, marker, java_module in zip(ARTIFACTS, MARKERS, MODULES):
        module = root if artifact == ARTIFACTS[0] else root/artifact
        pom = b.regular(module/'pom.xml'); xml = ET.fromstring(pom)
        need(xml.findtext('{*}artifactId') == artifact and xml.findtext('{*}version') == version and
             xml.findtext('{*}groupId') == 'io.github.patricklfdm', 'release POM coordinates')
        result[f'{artifact}-{version}.pom'] = dict(bytes=len(pom), sha256=digest(pom))
        for suffix, extension in (('', '.class'), ('-sources', '.java'), ('-javadoc', '.html')):
            path = module/'target'/f'{artifact}-{version}{suffix}.jar'; raw = b.regular(path)
            with zipfile.ZipFile(path) as jar:
                names = jar.namelist()
                need(len(names) == len(set(names)), 'duplicate JAR member')
                prefix = java_module+'/' if suffix == '-javadoc' else ''
                need(prefix+PACKAGE+marker+extension in names, 'missing packaged API: '+path.name)
                need(not any(re.search(r'(^|/)(fixture|admission|compatibility)/|/replication/v5[012]/|'
                                       r'(^|/)V5[012][^/]*(Test|Worker|Control|Fixture)[^/]*$|ReplicaNetworkFaults', n)
                             for n in names), 'release test asset leak')
                if suffix == '-sources':
                    sources = module/'src/main/java'
                    expected = {p.relative_to(sources).as_posix(): b.regular(p) for p in sources.rglob('*.java')}
                    need({n for n in names if n.endswith('.java')} == set(expected) and
                         all(jar.read(n) == raw_source for n, raw_source in expected.items()),
                         'packaged sources differ from runtime source')
                if not suffix:
                    manifest = jar.read('META-INF/MANIFEST.MF').decode().replace('\r', '')
                    need(re.findall(r'^Implementation-Version: (.+)$', manifest, re.M) == [version],
                         'release JAR version')
                    need(jar.read(f'META-INF/maven/io.github.patricklfdm/{artifact}/pom.xml') == pom,
                         'embedded POM differs from release POM')
                if SERVICE in names:
                    need(artifact == ARTIFACTS[1] and suffix != '-javadoc', 'processor service outside processor')
                    entries = [line.split('#')[0].strip() for line in jar.read(SERVICE).decode().splitlines()]
                    need([line for line in entries if line] == [PROCESSOR], 'processor service implementation')
                elif artifact == ARTIFACTS[1] and not suffix:
                    raise ValueError('processor service missing')
            result[path.name] = dict(bytes=len(raw), sha256=digest(raw))
    return result


def command(args, log):
    with log.open('xb') as output:
        result = subprocess.run(list(map(str, args)), cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    need(result.returncode == 0, 'release preparation command failed; see '+str(log))


def run(output, control_directory):
    output = Path(output).absolute(); output.mkdir(parents=True, exist_ok=False)
    record = dict(schema='gse-v52-release-preparation-v1', status='FAIL', execution='offline-release-preparation',
                  candidateFrozen=False, publication=False, paidCloud=False, rawCloudReplayed=False)
    try:
        record['cloudBaseline'] = b.check(ROOT)
        from scripts.build_coordinates import current
        version = current(ROOT)
        need(version in (b.policy(ROOT)['version'], '5.2.0'), 'release preparation version')
        record['version'] = version
        record['checkoutSource'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        record['workingTreeClean'] = not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()
        record['artifacts'] = artifact_inventory(ROOT, version)
        record['controls'] = controls.resolve(control_directory)
        command(['java', '-version'], output/'java-version.log')
        command(['javac', '-version'], output/'javac-version.log')
        record['toolchain'] = {name: (output/(name+'-version.log')).read_text().strip() for name in ('java', 'javac')}
        core = ROOT/'target'/f'{ARTIFACTS[0]}-{version}.jar'
        replication = ROOT/ARTIFACTS[2]/'target'/f'{ARTIFACTS[2]}-{version}.jar'
        published = Path(control_directory).absolute()
        old = [published/'general-search-engine-5.1.0.jar', published/'general-search-engine-replication-5.1.0.jar']
        helper = ROOT/'scripts/v52/java/release'; api = output/'api-classes'; api.mkdir()
        command(['javac', '-d', api, ROOT/'scripts/v51/java/PublishedApiCheck.java', helper/'PublishedV51ApiCheck.java'],
                output/'api-compile.log')
        command(['java', '-cp', api, 'fixture.v51.PublishedV51ApiCheck', *old, core, replication], output/'published-api.log')
        match = re.fullmatch(r'v52PublishedApi=PASS preservedDeclarations=(\d+) additiveDeclarations=(\d+)\s*',
                            (output/'published-api.log').read_text())
        need(match is not None and int(match[1]) > 0 and int(match[2]) > 0, 'published API receipt')
        record['publishedApi'] = dict(preservedDeclarations=int(match[1]), additiveDeclarations=int(match[2]))
        legacy = output/'legacy-classes'; legacy.mkdir()
        old_source = ROOT/'compatibility/v51-style-consumer/src/main/java/fixture'
        command(['javac', '-proc:none', '-cp', os.pathsep.join(map(str, old)), '-d', legacy,
                 old_source/'AutomaticDocument.java', old_source/'V51StyleConsumer.java',
                 helper/'LegacyImplementation.java', helper/'LegacyRunner.java'], output/'legacy-compile.log')
        probe = output/'probe-classes'; probe.mkdir()
        cp = os.pathsep.join(map(str, (probe, legacy, core, replication)))
        command(['javac', '-proc:none', '-cp', cp, '-d', probe, helper/'DefaultReadProbe.java', helper/'TokenProbe.java'],
                output/'probe-compile.log')
        command(['java', '-cp', cp, 'fixture.v52.DefaultReadProbe', output/'unused-authority'], output/'legacy.log')
        need(not (output/'unused-authority').exists(), 'stopped legacy consumer created authority')
        record['legacyBinary'] = 'compiled-with-published-5.1-run-with-candidate-including-inherited-read-default'
        fixtures = strict(b.regular(ROOT/b.DOCS/'fixtures/read-tokens-v1.json'))['cases']
        for case in fixtures:
            v = case['value']
            command(['java', '-cp', cp, 'fixture.v52.TokenProbe', case['hex'], v['version'], v['groupId'], v['historyId'],
                     v['manifestDigest'], v['index']], output/('token-'+case['name']+'.log'))
        record['tokenFixtures'] = len(fixtures)
        need(record['cloudBaseline'] == b.check(ROOT) and record['artifacts'] == artifact_inventory(ROOT, version),
             'release inputs changed during qualification')
        record['status'] = 'PASS'
    except Exception as error:
        record['failure'] = dict(type=type(error).__name__, message=str(error)); raise
    finally:
        with (output/'receipt.json').open('xb') as receipt: receipt.write(encoded(record)+b'\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--controls', type=Path, default=ROOT/'target/v52-published-controls')
    args = parser.parse_args(); record = run(args.output, args.controls)
    print(encoded({k: record[k] for k in ('status', 'version', 'publishedApi', 'tokenFixtures', 'candidateFrozen')}).decode())


if __name__ == '__main__': main()
