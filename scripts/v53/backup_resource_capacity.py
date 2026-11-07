"""Disk admission for the small backup history's transport, not runtime limits.

17 GiB raw archive allowance, a worst-case compressed copy and 6 GiB workspace
margin. Verification checks 40 GiB before download, then 23 GiB before extraction.
This does not admit the maximum-image history or establish peak-memory capacity.
"""
import argparse
import json
from pathlib import Path
import shutil
from .membership_model import need

GIB = 1024**3
FREE_BY_STAGE = {'execute': 40*GIB, 'verify-download': 40*GIB, 'verify': 23*GIB}


def check(path, stage):
    need(type(stage) is str and stage in FREE_BY_STAGE, 'backup hosted capacity stage')
    path = Path(path).resolve(strict=True)
    need(path.is_dir(), 'backup hosted capacity workspace directory')
    free = shutil.disk_usage(path).free
    need(free >= FREE_BY_STAGE[stage], 'backup hosted insufficient disk; stage not started')
    return dict(schema='gse-v53-backup-hosted-capacity-v1', status='PASS', stage=stage,
                workspace=str(path), freeBytes=free, minimumFreeBytes=FREE_BY_STAGE[stage],
                runtimeBudgetsChanged=False, maximumImageQualified=False, phase3Complete=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('directory'); p.add_argument('--stage', required=True, choices=FREE_BY_STAGE)
    a = p.parse_args(); print(json.dumps(check(a.directory, a.stage), sort_keys=True))
