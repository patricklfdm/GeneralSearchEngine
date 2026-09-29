"""Offline staged identity configuration and permission-drift qualification."""
import argparse
from copy import deepcopy
from pathlib import Path
from . import cloud_identity_setup as setup, cloud_identity_audit as audit
from . import cloud_preflight as p, remote_command as c, performance_model as m

NOW=1800000000


def fixture(cfg,mode='staged'):
    v=setup.proposal(cfg);o={}
    if mode=='absent':
        o.update(accounts=[],pools=[],roles=[],environments=dict(total_count=1,environments=[dict(name='v51-cloud-benchmark')]))
    else:
        o['project-policy']=dict(bindings=deepcopy(v['projectBindings']))
        o['bucket-policy']=dict(bindings=deepcopy(v['bucketBindings']))
        for name,role in v['roles'].items():o['role:'+name]=dict(deepcopy(role),name='projects/'+v['project']+'/roles/'+name)
        for key,i in v['identities'].items():
            o[key+':account']=dict(email=i['serviceAccount'],projectId=v['project'],disabled=True)
            o[key+':pool']=dict(name=i['pool'],state='ACTIVE',disabled=True)
            o[key+':providers']=[dict(name=i['provider'],state='ACTIVE',disabled=True,attributeMapping=i['attributeMapping'],
                attributeCondition=i['attributeCondition'],oidc=dict(issuerUri='https://token.actions.githubusercontent.com'))]
            o[key+':keys']=[]
            o[key+':policy']=dict(bindings=[dict(role='roles/iam.workloadIdentityUser',members=[i['principal']])])
    for name,env in v['environments'].items():
        if mode=='absent' and not env['reuse']:continue
        rules=[dict(type='branch_policy')]
        if env['body']['reviewers']:
            rules.append(dict(type='required_reviewers',prevent_self_review=False,reviewers=[dict(type='User',reviewer=dict(id=147357093))]))
        o[name+':environment']=dict(name=name,protection_rules=rules,deployment_branch_policy=dict(protected_branches=False,custom_branch_policies=True))
        o[name+':branches']=dict(total_count=1,branch_policies=[dict(id=1,name='master',type='branch')])
        o[name+':protection']=dict(total_count=0,custom_deployment_protection_rules=[])
    return dict(schema='gse-v51-identity-observations-v1',mode=mode,configurationSha256=p.configuration(cfg),startedAt=NOW-5,completedAt=NOW,observations=o)


def mutations():
    return {
        'runner-enabled':lambda o:o['runner:account'].update(disabled=False),
        'cleanup-pool-enabled':lambda o:o['schedule:pool'].update(disabled=False),
        'manual-provider-enabled':lambda o:o['manual:providers'][0].update(disabled=False),
        'foreign-repository':lambda o:o['runner:providers'][0].update(attributeCondition='true'),
        'schedule-allows-manual':lambda o:o['schedule:providers'][0].update(attributeCondition=o['schedule:providers'][0]['attributeCondition'].replace("'schedule'","'workflow_dispatch'")),
        'cross-pool-impersonation':lambda o:o['schedule:policy']['bindings'][0]['members'].append(o['runner:policy']['bindings'][0]['members'][0]),
        'cleanup-can-create':lambda o:o['role:gseV51CleanupCompute']['includedPermissions'].append('compute.instances.create'),
        'bucket-wide-delete':lambda o:o['bucket-policy']['bindings'][-1].pop('condition'),
        'evidence-delete':lambda o:o['bucket-policy']['bindings'][-1]['condition'].update(expression="resource.name.startsWith('projects/_/buckets/gse-benchmark-evidence-266952534277/objects/')"),
        'extra-editor':lambda o:o['project-policy']['bindings'].append(dict(role='roles/editor',members=o['project-policy']['bindings'][0]['members'])),
        'ssh-any-port':lambda o:o['project-policy']['bindings'][1].pop('condition'),
        'credential-key':lambda o:o['manual:keys'].append(dict(name='unexpected-key')),
        'runner-approval-missing':lambda o:o['v51-cloud-benchmark:environment'].update(protection_rules=[dict(type='branch_policy')]),
        'scheduled-reviewer':lambda o:o['v51-cloud-cleanup:environment']['protection_rules'].append(dict(type='required_reviewers')),
        'manual-unprotected-branch':lambda o:o['v51-cloud-manual-cleanup:branches']['branch_policies'][0].update(name='*'),
        'permission-query-denied':lambda o:o.update({'role:gseV51CleanupCompute':dict(error='PermissionError')}),
    }


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);cfg=c.read(p.CONFIG)
    setup.write(output/'proposal',cfg);value=fixture(cfg);commands=audit.queries(cfg,'staged');calls=[]
    data={tuple(args):value['observations'][key] for key,args in commands.items()}
    def reader(args):calls.append(args);return deepcopy(data[tuple(args)])
    collected=audit.collect(cfg,'staged',reader=reader,wall=lambda:NOW)
    result=audit.evaluate(cfg,'staged',collected,now=NOW)
    m.need(result['status']=='STAGED_MATCH' and not result['activationAllowed'],'offline staged identity baseline')
    c.write_once(output/'observations.json',collected);c.write_once(output/'queries.json',commands)
    c.write_once(output/'audit.json',result);negatives=[]
    for name,mutation in mutations().items():
        changed=deepcopy(collected);mutation(changed['observations'])
        rejected=audit.evaluate(cfg,'staged',changed,now=NOW)
        m.need(rejected['status']=='BLOCKED' and not rejected['cleanupReady'],'identity drift accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',checks={k:v for k,v in rejected['checks'].items() if v['status']=='BLOCKED'}))
    c.write_once(output/'negatives.json',negatives)
    receipt=dict(status='PASS',execution='offline-identity-qualification',readQueries=len(calls),negativeCases=len(negatives),
                 applied=False,activationAllowed=False,paidAdmission=False,cleanupReady=False)
    c.write_once(output/'receipt.json',receipt);print(m.canonical(receipt).decode());return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);args=parser.parse_args();run(args.output)
