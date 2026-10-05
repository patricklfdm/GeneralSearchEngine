"""Bound workflow-identity permission prechecks; never mutate cloud resources.

Project/bucket testIamPermissions is diagnostic. Runner also reads the frozen
external image; this does not prove image use or object/IAP conditional access.
No organization policy read is required.
"""
import argparse
from copy import deepcopy
import html
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from . import cloud_authority as a, cloud_ci as ci, cloud_preflight as p
from . import cloud_identity_setup as identities, cloud_observer_setup as observer
from . import cloud_cleanup_entry as entry, cloud_cleanup_credentials as credentials
from . import cloud_http as http, performance_model as m
from .remote_command import read, write_once

SCHEMA = 'gse-v51-permission-precheck-v1'
ROLES = ('observer', 'runner', 'manual', 'schedule')
JOBS = dict(observer='observations', runner='run', manual='cleanup', schedule='cleanup')
IAM_FORBIDDEN = ('resourcemanager.projects.setIamPolicy', 'iam.roles.create', 'iam.roles.update',
                 'iam.serviceAccounts.create', 'iam.serviceAccounts.delete',
                 'iam.serviceAccounts.setIamPolicy', 'iam.serviceAccounts.actAs',
                 'iam.serviceAccounts.getAccessToken', 'iam.serviceAccountKeys.create')
TOPOLOGY_WRITES = tuple(v for v in identities.RUNNER_COMPUTE if v.rsplit('.', 1)[1] not in
                        ('get', 'list', 'getGuestAttributes', 'useReadOnly', 'use'))
BUCKET_FORBIDDEN = ('storage.buckets.delete', 'storage.buckets.update', 'storage.buckets.setIamPolicy',
                    'storage.objects.list', 'storage.objects.create', 'storage.objects.delete', 'storage.objects.update')
LIMITATIONS = (p.IAM_LIMITATION,
              'testIamPermissions is diagnostic, not an authorization decision or an exhaustive privilege audit.',
              'Bucket-level results do not establish object-name conditional grants or denials; no object testIamPermissions endpoint is used.',
              'Resource-level grants, external image use and conditional IAP access require the corresponding real-path qualification.')
PENDING = ('exact lease/ledger read and conditional replacement permissions',
           'attempt-evidence creation and forbidden replacement/deletion; out-of-scope object rejection',
           'real resource/operation permissions, conditional IAP where applicable and independent provider evidence')
BOUNDARY = dict(effectiveIamQualified=False, objectPermissionsQualified=False, activationAllowed=False,
                cleanupReady=False, paidAdmission=False, paidCloud=False, fullRemoteQualification=False,
                artifactProvenanceVerified=False)


def selected(cfg, role):
    m.need(role in ROLES, 'permission identity role')
    if role == 'observer':
        value = observer.proposal(cfg)
        return dict(value, workflow=a.RUNNER_WORKFLOW)
    return identities.proposal(cfg)['identities'][role]


def identity(cfg, env, *, role, source, checkout):
    digest = p.configuration(cfg); a.digest(source, 40)
    chosen = selected(cfg, role); claims = chosen['claims']
    expected = dict(GITHUB_ACTIONS='true', GITHUB_REPOSITORY=ci.REPOSITORY,
        GITHUB_REPOSITORY_ID=str(ci.REPOSITORY_ID), GITHUB_REPOSITORY_OWNER_ID=str(ci.OWNER_ID),
        GITHUB_EVENT_NAME=claims['event_name'], GITHUB_REF='refs/heads/master',
        GITHUB_WORKFLOW_REF=claims['workflow_ref'], GITHUB_WORKFLOW_SHA=source,
        GITHUB_SHA=source, GITHUB_JOB=JOBS[role])
    expected['CLEANUP_ENVIRONMENT' if role in entry.TRIGGERS else 'PERMISSION_ENVIRONMENT'] = chosen['environment']
    m.need(all(env.get(k) == v for k, v in expected.items()) and checkout == source, 'permission workflow context mismatch')
    numbers = []
    for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'):
        value = env.get(key)
        m.need(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value) is not None, 'permission run identity')
        numbers.append(int(value))
    return dict(schema=SCHEMA, role=role, source=source, configurationSha256=digest,
        runId=numbers[0], runAttempt=numbers[1], workflow=chosen['workflow'], event=claims['event_name'],
        environment=chosen['environment'], serviceAccount=chosen['serviceAccount'], provider=chosen['provider'])


