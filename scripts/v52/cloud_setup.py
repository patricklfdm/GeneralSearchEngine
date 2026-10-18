"""Offline V5.2 identity/configuration review; never executes a deployment command."""
import argparse
from pathlib import Path
import shlex
from . import cloud_preflight as f, cloud_credentials as credentials, cloud_authority as a
from . import cloud_artifacts as artifacts, cloud_inputs as inputs
from .evidence import need, encoded, digest, strict

ROOT = Path(__file__).resolve().parents[2]
ROLES = dict(gseV52RunnerCompute=f.RUNNER, gseV52CleanupCompute=f.CLEANUP,
             gseV52RunnerIap=('iap.tunnelInstances.accessViaIAP',),
             gseV52BucketRead=('storage.buckets.get',), gseV52ObjectRead=('storage.objects.get',),
             gseV52ObjectCreate=('storage.objects.create',), gseV52ControlDelete=('storage.objects.delete',))
APIS = ('compute.googleapis.com', 'storage.googleapis.com', 'cloudresourcemanager.googleapis.com', 'iam.googleapis.com',
        'iamcredentials.googleapis.com', 'sts.googleapis.com', 'iap.googleapis.com')
SCHEMA = 'gse-v52-setup-review-v1'


def configuration():
    value = strict(inputs.regular(ROOT/f.CONFIG_PATH, 65536)); validate_configuration(value)
    return value


def validate_configuration(value):
    sha = f.configuration(value)
    # Use the quota policy actually implemented by the native preflight.
    need(value['provider']['diskType'] == 'pd-ssd' and
         value['provider']['machineType'].split('-', 1)[0] in ('e2', 'n2'), 'V5.2 setup quota policy')
    return sha


def proposal(cfg):
    sha = validate_configuration(cfg); c = cfg['provider']; project = c['project']
    scope = 'projects/'+project+'/roles/'; obj = 'projects/_/buckets/'+c['bucket']+'/objects/'
    def condition(title, expr):
        return dict(title=title, expression="resource.type == 'storage.googleapis.com/Object' && ("+expr+')')
    conditions = dict(
        read=condition('v52-control-read', "resource.name.startsWith('"+obj+a.PREFIX+"')"),
        mutable=condition('v52-mutable-control', ' || '.join("resource.name == '"+obj+k+"'" for k in (a.LEASE, a.LEDGER))),
        attempt=condition('v52-immutable-attempt', "resource.name.startsWith('"+obj+a.PREFIX+"attempts/')"))
    identities = {}; environments = {}; project_bindings = []; bucket_bindings = []
    # Scheduling is deliberately absent: manual cleanup is the operational prerequisite.
    for role in ('runner', 'manual'):
        selected = credentials.selection(c, cfg['projectNumber'], role)
        name = credentials.ROLES[role][0]; pool = selected['provider'].rsplit('/providers/', 1)[0]
        claims = dict(repository=credentials.REPOSITORY, repository_id=str(credentials.REPOSITORY_ID),
                      repository_owner_id=str(credentials.OWNER_ID), ref='refs/heads/master',
                      event_name=selected['event'], environment=selected['environment'],
                      workflow_ref=credentials.REPOSITORY+'/'+selected['workflow']+'@refs/heads/master')
        identities[role] = dict(selection=selected, name=name, pool=pool, claims=claims,
            attributeMapping={'google.subject':'assertion.sub', 'attribute.repository_id':'assertion.repository_id'},
            attributeCondition=' && '.join("assertion."+k+" == '"+v+"'" for k,v in claims.items()),
            principal='principalSet://iam.googleapis.com/'+pool+'/attribute.repository_id/'+str(credentials.REPOSITORY_ID),
            serviceAccountDisabled=True, poolDisabled=True, providerDisabled=True)
        environments[selected['environment']] = dict(body=dict(wait_timer=0, prevent_self_review=False,
            reviewers=[dict(type='User', id=credentials.OWNER_ID)],
            deployment_branch_policy=dict(protected_branches=False, custom_branch_policies=True)),
            branchPolicy=dict(name='master', type='branch'),
            secrets=['V52_EXPERIMENT_SSH_KEY'] if role=='runner' else [])
        def binding(role_name, **extra):
            return dict(role=scope+role_name, members=['serviceAccount:'+selected['serviceAccount']], **extra)
        project_bindings.append(binding('gseV52RunnerCompute' if role=='runner' else 'gseV52CleanupCompute'))
        if role=='runner':
            project_bindings.append(binding('gseV52RunnerIap', condition=dict(title='v52-ssh-only', expression='destination.port == 22')))
        bucket_bindings.extend([binding('gseV52BucketRead'), binding('gseV52ObjectRead', condition=conditions['read']),
            binding('gseV52ObjectCreate', condition=conditions['mutable']),
            binding('gseV52ObjectCreate', condition=conditions['attempt']),
            binding('gseV52ControlDelete', condition=conditions['mutable'])])
    return dict(schema=SCHEMA, execution='offline-setup-review-only', applied=False,
        configurationSha256=sha, configuration=cfg, identities=identities, environments=environments,
        roles={k:dict(title=k, stage='GA', includedPermissions=sorted(v)) for k,v in ROLES.items()},
        projectBindings=project_bindings, bucketBindings=bucket_bindings, requiredApis=list(APIS),
        paidAdmission=False, cleanupReady=False, fullRemoteQualification=False)


