"""Offline proposal for an isolated cleanup identity and its unattended environment."""
import argparse
import json
from pathlib import Path
import shlex
from .cloud_common import plan
from . import cloud_cleanup as cleanup


def write_proposal(output, p):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    who = cleanup.identity(p); member = 'serviceAccount:' + who['serviceAccount']
    roles = {
        cleanup.PROJECT_ROLE: dict(title='GSE V5 expired cleanup', description='Read and delete owned expired compute resources; no creation',
                                  stage='GA', includedPermissions=sorted(cleanup.PROJECT_PERMISSIONS)),
        cleanup.EVIDENCE_ROLE: dict(title='GSE V5 cleanup evidence', description='Read ownership lease and append reconciliation evidence',
                                   stage='GA', includedPermissions=['storage.objects.create', 'storage.objects.get'])}
    value = dict(schema='gse-v50-cleanup-setup-v1', applied=False, execution='offline-proposal-only',
                 identity=who, roles=roles, attributeMapping=cleanup.ATTRIBUTE_MAPPING,
                 attributeCondition=cleanup.condition(p), leaseCondition=cleanup.lease_condition(p),
                 environment=dict(wait_timer=0, reviewers=[], prevent_self_review=False,
                                  deployment_branch_policy=dict(protected_branches=False, custom_branch_policies=True)),
                 branchPolicy=dict(name='master', type='branch'))
    def save(name, obj): (output / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')
    save('proposal.json', value)
    for name, role in roles.items(): save(name + '.json', role)
    save('lease-condition.json', value['leaseCondition'])
    save('environment.json', value['environment']); save('branch-policy.json', value['branchPolicy'])
    (output / 'cleanup-wif.cel').write_text(value['attributeCondition'] + '\n')
    commands = []
    def add(*args): commands.append(list(args))
    project = '--project=' + p['project']
    add('gcloud', 'services', 'enable', 'iap.googleapis.com', project)
    add('gcloud', 'iam', 'roles', 'update', 'gseV50RunnerSupplement', project,
        '--add-permissions=compute.networks.getRegionEffectiveFirewalls,compute.networks.updatePolicy,compute.instances.setTags,compute.instances.setLabels,compute.disks.setLabels,serviceusage.services.get')
    add('gcloud', 'iam', 'service-accounts', 'create', 'gse-v50-cleanup', project, '--display-name=GSE V5 expired resource cleanup')
    add('gcloud', 'iam', 'workload-identity-pools', 'providers', 'create-oidc', who['provider'], project,
        '--issuer-uri=https://token.actions.githubusercontent.com',
        '--attribute-mapping=' + ','.join(k + '=' + v for k, v in value['attributeMapping'].items()),
        '--attribute-condition=' + value['attributeCondition'])
    for name in roles:
        add('gcloud', 'iam', 'roles', 'create', name, project, '--file=' + name + '.json')
        role = '--role=projects/' + p['project'] + '/roles/' + name
        if name == cleanup.PROJECT_ROLE:
            add('gcloud', 'projects', 'add-iam-policy-binding', p['project'], '--member=' + member, role, '--condition=None')
        else:
            add('gcloud', 'storage', 'buckets', 'add-iam-policy-binding', 'gs://' + p['bucket'], '--member=' + member, role, '--condition=None')
    add('gcloud', 'storage', 'buckets', 'add-iam-policy-binding', 'gs://' + p['bucket'], '--member=' + member,
        '--role=projects/' + p['project'] + '/roles/gseV50ControlDeleter', '--condition-from-file=lease-condition.json')
    add('gcloud', 'iam', 'service-accounts', 'add-iam-policy-binding', who['serviceAccount'], project,
        '--member=' + who['principal'], '--role=roles/iam.workloadIdentityUser', '--condition=None')
    environment = 'repos/' + p['repository'] + '/environments/' + cleanup.ENVIRONMENT
    add('gh', 'api', '--method', 'PUT', environment, '--input', 'environment.json')
    add('gh', 'api', '--method', 'POST', environment + '/deployment-branch-policies', '--input', 'branch-policy.json')
    save('commands.json', commands)
    (output / 'APPLY.md').write_text(
        '# Isolated V5 cleanup configuration\n\n'
        'Review the proposal and verify the new cleanup service account, provider, two roles and environment do not exist. '
        'An existing object is a stop: inspect it; never replace its policy blindly. Verify the existing '
        '`gseV50ControlDeleter` grants only `storage.objects.delete`. Run from this directory after authorization. '
        'The shared experiment environment/provider and their approval rules are not modified.\n\n'
        'The new WIF provider maps only `attribute.gse_v50_cleanup` and a prefixed subject. It cannot match the '
        'experiment account\'s `attribute.repository_id` impersonation grant. The cleanup account gets compute '
        'read/delete plus the network updatePolicy permission required for firewall deletion, bucket object read/create, '
        'and deletion of only the exact V5 active lease.\n\n'
        '```bash\nset -euo pipefail\n' + '\n'.join(shlex.join(c) for c in commands) + '\n```\n\n'
        'Read back all bindings and bucket policy version 3. Confirm the cleanup environment allows only master, '
        'has no reviewers/timers/custom protection rules, and that the paid environment is unchanged. '
        'After merge/full CI, obtain a successful scheduled or separately configured safe manual cleanup and refresh workflow preflight. '
        'This setup does not launch an experiment.\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    write_proposal(args.output, plan())
    print(json.dumps(dict(execution='offline-proposal-only', applied=False, output=str(args.output))))