def plan(cfg, role):
    selected(cfg, role); provider = cfg['provider']
    required = (observer.ROLES['gseV51ObserverComputeRead'] if role == 'observer' else
                identities.RUNNER_COMPUTE if role == 'runner' else identities.CLEANUP_COMPUTE)
    forbidden = set(IAM_FORBIDDEN) | {'compute.instances.setServiceAccount', 'compute.subnetworks.useExternalIp',
                                    'compute.projects.setCommonInstanceMetadata', 'storage.buckets.create'}
    forbidden.update(set(TOPOLOGY_WRITES) - set(required))
    required = sorted(required); forbidden = sorted(forbidden)
    project = 'https://cloudresourcemanager.googleapis.com/v1/projects/'+provider['project']+':testIamPermissions'
    bucket = 'https://storage.googleapis.com/storage/v1/b/'+provider['bucket']+'/iam/testPermissions'
    bucket_permissions = sorted(['storage.buckets.get', *BUCKET_FORBIDDEN])
    queries = dict(project=dict(method='POST', url=project, body=dict(permissions=sorted(required+forbidden)),
                             required=required, forbidden=forbidden),
                bucket=dict(method='GET', url=bucket+'?'+urlencode({'permissions':bucket_permissions}, doseq=True),
                            body=None, required=['storage.buckets.get'], forbidden=sorted(BUCKET_FORBIDDEN)))
    if role == 'runner':
        queries['image'] = dict(method='GET', url=p.queries(cfg)['image'], body=None,
            expectedImage=dict(name=provider['imageName'], id=provider['imageId'],
                               status='READY', architecture='X86_64'))
    return queries


def image(response, query):
    """Retain only the frozen identity fields, never arbitrary provider text."""
    m.need(type(response) is dict and
           all(response.get(k) == v for k, v in query['expectedImage'].items()) and
           response.get('deprecated') in (None, {}) and
           response.get('kind', 'compute#image') == 'compute#image' and
           p.gcp.link(response.get('selfLink', query['url'])) == query['url'],
           'frozen Runner image identity/status/architecture changed')
    return {k:response[k] for k in query['expectedImage']}


def permissions(response, query):
    # Only retain known permission names, never arbitrary provider response text.
    m.need(type(response) is dict and set(response) <= {'kind', 'permissions'}, 'permission response fields')
    if 'kind' in response:
        m.need(query['method'] == 'GET' and response['kind'] == 'storage#testIamPermissionsResponse', 'permission response kind')
    values = response.get('permissions', [])
    m.need(type(values) is list and all(type(v) is str for v in values) and len(values) == len(set(values)) and
           set(values) <= set(query['required']+query['forbidden']), 'permission response inventory')
    return sorted(values)


class _Client:
    def initialize(self, cfg, binding, tokens, transport, clock):
        self.configuration = deepcopy(cfg)
        self.binding = deepcopy(binding); self.queries = plan(cfg, binding['role'])
        self.tokens, self.transport, self.clock = tokens, transport, clock
        self.offline = transport.offline is True
        self.token = None

    def probe(self, name, deadline):
        m.need(p.configuration(self.configuration) == self.binding['configurationSha256'] and
               self.queries == plan(self.configuration, self.binding['role']), 'permission probe plan drift')
        m.need(name in self.queries, 'permission probe scope')
        query = self.queries[name]
        body = m.canonical(query['body']) if query['body'] is not None else None
        for attempt in range(2):
            remaining = deadline-self.clock(); m.need(remaining > 0, 'permission original deadline')
            if self.token is None or self.clock() >= self.token.usable_until:
                token = self.tokens(min(30, remaining))
                m.need(isinstance(token, http.AccessToken) and token.usable_until > self.clock(), 'permission credential expiry')
                credentials.bearer(token.value); self.token = token
            remaining = deadline-self.clock(); m.need(remaining > 0, 'permission original deadline')
            status, raw = self.transport.send(query['method'], query['url'],
                {'Authorization':'Bearer '+self.token.value, 'Content-Type':'application/json'},
                body, min(30, remaining), 64 << 10)
            m.need(self.clock() <= deadline, 'permission late response')
            if status == 401:
                self.token = None
                # All fixed queries are read-only, including the CRM POST.
                if attempt == 0: continue
            if status != 200: raise http.ApiError(status, query['method'])
            m.need(type(raw) is bytes and len(raw) <= 64 << 10, 'permission response size')
            response = m.strict_json(raw)
            return image(response, query) if name == 'image' else permissions(response, query)


