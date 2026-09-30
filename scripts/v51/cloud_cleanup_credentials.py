"""Bound GitHub WIF exchange for cleanup; deployment/identity activation is separate.

Consumes only the pinned auth action's external-account descriptor. No ambient
ADC, gcloud account, service-account key or caller-selected impersonation target.
JWT decoding checks context; Google STS must authenticate its signature.
"""
import base64
from copy import deepcopy
from datetime import datetime
import re
import time
from urllib.parse import parse_qsl, urlencode, urlsplit
from . import cloud_http as http, performance_model as m

STS = 'https://sts.googleapis.com/v1/token'
SCOPE = 'https://www.googleapis.com/auth/cloud-platform'
JWT = 'urn:ietf:params:oauth:token-type:jwt'
ACCESS = 'urn:ietf:params:oauth:token-type:access_token'


def bearer(value):
    m.need(isinstance(value, str) and 0 < len(value) <= 65536 and
           all(33 <= ord(c) <= 126 for c in value), 'cleanup credential shape')
    return value


def descriptor(binding, env, value):
    """Accept the exact auth@7c6bc77 descriptor and selected cleanup identity."""
    raw = env.get('ACTIONS_ID_TOKEN_REQUEST_URL', '')
    parsed = urlsplit(raw)
    m.need(parsed.scheme == 'https' and parsed.hostname is not None and
           parsed.hostname.endswith('.actions.githubusercontent.com') and
           parsed.netloc == parsed.hostname and parsed.path.endswith('/idtoken') and
           not parsed.fragment, 'cleanup OIDC endpoint')
    query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True) if parsed.query else []
    m.need(len(dict(query)) == len(query) and 'audience' not in dict(query), 'cleanup OIDC query')
    audience = 'https://iam.googleapis.com/'+binding['provider']
    url = parsed._replace(query=urlencode([*query, ('audience', audience)])).geturl()
    # URLSearchParams in the pinned action may encode spaces as '+' too. Compare
    # components/query pairs instead of depending on parameter ordering.
    expected = dict(type='external_account', audience='//iam.googleapis.com/'+binding['provider'],
                    subject_token_type=JWT, token_url=STS,
                    service_account_impersonation_url='https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+
                        binding['serviceAccount']+':generateAccessToken',
                    credential_source=dict(url=url, headers={'Authorization':'Bearer '+bearer(env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN'))},
                                           format=dict(type='json', subject_token_field_name='value')))
    m.need(type(value) is dict, 'cleanup credential descriptor')
    actual = deepcopy(value)
    try:
        source = urlsplit(actual['credential_source']['url'])
        m.need(source._replace(query='') == urlsplit(url)._replace(query='') and
               sorted(parse_qsl(source.query, keep_blank_values=True, strict_parsing=True)) ==
               sorted(parse_qsl(urlsplit(url).query, keep_blank_values=True, strict_parsing=True)), 'cleanup credential source')
        actual['credential_source']['url'] = url
    except (KeyError, TypeError, AttributeError):
        raise ValueError('cleanup credential descriptor') from None
    m.need(actual == expected, 'cleanup credential identity/descriptor mismatch')
    return expected


def claims(token, binding, now):
    bearer(token)
    try:
        parts = token.split('.')
        m.need(len(parts) == 3 and all(re.fullmatch('[A-Za-z0-9_-]+', p) for p in parts), 'cleanup JWT shape')
        decode = lambda p:m.strict_json(base64.urlsafe_b64decode(p+'='*((-len(p))%4)))
        header, value = decode(parts[0]), decode(parts[1])
        m.need(header['alg'] == 'RS256' and isinstance(header['kid'], str) and header['kid'], 'cleanup JWT header')
        from . import cloud_ci as ci
        expected = dict(iss='https://token.actions.githubusercontent.com',
                        aud='https://iam.googleapis.com/'+binding['provider'],
                        sub='repo:'+ci.REPOSITORY+':environment:'+binding['environment'],
                        repository=ci.REPOSITORY, repository_id=str(ci.REPOSITORY_ID),
                        repository_owner_id=str(ci.OWNER_ID), ref='refs/heads/master',
                        environment=binding['environment'], event_name=binding['event'],
                        workflow_ref=ci.REPOSITORY+'/'+binding['workflow']+'@refs/heads/master',
                        workflow_sha=binding['source'], sha=binding['source'],
                        run_id=str(binding['runId']), run_attempt=str(binding['runAttempt']))
        m.need(all(value.get(k) == v for k,v in expected.items()), 'cleanup OIDC claims mismatch')
        m.need(all(type(value[k]) is int for k in ('iat','nbf','exp')) and
               value['iat'] <= now+30 and value['nbf'] <= now+30 and
               value['iat'] < value['exp'] and now < value['exp'], 'cleanup OIDC token expired/invalid')
    except (KeyError, TypeError, UnicodeError, ValueError):
        raise ValueError('cleanup OIDC claims rejected') from None
    return value


class _Exchange:
    def __init__(self, binding, env, value, *, transport, clock=time.monotonic, wall=time.time):
        self.transport = transport
        self.exchanges = 0
        self.binding = deepcopy(binding)
        self.value = descriptor(binding, env, value)
        self.clock, self.wall = clock, wall

    def request(self, phase, method, url, headers, body, deadline):
        remaining = deadline-self.clock()
        m.need(remaining > 0, 'cleanup credential original deadline')
        try:
            status, raw = self.transport.send(method, url, headers, body, min(30, remaining), 128 << 10)
            m.need(self.clock() <= deadline, 'late credential response')
            m.need(status == 200 and type(raw) is bytes and len(raw) <= 128 << 10, 'credential response')
            return m.strict_json(raw)
        except Exception:
            # Never retain response text, subject tokens, Authorization or URL query.
            raise ValueError('cleanup credential exchange failed: '+phase) from None

    def __call__(self, timeout):
        m.need(type(timeout) in (int,float) and 0 < timeout <= 30, 'cleanup credential timeout')
        deadline = self.clock()+timeout
        source = self.value['credential_source']
        try:
            oidc = self.request('oidc', 'GET', source['url'], source['headers'], None, deadline)['value']
            claims(oidc, self.binding, self.wall())
            form = dict(audience=self.value['audience'], grant_type='urn:ietf:params:oauth:grant-type:token-exchange',
                        requested_token_type=ACCESS, subject_token_type=JWT, subject_token=oidc, scope=SCOPE)
            sts = self.request('sts', 'POST', STS, {'Content-Type':'application/x-www-form-urlencoded'},
                               urlencode(form).encode(), deadline)
            m.need(sts['token_type'] == 'Bearer' and sts['issued_token_type'] == ACCESS and
                   type(sts['expires_in']) is int and sts['expires_in'] > 0, 'cleanup STS response')
            # STS authenticates the OIDC signature; impersonation must then succeed
            # for this one account. A federated token is never sent to Compute/GCS.
            result = self.request('impersonation', 'POST', self.value['service_account_impersonation_url'],
                {'Content-Type':'application/json', 'Authorization':'Bearer '+bearer(sts['access_token'])},
                m.canonical(dict(scope=[SCOPE], lifetime='3600s')), deadline)
            expires = result['expireTime']
            m.need(isinstance(expires,str) and expires.endswith('Z'), 'cleanup token expiry')
            remaining = datetime.fromisoformat(expires[:-1]+'+00:00').timestamp()-self.wall()
            m.need(60 < remaining <= 3600, 'cleanup token lifetime')
            token = http.AccessToken(bearer(result['accessToken']), self.clock()+remaining-60)
            self.exchanges += 1
            return token
        except Exception:
            raise ValueError('cleanup credential exchange rejected') from None


class Credentials(_Exchange):
    """Preserved offline entry: passing a live transport still fails closed."""
    def __init__(self, binding, env, value, *, transport=None, clock=time.monotonic, wall=time.time):
        transport = transport if transport is not None else http.Network()
        m.need(transport.offline is True, 'native cleanup credentials not activated')
        super().__init__(binding, env, value, transport=transport, clock=clock, wall=wall)


class NetworkCredentials(_Exchange):
    """Fixed network exchange used only by the scoped native cleanup entry.

    No caller-selected transport, token supplier, account or endpoint override.
    Descriptor/claim checks and Google STS/impersonation remain shared.
    """
    def __init__(self, binding, env, value):
        super().__init__(binding, env, value, transport=http.Network())
