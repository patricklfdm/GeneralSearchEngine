"""Reconstruct shared expired cleanup from durable HTTP state.

No original runner, SSH private key, local workspace or caller-supplied request is
needed. Network writes require the dedicated native cleanup policy API.
"""
from copy import deepcopy
from . import cloud_authority as a, cloud_gcp as g, cloud_runner as r, performance_model as m
from .guest_setup import access


def context_key(req, *, authority=a):
    return authority.PREFIX+'attempts/'+authority.validate_request(req)+'/cleanup-context.json'


def context(configuration, req, guest_access, *, authority=a, qualification_manifest=None):
    value = dict(schema=authority.CONTEXT_SCHEMA, execution=authority.EXECUTION, paidCloud=authority.PAID_CLOUD,
                 requestSha256=authority.validate_request(req), configuration=deepcopy(configuration),
                 guestAccess=deepcopy(guest_access))
    if qualification_manifest is not None:
        value['schema'] = 'gse-v51-topology-cleanup-context-v1'
        value['qualificationManifest'] = deepcopy(qualification_manifest)
    validate_context(value, req, authority=authority)
    return value


def validate_context(value, req, *, authority=a):
    sha = authority.validate_request(req)
    fields = {'schema', 'execution', 'paidCloud', 'requestSha256', 'configuration', 'guestAccess'}
    schema = authority.CONTEXT_SCHEMA
    if type(value) is dict and 'qualificationManifest' in value:
        from . import cloud_native_authority as native, cloud_topology_contract as topology
        m.need(authority is native, 'topology context native authority')
        topology.validate(value['qualificationManifest'], req, value['configuration'])
        fields.add('qualificationManifest')
        schema = 'gse-v51-topology-cleanup-context-v1'
    m.need(type(value) is dict and set(value) == fields and value['schema'] == schema and
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


def provider_from_context(value, req, api, *, authority=a):
    validate_context(value, req, authority=authority)
    return g.Compute(value['configuration'], req, api, guest_access=value['guestAccess'], authority=authority,
                     qualification_manifest=value.get('qualificationManifest'))


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
    from .cloud_native_cleanup import NetworkCleanupApi
    from . import cloud_native_authority as native
    m.need(api.offline is True or authority is native and type(api) is NetworkCleanupApi,
           'native cleanup disabled pending qualification/activation')
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
        return provider_from_context(value, req, api, authority=authority)

    return r.reconcile(store, None, output, trigger=trigger, now=now, provider_factory=reconstruct, authority=authority, on_expired=on_expired)
