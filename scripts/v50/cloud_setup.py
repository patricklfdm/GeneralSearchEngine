"""Generate a local, reviewable IAM/WIF proposal; never contact or mutate GCP."""
import argparse
import difflib
import json
from pathlib import Path
import shlex
from .cloud_common import canonical, plan, read, require, sha
from .cloud_preflight import PROJECT_PERMISSIONS, claims, condition_allows_only

BASE_ROLE = 'gseCloudBenchmarkRunner'
SUPPLEMENT_ROLE = 'gseV50RunnerSupplement'
METADATA_ROLE = 'gseV50EvidenceMetadataReader'
DELETE_ROLE = 'gseV50ControlDeleter'


def proposal(p, provider, runner_role, project_policy):
    require(provider['name'] == p['wifProvider'] and provider['state'] == 'ACTIVE' and
            not provider.get('disabled', False) and
            provider['oidc']['issuerUri'] == 'https://token.actions.githubusercontent.com', 'provider identity/status')
    base_role = 'projects/' + p['project'] + '/roles/' + BASE_ROLE
    member = 'serviceAccount:' + p['serviceAccount']
    require(runner_role['name'] == base_role and not runner_role.get('deleted', False) and
            runner_role.get('stage') in ('ALPHA', 'BETA', 'GA'), 'runner role identity/status')
    permissions = runner_role['includedPermissions']
    require(isinstance(permissions, list) and all(isinstance(v, str) for v in permissions), 'runner role permissions')
    require(any(b.get('role') == base_role and member in b.get('members', []) and 'condition' not in b
                for b in project_policy['bindings']), 'base runner role must have an unconditional service-account binding')
    before = provider['attributeCondition']
    strict = ' && '.join("assertion." + k + " == '" + v + "'" for k, v in claims(p).items())
    # Preserve the existing expression verbatim. Both alternatives must enforce
    # every repository/ref/environment guard; the closed evaluator proves this.
    after = '(' + before + ') || (' + strict + ')'
    condition_allows_only(after, claims(p))
    try: condition_allows_only(before, claims(p)); after = before
    except ValueError: pass  # Only the new workflow is missing; after was checked.
    roles = {}
    missing = sorted(set(PROJECT_PERMISSIONS) - set(permissions))
    if missing:
        roles[SUPPLEMENT_ROLE] = dict(title='GSE V5 runner supplement', description='Additional V5 lifecycle and preflight permissions',
                                     stage='GA', includedPermissions=missing)
    roles[METADATA_ROLE] = dict(title='GSE V5 evidence metadata reader', description='Read evidence bucket metadata',
                               stage='GA', includedPermissions=['storage.buckets.get'])
    roles[DELETE_ROLE] = dict(title='GSE V5 control object deleter', description='Bind only with the V5 control-object condition',
                             stage='GA', includedPermissions=['storage.objects.delete'])
    prefix = 'projects/_/buckets/' + p['bucket'] + '/objects/' + p['evidencePrefix'] + '/control/'
    condition = dict(title='v50-control-prefix-delete', description='Lease deletion and conditional control-ledger replacement',
                     expression="resource.type == 'storage.googleapis.com/Object' && resource.name.startsWith('" + prefix + "')")
    return dict(schema='gse-v50-cloud-setup-proposal-v1', execution='offline-proposal-only', applied=False,
                planSha256=sha(canonical(p)), inputSha256={name: sha(canonical(value)) for name, value in
                    [('provider', provider), ('runnerRole', runner_role), ('projectPolicy', project_policy)]},
                member=member, project=p['project'], bucket=p['bucket'], provider=p['wifProvider'],
                wifBefore=before, wifAfter=after, roles=roles, deleteCondition=condition)


def write_proposal(output, p, provider, runner_role, project_policy):
    value = proposal(p, provider, runner_role, project_policy)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    def save(name, obj): (output / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')
    save('proposal.json', value)
    for name, obj in [('provider-before', provider), ('runner-role-before', runner_role), ('project-policy-before', project_policy)]:
        save(name + '.json', obj)
    for name, obj in value['roles'].items(): save(name + '.json', obj)
    save('control-delete-condition.json', value['deleteCondition'])
    for name in ('Before', 'After'): (output / ('wif-' + name.lower() + '.cel')).write_text(value['wif' + name] + '\n')
    (output / 'wif.diff').write_text(''.join(difflib.unified_diff(
        (value['wifBefore'] + '\n').splitlines(True), (value['wifAfter'] + '\n').splitlines(True), fromfile='before', tofile='after')))
    project = '--project=' + p['project']; member = '--member=' + value['member']
    commands = []
    def add(*args): commands.append(shlex.join(args))
    # Re-read all inputs before the first mutation. Any drift requires a new review.
    for name, command in [
            ('provider', ['gcloud', 'iam', 'workload-identity-pools', 'providers', 'describe', p['wifProvider'], project]),
            ('runner-role', ['gcloud', 'iam', 'roles', 'describe', BASE_ROLE, project]),
            ('project-policy', ['gcloud', 'projects', 'get-iam-policy', p['project']])]:
        commands.append(shlex.join([*command, '--format=json']) + ' > ' + name + '-current.json')
        add('python3', '-c', 'import json, sys; sys.exit(None if json.load(open("' + name +
            '-before.json")) == json.load(open("' + name + '-current.json")) else "cloud setup input changed; regenerate and review")')
    if value['wifBefore'] != value['wifAfter']:
        commands.append(shlex.join(['gcloud', 'iam', 'workload-identity-pools', 'providers', 'update-oidc', p['wifProvider'], project]) +
                        ' --attribute-condition="$(cat wif-after.cel)"')
    for role in value['roles']:
        add('gcloud', 'iam', 'roles', 'create', role, project, '--file=' + role + '.json')
        full_role = '--role=projects/' + p['project'] + '/roles/' + role
        if role == SUPPLEMENT_ROLE:
            add('gcloud', 'projects', 'add-iam-policy-binding', p['project'], member, full_role, '--condition=None')
        else:
            condition = '--condition-from-file=control-delete-condition.json' if role == DELETE_ROLE else '--condition=None'
            add('gcloud', 'storage', 'buckets', 'add-iam-policy-binding', 'gs://' + p['bucket'], member, full_role, condition)
    (output / 'APPLY.md').write_text(
        '# Cloud configuration proposal — review before execution\n\n'
        'No command has been executed. Run from this generated directory only after configuration review. '
        'The project supplement affects the shared service account and its existing workflows. '
        'Bucket metadata access is read-only; object deletion is bound only to the V5 control prefix.\n\n'
        'Use a fresh shell with fail-fast enabled. Any failed command stops setup. If a role already exists, '
        'inspect its definition and bindings; do not blindly replace it. Input comparisons detect earlier '
        'changes but are not an atomic lock against concurrent administrators.\n\n'
        '```bash\nset -euo pipefail\n' + '\n'.join(commands) + '\n```\n\n'
        'Read back the provider and bucket IAM policy version 3 after applying. Follow '
        '`docs/v5x/v5.0/PHASE_6_CLOUD_SETUP.md` for scheduled cleanup and workflow-identity preflight. '
        'This proposal neither enables cleanup nor authorizes paid execution.\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provider', type=Path, required=True)
    parser.add_argument('--runner-role', type=Path, required=True)
    parser.add_argument('--project-policy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = write_proposal(args.output, plan(), read(args.provider), read(args.runner_role), read(args.project_policy))
    print(json.dumps(dict(execution=result['execution'], applied=False, output=str(args.output))))
