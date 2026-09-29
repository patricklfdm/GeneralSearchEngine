"""Read-only explicit configuration audit. Disabled staging is never cloud admission."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import time
from . import cloud_identity_setup as setup, cloud_preflight as p, cloud_ci as ci
from . import cloud_authority as a, performance_model as m, remote_command as c


def queries(cfg, mode):
    m.need(mode in ('absent','staged'),'identity audit mode');v=setup.proposal(cfg)
    project='--project='+v['project'];result={}
    def add(key,*args):result[key]=list(args)
    def gh(key,path):add(key,'gh','api','--method','GET','repos/'+ci.REPOSITORY+'/'+path)
    if mode=='absent':
        add('accounts','gcloud','iam','service-accounts','list',project,'--format=json')
        add('pools','gcloud','iam','workload-identity-pools','list',project,'--location=global','--show-deleted','--format=json')
        add('roles','gcloud','iam','roles','list',project,'--show-deleted','--format=json')
        gh('environments','environments?per_page=100')
    else:
        add('project-policy','gcloud','projects','get-iam-policy',v['project'],'--format=json')
        add('bucket-policy','gcloud','storage','buckets','get-iam-policy','gs://'+v['bucket'],'--format=json')
        for name in v['roles']:add('role:'+name,'gcloud','iam','roles','describe',name,project,'--format=json')
        for key,identity in v['identities'].items():
            sa=identity['serviceAccount'];name=identity['name']
            add(key+':account','gcloud','iam','service-accounts','describe',sa,project,'--format=json')
            add(key+':policy','gcloud','iam','service-accounts','get-iam-policy',sa,project,'--format=json')
            add(key+':keys','gcloud','iam','service-accounts','keys','list','--iam-account='+sa,project,'--managed-by=user','--format=json')
            add(key+':pool','gcloud','iam','workload-identity-pools','describe',name,project,'--location=global','--format=json')
            add(key+':providers','gcloud','iam','workload-identity-pools','providers','list','--workload-identity-pool='+name,
                project,'--location=global','--show-deleted','--format=json')
    for name,env in v['environments'].items():
        if mode=='absent' and not env['reuse']:continue
        base='environments/'+name
        gh(name+':environment',base);gh(name+':branches',base+'/deployment-branch-policies?per_page=100')
        gh(name+':protection',base+'/deployment_protection_rules')
    return result


def read(args):
    # Command lists are constructed only by queries(); no shell, writes, tokens or dispatch.
    result=subprocess.run(args,capture_output=True,timeout=30)
    m.need(result.returncode==0 and len(result.stdout)<=8<<20,'identity observation unavailable/oversized')
    return m.strict_json(result.stdout)


def collect(cfg,mode,*,reader=read,wall=time.time):
    commands=queries(cfg,mode);started=int(wall())
    def one(item):
        key,args=item
        try:return key,reader(args)
        except Exception as error:return key,dict(error=type(error).__name__)  # No credential/stderr retention.
    with ThreadPoolExecutor(max_workers=4) as pool:observations=dict(pool.map(one,commands.items()))
    return dict(schema='gse-v51-identity-observations-v1',mode=mode,configurationSha256=p.configuration(cfg),
                startedAt=started,completedAt=int(wall()),observations=observations)


def check_environment(expected,observations):
    name=expected['name'];e=observations[name+':environment'];body=expected['body']
    m.need(e['name']==name and e['deployment_branch_policy']==body['deployment_branch_policy'],'environment name/branch restriction')
    rules=e['protection_rules'];m.need(type(rules) is list,'environment protection rules')
    kinds=[r['type'] for r in rules]
    m.need(len(kinds)==len(set(kinds)) and set(kinds)<= {'branch_policy','required_reviewers','wait_timer'},'unexpected protection rules')
    m.need(all(r.get('wait_timer')==0 for r in rules if r['type']=='wait_timer'),'environment must not wait on timer')
    reviewers=[r for r in rules if r['type']=='required_reviewers']
    if body['reviewers']:
        m.need(len(reviewers)==1 and reviewers[0]['prevent_self_review'] is False and
               [dict(type=r['type'],id=r['reviewer']['id']) for r in reviewers[0]['reviewers']]==body['reviewers'],
               'operator approval configuration')
    else:m.need(not reviewers,'scheduled cleanup must not wait for approval')
    b=observations[name+':branches']
    m.need(b['total_count']==1 and len(b['branch_policies'])==1 and
           all(b['branch_policies'][0][k]==value for k,value in expected['branchPolicy'].items()),'only master branch')
    custom=observations[name+':protection']
    m.need(custom['total_count']==0 and custom['custom_deployment_protection_rules']==[],'custom deployment gate')


def bindings(rows):
    """Ignore API row/member ordering and permit merged role/condition bindings."""
    m.need(type(rows) is list,'policy binding list');flat=set()
    for row in rows:
        m.need(set(row) <= {'role','members','condition'} and type(row['members']) is list and row['members'],'policy binding fields')
        for member in row['members']:
            item=m.canonical([row['role'],row.get('condition'),member])
            m.need(item not in flat,'duplicate policy binding/member');flat.add(item)
    return flat


def evaluate(cfg,mode,value,*,now):
    wanted=setup.proposal(cfg);checks={};o=value.get('observations',{})
    def check(name,fn):
        try:fn();checks[name]=dict(status='PASS')
        except (ValueError,KeyError,TypeError,IndexError,AttributeError) as error:checks[name]=dict(status='BLOCKED',reason=str(error)[:200])
    def envelope():
        m.need(value['schema']=='gse-v51-identity-observations-v1' and value['mode']==mode and
               value['configurationSha256']==wanted['configurationSha256'],'audit identity')
        a.integer(value['startedAt'],1);a.integer(value['completedAt'],1);a.integer(now,1)
        m.need(now-900<=value['startedAt']<=value['completedAt']<=now,'audit freshness')
        m.need(set(o)==set(queries(cfg,mode)),'audit query inventory')
        m.need(all(not isinstance(v,dict) or 'error' not in v for v in o.values()),'unavailable identity observation')
    check('observations',envelope)
    if checks['observations']['status']=='PASS':
        if mode=='absent':
            def absence():
                ids=wanted['identities'].values()
                for key,field,names in (
                    ('accounts','email',{i['serviceAccount'] for i in ids}),
                    ('pools','name',{i['pool'] for i in ids}),
                    ('roles','name',{'projects/'+wanted['project']+'/roles/'+r for r in wanted['roles']})):
                    m.need(type(o[key]) is list and all(v[field] not in names for v in o[key]),'existing staged '+key)
                env=o['environments'];rows=env['environments'];a.integer(env['total_count'],0,100)
                m.need(len(rows)==env['total_count'] and len({r['name'] for r in rows})==len(rows),'environment inventory truncated/duplicate')
                new={name for name,v in wanted['environments'].items() if not v['reuse']}
                m.need(all(r['name'] not in new for r in rows),'existing cleanup environment')
            check('newResourcesAbsent',absence)
        else:
            for key,i in wanted['identities'].items():
                def identity(key=key,i=i):
                    account=o[key+':account'];pool=o[key+':pool'];providers=o[key+':providers']
                    m.need(account['email']==i['serviceAccount'] and account['projectId']==wanted['project'] and account.get('disabled') is True,'service account must remain disabled')
                    m.need(o[key+':keys']==[],'user-managed credential key')
                    m.need(pool['name']==i['pool'] and pool['state']=='ACTIVE' and pool.get('disabled') is True,'pool must remain disabled')
                    m.need(type(providers) is list and len(providers)==1,'unexpected provider inventory')
                    provider=providers[0]
                    m.need(provider['name']==i['provider'] and provider['state']=='ACTIVE' and provider.get('disabled') is True,'provider must remain disabled')
                    m.need(provider['attributeMapping']==i['attributeMapping'] and provider['attributeCondition']==i['attributeCondition'],'WIF mapping/condition drift')
                    m.need(provider['oidc']['issuerUri']=='https://token.actions.githubusercontent.com' and
                           not provider['oidc'].get('allowedAudiences'),'WIF issuer/audiences')
                    expected=[dict(role='roles/iam.workloadIdentityUser',members=[i['principal']])]
                    m.need(bindings(o[key+':policy'].get('bindings',[]))==bindings(expected),'service account impersonation drift')
                check(key,identity)
            for name,role in wanted['roles'].items():
                def check_role(name=name,role=role):
                    v=o['role:'+name]
                    m.need(v['name']=='projects/'+wanted['project']+'/roles/'+name and v['stage']=='GA' and not v.get('deleted',False),'role identity/state')
                    m.need(sorted(v['includedPermissions'])==role['includedPermissions'],'role permission drift')
                check(name,check_role)
            members={'serviceAccount:'+i['serviceAccount'] for i in wanted['identities'].values()}
            roles={'projects/'+wanted['project']+'/roles/'+r for r in wanted['roles']}
            for kind in ('project','bucket'):
                def policy(kind=kind):
                    rows=o[kind+'-policy'].get('bindings',[]);bindings(rows)
                    related=[r for r in rows if set(r['members']) & members or r['role'] in roles]
                    m.need(bindings(related)==bindings(wanted[kind+'Bindings']),'explicit '+kind+' grants drift')
                check(kind+'Grants',policy)
        for name,env in wanted['environments'].items():
            if mode=='staged' or env['reuse']:check(name,lambda env=env:check_environment(env,o))
    return dict(schema='gse-v51-identity-audit-v1',mode=mode,configurationSha256=wanted['configurationSha256'],
                status=('ABSENCE_REVIEWED' if mode=='absent' else 'STAGED_MATCH') if all(v['status']=='PASS' for v in checks.values()) else 'BLOCKED',
                checks=checks,observedAt=now,paidAdmission=False,cleanupReady=False,fullRemoteQualification=False,
                effectiveIamQualified=False,activationAllowed=False,
                limitations=['Explicit sampled policies only; organization/folder inheritance, deny policies and grants on other resources are not established.',
                             'Disabled staging is not a native provider or cleanup qualification; activation requires separate review.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('absent','staged'))
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    cfg=c.read(p.CONFIG);args.output.mkdir(parents=True,exist_ok=False)
    value=collect(cfg,args.mode);c.write_once(args.output/'observations.json',value)
    receipt=evaluate(cfg,args.mode,value,now=int(time.time()));receipt['execution']='read-only-identity-audit'
    receipt['source']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ci.ROOT,text=True).strip()
    c.write_once(args.output/'receipt.json',receipt);print(m.canonical(receipt).decode())
    if receipt['status']=='BLOCKED':raise SystemExit(2)


if __name__=='__main__':main()
