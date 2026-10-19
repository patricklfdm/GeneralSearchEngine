"""Exact V5.2 operator review data; neither approval nor copied JSON grants APIs.

Fresh GitHub/full-CI, provider/IAM, cleanup and native credential admission must
still be performed by the owned entry. No network or control writes occur here.
"""
from copy import deepcopy
from urllib.parse import urlsplit
from . import cloud_authority as a, cloud_suite as suite, cloud_provider as provider, cloud_inputs as inputs
from .evidence import need, encoded, digest

SCHEMA = 'gse-v52-prepared-request-v1'
APPROVAL_SECONDS = 3600
INCLUDES = ('three-vms', 'boot-disks', 'data-disks', 'control', 'evidence', 'cleanup', 'failed-attempts')
FLAGS = dict(paidAdmission=False, resourcesCreated=False, engineWorkloadExecuted=False, fullRemoteQualification=False)


def baseline(value, domain):
    """Retain the exact observed generation, including an initially absent ledger."""
    if value is None: return 0, a.empty_ledger(domain=domain)
    a.fields(value, 'generation ledger', 'prepared ledger baseline'); a.integer(value['generation'], 1)
    a.inspect_ledger(value['ledger'], domain=domain)
    return value['generation'], deepcopy(value['ledger'])


def estimate(value, req, now):
    """Bind an operator's dated estimate; this does not verify live cloud prices."""
    a.fields(value, 'schema currency configurationSha256 layoutSha256 createdAt expiresAt coverageSeconds '
             'costMicrousd includes priceSources', 'operator estimate')
    need(value['schema'] == 'gse-v52-operator-estimate-v1' and value['currency'] == 'USD', 'V5.2 estimate schema/currency')
    need(value['configurationSha256'] == req['configurationSha256'] and value['layoutSha256'] == digest(encoded(req['layout'])),
         'V5.2 estimate configuration/layout')
    a.integer(value['createdAt'], 1); a.integer(value['expiresAt'], value['createdAt']+1)
    a.integer(now, value['createdAt'], value['expiresAt']-1); a.integer(value['coverageSeconds'], 1)
    a.integer(value['costMicrousd'], 1)
    need(value['includes'] == list(INCLUDES), 'V5.2 estimate incomplete cost scope')
    links = value['priceSources']
    need(type(links) is list and 1 <= len(links) <= 16 and all(type(v) is str and 0 < len(v) <= 2048 for v in links)
         and len(set(links)) == len(links), 'V5.2 estimate source inventory')
    for link in links:
        parsed = urlsplit(link)
        need(parsed.scheme == 'https' and parsed.netloc in ('cloud.google.com', 'docs.cloud.google.com', 'docs.github.com') and
             not parsed.query and not parsed.fragment and parsed.path.startswith('/') and not any(c.isspace() for c in link),
             'V5.2 estimate source URL')
    return value['costMicrousd']


def prepare(configuration, project_number, proof, guest_access, resource_layout, ownership_policy, original_ledger, quote,
            *, source, sequence, member, now, domain):
    """Deterministically bind one whole member. No write or admission side effect."""
    cfg = provider.config(configuration); a.numeric(project_number); inputs.validate_proof(proof)
    need(proof['source']['source'] == a.hex_value(source, 40), 'V5.2 prepared source mismatch')
    a.integer(now, 1, a.MAX_INTEGER-APPROVAL_SECONDS)
    bound = dict(source=source, checkoutSha256=proof['source']['checkoutSha256'], sequence=sequence,
        suiteSha256=suite.PLAN_SHA, programSha256=suite.model.PLAN_SHA,
        **{key: proof[key] for key in ('buildManifestSha256', 'packageSha256', 'controlsManifestSha256')})
    selected = suite.selection(bound, member, guest_access['attempt'])
    req = a.with_access(a.request(selected, cfg, resource_layout, ownership_policy, now=now, domain=domain), guest_access)
    _, ledger = baseline(original_ledger, domain)
    previous = a.inspect_ledger(ledger, domain=domain)['reservedCostMicrousd']; cost = estimate(quote, req, now)
    reserved = a.reserve(ledger, req, previous_cost=previous, cost=cost)
    return dict(schema=SCHEMA, status='PREPARED_NOT_ADMITTED', configuration=deepcopy(configuration),
        projectNumber=project_number, inputs=deepcopy(proof), request=req, baseline=deepcopy(original_ledger),
        estimate=deepcopy(quote), reservation=dict(previousCostMicrousd=previous, costMicrousd=cost),
        warnings=a.budget_warning(req, reserved), expiresAt=min(now+APPROVAL_SECONDS, quote['expiresAt']), **FLAGS)


def validate(value, now):
    a.fields(value, 'schema status configuration projectNumber inputs request baseline estimate reservation warnings expiresAt '
             'paidAdmission resourcesCreated engineWorkloadExecuted fullRemoteQualification', 'prepared request')
    req = value['request']; domain = a.domain(req); a.validate_request(req, domain=domain)
    need(req['schema'] == 'gse-v52-owned-request-v2', 'V5.2 prepared guest access required')
    selected = req['selection']; expected = prepare(value['configuration'], value['projectNumber'], value['inputs'],
        req['guestAccess'], req['layout'], req['policy'], value['baseline'], value['estimate'],
        source=selected['binding']['source'], sequence=selected['binding']['sequence'], member=selected['member']['name'],
        now=req['createdAt'], domain=domain)
    need(encoded(value) == encoded(expected), 'V5.2 prepared data changed')
    a.integer(now, req['createdAt'], value['expiresAt']-1)
    estimate(value['estimate'], req, now)
    return digest(encoded(value))


def approval_template(value):
    req = value['request']
    return dict(schema='gse-v52-prepared-approval-v1', confirmed=False,
        planSha256=validate(value, req['createdAt']), requestSha256=a.validate_request(req, domain=a.domain(req)),
        expiresAt=value['expiresAt'], **deepcopy(value['reservation']))


def review(value, approved, confirmation, *, current_inputs, current_configuration, project_number,
           current_ledger, active_lease, now):
    """Compare independently obtained current inputs, never authorize a provider.

    Callers must re-observe facts; passing back stored copies proves no freshness.
    The future native entry must own those observations and the concrete adapter.
    """
    sha = validate(value, now); expected = approval_template(value); expected['confirmed'] = True
    need(encoded(approved) == encoded(expected) and type(confirmation) is str and confirmation == sha,
         'V5.2 exact operator approval missing/changed')
    inputs.validate_proof(current_inputs); provider.config(current_configuration); a.numeric(project_number)
    need(encoded(current_inputs) == encoded(value['inputs']), 'V5.2 current build/package changed')
    need(encoded(current_configuration) == encoded(value['configuration']) and project_number == value['projectNumber'],
         'V5.2 current provider configuration changed')
    baseline(current_ledger, a.domain(value['request']))
    need(active_lease is None and encoded(current_ledger) == encoded(value['baseline']), 'V5.2 current lease/ledger changed')
    return dict(schema='gse-v52-prepared-review-v1', status='APPROVAL_BOUND_NOT_ADMITTED', planSha256=sha,
        requestSha256=expected['requestSha256'], checkedAt=now, expiresAt=value['expiresAt'], **FLAGS)
