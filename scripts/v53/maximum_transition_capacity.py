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


def validate(value,stage='execute'):
    need(type(stage) is str and stage in FREE_BY_STAGE, 'maximum-transition capacity stage')
    fields={'schema','status','stage','workspace','system','release','freeBytes','minimumFreeBytes',
            'availableMemoryBytes','minimumAvailableMemoryBytes','runtimeBudgetsChanged','phase3Complete'}
    need(type(value) is dict and set(value)==fields and value['schema']==SCHEMA and value['status']=='PASS' and
         value['stage']==stage and value['system']=='Linux' and type(value['release']) is str and value['release'] and
         not any(v in value['release'].lower() for v in ('microsoft','wsl')) and
         type(value['workspace']) is str and 0<len(value['workspace'])<=4096 and '\0' not in value['workspace'] and
         Path(value['workspace']).is_absolute() and value['runtimeBudgetsChanged'] is False and value['phase3Complete'] is False,
         'maximum-transition capacity receipt scope')
    need(all(type(value[k]) is int for k in ('freeBytes','minimumFreeBytes','availableMemoryBytes','minimumAvailableMemoryBytes')) and
         value['minimumFreeBytes']==FREE_BY_STAGE[stage] and value['freeBytes']>=FREE_BY_STAGE[stage] and
         value['minimumAvailableMemoryBytes']==MINIMUM_AVAILABLE_MEMORY and value['availableMemoryBytes']>=MINIMUM_AVAILABLE_MEMORY,
         'maximum-transition capacity receipt limits')


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
    value=dict(schema=SCHEMA, status='PASS', stage=stage, workspace=str(path), system=system, release=release,
                freeBytes=free, minimumFreeBytes=FREE_BY_STAGE[stage], availableMemoryBytes=available[0],
                minimumAvailableMemoryBytes=MINIMUM_AVAILABLE_MEMORY, runtimeBudgetsChanged=False,
                phase3Complete=False)
    validate(value,stage);return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('directory'); parser.add_argument('--stage', choices=FREE_BY_STAGE, default='execute')
    args = parser.parse_args(); print(json.dumps(check(args.directory, args.stage), sort_keys=True))