def files(cfg):
    """Closed review bundle: explicit argv and bodies, no apply subprocess or credentials."""
    value = proposal(cfg); c = cfg['provider']; project = '--project='+c['project']
    result = {'proposal.json':encoded(value), 'configuration.json':encoded(cfg)}
    read = []; stage = []; activate = {}; disable = {}
    def add(target, *args): target.append(list(args))
    add(read, 'gcloud', 'projects', 'describe', c['project'], '--format=json')
    add(read, 'gcloud', 'projects', 'get-iam-policy', c['project'], '--format=json')
    add(read, 'gcloud', 'services', 'list', project, '--enabled', '--format=json')
    add(read, 'gcloud', 'storage', 'buckets', 'describe', 'gs://'+c['bucket'], '--format=json')
    add(read, 'gcloud', 'storage', 'buckets', 'get-iam-policy', 'gs://'+c['bucket'], '--format=json')
    add(read, 'gcloud', 'compute', 'networks', 'describe', c['network'], project, '--format=json')
    add(read, 'gcloud', 'compute', 'networks', 'subnets', 'describe', c['subnetwork'], project,
        '--region='+c['region'], '--format=json')
    add(read, 'gcloud', 'compute', 'images', 'describe', c['imageName'], '--project='+c['imageProject'], '--format=json')
    for plural,key in (('machine-types','machineType'), ('disk-types','diskType')):
        add(read, 'gcloud', 'compute', plural, 'describe', c[key], project, '--zone='+c['zone'], '--format=json')
    for role, identity in value['identities'].items():
        selected=identity['selection']; name=identity['name']; sa=selected['serviceAccount']
        pool=['--location=global', project]; provider=[*pool, '--workload-identity-pool='+name]
        add(read, 'gcloud', 'iam', 'service-accounts', 'describe', sa, project, '--format=json')
        add(read, 'gcloud', 'iam', 'service-accounts', 'get-iam-policy', sa, project, '--format=json')
        add(read, 'gcloud', 'iam', 'workload-identity-pools', 'describe', name, *pool, '--format=json')
        add(read, 'gcloud', 'iam', 'workload-identity-pools', 'providers', 'describe', 'github', *provider, '--format=json')
        env_path='repos/'+credentials.REPOSITORY+'/environments/'+selected['environment']
        add(read, 'gh', 'api', '--method', 'GET', env_path)
        add(read, 'gh', 'api', '--method', 'GET', env_path+'/deployment-branch-policies', '--paginate')
        add(stage, 'gcloud', 'iam', 'service-accounts', 'create', name, project)
        add(stage, 'gcloud', 'iam', 'service-accounts', 'disable', sa, project)
        add(stage, 'gcloud', 'iam', 'workload-identity-pools', 'create', name, *pool, '--disabled')
        add(stage, 'gcloud', 'iam', 'workload-identity-pools', 'providers', 'create-oidc', 'github', *provider,
            '--disabled', '--issuer-uri=https://token.actions.githubusercontent.com',
            '--attribute-mapping='+','.join(k+'='+v for k,v in identity['attributeMapping'].items()),
            '--attribute-condition='+identity['attributeCondition'])
        add(stage, 'gcloud', 'iam', 'service-accounts', 'add-iam-policy-binding', sa, project,
            '--member='+identity['principal'], '--role=roles/iam.workloadIdentityUser', '--condition=None')
        activate[role] = [
            ['gcloud','iam','service-accounts','enable',sa,project],
            ['gcloud','iam','workload-identity-pools','update',name,*pool,'--no-disabled'],
            ['gcloud','iam','workload-identity-pools','providers','update-oidc','github',*provider,'--no-disabled']]
        disable[role] = [
            ['gcloud','iam','workload-identity-pools','providers','update-oidc','github',*provider,'--disabled'],
            ['gcloud','iam','workload-identity-pools','update',name,*pool,'--disabled'],
            ['gcloud','iam','service-accounts','disable',sa,project]]
    for name, role in value['roles'].items():
        result[name+'.json']=encoded(role)
        add(read,'gcloud','iam','roles','describe',name,project,'--format=json')
        add(stage,'gcloud','iam','roles','create',name,project,'--file='+name+'.json')
    for kind in ('project','bucket'):
        for index,binding in enumerate(value[kind+'Bindings']):
            flag='--condition=None'
            if 'condition' in binding:
                name=f'{kind}-condition-{index}.json';result[name]=encoded(binding['condition']);flag='--condition-from-file='+name
            command=(['gcloud','projects','add-iam-policy-binding',c['project']] if kind=='project' else
                     ['gcloud','storage','buckets','add-iam-policy-binding','gs://'+c['bucket']])
            add(stage,*command,'--member='+binding['members'][0],'--role='+binding['role'],flag)
    for name,environment in value['environments'].items():
        result[name+'.json']=encoded(environment['body']);result[name+'-branch.json']=encoded(environment['branchPolicy'])
        endpoint='repos/'+credentials.REPOSITORY+'/environments/'+name
        add(stage,'gh','api','--method','PUT',endpoint,'--input',name+'.json')
        add(stage,'gh','api','--method','POST',endpoint+'/deployment-branch-policies','--input',name+'-branch.json')
    commands=dict(inspect=read, stageDisabled=stage, activate=activate, disable=disable)
    result['commands.json']=encoded(commands)
    lines=['# V5.2 setup commands (not executed)', '',
           'Read PHASE_6_CLOUD_SETUP.md before application. Run only from this generated directory. '
           'Inspect original state first; HTTP 403 is not absence. Existing identities, roles or environments '
           'require a separate diff review. Staging is create-only; do not blindly replay partial failures.', '']
    for title, rows in [('Inspect only',read), ('Stage disabled after operator authorization',stage),
                        *[(f'Activate {role} after staged-state review',rows) for role,rows in activate.items()],
                        *[(f'Disable {role} after live-lease review',rows) for role,rows in disable.items()]]:
        lines.extend(['## '+title,'','```bash','set -euo pipefail',*(shlex.join(row) for row in rows),'```',''])
    lines.extend(['Disabling WIF does not revoke already issued tokens. Keep manual cleanup usable while an owned '
                  'lease may still need reconciliation. These commands do not delete resources, evidence, ledger, '
                  'other version identities or shared bucket settings.', ''])
    result['COMMANDS.md']='\n'.join(lines).encode()
    return result


