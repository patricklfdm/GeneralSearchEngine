"""Offline credential/HTTP qualification; never evidence of actual Google IAM."""
import argparse
from copy import deepcopy
from pathlib import Path
from . import cloud_permissions as p, cloud_preflight as preflight, cloud_ci as ci
from . import cloud_cleanup_auth_fake as auth, cloud_fake, performance_model as m
from .remote_command import read, write_once


class Provider:
    offline = True
    def __init__(self, cfg, role):
        self.queries = p.plan(cfg, role); self.requests = []
        self.responses = {name:dict(permissions=q['required']) for name,q in self.queries.items()}
        self.status = 200

    def send(self, method, url, headers, body, timeout, maximum):
        m.need(headers['Authorization'] == 'Bearer '+auth.ACCOUNT_SECRET, 'permission provider credential')
        name, query = next((name,q) for name,q in self.queries.items() if q['method']==method and q['url']==url)
        m.need(body == (None if query['body'] is None else m.canonical(query['body'])), 'permission request body')
        self.requests.append(dict(scope=name, method=method, url=url, timeout=timeout, maximum=maximum))
        return self.status, m.canonical(self.responses[name])


def fixture(role):
    cfg = read(preflight.CONFIG); source = 'c'*40; chosen = p.selected(cfg, role)
    env = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=ci.REPOSITORY, GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID),
               GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID), GITHUB_EVENT_NAME=chosen['claims']['event_name'],
               GITHUB_REF='refs/heads/master', GITHUB_WORKFLOW_REF=chosen['claims']['workflow_ref'],
               GITHUB_WORKFLOW_SHA=source, GITHUB_SHA=source, GITHUB_JOB=p.JOBS[role],
               GITHUB_RUN_ID='12345', GITHUB_RUN_ATTEMPT='2')
    env['CLEANUP_ENVIRONMENT' if role in ('manual','schedule') else 'PERMISSION_ENVIRONMENT'] = chosen['environment']
    binding = p.identity(cfg, env, role=role, source=source, checkout=source)
    env, descriptor = auth.inputs(binding, env)
    clock = cloud_fake.Clock(); issuer = auth.Issuer(binding, clock); provider = Provider(cfg, role)
    client = p.OfflineClient(cfg, binding, env, descriptor, transport=provider, issuer=issuer,
                             clock=clock.seconds, wall=clock.wall)
    repo = dict(id=ci.REPOSITORY_ID, full_name=ci.REPOSITORY, owner=dict(id=ci.OWNER_ID))
    run = dict(repository=repo, head_repository=deepcopy(repo), id=binding['runId'], run_attempt=binding['runAttempt'],
               head_sha=source, head_branch='master', path=binding['workflow'], event=binding['event'],
               status='in_progress', conclusion=None)
    return cfg, binding, env, descriptor, clock, issuer, provider, client, run


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False); rows = []
    for role in p.ROLES:
        cfg,binding,env,descriptor,clock,issuer,provider,client,observation = fixture(role)
        p.entry.validate_run(binding, observation)
        value = p.collect(cfg, binding, client, wall=clock.wall)
        result = p.evaluate(cfg, binding, value, now=clock.wall())
        m.need(result['status']=='PRECHECK_PASS' and result['execution']=='offline-permission-probes', 'offline permission positive')
        root = output/role; root.mkdir()
        write_once(root/'binding.json', binding); write_once(root/'observations.json',value); write_once(root/'receipt.json',result)
        write_once(root/'requests.json',provider.requests); write_once(root/'exchange-stages.json',issuer.calls)
        (root/'summary.md').write_text(p.summary(result))
        negatives = []
        for name, mutate in (
            ('missing-required',lambda v:v['observations']['project'].update(permissions=[])),
            ('forbidden-grant',lambda v:v['observations']['project']['permissions'].append('iam.serviceAccountKeys.create')),
            ('bucket-wide-delete',lambda v:v['observations']['bucket']['permissions'].append('storage.objects.delete')),
            ('provider-denied',lambda v:v['observations'].update(bucket=dict(error='ApiError',httpStatus=403))),
            ('other-source',lambda v:v.update(source='d'*40)),
            ('other-attempt',lambda v:v.update(runAttempt=3)),
            ('other-account',lambda v:v.update(serviceAccount='wrong@example.com')),
            ('stale',lambda v:v.update(startedAt=clock.wall()-901))):
            bad = deepcopy(value); mutate(bad)
            verdict = p.evaluate(cfg,binding,bad,now=clock.wall())
            m.need(verdict['status']=='BLOCKED','permission negative accepted: '+name)
            negatives.append(dict(case=name,status='REJECTED'))
        write_once(root/'negatives.json',negatives)
        rows.append(dict(role=role,status='PASS',queries=len(provider.requests),negatives=len(negatives)))
    result = dict(status='PASS',execution='offline-permission-qualification',identities=rows,**p.BOUNDARY)
    write_once(output/'receipt.json',result); print(m.canonical(result).decode()); return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('output',type=Path)
    run(parser.parse_args().output)
