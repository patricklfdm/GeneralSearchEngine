"""Synthetic quota/identity checks; never provision or assert hosted acceptance."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from . import large_host_preflight as p


def fixture():
    def quotas(**values):
        return [dict(metric=k, limit=v, usage=0) for k, v in values.items()]
    name = 'ubuntu-2404-noble-amd64-v20261105'
    return dict(project=dict(name=p.PROJECT, quotas=quotas(CPUS_ALL_REGIONS=32, NETWORKS=5, FIREWALLS=100)),
                region=dict(name=p.REGION, status='UP', quotas=quotas(E2_CPUS=24, SSD_TOTAL_GB=2048,
                            DISKS_TOTAL_GB=4096, IN_USE_ADDRESSES=8, INSTANCES=24)),
                machine=dict(name=p.MACHINE, zone=p.ZONE, guestCpus=8, memoryMb=32768),
                image=dict(name=name, id='123', architecture='X86_64', status='READY',
                    selfLink='https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/'+name))


class LargeHostPreflightTest(unittest.TestCase):
    def test_sufficient_inventory_is_never_deployment_permission_or_evidence(self):
        result = p.inspect(fixture())
        self.assertEqual('PASS', result['status'])
        for key in ('deploymentReady', 'paidResourcesCreated', 'phase3Complete'):
            self.assertFalse(result[key])
        self.assertTrue(result['authorizationRequired'])
        self.assertEqual(0, result['workflowsDispatched'])

    def test_standard_disk_quota_cannot_cover_balanced_and_boot_is_counted(self):
        for limit in (500, 1024, 1055, 1056):
            value = fixture()
            next(q for q in value['region']['quotas'] if q['metric'] == 'SSD_TOTAL_GB')['limit'] = limit
            result = p.inspect(value)
            self.assertEqual('PASS' if limit == 1056 else 'BLOCKED', result['status'])

    def test_used_quota_global_cpu_and_missing_duplicate_or_nonfinite_metrics_block(self):
        original = fixture()
        cases = []
        for field, value in (('usage', 1024), ('limit', float('nan')), ('limit', True)):
            data = copy.deepcopy(original)
            next(q for q in data['region']['quotas'] if q['metric'] == 'SSD_TOTAL_GB')[field] = value
            cases.append(data)
        data = copy.deepcopy(original); data['project']['quotas'][0]['limit'] = 4; cases.append(data)
        data = copy.deepcopy(original); data['region']['quotas'].pop(0); cases.append(data)
        data = copy.deepcopy(original); data['region']['quotas'].append(data['region']['quotas'][0]); cases.append(data)
        for data in cases:
            with self.subTest(data=data): self.assertEqual('BLOCKED', p.inspect(data)['status'])

    def test_image_architecture_status_identity_and_location_drift_block(self):
        for section, key, value in [('project','name','elsewhere'), ('region','status','DOWN'),
                ('machine','zone','us-west4-a'), ('machine','memoryMb',8192),
                ('image','architecture','ARM64'), ('image','status','PENDING'),
                ('image','id',''), ('image','selfLink','https://example.invalid/image'),
                ('image','deprecated',dict(state='DEPRECATED'))]:
            data = fixture(); data[section][key] = value
            with self.subTest(section=section, key=key): self.assertEqual('BLOCKED', p.inspect(data)['status'])

    def test_offline_files_are_hashed_without_mutating_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, data in fixture().items(): (root/(name+'.json')).write_text(json.dumps(data))
            before = {f.name:f.read_bytes() for f in root.iterdir()}
            result = p.read_inventory(root)
            self.assertEqual('PASS', result['status'])
            self.assertEqual(set(before), set(result['inputFiles']))
            self.assertEqual(before, {f.name:f.read_bytes() for f in root.iterdir()})
            (root/'image.json').unlink()
            with self.assertRaisesRegex(ValueError, 'missing regular'): p.read_inventory(root)


if __name__ == '__main__':
    unittest.main()
