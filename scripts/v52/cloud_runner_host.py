"""Closed execution-host routing; only declared whole-history shards run on hosted jobs.

Runner choice never grants cloud authority. The operator still binds the exact
prepared artifact, source, approval, lease, resource IDs and original histories.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import threading
import time
from .evidence import need

HOSTS = ('github-hosted', 'self-hosted')
RUNS_ON = "${{ fromJSON(inputs.execution_host == 'self-hosted' && '[\"self-hosted\",\"Linux\",\"X64\",\"gse-v52-cloud-d-wsl\"]' || '[\"ubuntu-24.04\"]') }}"
TIMEOUT = "${{ inputs.execution_host == 'self-hosted' && 1380 || 360 }}"
MINIMUM_FREE = 4 << 30


def selected(env):
    value=env.get('V52_EXECUTION_HOST')
    need(value in HOSTS,'V5.2 unknown execution host')
    return value


def require_member(name, env):
    from . import cloud_suite as suite
    suite.member(name)
    need(selected(env)=='self-hosted' or name in suite.HOSTED_MEMBERS,
         'V5.2 hosted execution requires one complete declared shard')


def check(env):
    host=selected(env)
    need(env.get('RUNNER_ENVIRONMENT')==host and env.get('RUNNER_OS')=='Linux' and
         env.get('RUNNER_ARCH')=='X64','V5.2 execution host identity mismatch')
    if host=='self-hosted':
        from . import cloud_self_hosted
        return cloud_self_hosted.check(env,cloud_self_hosted.configuration())
    need(env.get('V52_OPERATION') in ('prepare','run'),
         'V5.2 complete-set replay requires the retained self-hosted route')
    need(shutil.disk_usage(Path.cwd()).free>=MINIMUM_FREE,'V5.2 hosted disk admission floor')
    return dict(host=host,jobPlatformLimitSeconds=21600,timeBudget='soft',costBudget='soft')


def execute(source, output):
    env=dict(os.environ);check(env)
    if selected(env)=='self-hosted':
        from . import cloud_self_hosted
        return cloud_self_hosted.execute(source,output)
    from . import cloud_operator
    stop=threading.Event();began=time.monotonic()
    def beat():
        while not stop.wait(60):
            elapsed=time.monotonic()-began;free=shutil.disk_usage(Path.cwd()).free
            print(json.dumps(dict(stage='hosted-progress',elapsedSeconds=round(elapsed,1),
                freeGiB=round(free/(1<<30),2),jobPlatformLimitSeconds=21600)),flush=True)
            if elapsed>=4*3600 or free<MINIMUM_FREE:
                print('::warning::Hosted headroom low; operation continues. GitHub enforces the six-hour job limit.',flush=True)
    thread=threading.Thread(target=beat,daemon=True);thread.start()
    try:return cloud_operator.execute_native(source,output)
    finally:stop.set();thread.join()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('check','execute'))
    p.add_argument('--source');p.add_argument('--output',type=Path);args=p.parse_args()
    if args.action=='execute' and (not args.source or not args.output):p.error('execute requires source/output')
    try:
        result=check(dict(os.environ)) if args.action=='check' else execute(args.source,args.output)
        print(json.dumps(result),flush=True);return 0
    except Exception:
        print('v52RunnerHost=FAIL; inspect the safe operation diagnostics',flush=True);return 2


if __name__=='__main__':raise SystemExit(main())
