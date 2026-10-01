"""Offline proposals for disabled V5.1 runner and cleanup identities; never applies."""
import argparse
from pathlib import Path
import shlex
from . import cloud_authority as a, cloud_ci as ci, cloud_preflight as p, performance_model as m, remote_command as c

# Permissions follow the current Compute adapter's requests, including fields that
# have independent permission checks at insertion. This is not a future-fault grant.
CLEANUP_COMPUTE = (
    'compute.disks.get', 'compute.disks.delete', 'compute.instances.get', 'compute.instances.delete',
    'compute.firewalls.get', 'compute.firewalls.delete', 'compute.networks.updatePolicy',
    'compute.zoneOperations.get', 'compute.zoneOperations.list',
    'compute.globalOperations.get', 'compute.globalOperations.list')
RUNNER_COMPUTE = CLEANUP_COMPUTE + (
    'compute.projects.get', 'compute.regions.get', 'compute.zones.get', 'compute.machineTypes.get',
    'compute.images.get', 'compute.images.useReadOnly', 'compute.diskTypes.get',
    'compute.disks.create', 'compute.disks.setLabels', 'compute.disks.use',
    'compute.instances.create', 'compute.instances.setLabels', 'compute.instances.setMetadata',
    'compute.instances.setTags', 'compute.instances.getGuestAttributes',
    'compute.firewalls.create', 'compute.networks.get', 'compute.subnetworks.get', 'compute.subnetworks.use')
ROLES = dict(gseV51RunnerCompute=RUNNER_COMPUTE, gseV51CleanupCompute=CLEANUP_COMPUTE,
             gseV51RunnerIap=('iap.tunnelInstances.accessViaIAP',),
             gseV51CloudBucketRead=('storage.buckets.get',),
             gseV51CloudObjectRead=('storage.objects.get',),
             gseV51CloudObjectCreate=('storage.objects.create',),
             gseV51CloudControlDelete=('storage.objects.delete',))
TRIGGERS = dict(runner=('gse-v51-runner', a.RUNNER_WORKFLOW, 'workflow_dispatch', a.ENVIRONMENT),
                schedule=('gse-v51-cleanup', a.CLEANUP_WORKFLOWS['schedule'], 'schedule', 'v51-cloud-cleanup'),
                manual=('gse-v51-manual-cleanup', a.CLEANUP_WORKFLOWS['workflow_dispatch'], 'workflow_dispatch', 'v51-cloud-manual-cleanup'))
STAGING = 'disabled-service-account-pool-and-provider'


def environment(name, approval):
    return dict(name=name, reuse=name == a.ENVIRONMENT,
                body=dict(wait_timer=0, prevent_self_review=False,
                          reviewers=[dict(type='User', id=ci.OWNER_ID)] if approval else [],
                          deployment_branch_policy=dict(protected_branches=False, custom_branch_policies=True)),
                branchPolicy=dict(name='master', type='branch'))


def proposal(cfg):
    digest = p.configuration(cfg); project = cfg['provider']['project']; bucket = cfg['provider']['bucket']
    scope = 'projects/'+project+'/roles/'
    obj = 'projects/_/buckets/'+bucket+'/objects/'
    def condition(title, expression):return dict(title=title, expression="resource.type == 'storage.googleapis.com/Object' && ("+expression+')')
    conditions = dict(
        controlRead=condition('v51-cloud-control-read', "resource.name.startsWith('"+obj+a.PREFIX+"')"),
        controlMutable=condition('v51-cloud-mutable-objects', ' || '.join("resource.name == '"+obj+key+"'" for key in (a.LEASE, a.LEDGER))),
        attemptCreate=condition('v51-cloud-attempt-evidence', "resource.name.startsWith('"+obj+a.PREFIX+"attempts/')"))
    identities = {}
    for trigger, (name, workflow, event, env) in TRIGGERS.items():
        pool = 'projects/'+cfg['projectNumber']+'/locations/global/workloadIdentityPools/'+name
        claims = dict(repository=ci.REPOSITORY, repository_id=str(ci.REPOSITORY_ID), repository_owner_id=str(ci.OWNER_ID),
                      ref='refs/heads/master', event_name=event, environment=env,
                      workflow_ref=ci.REPOSITORY+'/'+workflow+'@refs/heads/master')
        identities[trigger] = dict(name=name, serviceAccount=name+'@'+project+'.iam.gserviceaccount.com',
            pool=pool, provider=pool+'/providers/github', workflow=workflow, environment=env, claims=claims,
            attributeMapping={'google.subject':'assertion.sub', 'attribute.repository_id':'assertion.repository_id'},
            attributeCondition=' && '.join("assertion."+k+" == '"+v+"'" for k,v in claims.items()),
            principal='principalSet://iam.googleapis.com/'+pool+'/attribute.repository_id/'+str(ci.REPOSITORY_ID),
            serviceAccountDisabled=True, poolDisabled=True, providerDisabled=True)
    project_bindings, bucket_bindings = [], []
    for trigger, identity in identities.items():
        member = 'serviceAccount:'+identity['serviceAccount']
        def binding(role, **extra):return dict(role=scope+role, members=[member], **extra)
        project_bindings.append(binding('gseV51RunnerCompute' if trigger == 'runner' else 'gseV51CleanupCompute'))
        if trigger == 'runner':
            project_bindings.append(binding('gseV51RunnerIap', condition=dict(title='v51-runner-ssh-only', expression='destination.port == 22')))
        bucket_bindings.extend([
            binding('gseV51CloudBucketRead'),
            binding('gseV51CloudObjectRead', condition=conditions['controlRead']),
            binding('gseV51CloudObjectCreate', condition=conditions['controlMutable']),
            binding('gseV51CloudObjectCreate', condition=conditions['attemptCreate']),
            binding('gseV51CloudControlDelete', condition=conditions['controlMutable'])])
    return dict(schema='gse-v51-staged-identities-v1', execution='offline-proposal-only', applied=False,
        staging=STAGING, configurationSha256=digest, project=project, projectNumber=cfg['projectNumber'], bucket=bucket,
        identities=identities, roles={name:dict(title=name, stage='GA', includedPermissions=sorted(permissions)) for name,permissions in ROLES.items()},
        environments={name:environment(name, trigger != 'schedule') for trigger,(_,_,_,name) in TRIGGERS.items()},
        projectBindings=project_bindings, bucketBindings=bucket_bindings,
        paidAdmission=False, cleanupReady=False, fullRemoteQualification=False)


