"""No-GCP qualification planner. No credentials, SDK, remote calls or resource creation."""
from copy import deepcopy
import hashlib
import json
import re

SUITE='v5.1-automatic-leadership-suite-v1'
SCHEMA='gse-v51-leadership-evidence-v1'


def need(value,message):
    if not value:raise ValueError(message)


def plan(source,*,now,lease_seconds=5400,grace_seconds=1080,maximum_cost_microusd=5_000_000,
         previous_cost_microusd=0,budget_microusd=100_000_000):
    need(re.fullmatch('[0-9a-f]{40}',source),'source identity')
    for value in (now,lease_seconds,grace_seconds,maximum_cost_microusd,previous_cost_microusd,budget_microusd):
        need(type(value) is int and 0<=value<1<<63,'finite integer')
    need(now>0 and 1<=lease_seconds<=5400 and 1<=grace_seconds<=1080,'lease/grace bounds')
    need(now+lease_seconds+grace_seconds<1<<63,'expiry overflow')
    need(0<maximum_cost_microusd and previous_cost_microusd+maximum_cost_microusd<=budget_microusd,'cost envelope')
    return dict(schema=SCHEMA,suite=SUITE,execution='fake-control-plane-only',source=source,
                voters=[dict(node=f'node-{i}',cpus=8,diskGiB=150) for i in (1,2,3)],concurrent=True,
                maxVcpus=32,maxDiskGiB=500,expiresAt=now+lease_seconds,operationGraceSeconds=grace_seconds,
                maximumCostMicrousd=maximum_cost_microusd,previousCostMicrousd=previous_cost_microusd,
                budgetMicrousd=budget_microusd,priceQualification='not-performed; input envelope only',
                failuresRetained=True,automaticRuntimeEnabled=False,paidAdmission=False)


def reconcile(lease,observed,now):
    """Shared fake authority rules for scheduled/manual probes; exact identities or no deletion."""
    need(type(now) is int and now>=0,'clock')
    need(type(lease) is dict and lease.get('suite')==SUITE,'lease suite')
    need(type(lease.get('expiresAt')) is int and type(lease.get('operationGraceSeconds')) is int,'lease fields')
    need(lease['expiresAt']>0 and 0<=lease['operationGraceSeconds']<=1080,'operation grace/expiry')
    resources=lease.get('resources');need(type(resources) is list and len(resources)<=32,'inventory bound')
    names=[r['name'] for r in resources];need(len(set(names))==len(names),'duplicate resources')
    if now<lease['expiresAt']+lease['operationGraceSeconds']:return dict(status='WAITING',delete=[])
    deletion=[]
    for resource in resources:
        current=observed.get(resource['name'])
        if current is None:continue
        need(type(resource['id']) is str and re.fullmatch('[1-9][0-9]{0,19}',resource['id']),'exact resource ID')
        need(current==resource and resource['owner']==lease['owner'],'ownership/ID mismatch')
        deletion.append(resource['name'])
    return dict(status='PASS',delete=deletion)


def qualify(source):
    p=plan(source,now=1000)
    need(p['concurrent'] and sum(v['cpus'] for v in p['voters'])<=p['maxVcpus']
         and sum(v['diskGiB'] for v in p['voters'])<=p['maxDiskGiB'],'concurrent topology budget')
    lease=dict(suite=SUITE,owner='fixture-owner',expiresAt=1100,operationGraceSeconds=30,
               resources=[dict(name=f'fixture-node-{i}',id=str(i),owner='fixture-owner') for i in (1,2,3)])
    resources={v['name']:v for v in lease['resources']}
    need(reconcile(lease,resources,1129)['status']=='WAITING','active lease deletion')
    receipt=reconcile(lease,resources,1130)
    need(len(receipt['delete'])==3,'expired owned inventory')
    # Reconciliation is a plan; fake application mutates only this local dictionary.
    for name in receipt['delete']:resources.pop(name)
    need(reconcile(lease,resources,1131)==dict(status='PASS',delete=[]),'cleanup idempotence')
    return dict(status='PASS',plan=p,cleanup=dict(status='PASS',leftovers=[]),execution='fake-control-plane-only')
