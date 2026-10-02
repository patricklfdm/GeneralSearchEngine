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
DIAGNOSTICS = {
    'CREDENTIAL_FILE_PATH':'The auth action credential path is missing or not absolute.',
    'CREDENTIAL_FILE_OPEN':'The credential file cannot be opened without following symlinks.',
    'CREDENTIAL_FILE_TYPE':'The credential file is not a regular file.',
    'CREDENTIAL_FILE_SIZE':'The credential file is empty or exceeds the byte limit.',
    'CREDENTIAL_FILE_READ':'The credential file cannot be read.',
    'CREDENTIAL_FILE_JSON':'The credential file is not valid strict JSON.',
    'OIDC_URL_SHAPE':'The runtime OIDC request URL is missing or malformed.',
    'OIDC_URL_SCHEME':'The runtime OIDC request URL does not use HTTPS.',
    'OIDC_URL_HOST':'The runtime OIDC host is outside the admitted GitHub domain.',
    'OIDC_URL_AUTHORITY':'The runtime OIDC URL includes a port, user information or another unsupported authority form.',
    'OIDC_URL_PATH':'The runtime OIDC URL has no absolute endpoint path.',
    'OIDC_URL_FRAGMENT':'The runtime OIDC URL contains a fragment.',
    'OIDC_URL_QUERY':'The runtime OIDC query is malformed, duplicated or already contains an audience.',
    'OIDC_REQUEST_TOKEN_SHAPE':'The runtime OIDC request token is missing or malformed.',
    'DESCRIPTOR_TYPE':'The credential descriptor is not a JSON object.',
    'DESCRIPTOR_FIELDS':'The credential descriptor has missing or unexpected fields.',
    'DESCRIPTOR_CREDENTIAL_TYPE':'The credential type does not match external_account.',
    'DESCRIPTOR_AUDIENCE':'The credential audience does not match the bound WIF provider.',
    'DESCRIPTOR_SUBJECT_TOKEN_TYPE':'The subject token type does not match JWT.',
    'DESCRIPTOR_TOKEN_URL':'The token URL does not match the fixed Google STS endpoint.',
    'DESCRIPTOR_IMPERSONATION_URL':'The impersonation URL does not match the bound service account.',
    'DESCRIPTOR_SOURCE_FIELDS':'The credential source has missing or unexpected fields or is not an object.',
    'DESCRIPTOR_SOURCE_URL':'The credential source URL does not match the runtime OIDC endpoint.',
    'DESCRIPTOR_SOURCE_QUERY':'The credential source query does not match the runtime query and bound audience.',
    'DESCRIPTOR_SOURCE_AUTHORIZATION':'The credential source header does not match the runtime request token.',
    'DESCRIPTOR_SOURCE_FORMAT':'The credential source format does not match the pinned auth action.',
}


class CredentialError(ValueError):
    """Only a code from this closed inventory may reach receipts or summaries."""
    def __init__(self, reason_code):
        if type(reason_code) is not str or reason_code not in DIAGNOSTICS:
            raise ValueError('unknown credential diagnostic code')
        self.reason_code = reason_code
        phase = 'file' if reason_code.startswith('CREDENTIAL_FILE_') else 'descriptor'
        super().__init__('cleanup credential '+phase+' rejected: '+reason_code)


def require(value, code):
    if not value: raise CredentialError(code)


def diagnostic(error):
    code = getattr(error, 'reason_code', None)
    return {'reasonCode':code} if isinstance(error, CredentialError) and type(code) is str and code in DIAGNOSTICS else {}


def failure_rows(failure):
    if not failure: return []
    code = failure.get('reasonCode')
    code = code if type(code) is str and code in DIAGNOSTICS else 'UNCLASSIFIED'
    phase = failure.get('phase')
    phase = phase if phase in ('credentials','permissions','github','reconciliation','entry') else 'unknown'
    return [('Failure phase',phase),('Failure code',code),
            ('Failure detail',DIAGNOSTICS.get(code,'No classified credential failure was retained.'))]


def bearer(value):
    m.need(isinstance(value, str) and 0 < len(value) <= 65536 and
           all(33 <= ord(c) <= 126 for c in value), 'cleanup credential shape')
    return value


