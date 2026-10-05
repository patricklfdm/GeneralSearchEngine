"""Run an exhaustive, disjoint part of the V5.1 Python suite without Maven."""
import argparse
import json
from pathlib import Path
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
LANES = ('core', 'admission', 'storage')
STORAGE = frozenset('scripts.v51.test_' + name for name in (
    'cloud_fixture_driver', 'cloud_topology_fixture', 'cloud_experiment_resources',
    'cloud_runner_storage', 'cloud_runner_storage_entry'))


def partition(modules):
    result = {lane: [] for lane in LANES}
    for module in sorted(modules):
        lane = ('storage' if module in STORAGE else
                'admission' if module.startswith('scripts.v51.test_cloud_') else 'core')
        result[lane].append(module)
    return result


def inventory():
    return ['scripts.v51.' + path.stem for path in sorted((ROOT / 'scripts/v51').glob('test_*.py'))]


def run_suite(suite, output, lane, modules):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    expected = suite.countTestCases()
    with (output / 'timings.jsonl').open('x') as timings:
        class Result(unittest.TextTestResult):
            def startTest(self, test):
                self.started = time.monotonic()
                super().startTest(test)

            def stopTest(self, test):
                super().stopTest(test)
                timings.write(json.dumps(dict(test=test.id(), seconds=time.monotonic()-self.started))+'\n')
                timings.flush()

        result = unittest.TextTestRunner(resultclass=Result).run(suite)
    passed = result.wasSuccessful() and result.testsRun == expected and expected > 0
    receipt = dict(lane=lane, status='PASS' if passed else 'FAIL', modules=modules,
                   expected=expected, executed=result.testsRun, skipped=len(result.skipped),
                   failures=len(result.failures), errors=len(result.errors))
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lane', choices=LANES)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    modules = partition(inventory())[args.lane]
    suite = unittest.TestLoader().loadTestsFromNames(modules)
    if not run_suite(suite, args.output, args.lane, modules):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
