"""Reconstruct shared expired cleanup from durable HTTP state, offline only.

No original runner, SSH private key, local workspace or caller-supplied request is
needed. Native credentials and writes remain independently disabled.
"""
from copy import deepcopy
from . import cloud_authority as a, cloud_gcp as g, cloud_runner as r, performance_model as m
from .guest_setup import access


def context_key(req, *, authority=a):
    return authority.PREFIX+'attempts/'+authority.validate_request(req)+'/cleanup-context.json'


def context(configuration, req, guest_access, *, authority=a):
    value = dict(schema=authority.CONTEXT_SCHEMA, execution=authority.EXECUTION, paidCloud=authority.PAID_CLOUD,
                 requestSha256=authority.validate_request(req), configuration=deepcopy(configuration),
                 guestAccess=deepcopy(guest_access))
    validate_context(value, req, authority=authority)
    return value


def validate_context(value, req, *, authority=a):
    sha = authority.validate_request(req)
    m.need(type(value) is dict and set(value) == {'schema', 'execution', 'paidCloud', 'requestSha256',
           'configuration', 'guestAccess'} and value['schema'] == authority.CONTEXT_SCHEMA and
           value['execution'] == authority.EXECUTION and value['paidCloud'] is authority.PAID_CLOUD and
           value['requestSha256'] == sha, 'cleanup context identity')
    m.need(g.config(value['configuration']) == req['configurationSha256'], 'cleanup context configuration')
    guest = value['guestAccess']
    if 'guestAccessSha256' in req:
        access(guest)
        m.need(guest['attempt'] == req['attempt'] and m.sha(m.canonical(guest)) == req['guestAccessSha256'],
               'cleanup context SSH attempt/digest')
    else:
        m.need(guest is None, 'cleanup context unbound SSH access')
    return value


def retain_context(store, req, value, *, authority=a):
    validate_context(value, req, authority=authority)
    m.need(store.execution == authority.ADAPTER_EXECUTION and getattr(store, 'bucket', None) == value['configuration']['bucket'],
           'cleanup context storage bucket/scope')
    return r.retain(store, context_key(req, authority=authority), value)


def reconcile(configuration, api, output, *, trigger, now, authority=a, on_expired=None):
    """Bootstrap a new provider only after the shared expiry/grace check.

    The configured bucket is the entry location, not deletion authority. The
    retained lease, charged request, context and original operations bind scope.
    """
    m.need(api.offline is True, 'native cleanup disabled pending qualification/activation')
    g.config(configuration)
    store = g.Store(configuration, api, authority=authority)

    def reconstruct(lease):
        req = lease['request']; sha = authority.validate_request(req)
        m.need(g.config(configuration) == req['configurationSha256'], 'cleanup selected configuration')
        ledger = store.get(a.LEDGER)
        m.need(ledger is not None, 'cleanup reservation missing')
        _, attempts = authority.inspect_ledger(ledger[1])
        m.need(sha in attempts and attempts[sha]['request'] == req, 'cleanup reservation mismatch')
        retained = store.get(context_key(req, authority=authority))
        m.need(retained is not None, 'cleanup context missing')
        value = validate_context(retained[1], req, authority=authority)
        m.need(value['configuration'] == configuration, 'cleanup retained configuration')
        return g.Compute(configuration, req, api, guest_access=value['guestAccess'], authority=authority)

    return r.reconcile(store, None, output, trigger=trigger, now=now, provider_factory=reconstruct, authority=authority, on_expired=on_expired)
