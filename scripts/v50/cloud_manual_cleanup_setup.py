"""Offline proposal for a separate manual cleanup principal using existing cleanup roles."""
import argparse
import json
from pathlib import Path
import shlex
from .cloud_common import plan
from . import cloud_cleanup as cleanup


def write_proposal(output, p):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    who = cleanup.identity(p, trigger='manual'); member = 'serviceAccount:' + who['serviceAccount']
    roles = {cleanup.PROJECT_ROLE: sorted(cleanup.PROJECT_PERMISSIONS),
             cleanup.EVIDENCE_ROLE: ['storage.objects.create', 'storage.objects.get'],
             'gseV50ControlDeleter': ['storage.objects.delete']}
    value = dict(schema='gse-v50-manual-cleanup-setup-v1', execution='offline-proposal-only', applied=False,
                 identity=who, attributeMapping=cleanup.attribute_mapping('manual'),
                 attributeCondition=cleanup.condition(p, trigger='manual'), leaseCondition=cleanup.lease_condition(p),
                 reusedRoles=roles, approvalEnvironment=p['environment'], cleanupEnvironment=cleanup.ENVIRONMENT)
    def save(name, data): (output / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    save('proposal.json', value); save('lease-condition.json', value['leaseCondition'])
    commands = []; project = '--project=' + p['project']
    def add(*args): commands.append(list(args))
    # Exact role contents are checked before any binding. Reuse does not authorize
    # silently broadening a role shared with the unattended cleanup principal.
    for name, permissions in roles.items():
        script = ('import json,subprocess,sys; r=json.loads(subprocess.check_output(' +
                  repr(['gcloud', 'iam', 'roles', 'describe', name, project, '--format=json']) + ')); '
                  'sys.exit(None if r.get("name")==' + repr('projects/' + p['project'] + '/roles/' + name) +
                  ' and not r.get("deleted",False) and r.get("stage")=="GA" and '
                  'set(r.get("includedPermissions",[]))==set(' + repr(permissions) +
                  ') else "cleanup role drift; review before binding")')
        add('python3', '-c', script)
    add('gcloud', 'iam', 'service-accounts', 'create', 'gse-v50-manual-cleanup', project,
        '--display-name=GSE V5 safe manual cleanup')
    add('gcloud', 'iam', 'workload-identity-pools', 'providers', 'create-oidc', who['provider'], project,
        '--issuer-uri=https://token.actions.githubusercontent.com',
        '--attribute-mapping=' + ','.join(k + '=' + v for k, v in value['attributeMapping'].items()),
        '--attribute-condition=' + value['attributeCondition'])
    add('gcloud', 'projects', 'add-iam-policy-binding', p['project'], '--member=' + member,
        '--role=projects/' + p['project'] + '/roles/' + cleanup.PROJECT_ROLE, '--condition=None')
    add('gcloud', 'storage', 'buckets', 'add-iam-policy-binding', 'gs://' + p['bucket'], '--member=' + member,
        '--role=projects/' + p['project'] + '/roles/' + cleanup.EVIDENCE_ROLE, '--condition=None')
    add('gcloud', 'storage', 'buckets', 'add-iam-policy-binding', 'gs://' + p['bucket'], '--member=' + member,
        '--role=projects/' + p['project'] + '/roles/gseV50ControlDeleter', '--condition-from-file=lease-condition.json')
    add('gcloud', 'iam', 'service-accounts', 'add-iam-policy-binding', who['serviceAccount'], project,
        '--member=' + who['principal'], '--role=roles/iam.workloadIdentityUser', '--condition=None')
    save('commands.json', commands)
    (output / 'APPLY.md').write_text(
        '# Safe manual cleanup configuration\n\n'
        'This is an offline proposal. Review the exact principal and role contents before applying. '
        'Verify the new service account and WIF provider are absent; inspect existing objects instead of overwriting them. '
        'The existing scheduled/paid WIF providers, role definitions, environments and their approval rules stay intact.\n\n'
        'The manual workflow first uses the existing paid environment for operator approval, without cloud credentials. '
        'Only its dependent cleanup job enters the existing cleanup environment and shared cleanup concurrency group. '
        'Its new WIF provider allows only the manual workflow_dispatch event on protected master.\n\n'
        '```bash\nset -euo pipefail\n' + '\n'.join(shlex.join(c) for c in commands) + '\n```\n\n'
        'Read back all bindings and bucket IAM policy version 3. The new principal has compute read/delete, '
        'evidence get/create and conditional deletion of only the exact active lease. It cannot create a topology, '
        'delete budget/sequence ledgers or impersonate the experiment account. After merge, manually dispatch '
        '`v50-manual-cleanup.yml` on master and approve the authorization job. No lease returns PASS; an active lease '
        'returns WAITING; only expiry plus operation grace permits reconciliation.\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); write_proposal(args.output, plan())
    print(json.dumps(dict(execution='offline-proposal-only', applied=False, output=str(args.output))))
