"""Pure root-admission contract checks. No elevation, network or guest writes.

Observations supplied here qualify only the offline contract. A PASS is not an
execution capability or evidence that the observed privileged context existed.
"""
from copy import deepcopy
import re
from . import cloud_authority as a, guest_delivery as delivery, guest_delivery_receiver as receiver
from . import guest_setup, performance_model as m, remote_command as command

from .guest_root_policy import PARENT, EXECUTION, validate_plan, assess


def plan(req, lease, facts, access, helper):
    """Bind the proposed installation to retained provider IDs and exact bytes."""
    request_sha = a.validate_request(req); a.validate_lease(lease); guest_setup.access(access)
    m.need(lease['request'] == req and req.get('guestAccessSha256') == m.sha(m.canonical(access)),
           'root request/lease/access binding')
    provider = facts['provider']
    m.need(type(provider) is dict and set(provider) == {'instanceId', 'diskId', 'node', 'sizeGiB', 'attempt'} and
           type(provider['node']) is int and provider['node'] in (1, 2, 3) and
           type(provider['sizeGiB']) is int and provider['sizeGiB'] == 100 and
           provider['attempt'] == req['attempt'], 'root provider shape')
    node = provider['node']
    wanted = [('instance', 'voter', provider['instanceId']), ('disk', 'data', provider['diskId']),
              ('disk', 'boot', facts['bootDiskId'])]
    for kind, purpose, identity in wanted:
        m.need(isinstance(identity, str) and re.fullmatch('[1-9][0-9]{0,19}', identity), 'root numeric resource ID')
        rows = [row for row in lease['resources'] if row['spec']['kind'] == kind and
                row['spec']['purpose'] == purpose and row['spec'].get('node') == node]
        m.need(len(rows) == 1 and rows[0]['attempted'] is True and rows[0]['id'] == identity,
               'root retained resource identity')
        if kind == 'instance': m.need(facts['instance'] == rows[0]['spec']['name'], 'root instance name')
    m.need(len({identity for _, _, identity in wanted}) == 3, 'root distinct resource IDs')
    binding = command.binding(req['source'], req['bundleSha256'], req['attempt'], 'node-'+str(node))
    desc = delivery.describe(helper, binding, provider, access)
    result = dict(schema='gse-v51-root-admission-plan-v1', execution=EXECUTION, requestSha256=request_sha,
        providerFactsSha256=m.sha(m.canonical(facts)), delivery=desc, access=access,
        destination=PARENT+'/'+req['attempt']+'-node-'+str(node), allowedActions=['install', 'query', 'check'],
        paidCloud=False, privilegedExecution=False, nativeWritesEnabled=False, fullRemoteQualification=False)
    return deepcopy(validate_plan(result))
