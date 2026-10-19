"""Install/import the exact guest closure without repository/site fallback.

No workload, voter, SSH connection or cloud resource is started by this gate.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from . import remote_python_package as package, remote_python_receiver as receiver

PROBE = '''import importlib,json,pathlib,sys
sys.dont_write_bytecode=True
root=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(root))
entries=json.loads(sys.argv[2])
for entry in entries: importlib.import_module(entry)
from scripts.v52 import cloud_suite,measurement_model
from scripts.build_coordinates import current
from scripts.v51 import format_inspector as fmt
cloud_suite.load();measurement_model.load();version=current(root)
fmt.load();fmt._bootstrap_records((fmt.CATALOG.parent/'bootstrap-catalog.json').read_bytes())
fmt._wire_catalog(fmt.CATALOG.read_bytes(),tuple(p.read_bytes() for p in fmt.WIRE_EXTENSIONS))
paths={name:str(pathlib.Path(module.__file__).relative_to(root)) for name,module in list(sys.modules.items())
       if name.startswith('scripts.') and getattr(module,'__file__',None)}
if not all(str(p)==str(root/'scripts') for p in sys.modules['scripts'].__path__):
 raise ValueError('Python capsule foreign namespace')
print(json.dumps(dict(loaded=paths,suiteSha256=cloud_suite.PLAN_SHA,version=version,
                     gitPresent=(root/'.git').exists(),isolated=bool(sys.flags.isolated),noSite=bool(sys.flags.no_site))))
'''


def probe(root, value):
    receiver.installed(root, value)
    result = subprocess.run([sys.executable, '-I', '-S', '-c', PROBE, str(root/'files'), json.dumps(receiver.ENTRIES)],
                            cwd=root, text=True, capture_output=True, timeout=30)
    receiver.need(result.returncode == 0, 'Python capsule isolated imports failed: ' + result.stderr[-3000:])
    observed = receiver.decode(result.stdout)
    receiver.need(set(observed) == {'loaded','suiteSha256','version','gitPresent','isolated','noSite'} and
                  observed['isolated'] is True and observed['noSite'] is True and observed['gitPresent'] is False,
                  'Python capsule isolated environment')
    receiver.need(set(receiver.ENTRIES) <= set(observed['loaded']) and
                  set(observed['loaded'].values()) <= set(value['files']), 'Python capsule loaded dependency identity')
    receiver.installed(root, value)  # No pyc, unlisted file or mutation is accepted.
    return observed


def run(output, source_root=package.ROOT):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=False)
    result = dict(status='FAIL', execution='isolated-python-package-only',
                  workloadExecuted=False, fullRemoteQualification=False, paidCloud=False)
    try:
        built = package.create(source_root, output/'package')
        value = receiver.decode((output/'package/descriptor.json').read_bytes())
        raw = (output/'package/payload.json').read_bytes()
        parent = output/'private'; parent.mkdir(mode=0o700)
        trusted = Path(receiver.__file__).read_text()
        request = receiver.encoded(dict(descriptor=value, payload=raw.decode('ascii')))
        args = [sys.executable, '-I', '-S', '-c', trusted, 'install', str(parent), built['descriptorSha256']]
        installed = subprocess.run(args, input=request, capture_output=True, timeout=30, cwd=parent)
        receiver.need(installed.returncode == 0, 'Python capsule trusted installation failed: ' + installed.stderr.decode()[-3000:])
        receipt = receiver.decode(installed.stdout); root = Path(receipt['root'])
        receiver.need(root != source_root and not (root/'files/.git').exists(), 'Python capsule independent installation')
        observed = probe(root, value)
        receiver.need(package.binding(source_root) == built['source'], 'Python source changed during qualification')
        result.update(status='PASS', source=built['source'], descriptorSha256=built['descriptorSha256'],
                      payloadSha256=value['sha256'], trustedReceiverSha256=receiver.digest(trusted.encode()),
                      files=built['files'], expandedBytes=built['expandedBytes'], payloadBytes=built['payloadBytes'],
                      installation=receipt, imports=observed)
        return result
    except BaseException as error:
        result['failure'] = dict(type=type(error).__name__, message=str(error)); raise
    finally:
        (output/'receipt.json').write_bytes(receiver.encoded(result)+b'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('output'); args = parser.parse_args()
    print(json.dumps(run(args.output)))