def write(output, cfg):
    value = proposal(cfg); output = Path(output); output.mkdir(parents=True, exist_ok=False)
    def save(name, obj):c.write_once(output/name, obj)
    save('proposal.json',value);save('configuration.json',cfg)
    commands=[]
    def add(*args):commands.append(list(args))
    project='--project='+value['project']
    # Each freshly created SA is disabled BEFORE any role grant or impersonation binding.
    for identity in value['identities'].values():
        name=identity['name'];sa=identity['serviceAccount']
        add('gcloud','iam','service-accounts','create',name,project)
        add('gcloud','iam','service-accounts','disable',sa,project)
        add('gcloud','iam','workload-identity-pools','create',name,project,'--location=global','--disabled')
        add('gcloud','iam','workload-identity-pools','providers','create-oidc','github',project,'--location=global',
            '--workload-identity-pool='+name,'--disabled','--issuer-uri=https://token.actions.githubusercontent.com',
            '--attribute-mapping='+','.join(k+'='+v for k,v in identity['attributeMapping'].items()),
            '--attribute-condition='+identity['attributeCondition'])
        add('gcloud','iam','service-accounts','add-iam-policy-binding',sa,project,
            '--member='+identity['principal'],'--role=roles/iam.workloadIdentityUser','--condition=None')
    for name,role in value['roles'].items():
        save(name+'.json',role)
        add('gcloud','iam','roles','create',name,project,'--file='+name+'.json')
    for kind in ('project','bucket'):
        for i,b in enumerate(value[kind+'Bindings']):
            flag='--condition=None'
            if 'condition' in b:
                name=f'{kind}-condition-{i}.json';save(name,b['condition']);flag='--condition-from-file='+name
            args=(['gcloud','projects','add-iam-policy-binding',value['project']] if kind=='project' else
                  ['gcloud','storage','buckets','add-iam-policy-binding','gs://'+value['bucket']])
            add(*args,'--member='+b['members'][0],'--role='+b['role'],flag)
    for name,env in value['environments'].items():
        if env['reuse']:continue  # Existing observer/approval environment is only inspected.
        save(name+'.json',env['body']);save(name+'-branch.json',env['branchPolicy'])
        api='repos/'+ci.REPOSITORY+'/environments/'+name
        add('gh','api','--method','PUT',api,'--input',name+'.json')
        add('gh','api','--method','POST',api+'/deployment-branch-policies','--input',name+'-branch.json')
    save('commands.json',commands)
    (output/'APPLY.md').write_text('# Disabled V5.1 identity staging proposal\n\n'
        'No commands have run. Review and obtain operator authorization before applying. '
        'First run `python3 -m scripts.v51.cloud_identity_audit absent --output <new-directory>` from the repository root. '
        'Every new account, pool, role and cleanup environment must be absent; the reused runner/observer environment must match. '
        'Inspect any collision, partial application or failure instead of overwriting, enabling or blindly replaying. '
        'Run the following only from this generated directory with `set -e`; verify role visibility before bindings if propagation delays occur.\n\n'
        'All new service accounts, pools and providers stay disabled. The current observer workflow shares the future runner path/environment; '
        'enabling the staged runner now would allow its OIDC claims to match. There is no activation command or switch in this proposal. '
        'Existing observer and V5.0 identities/environments are not modified.\n\n'
        '```bash\nset -euo pipefail\n'+'\n'.join(shlex.join(v) for v in commands)+'\n```\n\n'
        'Then run `python3 -m scripts.v51.cloud_identity_audit staged --output <new-directory>` from the repository root. '
        'STAGED_MATCH verifies only the sampled explicit configuration, not usable credentials or comprehensive least privilege. '
        'Organization/folder policy reads are optional; unavailable inheritance remains an unassessed limitation. '
        'Do not add organization privileges. Actual workflow-identity required permissions and forbidden-action probes remain necessary before readiness. '
        'Project Compute grants include project-wide deletion/network policy privileges: resource ownership and exact IDs remain application checks. '
        'Cleanup may replace the exact lease and ledger because shared reconciliation appends a terminal ledger event; it cannot delete attempt evidence '
        'through these explicit bucket grants. No VM creation, workflow dispatch, live reconciliation, paid admission or enablement is performed by this generator.\n')
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();v=write(args.output,c.read(p.CONFIG))
    print(m.canonical(dict(status='PROPOSAL_ONLY',staging=v['staging'],applied=False,output=str(args.output))).decode())
