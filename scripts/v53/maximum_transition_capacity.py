"""Workspace admission for the opt-in large physical history, not runtime limits.

The history cannot be shortened to fit a host. WSL guest free space alone does
not prove backing-volume space, so this entry requires a native Linux host.
"""
import argparse
import json
import platform
from pathlib import Path
import shutil
from .membership_model import need

GIB = 1024**3
# Original <=128 GiB plus source/classes; leave room for a worst-case archive,
# another retained failed original is never deleted to meet this requirement.
MINIMUM_FREE = 272*GIB
FREE_BY_STAGE = {'execute': MINIMUM_FREE, 'verify': 144*GIB}
MINIMUM_AVAILABLE_MEMORY = 8*GIB
SCHEMA = 'gse-v53-maximum-transition-capacity-v1'


def check(path, stage='execute'):
    need(type(stage) is str and stage in FREE_BY_STAGE, 'maximum-transition capacity stage')
    path = Path(path).resolve(strict=True)
    need(path.is_dir(), 'maximum-transition capacity workspace directory')
    system, release = platform.system(), platform.release()
    need(system == 'Linux' and not any(v in release.lower() for v in ('microsoft', 'wsl')),
         'maximum-transition capacity requires native Linux backing-volume admission')
    available = []
    for line in Path('/proc/meminfo').read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'MemAvailable:':
            need(len(fields) == 3 and fields[2] == 'kB' and fields[1].isdigit(), 'maximum-transition capacity memory record')
            available.append(int(fields[1])*1024)
    need(len(available) == 1, 'maximum-transition capacity memory available')
    free = shutil.disk_usage(path).free
    need(free >= FREE_BY_STAGE[stage], 'maximum-transition capacity insufficient disk; stage not started')
    need(available[0] >= MINIMUM_AVAILABLE_MEMORY, 'maximum-transition capacity insufficient memory; original not started')
    return dict(schema=SCHEMA, status='PASS', stage=stage, workspace=str(path), system=system, release=release,
                freeBytes=free, minimumFreeBytes=FREE_BY_STAGE[stage], availableMemoryBytes=available[0],
                minimumAvailableMemoryBytes=MINIMUM_AVAILABLE_MEMORY, runtimeBudgetsChanged=False,
                phase3Complete=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('--stage', choices=FREE_BY_STAGE, default='execute')
    args = parser.parse_args(); print(json.dumps(check(args.directory, args.stage), sort_keys=True))