class OfflineClient(_Client):
    def __init__(self, cfg, binding, env, descriptor, *, transport, issuer, clock, wall):
        m.need(transport.offline is True and issuer.offline is True, 'permission fixture must be offline')
        m.need(binding == identity(cfg, env, role=binding['role'], source=binding['source'], checkout=binding['source']), 'permission binding drift')
        tokens = credentials.Credentials(binding, env, descriptor, transport=issuer, clock=clock, wall=wall)
        self.initialize(cfg, binding, tokens, transport, clock)


class NetworkClient(_Client):
    def __init__(self, cfg, binding, env, descriptor):
        m.need(binding == identity(cfg, env, role=binding['role'], source=binding['source'], checkout=binding['source']), 'permission binding drift')
        tokens = credentials.NetworkCredentials(binding, env, descriptor)
        self.initialize(cfg, binding, tokens, http.Network(), time.monotonic)


def collect(cfg, binding, client, *, wall=time.time):
    m.need(client.binding == binding and client.queries == plan(cfg, binding['role']), 'permission client scope drift')
    started = int(wall()); deadline = client.clock()+180; observations = {}
    for name in client.queries:
        try: observations[name] = {('image' if name == 'image' else 'permissions'):client.probe(name, deadline)}
        except Exception as error:
            observations[name] = dict(error=type(error).__name__)
            if isinstance(error, http.ApiError): observations[name]['httpStatus'] = error.status
    return dict(binding, execution='offline-permission-probes' if client.offline else 'workflow-permission-probes',
                startedAt=started, completedAt=int(wall()), planSha256=m.sha(m.canonical(client.queries)),
                credentialExchangeCompleted=client.tokens.exchanges > 0, observations=observations)


def evaluate(cfg, binding, value, *, now):
    queries = plan(cfg, binding['role']); checks = {}; a.integer(now, 1)
    try:
        m.need(all(value.get(k) == v for k, v in binding.items()) and
               value['execution'] in ('offline-permission-probes', 'workflow-permission-probes') and
               value['planSha256'] == m.sha(m.canonical(queries)), 'permission observation binding')
        a.integer(value['startedAt'], 1); a.integer(value['completedAt'], 1)
        m.need(now-900 < value['startedAt'] <= value['completedAt'] <= now and
               value['completedAt']-value['startedAt'] <= 180, 'permission observation time')
        m.need(value['credentialExchangeCompleted'] is True and set(value['observations']) == set(queries), 'permission observation completeness')
        for name, query in queries.items():
            observed = value['observations'][name]
            if 'error' in observed:
                checks[name] = dict(status='BLOCKED', reason='permission query unavailable', httpStatus=observed.get('httpStatus'))
                continue
            if name == 'image':
                m.need(set(observed) == {'image'} and observed['image'] == image(observed['image'], query),
                       'Runner image observation fields')
                checks[name] = dict(status='PASS', detail=observed['image'])
                continue
            actual = set(permissions(observed, query)); missing = sorted(set(query['required'])-actual)
            forbidden = sorted(set(query['forbidden']) & actual)
            checks[name] = dict(status='BLOCKED' if missing or forbidden else 'PASS',
                                missing=missing, forbidden=forbidden)
    except (KeyError, TypeError, ValueError): checks['binding'] = dict(status='BLOCKED', reason='invalid/incomplete permission observations')
    return dict(binding, status='PRECHECK_PASS' if checks and all(v['status']=='PASS' for v in checks.values()) else 'BLOCKED',
                execution=value.get('execution', 'incomplete-permission-probes'), observedAt=now,
                plan=queries, observationsSha256=m.sha(m.canonical(value)), checks=checks,
                limitations=list(LIMITATIONS), pending=list(PENDING), **BOUNDARY)


