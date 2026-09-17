"""Exact scheduled/manual cleanup identities; one shared deletion authority."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import urllib.parse
from .cloud_common import plan, require, save
from .cloud_gcp import Api
from .cloud_runner import LEASE, BUDGET
from .cloud_presets import SEQUENCES

WORKFLOW = '.github/workflows/v50-expired-cleanup.yml'
MANUAL_WORKFLOW = '.github/workflows/v50-manual-cleanup.yml'
MANUAL_APPROVAL_JOB = 'Authorize manual cleanup'
ENVIRONMENT = 'cloud-benchmark-cleanup'
IDENTITY_STEP = 'Verify cleanup identity and permissions'
CLEANUP_STEP = 'Reconcile only an expired retained ownership lease'
PROJECT_ROLE = 'gseV50CleanupRunner'
EVIDENCE_ROLE = 'gseV50CleanupEvidence'
PROJECT_PERMISSIONS = ['compute.disks.get', 'compute.disks.delete',
    'compute.instances.get', 'compute.instances.delete', 'compute.firewalls.get', 'compute.firewalls.delete',
    'compute.networks.updatePolicy',  # Required by firewalls.delete as well as insert.
    'compute.zoneOperations.get', 'compute.zoneOperations.list',
    'compute.globalOperations.get', 'compute.globalOperations.list']
FORBIDDEN_PERMISSIONS = ['compute.instances.create', 'compute.disks.create', 'compute.firewalls.create',
    'compute.disks.setLabels', 'compute.projects.setCommonInstanceMetadata',
    'compute.instances.setMetadata', 'compute.instances.setTags', 'compute.instances.setLabels',
    'compute.instances.attachDisk', 'compute.instances.detachDisk']
ATTRIBUTE_MAPPING = {'google.subject': "'v50-cleanup:' + assertion.sub",
                     'attribute.gse_v50_cleanup': 'assertion.repository_id'}


def workflow(trigger='schedule'):
    require(trigger in ('schedule', 'manual'), 'unknown cleanup trigger')
    return WORKFLOW if trigger == 'schedule' else MANUAL_WORKFLOW


def trigger_for(path, event):
    for trigger, expected in [('schedule', 'schedule'), ('manual', 'workflow_dispatch')]:
        if path == workflow(trigger) and event == expected: return trigger
    raise ValueError('wrong cleanup workflow/event')


def attribute_mapping(trigger='schedule'):
    workflow(trigger)
    return dict(ATTRIBUTE_MAPPING) if trigger == 'schedule' else {
        'google.subject': "'v50-manual-cleanup:' + assertion.sub",
        'attribute.gse_v50_manual_cleanup': 'assertion.repository_id'}


def identity(p, *, trigger='schedule'):
    workflow(trigger)
    pool = p['wifProvider'].rsplit('/providers/', 1)[0]
    manual = trigger == 'manual'
    return dict(provider=pool + '/providers/' + ('v50-manual-cleanup' if manual else 'v50-expired-cleanup'),
                serviceAccount=('gse-v50-manual-cleanup' if manual else 'gse-v50-cleanup') + '@' + p['project'] + '.iam.gserviceaccount.com',
                principal='principalSet://iam.googleapis.com/' + pool +
                          ('/attribute.gse_v50_manual_cleanup/' if manual else '/attribute.gse_v50_cleanup/') + p['repositoryId'])


def claims(p, *, trigger='schedule'):
    return dict(repository=p['repository'], repository_id=p['repositoryId'], repository_owner_id=p['repositoryOwnerId'],
                ref=p['ref'], environment=ENVIRONMENT, event_name='workflow_dispatch' if trigger == 'manual' else 'schedule',
                workflow_ref=p['repository'] + '/' + workflow(trigger) + '@' + p['ref'])


def condition(p, *, trigger='schedule'):
    return ' && '.join("assertion." + k + " == '" + v + "'" for k, v in claims(p, trigger=trigger).items())


def lease_condition(p):
    return dict(title='v50-cleanup-lease-delete', description='Only the expired V5 ownership lease',
                expression="resource.type == 'storage.googleapis.com/Object' && resource.name == 'projects/_/buckets/" +
                           p['bucket'] + "/objects/" + LEASE + "'")


def require_context(p, env=None, *, trigger='schedule'):
    env = os.environ if env is None else env
    expected = claims(p, trigger=trigger)
    require(env.get('GITHUB_EVENT_NAME') == expected['event_name'] and env.get('GITHUB_REF') == p['ref'] and
            env.get('GITHUB_WORKFLOW_REF') == expected['workflow_ref'],
            'dedicated ' + ('scheduled' if trigger == 'schedule' else 'manual') + ' protected-master cleanup only')


def check_environment(environment, branches, custom_rules):
    require(isinstance(environment, dict) and 'error' not in environment, 'cleanup environment query failed: ' + str(environment))
    require(environment.get('name') == ENVIRONMENT, 'cleanup environment identity')
    rules = environment.get('protection_rules')
    require(isinstance(rules, list) and all(isinstance(r, dict) and r.get('type') == 'branch_policy' for r in rules),
            'cleanup environment must not wait for reviewers, timers or deployment protection rules')
    require(environment.get('deployment_branch_policy') == dict(protected_branches=False, custom_branch_policies=True),
            'cleanup environment requires an exact master branch policy')
    require(isinstance(custom_rules, dict) and 'error' not in custom_rules and custom_rules.get('total_count') == 0 and
            custom_rules.get('custom_deployment_protection_rules') == [], 'cleanup custom deployment protection rules must be empty')
    require(isinstance(branches, dict) and 'error' not in branches and branches.get('total_count') == 1 and
            isinstance(branches.get('branch_policies'), list) and len(branches['branch_policies']) == 1 and
            isinstance(branches['branch_policies'][0], dict) and
            branches['branch_policies'][0].get('name') == 'master' and
            branches['branch_policies'][0].get('type') == 'branch', 'cleanup environment must allow only the master branch')


def permission_set(response, scope):
    require(isinstance(response, dict) and 'error' not in response, scope + ' permission query failed')
    values = response.get('permissions', [])
    require(isinstance(values, list) and all(isinstance(v, str) for v in values), scope + ' permission response malformed')
    return set(values)


def verify(p, api=None, *, trigger='schedule'):
    """Effective permission checks run under the cleanup SA before reading a lease."""
    require_context(p, trigger=trigger)
    api = api or Api()
    auth = subprocess.run(['gcloud', 'auth', 'list', '--filter=status:ACTIVE', '--format=value(account)'],
                          capture_output=True, text=True, timeout=30)
    require(auth.returncode == 0 and auth.stdout.strip() == identity(p, trigger=trigger)['serviceAccount'], 'cleanup service account identity')
    result = api.call('POST', 'https://cloudresourcemanager.googleapis.com/v1/projects/' + p['project'] + ':testIamPermissions',
                      dict(permissions=PROJECT_PERMISSIONS + FORBIDDEN_PERMISSIONS))
    actual = permission_set(result, 'project')
    require(set(PROJECT_PERMISSIONS) <= actual, 'missing cleanup project permissions')
    require(not set(FORBIDDEN_PERMISSIONS) & actual, 'cleanup account can create or modify a topology')
    base = 'https://storage.googleapis.com/storage/v1/b/' + p['bucket']
    storage = api.call('GET', base + '/iam/testPermissions?' + urllib.parse.urlencode(
        {'permissions': ['storage.objects.get', 'storage.objects.create']}, doseq=True))
    require(permission_set(storage, 'bucket') >= {'storage.objects.get', 'storage.objects.create'}, 'cleanup evidence read/create permissions')
    for name in (LEASE, BUDGET, SEQUENCES, p['evidencePrefix'] + '/cleanup-permission-probe.json'):
        access = api.call('GET', base + '/o/' + urllib.parse.quote(name, safe='') + '/iam/testPermissions?permissions=storage.objects.delete')
        require(('storage.objects.delete' in permission_set(access, name)) == (name == LEASE), 'cleanup delete scope: ' + name)
    return dict(status='PASS', principal=auth.stdout.strip(), trigger=trigger,
                topologyCreationAllowed=False, deleteScopeProbes='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--trigger', choices=('schedule', 'manual'), default='schedule')
    args = parser.parse_args()
    result = verify(plan(), trigger=args.trigger); save(args.output, result); print(json.dumps(result))
