"""Additional disk space for maximum-native hosted archives and unpacked inputs.

These conservative transport margins do not change runtime resource budgets or
the existing 272/144 GiB direct-execution checks. Old failed work is not deleted.
"""
import argparse
import json
from . import maximum_transition_capacity as native

GIB=native.GIB
FREE_BY_STAGE={'execute':280*GIB,'verify-download':416*GIB,'verify':288*GIB}


def check(path,stage):
    native.need(type(stage) is str and stage in FREE_BY_STAGE,'maximum native hosted capacity stage')
    observed=native.check(path,'execute' if stage=='execute' else 'verify')
    native.need(observed['freeBytes']>=FREE_BY_STAGE[stage],
                'maximum native hosted insufficient disk; stage not started')
    return dict(schema='gse-v53-maximum-native-hosted-capacity-v1',status='PASS',stage=stage,
                minimumFreeBytes=FREE_BY_STAGE[stage],capacity=observed,
                runtimeBudgetsChanged=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory');p.add_argument('--stage',required=True,choices=FREE_BY_STAGE)
    a=p.parse_args();print(json.dumps(check(a.directory,a.stage),sort_keys=True))
