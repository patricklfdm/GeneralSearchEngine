"""Retained offline observations and negative cases; never contacts GitHub/GCP."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import argparse
import base64
from . import cloud_preflight as p, cloud_ci as ci, cloud_authority as a, performance_model as m, remote_command as c
from .cloud_http import Api

SOURCE = 'a'*40
NOW = 1800000000


def fixture():
    cfg = c.read(p.CONFIG); v = cfg['provider']; workflow = (ci.ROOT/ci.WORKFLOW).read_text()
    def at(seconds):return datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace('+00:00','Z')
    run = dict(id=12, run_attempt=2, head_sha=SOURCE, head_branch='master', event='push', path=ci.WORKFLOW,
               status='completed', conclusion='success', repository=dict(id=ci.REPOSITORY_ID, full_name=ci.REPOSITORY, owner=dict(id=ci.OWNER_ID)))
    jobs = [dict(id=i, run_id=12, run_attempt=2, head_sha=SOURCE, name=name, status='completed', conclusion='success',
                 started_at=at(NOW-300), completed_at=at(NOW-30), steps=[]) for i, name in enumerate(ci.expected_jobs(workflow),1)]
    next(j for j in jobs if j['name']==ci.OWNED_JOB)['steps'] = [dict(name=ci.OWNED_STEP, status='completed', conclusion='success', started_at=at(NOW-290), completed_at=at(NOW-40))]
    observations = dict(masterBefore=SOURCE, masterAfter=SOURCE, run=run, runAfter=deepcopy(run), jobs=jobs, workflowSha256=m.sha(workflow.encode()),configurationSha256=p.configuration(cfg))
    github = dict(source=SOURCE, startedAt=NOW-10, completedAt=NOW-1, observations=observations)
    def quotas(values):return [dict(metric=k, limit=v, usage=0) for k,v in values.items()]
    base = 'https://compute.googleapis.com/compute/v1/projects/'+v['project']
    raw = dict(principal=cfg['observerServiceAccount'],
        project=dict(name=v['project'],id='5021569533786003310',selfLink=base,quotas=quotas({'CPUS_ALL_REGIONS':24,'FIREWALLS':4})),
        region=dict(name=v['region'],quotas=quotas({'N2_CPUS':24,'CPUS':24,'SSD_TOTAL_GB':450})),
        zone=dict(name=v['zone'],status='UP'),machine=dict(name=v['machineType'],guestCpus=8,memoryMb=32768),
        image=dict(name=v['imageName'],id=v['imageId'],status='READY',architecture='X86_64'),
        subnetwork=dict(name=v['subnetwork'],network=base+'/global/networks/'+v['network'],region=base+'/regions/'+v['region'],privateIpGoogleAccess=True),
        bucket=dict(name=v['bucket'],projectNumber=cfg['projectNumber'],iamConfiguration=dict(uniformBucketLevelAccess=dict(enabled=True))),
        lease=None, ledger=None)
    provider=dict(configurationSha256=p.configuration(cfg),execution='offline-preflight-fixture',startedAt=NOW-10,completedAt=NOW-1,observations=raw)
    return cfg,github,provider


class Http:
    offline=True
    def __init__(self,cfg,raw):self.responses={url:raw[k] for k,url in p.queries(cfg).items()};self.requests=[]
    def send(self, method,url,headers,body,timeout,maximum):
        self.requests.append(dict(method=method,url=url))
        m.need(method=='GET' and body is None,'preflight wrote to provider')
        if url in self.responses:return 200,m.canonical(self.responses[url])
        m.need('/o/v5.1-automatic-leadership%2Fcontrol%2F' in url,'unexpected provider read')
        return 404,b''


def github_api(value):
    obs=value['observations'];run=obs['run'];jobs=obs['jobs'];workflow=(ci.ROOT/ci.WORKFLOW).read_bytes()
    data={'branches/master':dict(commit=dict(sha=SOURCE)),
          'actions/workflows/ci.yml/runs?branch=master&head_sha='+SOURCE+'&per_page=100':dict(workflow_runs=[run]),
          'actions/runs/12':run,
          'actions/runs/12/attempts/2/jobs?per_page=100&page=1':dict(total_count=len(jobs),jobs=jobs),
          'contents/'+ci.WORKFLOW+'?ref='+SOURCE:dict(encoding='base64',size=len(workflow),content=base64.b64encode(workflow).decode())}
    raw=p.CONFIG.read_bytes()
    data['contents/'+ci.CONFIG_PATH+'?ref='+SOURCE]=dict(encoding='base64',size=len(raw),content=base64.b64encode(raw).decode())
    return data


def run(output):
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    cfg,github,provider=fixture();http=Http(cfg,provider['observations'])
    api=Api(transport=http,tokens=lambda timeout:'fixture-token',clock=lambda:1)
    observed=p.collect_provider(cfg,api=api,who=lambda:cfg['observerServiceAccount'],wall=lambda:NOW)
    data=github_api(github);github['observations']=ci.collect(SOURCE,get=lambda path:deepcopy(data[path]))
    result=p.evaluate(cfg,SOURCE,github,observed,now=NOW)
    m.need(result['status']=='OBSERVATIONS_READY' and result['paidAdmission'] is False,'offline positive observation')
    c.write_once(root/'configuration.json',cfg);c.write_once(root/'github.json',github);c.write_once(root/'provider.json',observed)
    c.write_once(root/'provider-requests.json',http.requests);c.write_once(root/'preflight.json',result)
    mutations={
        'skipped-ci':lambda g,v:g['observations']['jobs'][0].update(conclusion='skipped'),
        'different-attempt':lambda g,v:g['observations']['jobs'][0].update(run_attempt=1),
        'master-moved':lambda g,v:g['observations'].update(masterAfter='b'*40),
        'foreign-compute-project':lambda g,v:v['observations']['project'].update(selfLink='https://compute.googleapis.com/compute/v1/projects/other-project'),
        'foreign-bucket-project':lambda g,v:v['observations']['bucket'].update(projectNumber='123456789'),
        'private-access-disabled':lambda g,v:v['observations']['subnetwork'].update(privateIpGoogleAccess=False),
        'changed-image':lambda g,v:v['observations']['image'].update(id='1'),
        'insufficient-quota':lambda g,v:v['observations']['region']['quotas'][0].update(usage=1),
        'foreign-observer':lambda g,v:v['observations'].update(principal='other'),
        'premature-delete':lambda g,v:v['observations']['bucket'].update(lifecycle=dict(rule=[dict(action=dict(type='Delete'),condition=dict(age=29))])),
        'locked-control':lambda g,v:v['observations']['bucket'].update(retentionPolicy=dict(retentionPeriod='2592000')),
        'unavailable-ledger':lambda g,v:v['observations'].update(ledger=dict(error='PermissionError')),
        'expired-observation':lambda g,v:v.update(startedAt=NOW-901),
    }
    negatives=[]
    for name,mutate in mutations.items():
        g,v=deepcopy(github),deepcopy(observed);mutate(g,v);r=p.evaluate(cfg,SOURCE,g,v,now=NOW)
        m.need(r['status']=='BLOCKED' and not r['paidAdmission'],'preflight negative accepted: '+name)
        negatives.append(dict(case=name,status='REJECTED',blockers=r['blockers']))
    c.write_once(root/'negatives.json',negatives)
    receipt=dict(status='PASS',execution='offline-preflight-fixture',providerReads=len(http.requests),negativeCases=len(negatives),paidCloud=False,fullRemoteQualification=False)
    c.write_once(root/'receipt.json',receipt);print(m.canonical(receipt).decode());return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);run(parser.parse_args().output)
