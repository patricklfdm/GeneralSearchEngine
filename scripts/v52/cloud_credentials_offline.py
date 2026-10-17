"""Offline exact-attempt observations. Synthetic JWTs never certify real IAM."""
from copy import deepcopy
from . import cloud_credentials as c
from .evidence import need
from scripts.v51 import cloud_cleanup_auth_fake as issuer


class Clock:
    def __init__(self):self.now=10.0
    def seconds(self):return self.now
    def wall(self):return 1800000000+int(self.now)
    def sleep(self,seconds):self.now+=seconds


class Invocation:
    def __init__(self,binding,clock):
        self.binding,self.clock=deepcopy(binding),clock;self.source=binding['source'];self.calls=[]
        repo=dict(id=c.REPOSITORY_ID,full_name=c.REPOSITORY,owner=dict(id=c.OWNER_ID))
        self.value=dict(id=binding['runId'],run_attempt=binding['runAttempt'],head_sha=binding['source'],
            head_branch='master',path=binding['workflow'],event=binding['event'],status='in_progress',conclusion=None,
            repository=repo,head_repository=deepcopy(repo))
        self.change=lambda number,value:value

    def get(self,path,deadline):
        base='actions/runs/'+str(self.binding['runId'])
        need(path in (base,base+'/attempts/'+str(self.binding['runAttempt'])),'offline GitHub path')
        self.calls.append(path);return self.change(len(self.calls),deepcopy(self.value))


def fixture(configuration,role='runner',source='a'*40):
    project='123456789';selected=c.selection(configuration,project,role)
    env=dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=c.REPOSITORY,GITHUB_REPOSITORY_ID=str(c.REPOSITORY_ID),
        GITHUB_REPOSITORY_OWNER_ID=str(c.OWNER_ID),GITHUB_EVENT_NAME=selected['event'],GITHUB_REF='refs/heads/master',
        GITHUB_WORKFLOW_REF=c.REPOSITORY+'/'+selected['workflow']+'@refs/heads/master',GITHUB_WORKFLOW_SHA=source,
        GITHUB_SHA=source,GITHUB_JOB=selected['job'],V52_CLOUD_ENVIRONMENT=selected['environment'],
        GITHUB_RUN_ID='123456',GITHUB_RUN_ATTEMPT='2')
    binding=c.identity(configuration,project,env,role=role,source=source,checkout=source)
    env,descriptor=issuer.inputs(binding,env);clock=Clock();invocation=Invocation(binding,clock)
    return project,env,descriptor,invocation,issuer.Issuer(binding,clock)
