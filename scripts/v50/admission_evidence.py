"""Retain independent Step A classifications and require executed Java gate evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from . import admission_format as oracle

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'general-search-engine-replication/src/test/resources/replication/v50-admission-fixtures-v2.json'


def run(output):
    result = {'schema': 'gse-v50-admission-foundation-evidence-v1',
              'sourceSha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'workingTreeDiffSha256': hashlib.sha256(subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=ROOT)).hexdigest(),
              'fixtureSha256': hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
              'publicRuntime': 'not-exercised-by-foundation-gate', 'offlineAuthorityGate': 'separate', 'cases': [], 'java': []}
    source_files = subprocess.check_output(['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT).split(b'\0')
    source_inventory = []
    for name in sorted(set(source_files) - {b''}):
        path = ROOT / name.decode('utf-8')
        if path.is_file():
            source_inventory.append([name.decode('utf-8'), hashlib.sha256(path.read_bytes()).hexdigest()])
    result['sourceInventorySha256'] = hashlib.sha256(json.dumps(source_inventory, separators=(',', ':')).encode()).hexdigest()
    result['workingTreeDirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT))
    try:
        for case, files in oracle.cases(FIXTURE):
            try:
                actual = oracle.validate(files)
            except (ValueError, KeyError, UnicodeError) as error:
                oracle.check(not case['valid'], case['name'] + ': unexpected rejection')
                result['cases'].append(dict(name=case['name'], classification='REJECT', detail=str(error)))
            else:
                oracle.check(case['valid'] and actual == case['expected'], case['name'] + ': unexpected acceptance/result')
                result['cases'].append(dict(name=case['name'], classification='ACCEPT', result=actual))
        reports = ROOT / 'general-search-engine-replication/target/surefire-reports'
        for test in ('admission.V50AdmissionFormatTest', 'admission.V50AdmissionDeclarationsTest', 'replication.V50PublicApiInventoryTest'):
            report = reports / ('TEST-io.github.patricklfdm.generalsearch.' + test + '.xml')
            suite = ET.parse(report).getroot()
            oracle.check(int(suite.attrib['tests']) > 0 and all(int(suite.attrib.get(k, 0)) == 0 for k in ('failures', 'errors', 'skipped')),
                         'Java gate did not execute successfully: ' + test)
            # A stale earlier build must not satisfy --skip-build after test/oracle edits.
            source_root = ROOT / 'general-search-engine-replication/src'
            newer = [p for p in source_root.rglob('*') if p.is_file() and p.suffix in ('.java', '.json', '.txt', '.sha256')
                     and p.stat().st_mtime_ns > report.stat().st_mtime_ns]
            oracle.check(not newer, 'Java reports predate source/fixtures; rerun Maven tests')
            result['java'].append(dict(test=test, tests=int(suite.attrib['tests']), reportSha256=hashlib.sha256(report.read_bytes()).hexdigest()))
        result['status'] = 'PASS'
    except Exception as error:
        result['status'], result['failure'] = 'FAIL', str(error)
        raise
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print('v50AdmissionEvidence=' + str(output))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run(args.output)
