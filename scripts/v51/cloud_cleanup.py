"""Reconstruct shared expired cleanup from durable HTTP state, offline only.

No original runner, SSH private key, local workspace or caller-supplied request is
needed. Native credentials and writes remain independently disabled.
"""
from copy import deepcopy
from . import cloud_authority as a, cloud_gcp as g, cloud_runner as r, performance_model as m
from .guest_setup import access


def context_key(req):
    return a.PREFIX+'attempts/'+a.validate_request(req)+'/cleanup-context.json'


def context(configuration, req, guest_access):
    value = dict(schema='gse-v51-cleanup-context-v1', execution=a.EXECUTION, paidCloud=False,
                 requestSha256=a.validate_request(req), configuration=deepcopy(configuration),
                 guestAccess=deepcopy(guest_access))
    validate_context(value, req)
    return value


def validate_context(value, req):
    sha = a.validate_request(req)
    m.need(type(value) is dict and set(value) == {'schema', 'execution', 'paidCloud', 'requestSha256',
           'configuration', 'guestAccess'} and value['schema'] == 'gse-v51-cleanup-context-v1' and
           value['execution'] == a.EXECUTION and value['paidCloud'] is False and
           value['requestSha256'] == sha, 'cleanup context identity')
    m.need(g.config(value['configuration']) == req['configurationSha256'], 'cleanup context configuration')
    guest = value['guestAccess']
    if req['schema'] == 'gse-v51-cloud-request-v2':
        access(guest)
        m.need(guest['attempt'] == req['attempt'] and m.sha(m.canonical(guest)) == req['guestAccessSha256'],
               'cleanup context SSH attempt/digest')
    else:
        m.need(guest is None, 'cleanup context unbound SSH access')
    return value


def retain_context(store, req, value):
    validate_context(value, req)
    m.need(store.execution == a.EXECUTION and getattr(store, 'bucket', None) == value['configuration']['bucket'],
           'cleanup context storage bucket/scope')
    return r.retain(store, context_key(req), value)


def reconcile(configuration, api, output, *, trigger, now):
    """Bootstrap a new provider only after the shared expiry/grace check.

    The configured bucket is the entry location, not deletion authority. The
    retained lease, charged request, context and original operations bind scope.
    """
    m.need(api.offline is True, 'native cleanup disabled pending qualification/activation')
    g.config(configuration)
    store = g.Store(configuration, api)

    def reconstruct(lease):
        req = lease['request']; sha = a.validate_request(req)
        m.need(g.config(configuration) == req['configurationSha256'], 'cleanup selected configuration')
        ledger = store.get(a.LEDGER)
        m.need(ledger is not None, 'cleanup reservation missing')
        _, attempts = a.inspect_ledger(ledger[1])
        m.need(sha in attempts and attempts[sha]['request'] == req, 'cleanup reservation mismatch')
        retained = store.get(context_key(req))
        m.need(retained is not None, 'cleanup context missing')
        value = validate_context(retained[1], req)
        m.need(value['configuration'] == configuration, 'cleanup retained configuration')
        return g.Compute(configuration, req, api, guest_access=value['guestAccess'])

    return r.reconcile(store, None, output, trigger=trigger, now=now, provider_factory=reconstruct)
