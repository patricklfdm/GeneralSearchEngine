"""Read-only host preparation; never provisions, dispatches or admits evidence.

Use the actual mounted Actions workspace. Every execution/replay still runs its
own capacity gate after inputs arrive; this observation cannot replace it.
"""
import argparse
import json
from pathlib import Path
from . import maximum_transition_capacity as direct
from . import maximum_native_capacity as hosted
from . import maximum_resource_attested as final


def inspect(workspace):
    checks = []
    for name, check in (
            ('direct-execute', lambda: direct.check(workspace, 'execute')),
            ('hosted-execute', lambda: hosted.check(workspace, 'execute')),
            ('hosted-download', lambda: hosted.check(workspace, 'verify-download')),
            ('hosted-verify', lambda: hosted.check(workspace, 'verify')),
            ('final-after-inputs', lambda: final.capacity(workspace))):
        try:
            checks.append(dict(name=name, status='PASS', observation=check()))
        except (OSError, ValueError) as error:
            checks.append(dict(name=name, status='BLOCKED', reason=str(error)))
    return dict(schema='gse-v53-large-runner-readiness-v1',
                status='PASS' if all(v['status'] == 'PASS' for v in checks) else 'BLOCKED',
                hardwareOnly=True, inputsPresentNotVerified=True,
                phase3Complete=False, checks=checks)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    args = parser.parse_args()
    result = inspect(args.workspace)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