def summary(value):
    def safe(v): return html.escape(str(v)).replace('|', '&#124;').replace('\n', ' ')
    image_check = value.get('checks', {}).get('image', {})
    image_section = ''
    if value.get('role') == 'runner':
        image_section = '\n## Frozen image read\n\n'+(
            ''.join('- '+safe(k)+': '+safe(v)+'\n' for k,v in image_check['detail'].items())
            if image_check.get('detail') else 'Image observation unavailable; inspect the failed checks.\n')
        image_section += '\nA successful image read does not prove permission to create a boot disk from it.\n'
    rows = [('Status',value['status'])]+[(key,value[key]) for key in
            ('role','source','runId','runAttempt','serviceAccount','provider','environment','configurationSha256','execution') if key in value]
    rows += credentials.failure_rows(value.get('failure'))
    return ('# V5.1 identity permission precheck\n\n| Parameter | Value |\n| --- | --- |\n'+
            ''.join('| '+safe(k)+' | '+safe(v)+' |\n' for k,v in rows)+
            '\n## Queried permissions\n\n| Scope | Result | Missing | Forbidden returned |\n| --- | --- | --- | --- |\n'+
            ''.join('| '+safe(k)+' | '+safe(v['status'])+' | '+safe(v.get('missing',v.get('reason',''))) +
                    ' | '+safe(v.get('forbidden',[]))+' |\n' for k,v in value.get('checks',{}).items())+
            image_section+
            '\n## Still required\n\n'+''.join('- '+safe(v)+'\n' for v in PENDING)+
            '\n## Limitations\n\n'+''.join('- '+safe(v)+'\n' for v in LIMITATIONS)+
            '\nThis precheck does not authorize activation, cleanup readiness or paid execution.\n')


def check_saved(cfg, binding, output, *, now):
    """Recompute a same-run precheck; local JSON still is not signed provenance."""
    output = Path(output)
    observed = read(output/'observations.json'); receipt = read(output/'receipt.json')
    m.need(read(output/'binding.json') == binding, 'permission saved binding')
    m.need(receipt == evaluate(cfg, binding, observed, now=receipt['observedAt']), 'permission receipt differs from observations')
    result = evaluate(cfg, binding, observed, now=now)
    m.need(result['status'] == 'PRECHECK_PASS' and result['execution'] == 'workflow-permission-probes', 'permission precheck incomplete or offline')
    return dict(status='PASS', detail=dict(serviceAccount=binding['serviceAccount'],
                scopes=list(plan(cfg, binding['role'])), objectPermissionsQualified=False))


def run(cfg, env, output, *, role, source, checkout):
    binding = identity(cfg, env, role=role, source=source, checkout=checkout)
    entry.collect_run(binding)  # Existing exact latest/attempt/latest repository checks.
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    write_once(output/'binding.json', binding)
    value = dict(binding, status='BLOCKED', execution='incomplete-permission-probes', **BOUNDARY)
    phase = 'credentials'
    try:
        client = NetworkClient(cfg, binding, env, entry.credential_file(env))
        phase = 'permissions'; observed = collect(cfg, binding, client, wall=time.time)
        write_once(output/'observations.json', observed)
        phase = 'github'; entry.collect_run(binding)
        value = evaluate(cfg, binding, observed, now=int(time.time()))
    except (Exception, KeyboardInterrupt) as error:
        value['failure'] = dict(phase=phase, type=type(error).__name__, **credentials.diagnostic(error))
    write_once(output/'receipt.json', value); (output/'summary.md').write_text(summary(value))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role', choices=ROLES, required=True)
    parser.add_argument('--source', required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = run(read(p.CONFIG), os.environ, args.output, role=args.role, source=args.source,
                checkout=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ci.ROOT, text=True).strip())
    result = dict(status=value['status'], role=args.role, paidAdmission=False)
    if 'failure' in value: result['failure'] = value['failure']
    print(m.canonical(result).decode())
    if value['status'] != 'PRECHECK_PASS': raise SystemExit(2)


if __name__ == '__main__': main()
