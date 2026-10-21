"""Dedicated operator Runner checks and local evidence preservation; no cloud I/O.

The administrator installs this file outside the checkout for pre/post-job hooks.
Only trusted manual master jobs belong on this machine. Labels and these hooks
do not turn a persistent public-repository Runner into an untrusted-code sandbox.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import threading
import time

CONFIG = Path('/etc/gse-runner/host.json')
HOST_SPACE = Path('/run/gse-runner/host-space.json')
REPOSITORY = 'patricklfdm/GeneralSearchEngine'
WORKFLOW = REPOSITORY + '/.github/workflows/v52-replication-evidence.yml@refs/heads/master'
LABEL = 'gse-v52-cloud-d-wsl'
SPACE_WARNING = 30 << 30


def need(value, message):
    if not value:
        raise ValueError(message)


def private(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         'Runner directory must be an absolute unlinked path')
    info = path.stat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and not info.st_mode & 0o077,
         'Runner directory must be privately owned')
    return path


def configuration(path=CONFIG):
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Runner configuration link')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022 and info.st_size < 4096,
         'Runner configuration must be administrator owned')
    value = json.loads(path.read_text())
    need(set(value) == {'schema', 'name', 'workspaceRoot', 'archiveRoot', 'stateRoot', 'backingStore'} and
         value['schema'] == 'gse-v52-self-hosted-v1' and value['name'] == LABEL and
         value['backingStore'] == 'D:\\GSE-Runner\\Ubuntu', 'Runner configuration identity')
    for key in ('workspaceRoot', 'archiveRoot', 'stateRoot'):
        private(value[key])
    roots = [Path(value[k]) for k in ('workspaceRoot', 'archiveRoot', 'stateRoot')]
    need(len(set(roots)) == 3 and not any(x in y.parents for x in roots for y in roots if x != y),
         'Runner directories overlap')
    return value


def context(env, cfg):
    expected = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=REPOSITORY, GITHUB_EVENT_NAME='workflow_dispatch',
                    GITHUB_REF='refs/heads/master', GITHUB_WORKFLOW_REF=WORKFLOW, GITHUB_JOB='runner',
                    RUNNER_NAME=cfg['name'], RUNNER_OS='Linux', RUNNER_ARCH='X64', RUNNER_ENVIRONMENT='self-hosted')
    need(all(env.get(k) == v for k, v in expected.items()), 'Runner only accepts the protected manual master workflow')
    for name in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        need(re.fullmatch(r'[1-9][0-9]{0,19}', env.get(name, '')) is not None, 'Runner run/attempt identity')
    workspace = Path(env.get('GITHUB_WORKSPACE', ''))
    expected_workspace = Path(cfg['workspaceRoot'])/'GeneralSearchEngine/GeneralSearchEngine'
    need(workspace == expected_workspace and not any(p.is_symlink() for p in (workspace, *workspace.parents)),
         'Runner workspace identity')
    return dict(run=env['GITHUB_RUN_ID'], attempt=env['GITHUB_RUN_ATTEMPT'], workspace=str(workspace))


def space(path):
    row = dict(stage='self-hosted-storage', linuxFreeGiB=round(shutil.disk_usage(path).free / (1 << 30), 2),
               linuxWarningBelowGiB=SPACE_WARNING >> 30, hostSpace='UNAVAILABLE')
    try:
        need(not HOST_SPACE.is_symlink(), 'host space link')
        info = HOST_SPACE.stat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022 and info.st_size < 1024,
             'host space file ownership')
        value = json.loads(HOST_SPACE.read_text())
        need(set(value) == {'drive', 'freeBytes', 'totalBytes', 'checkedAt'} and value['drive'] == 'D:' and
             all(type(value[k]) is int for k in ('freeBytes', 'totalBytes', 'checkedAt')) and
             0 <= value['freeBytes'] <= value['totalBytes'] and 0 <= time.time()-value['checkedAt'] <= 180,
             'host space fields/staleness')
        row.update(hostSpace='CURRENT', hostFreeGiB=round(value['freeBytes']/(1 << 30), 2), hostWarningBelowGiB=20)
    except (OSError, ValueError, TypeError):
        pass
    return row


def check(env, cfg):
    bound = context(env, cfg)
    os_release = Path('/etc/os-release').read_text()
    need('ID=ubuntu\n' in os_release and 'VERSION_ID="24.04"' in os_release, 'Runner requires Ubuntu 24.04')
    filesystem = subprocess.check_output(['stat', '-f', '-c', '%T', cfg['workspaceRoot']], text=True,
                                         env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}).strip()
    need(filesystem == 'ext2/ext3', 'Runner workspace requires Linux ext4 storage')
    storage = space(cfg['workspaceRoot'])
    need(storage['hostSpace'] == 'CURRENT', 'Start the Windows Runner launcher to publish current D-drive space')
    print(json.dumps(dict(status='PASS', runner=cfg['name'], backingStore=cfg['backingStore'], **storage)), flush=True)
    return bound


def started(env, cfg):
    bound = check(env, cfg)
    # Never let checkout clean erase an unpreserved preceding job's output.
    state = Path(cfg['stateRoot'])/'active.json'
    need(not state.exists() and not (Path(bound['workspace'])/'target/v52-runner').exists(),
         'Previous Runner output needs preservation before another job')
    with state.open('x') as stream:
        json.dump(bound, stream)
    state.chmod(0o600)


def completed(env, cfg):
    bound = context(env, cfg); state = Path(cfg['stateRoot'])/'active.json'
    need(not state.is_symlink() and json.loads(state.read_text()) == bound, 'Runner completion identity')
    destination = Path(cfg['archiveRoot'])/(bound['run']+'-'+bound['attempt'])
    destination.mkdir(mode=0o700)
    source = Path(bound['workspace'])/'target/v52-runner'
    # Atomic move on the same D-backed Linux filesystem: no duplicate allocation,
    # no credential-containing checkout archive, no deletion of failed evidence.
    if source.exists():
        private(source)
        need(source.stat().st_dev == destination.stat().st_dev, 'Runner archive must share the workspace filesystem')
        source.rename(destination/'evidence')
    (destination/'local-receipt.json').write_text(json.dumps(dict(**bound, evidencePreserved=(destination/'evidence').exists()))+'\n')
    state.unlink()
    print(json.dumps(dict(stage='self-hosted-preserved', run=bound['run'], attempt=bound['attempt'])), flush=True)


def execute(source, output):
    cfg = configuration(); check(dict(os.environ), cfg)
    stop = threading.Event(); began = time.monotonic()
    def heartbeat():
        while not stop.wait(60):
            row = space(cfg['workspaceRoot']); row['elapsedSeconds'] = round(time.monotonic()-began, 1)
            print(json.dumps(row), flush=True)
            if row['linuxFreeGiB'] < SPACE_WARNING/(1 << 30) or row.get('hostFreeGiB', 20) < 20 or row['hostSpace'] != 'CURRENT':
                print('::warning::Self-hosted storage low or Windows disk monitor stale; operation continues.', flush=True)
    thread = threading.Thread(target=heartbeat, daemon=True); thread.start()
    try:
        # Keep the original operator's signal/cleanup behavior in this process.
        from . import cloud_operator
        return cloud_operator.execute_native(source, output)
    finally:
        stop.set(); thread.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'started', 'completed', 'execute'))
    parser.add_argument('--source'); parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == 'execute':
            if not args.source or not args.output: parser.error('execute needs source/output')
            print(json.dumps(execute(args.source, args.output)), flush=True)
        else:
            globals()[args.action](dict(os.environ), configuration())
    except Exception:
        # Preserve the original operator's closed public failure boundary.
        print('v52SelfHosted=FAIL; inspect the safe operation summary and local Runner state', flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
