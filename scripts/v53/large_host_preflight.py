"""Offline checks of the proposed GCP runner's read-only inventory.

This is preparation, not admission or authorization. No API, resource mutation,
workflow dispatch, workload, credential handling or capacity reservation occurs.
Recollect immediately before deployment; a quota is not an availability promise.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

PROJECT = 'gse-benchmark'
REGION = 'us-central1'
ZONE = 'us-central1-a'
MACHINE = 'e2-standard-8'
BOOT_GIB = 32
WORK_GIB = 1024
FILES = ('project', 'region', 'machine', 'image')


def inspect(values):
    checks = []

    def check(name, passed, detail):
        checks.append(dict(name=name, status='PASS' if passed else 'BLOCKED', detail=detail))

    def quota(scope, metric, required):
        rows = [r for r in values[scope].get('quotas', []) if r.get('metric') == metric]
        valid = len(rows) == 1 and all(type(rows[0].get(k)) in (int, float) and
            math.isfinite(rows[0][k]) and rows[0][k] >= 0 for k in ('limit', 'usage'))
        available = rows[0]['limit'] - rows[0]['usage'] if valid else None
        check(scope + '/' + metric, valid and available >= required,
              dict(required=required, available=available, observed=rows))

    project, region, machine, image = (values[k] for k in FILES)
    check('project', project.get('name') == PROJECT, project.get('name'))
    check('region', region.get('name') == REGION and region.get('status') == 'UP',
          dict(name=region.get('name'), status=region.get('status')))
    check('machine', machine.get('name') == MACHINE and
          machine.get('zone', '').split('/')[-1] == ZONE and
          machine.get('guestCpus') == 8 and machine.get('memoryMb') == 32768, machine)
    expected_image = 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/'
    name = image.get('name', '')
    check('image', name.startswith('ubuntu-2404-noble-amd64-v') and
          image.get('selfLink') == expected_image + name and
          str(image.get('id', '')).isdigit() and image.get('architecture') == 'X86_64' and
          image.get('status') == 'READY' and not image.get('deprecated'), image)
    for metric, required in (('E2_CPUS', 8), ('SSD_TOTAL_GB', BOOT_GIB + WORK_GIB),
                             ('IN_USE_ADDRESSES', 1), ('INSTANCES', 1)):
        quota('region', metric, required)
    # New isolated custom VPC + one IAP-only SSH rule. Do not inherit default SSH/RDP.
    for metric, required in (('CPUS_ALL_REGIONS', 8), ('NETWORKS', 1), ('FIREWALLS', 1)):
        quota('project', metric, required)
    return dict(schema='gse-v53-large-host-preflight-v1',
                status='PASS' if all(c['status'] == 'PASS' for c in checks) else 'BLOCKED',
                checks=checks, catalogueAndQuotaOnly=True, deploymentReady=False,
                authorizationRequired=True, paidResourcesCreated=False,
                workflowsDispatched=0, phase3Complete=False,
                remaining=['Explicit operator startup authorization',
                           'Fresh inventory, exact-image identity and resource-name collision checks',
                           'Reviewed isolated network/IAP access, effective IAM and runner access',
                           'Create host only after authorization; validate actual mounted workspace',
                           'Register manual workflows and freeze exact source before dispatch'])


def read_inventory(root):
    values, inventory = {}, {}
    for name in FILES:
        path = root / (name + '.json')
        if path.is_symlink() or not path.is_file():
            raise ValueError('missing regular inventory file: ' + path.name)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError('oversized inventory file: ' + path.name)
        raw = path.read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError('invalid inventory object: ' + path.name)
        values[name] = value
        inventory[path.name] = dict(sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    result = inspect(values)
    result['inputFiles'] = inventory
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = read_inventory(args.inventory)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        result = dict(status='BLOCKED', reason=str(error), deploymentReady=False,
                      paidResourcesCreated=False, workflowsDispatched=0, phase3Complete=False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result['status'] == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
