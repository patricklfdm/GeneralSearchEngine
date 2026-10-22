"""Bounded Java context fixture production and independent portable qualification."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from . import context_evidence as e
from . import context_negatives as negatives
from .foundation import ROOT, JARS, binding, jar, need, save


def run(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='gse-v53-context-qualification-v1', status='RUNNING', runtimeEnabled=False, authorityEvidence=False)
    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        receipt['source'] = binding(ROOT, source)
        receipt['jars'] = [jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))]
        classes = ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        names = ('V53ContextWorker.class', 'V53ContextFixture.class', 'V53DeclarationsTest.class')
        receipt['fixtureClasses'] = {name: e.sha((classes/name).read_bytes()) for name in names}
        for name in names:
            java = ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/name.replace('.class', '.java')
            need(java.stat().st_mtime_ns <= (classes/name).stat().st_mtime_ns, 'stale fixture class')
        cp = os.pathsep.join(str(ROOT/p) for p in (*JARS, 'general-search-engine-replication/target/test-classes'))
        result = subprocess.run(['java', '-cp', cp, 'io.github.patricklfdm.generalsearch.replication.V53ContextWorker', str(output/'physical')],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        (output/'worker.stdout').write_text(result.stdout); (output/'worker.stderr').write_text(result.stderr)
        need(result.returncode == 0, 'context fixture worker: '+result.stderr[-3000:])
        validation = e.validate(output/'physical'); save(output/'validation.json', validation)
        cases = negatives.run(output/'physical'); save(output/'negatives.json', cases)
        need(binding(ROOT, source) == receipt['source'], 'source changed during context qualification')
        need([jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))] == receipt['jars'], 'JAR changed during context qualification')
        receipt.update(status='PASS', profiles=len(validation['profiles']), certificates=validation['certificates'],
                       negativeCases=len(cases), relocatedReplay='PASS', manifestSha256=e.sha((output/'physical/manifest.json').read_bytes()))
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: save(output/'receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k not in ('source', 'jars', 'fixtureClasses')}, sort_keys=True))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args(); run(args.output)
