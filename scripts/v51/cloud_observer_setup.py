"""Generate a create-only observer IAM/WIF proposal; no subprocess or network."""
import argparse
import json
from pathlib import Path
import shlex
from . import cloud_preflight as p, cloud_ci as ci, cloud_authority as a, remote_command as c

ROLES = {
    'gseV51ObserverComputeRead': ['compute.projects.get','compute.regions.get','compute.zones.get','compute.machineTypes.get','compute.images.get','compute.subnetworks.get'],
    'gseV51ObserverBucketRead': ['storage.buckets.get'],
    'gseV51ObserverControlRead': ['storage.objects.get'],
}


def proposal(cfg):
    digest=p.configuration(cfg);project=cfg['provider']['project'];bucket=cfg['provider']['bucket']
    claims=dict(repository=ci.REPOSITORY,repository_id=str(ci.REPOSITORY_ID),repository_owner_id=str(ci.OWNER_ID),
                ref='refs/heads/master',event_name='workflow_dispatch',environment=a.ENVIRONMENT,
                workflow_ref=ci.REPOSITORY+'/'+a.RUNNER_WORKFLOW+'@refs/heads/master')
    condition=' && '.join("assertion."+k+" == '"+v+"'" for k,v in claims.items())
    objects=['projects/_/buckets/'+bucket+'/objects/'+k for k in (a.LEASE,a.LEDGER)]
    control=dict(title='v51-observer-control-read',expression="resource.type == 'storage.googleapis.com/Object' && ("+
                 ' || '.join("resource.name == '"+v+"'" for v in objects)+')')
    return dict(schema='gse-v51-observer-setup-v1',execution='offline-proposal-only',applied=False,
                configurationSha256=digest,project=project,bucket=bucket,serviceAccount=cfg['observerServiceAccount'],
                provider=cfg['observerWifProvider'],pool='gse-v51-observer',claims=claims,
                providerCondition=condition,attributeMapping={'google.subject':'assertion.sub','attribute.repository':'assertion.repository'},
                roles={name:dict(title=name,stage='GA',includedPermissions=permissions) for name,permissions in ROLES.items()},
                controlCondition=control,environment=a.ENVIRONMENT,
                principal='principalSet://iam.googleapis.com/projects/'+cfg['projectNumber']+
                    '/locations/global/workloadIdentityPools/gse-v51-observer/attribute.repository/'+ci.REPOSITORY)


def write(output,cfg):
    value=proposal(cfg);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    def save(name,v):(output/name).write_text(json.dumps(v,indent=2)+'\n')
    save('proposal.json',value);save('configuration.json',cfg);save('control-read-condition.json',value['controlCondition'])
    for name,role in value['roles'].items():save(name+'.json',role)
    project='--project='+value['project'];member='--member=serviceAccount:'+value['serviceAccount'];commands=[]
    def add(*args):commands.append(shlex.join(args))
    add('gcloud','iam','service-accounts','create','gse-v51-observer',project)
    add('gcloud','iam','workload-identity-pools','create',value['pool'],project,'--location=global','--display-name=GSE V5.1 observer')
    add('gcloud','iam','workload-identity-pools','providers','create-oidc','github',project,'--location=global',
        '--workload-identity-pool='+value['pool'],'--issuer-uri=https://token.actions.githubusercontent.com',
        '--attribute-mapping='+','.join(k+'='+v for k,v in value['attributeMapping'].items()),'--attribute-condition='+value['providerCondition'])
    add('gcloud','iam','service-accounts','add-iam-policy-binding',value['serviceAccount'],project,
        '--role=roles/iam.workloadIdentityUser','--member='+value['principal'])
    for role in value['roles']:
        add('gcloud','iam','roles','create',role,project,'--file='+role+'.json')
        full='--role=projects/'+value['project']+'/roles/'+role
        if role=='gseV51ObserverComputeRead':add('gcloud','projects','add-iam-policy-binding',value['project'],member,full,'--condition=None')
        else:add('gcloud','storage','buckets','add-iam-policy-binding','gs://'+value['bucket'],member,full,
                 '--condition-from-file=control-read-condition.json' if role=='gseV51ObserverControlRead' else '--condition=None')
    (output/'APPLY.md').write_text('# V5.1 observer setup proposal\n\n'
        'No command has run. Review this proposal and existing project/org grants before applying. '
        'It creates a dedicated pool and service account and grants only the listed reads. '
        'Create-only commands stop on existing resources; do not replace them or continue blindly. '
        'These are additive IAM grants, not proof that the account has no inherited permissions.\n\n'
        'Configure the GitHub `v51-cloud-benchmark` environment for protected master and required reviewer approval. '
        'This proposal does not modify GitHub settings. Read back IAM/WIF/environment state before the first preflight.\n\n'
        'From this generated directory, after review:\n\n```bash\nset -euo pipefail\n'+'\n'.join(commands)+'\n```\n\n'
        'No VM, disk, firewall, object-write/delete, runner or cleanup permission is granted. '
        'A successful observer workflow remains an observation, not paid admission.\n')
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=write(args.output,c.read(p.CONFIG));print(json.dumps(dict(execution=result['execution'],applied=False,output=str(args.output))))