def write(output, cfg):
    content=files(cfg); output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)), 'V5.2 setup output link')
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in content.items():
        with (output/name).open('xb') as stream: stream.write(raw)
    artifacts.save(output/'manifest.json',dict(schema=SCHEMA, status='REVIEW_ONLY', applied=False,
        configurationSha256=f.configuration(cfg), files={name:digest(raw) for name,raw in content.items()}))
    return check(output, cfg)


def check(output, cfg):
    output=Path(output); need(not any(p.is_symlink() for p in (output,*output.parents)), 'V5.2 setup output link')
    expected=files(cfg)
    need(set(p.name for p in output.iterdir()) == set(expected)|{'manifest.json'}, 'V5.2 setup inventory')
    for name,raw in expected.items():
        need(inputs.regular(output/name, 1<<20)==raw, 'V5.2 setup file drift: '+name)
    manifest=strict(inputs.regular(output/'manifest.json',65536))
    need(manifest==dict(schema=SCHEMA,status='REVIEW_ONLY',applied=False,configurationSha256=f.configuration(cfg),
        files={name:digest(raw) for name,raw in expected.items()}), 'V5.2 setup manifest drift')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('generate','check'))
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=(write if args.action=='generate' else check)(args.output,configuration())
    print(encoded(dict(status=result['status'],applied=False,files=len(result['files']),output=str(args.output))).decode())
