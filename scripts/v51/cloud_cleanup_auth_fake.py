"""Offline HTTP credential issuer double; never cryptographic/IAM evidence."""
import base64
from copy import deepcopy
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit, urlencode
from . import cloud_cleanup_credentials as auth, cloud_ci as ci, performance_model as m


# Synthetic runner route with repeated slashes and identifiers after /idtoken;
# keep this in shared qualification so a terminal-suffix assumption cannot hide.
OIDC = ('https://pipelines.actions.githubusercontent.com/42//idtoken/'
        '11111111-1111-4111-8111-111111111111/22222222-2222-4222-8222-222222222222?api-version=2.0')
SUBJECT_SECRET = 'offline-request-secret'
FEDERATED_SECRET = 'offline-federated-secret'
ACCOUNT_SECRET = 'offline-account-secret'


def inputs(binding, env):
    env = dict(env, ACTIONS_ID_TOKEN_REQUEST_URL=OIDC, ACTIONS_ID_TOKEN_REQUEST_TOKEN=SUBJECT_SECRET)
    value = dict(type='external_account', audience='//iam.googleapis.com/'+binding['provider'],
        subject_token_type=auth.JWT, token_url=auth.STS,
        service_account_impersonation_url='https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+binding['serviceAccount']+':generateAccessToken',
        credential_source=dict(url=OIDC+'&'+urlencode(dict(audience='https://iam.googleapis.com/'+binding['provider'])),
            headers=dict(Authorization='Bearer '+SUBJECT_SECRET), format=dict(type='json', subject_token_field_name='value')))
    return env, value


class Issuer:
    offline = True
    def __init__(self, binding, clock):
        self.binding, self.clock = deepcopy(binding), clock
        self.calls, self.claim_changes, self.response_changes = [], {}, {}
        self.fail, self.delay, self.lifetime = None, 0, 3600

    def jwt(self):
        b = self.binding; now = self.clock.wall()
        owner, repository = ci.REPOSITORY.split('/')
        value = dict(iss='https://token.actions.githubusercontent.com', aud='https://iam.googleapis.com/'+b['provider'],
            sub=f'repo:{owner}@{ci.OWNER_ID}/{repository}@{ci.REPOSITORY_ID}:environment:'+b['environment'], repository=ci.REPOSITORY,
            repository_id=str(ci.REPOSITORY_ID), repository_owner_id=str(ci.OWNER_ID),
            ref='refs/heads/master', environment=b['environment'], event_name=b['event'],
            workflow_ref=ci.REPOSITORY+'/'+b['workflow']+'@refs/heads/master', workflow_sha=b['source'], sha=b['source'],
            run_id=str(b['runId']), run_attempt=str(b['runAttempt']), iat=now, nbf=now, exp=now+300)
        value.update(self.claim_changes)
        encode = lambda v:base64.urlsafe_b64encode(m.canonical(v)).rstrip(b'=').decode()
        return encode(dict(alg='RS256',kid='offline-key'))+'.'+encode(value)+'.b2ZmbGluZQ'

    def send(self, method, url, headers, body, timeout, maximum):
        host = urlsplit(url).hostname
        stage = 'sts' if host == 'sts.googleapis.com' else 'impersonation' if host == 'iamcredentials.googleapis.com' else 'oidc'
        self.calls.append(dict(stage=stage, timeout=timeout))  # No tokens/bodies/URLs retained.
        self.clock.sleep(self.delay)
        if self.fail == stage: return 403, b'private issuer error '+SUBJECT_SECRET.encode()
        if stage == 'oidc':
            m.need(method == 'GET' and body is None and headers == {'Authorization':'Bearer '+SUBJECT_SECRET} and
                parse_qs(urlsplit(url).query)['audience'] == ['https://iam.googleapis.com/'+self.binding['provider']], 'offline OIDC request')
            self.subject = self.jwt()
            result = dict(value=self.subject)
        elif stage == 'sts':
            form = {k:v[0] for k,v in parse_qs(body.decode()).items()}
            expected = dict(audience='//iam.googleapis.com/'+self.binding['provider'],
                grant_type='urn:ietf:params:oauth:grant-type:token-exchange', requested_token_type=auth.ACCESS,
                subject_token_type=auth.JWT, subject_token=self.subject, scope=auth.SCOPE)
            m.need(method == 'POST' and form == expected and headers == {'Content-Type':'application/x-www-form-urlencoded'}, 'offline STS request')
            result = dict(access_token=FEDERATED_SECRET, issued_token_type=auth.ACCESS, token_type='Bearer', expires_in=300)
        else:
            m.need(method == 'POST' and url.endswith('/'+self.binding['serviceAccount']+':generateAccessToken') and
                headers == {'Content-Type':'application/json','Authorization':'Bearer '+FEDERATED_SECRET} and
                m.strict_json(body) == dict(scope=[auth.SCOPE], lifetime='3600s'), 'offline impersonation request')
            expiry = datetime.fromtimestamp(self.clock.wall()+self.lifetime,timezone.utc).isoformat().replace('+00:00','Z')
            result = dict(accessToken=ACCOUNT_SECRET, expireTime=expiry)
        result.update(self.response_changes.get(stage,{}))
        return 200, m.canonical(result)


class Provider:
    offline = True
    def __init__(self, delegate): self.delegate = delegate; self.authorized_calls = 0
    def send(self, method, url, headers, body, timeout, maximum):
        m.need(headers['Authorization'] == 'Bearer '+ACCOUNT_SECRET, 'provider received wrong credential')
        self.authorized_calls += 1
        return self.delegate.send(method, url, headers, body, timeout, maximum)
