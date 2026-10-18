"""Exhaustive V5.2 Python partitions; no Maven or cloud workload execution."""
import argparse
import json
from pathlib import Path
import threading
import time
import unittest
from scripts.ci_v51_python import run_suite

ROOT=Path(__file__).resolve().parents[1]
LANES=('core','measurement','transport','cloud-provenance','cloud-control',
       'native-admission','native-storage','native-evidence')
NATIVE={
    'native-admission':('cloud_acquisition_context','cloud_native_cleanup','cloud_native_runner'),
    'native-storage':('cloud_iap','cloud_storage','cloud_java'),
    'native-evidence':('cloud_member_factory','cloud_retention','cloud_member_evidence'),
}
PROVENANCE=('cloud_inputs','cloud_artifacts','cloud_ci','cloud_prepared','cloud_credentials',
            'cloud_preflight','cloud_recent_cleanup','cloud_cleanup_bundle')
EXTRA='scripts.v51.test_runtime_process_generations'


def inventory():return ['scripts.v52.'+p.stem for p in sorted((ROOT/'scripts/v52').glob('test_*.py'))]+[EXTRA]


def partition(modules):
    result={lane:[] for lane in LANES}
    if len(modules)!=len(set(modules)):raise ValueError('duplicate V5.2 Python module')
    for module in sorted(modules):
        if module==EXTRA:lane='transport'
        else:
            if not module.startswith('scripts.v52.test_'):raise ValueError('unknown V5.2 Python module scope')
            name=module.removeprefix('scripts.v52.test_')
            lane=next((key for key,names in NATIVE.items() if name in names),None)
            lane=lane or ('cloud-provenance' if name in PROVENANCE else 'cloud-control' if name.startswith('cloud_') else
                'transport' if name.startswith('remote_') else 'measurement' if name.startswith('measurement_') else 'core')
        result[lane].append(module)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('lane',choices=LANES)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    modules=partition(inventory())[args.lane];suite=unittest.TestLoader().loadTestsFromNames(modules)
    # Clock-oriented tests may patch the time module; progress uses the real
    # captured clock rather than reporting their deliberately displaced epoch.
    done=threading.Event();clock=time.monotonic;start=clock()
    def heartbeat():
        while not done.wait(60):
            print(json.dumps(dict(lane=args.lane,stage='python-tests',elapsedSeconds=round(clock()-start,1))),flush=True)
    worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
    try:
        if not run_suite(suite,args.output,args.lane,modules):raise SystemExit(1)
    finally:done.set();worker.join()


if __name__=='__main__':main()