def descriptor(binding, env, value):
    """Accept the exact auth@7c6bc77 descriptor and selected cleanup identity."""
    raw = env.get('ACTIONS_ID_TOKEN_REQUEST_URL', '')
    require(isinstance(raw,str) and raw, 'OIDC_URL_SHAPE')
    try: parsed = urlsplit(raw)
    except ValueError: raise CredentialError('OIDC_URL_SHAPE') from None
    require(parsed.scheme == 'https', 'OIDC_URL_SCHEME')
    require(parsed.hostname is not None and parsed.hostname.endswith('.actions.githubusercontent.com'), 'OIDC_URL_HOST')
    require(parsed.netloc == parsed.hostname, 'OIDC_URL_AUTHORITY')
    # The runner supplies an opaque service route, not a stable /idtoken suffix.
    # Bind the descriptor to that exact path below, as the pinned auth action does.
    require(parsed.path.startswith('/') and parsed.path != '/', 'OIDC_URL_PATH')
    require(not parsed.fragment, 'OIDC_URL_FRAGMENT')
    try: query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True) if parsed.query else []
    except ValueError: raise CredentialError('OIDC_URL_QUERY') from None
    require(len(dict(query)) == len(query) and 'audience' not in dict(query), 'OIDC_URL_QUERY')
    audience = 'https://iam.googleapis.com/'+binding['provider']
    url = parsed._replace(query=urlencode([*query, ('audience', audience)])).geturl()
    # URLSearchParams in the pinned action may encode spaces as '+' too. Compare
    # components/query pairs instead of depending on parameter ordering.
    try: token = bearer(env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN'))
    except ValueError: raise CredentialError('OIDC_REQUEST_TOKEN_SHAPE') from None
    expected = dict(type='external_account', audience='//iam.googleapis.com/'+binding['provider'],
                    subject_token_type=JWT, token_url=STS,
                    service_account_impersonation_url='https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+
                        binding['serviceAccount']+':generateAccessToken',
                    credential_source=dict(url=url, headers={'Authorization':'Bearer '+token},
                                           format=dict(type='json', subject_token_field_name='value')))
    require(type(value) is dict, 'DESCRIPTOR_TYPE')
    require(set(value) == set(expected), 'DESCRIPTOR_FIELDS')
    for field,code in (
        ('type','DESCRIPTOR_CREDENTIAL_TYPE'), ('audience','DESCRIPTOR_AUDIENCE'),
        ('subject_token_type','DESCRIPTOR_SUBJECT_TOKEN_TYPE'), ('token_url','DESCRIPTOR_TOKEN_URL'),
        ('service_account_impersonation_url','DESCRIPTOR_IMPERSONATION_URL')):
        require(value[field] == expected[field], code)
    actual = value['credential_source']; wanted = expected['credential_source']
    require(type(actual) is dict and set(actual) == set(wanted), 'DESCRIPTOR_SOURCE_FIELDS')
    require(type(actual['url']) is str, 'DESCRIPTOR_SOURCE_URL')
    try:
        source = urlsplit(actual['url'])
    except ValueError: raise CredentialError('DESCRIPTOR_SOURCE_URL') from None
    require(source._replace(query='') == urlsplit(url)._replace(query=''), 'DESCRIPTOR_SOURCE_URL')
    try: actual_query = parse_qsl(source.query, keep_blank_values=True, strict_parsing=True)
    except ValueError: raise CredentialError('DESCRIPTOR_SOURCE_QUERY') from None
    require(sorted(actual_query) == sorted(parse_qsl(urlsplit(url).query, keep_blank_values=True, strict_parsing=True)),
            'DESCRIPTOR_SOURCE_QUERY')
    require(actual['headers'] == wanted['headers'], 'DESCRIPTOR_SOURCE_AUTHORIZATION')
    require(actual['format'] == wanted['format'], 'DESCRIPTOR_SOURCE_FORMAT')
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
        owner, repository = ci.REPOSITORY.split('/')
        # This repository uses GitHub's immutable subject format. Bind both names
        # and numeric IDs; do not fall back to the legacy name-only subject.
        subject = f'repo:{owner}@{ci.OWNER_ID}/{repository}@{ci.REPOSITORY_ID}:environment:'+binding['environment']
        expected = dict(iss='https://token.actions.githubusercontent.com',
                        aud='https://iam.googleapis.com/'+binding['provider'],
                        sub=subject,
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
