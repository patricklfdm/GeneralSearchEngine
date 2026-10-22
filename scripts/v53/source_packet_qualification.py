"""Fresh Java packets, independent transport replay and original-first mutations."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from . import source_packet as p
from . import format_fixture as f
from .foundation import ROOT, JARS, binding, jar, need, save
from .context_evidence import sha


def negatives(root):
    p.validate(root)
    data = (root/'packet.bin').read_bytes(); basis = f.decode((root/'basis.bin').read_bytes(), 'records', 'BASIS')
    packet = p.decode(data); results = []
    def rejected(name, action):
        try: action()
        except ValueError as error: results.append(dict(case=name, status='REJECT', reason=str(error)))
        else: raise ValueError('accepted packet negative: '+name)
    for offset in (0, 4, 6, 8, 10, 12, 48, 52+len(packet['capsuleBytes'])):
        altered = bytearray(data); altered[offset] ^= 128; altered[16:48] = bytes.fromhex(sha(altered[:16]+altered[48:]))
        rejected('offset-'+str(offset), lambda: p.decode(bytes(altered)))
    altered = bytearray(data); altered[-1] ^= 1; altered[16:48] = bytes.fromhex(sha(altered[:16]+altered[48:]))
    rejected('member-bytes', lambda: p.decode(bytes(altered)))
    for field in ('root', 'cut', 'capsule', 'inventory', 'accepted', 'view'):
        altered = copy.deepcopy(basis)
        if field == 'cut': altered['cut']['index'] += 1
        else: altered[field] = 'ff'*32
        rejected('basis-'+field, lambda: p.bind(packet, f.encode('records', 'BASIS', altered)))
    need(len(results) == 15, 'packet negative inventory')
    return results


def run(output):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema='gse-v53-source-packet-qualification-v1', status='RUNNING', runtimeEnabled=False, capsuleAuthorityVerified=False)
    try:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        receipt['source'] = binding(ROOT, source)
        receipt['jars'] = [jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))]
        cp = os.pathsep.join(str(ROOT/path) for path in (*JARS, 'general-search-engine-replication/target/test-classes'))
        class_dir = ROOT/'general-search-engine-replication/target/test-classes/io/github/patricklfdm/generalsearch/replication'
        receipt['classes'] = {path.name: sha(path.read_bytes()) for path in sorted(class_dir.glob('V53*.class'))}
        for name in ('V53SourcePacketWorker', 'V53SourcePacketTest', 'V53ContextFixture', 'V53DeclarationsTest'):
            source_file = ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/replication'/(name+'.java')
            need(source_file.stat().st_mtime_ns <= (class_dir/(name+'.class')).stat().st_mtime_ns, 'stale packet worker')
        result = subprocess.run(['java', '-cp', cp, 'io.github.patricklfdm.generalsearch.replication.V53SourcePacketWorker', str(output/'physical')],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        (output/'worker.stdout').write_text(result.stdout); (output/'worker.stderr').write_text(result.stderr)
        need(result.returncode == 0, 'packet worker: '+result.stderr[-3000:])
        cases = {}; mutations = {}
        for name in ('initial', 'accepted-tail'):
            root = output/'physical'/name; cases[name] = p.validate(root); mutations[name] = negatives(root)
            with tempfile.TemporaryDirectory(prefix='v53-packet-replay-') as temp:
                copied = Path(temp)/'relocated'; shutil.copytree(root, copied)
                need(p.validate(copied) == cases[name], 'relocated packet replay')
        save(output/'validation.json', cases); save(output/'negatives.json', mutations)
        need(binding(ROOT, source) == receipt['source'], 'source changed during packet qualification')
        need([jar(ROOT/path, role) for path, role in zip(JARS, ('core', 'replication'))] == receipt['jars'], 'JAR changed during packet qualification')
        receipt.update(status='PASS', cases=cases, negativeCases=30, relocatedReplay='PASS',
                       files={path.relative_to(output).as_posix(): sha(path.read_bytes()) for path in sorted(output.rglob('*')) if path.is_file()})
    except BaseException as error:
        receipt.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally: save(output/'receipt.json', receipt)
    print(json.dumps(dict(status=receipt['status'], cases=receipt['cases'], negativeCases=30, capsuleAuthorityVerified=False), sort_keys=True))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args(); run(args.output)
