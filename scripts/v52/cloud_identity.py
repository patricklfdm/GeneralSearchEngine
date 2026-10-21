"""Fresh provider samples for one bound guest; not guest or paid qualification."""
from copy import deepcopy
import ipaddress
import math
from . import cloud_authority as a, cloud_provider as p, cloud_access as access
from .evidence import need, encoded, digest

SCHEMA='gse-v52-provider-guest-observation-v1'


def current(provider, expected):
    need(type(provider) is p.Provider and p.qualified(provider.store,provider),'V5.2 unqualified guest observer')
    req=provider.request;need(req['schema']=='gse-v52-owned-request-v2','V5.2 missing bound guest access')
    access.validate(req['guestAccess'],req['selection']['attempt'])
    stored=provider.store.get(a.LEASE)
    p.read_need(stored is not None,'V52_CONTROL_LEASE_ABSENT')
    lease=a.validate_lease(stored[1])
    p.read_need(lease['request']==req and lease['phase']=='ACTIVE' and lease['renewedAt']<=provider.wall()<lease['expiresAt'],
                'V52_CONTROL_LEASE_INACTIVE')
    claim=a.resource_claim(lease);need(claim==expected,'V5.2 guest allocation changed')
    ledger=provider.store.get(a.LEDGER);need(ledger is not None,'V5.2 guest charge absent')
    row=a.inspect_ledger(ledger[1],domain=p.api_domain(provider.api))['attempts'].get(claim['requestSha256'])
    need(row is not None and row['status']=='PENDING' and row['request']==req,'V5.2 guest charge changed')
    return lease


def observe(provider, expected, node, *, deadline):
    """Exact instance+two disks on both sides of the original host-key request.

    A caller can retry only HostKeyPending under its original bounded readiness
    allowance. Permissions, malformed keys, ID drift and ownership expiry reject.
    """
    need(type(node) is str and node in ('node-1','node-2','node-3'),'V5.2 guest node')
    need(type(deadline) in (int,float) and math.isfinite(deadline) and deadline-provider.api.clock()<=300,
         'V5.2 guest observation deadline')
    if deadline<=provider.api.clock():raise TimeoutError('V5.2 guest observation deadline')
    current(provider,expected);claim=deepcopy(expected);identity=claim['nodes'][node]
    rows=identity['identity']['resources'];vmrow=next(r for r in rows if r['spec']['kind']=='instance')
    disks=[r for r in rows if r['spec']['kind']=='disk']
    def sample():
        current(provider,claim);values={}
        for row in rows:
            value=provider.api.call('GET',provider.endpoint(row['spec'],row['id']),deadline=deadline)
            checked=provider.inspect(row['spec'],value)
            need(checked['id']==row['id'],'V5.2 guest resource ID changed')
            values[row['spec']['name']]=value
        vm=values[vmrow['spec']['name']]
        need(vm.get('status')=='RUNNING','V5.2 guest instance not RUNNING')
        address=vm['networkInterfaces'][0].get('networkIP')
        need(type(address) is str,'V5.2 guest private address')
        ip=ipaddress.IPv4Address(address)
        need(str(ip)==address and any(ip in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')),
             'V5.2 guest private address')
        for row in disks:
            disk=values[row['spec']['name']]
            need(disk.get('status')=='READY' and type(disk.get('users')) is list and
                 [p.link(v) for v in disk['users']]==[provider.endpoint(vmrow['spec'])], 'V5.2 guest disk attachment/status')
        return dict(instanceId=vmrow['id'],instance=vmrow['spec']['name'],privateAddress=address,
                    bootDiskId=next(r['id'] for r in disks if r['spec']['purpose']=='boot'),
                    dataDiskId=next(r['id'] for r in disks if r['spec']['purpose']=='data'),
                    dataDiskGiB=next(r['spec']['sizeGiB'] for r in disks if r['spec']['purpose']=='data'))
    first=sample();pending=None;key=None
    try:
        response=provider.api.call('GET',p.query(provider.endpoint(vmrow['spec'])+'/getGuestAttributes',queryPath='hostkeys/'),
                                   deadline=deadline,maximum=65536)
        key=access.host_key(response)
    except p.ApiError as error:
        if error.status!=404:raise
        pending=access.HostKeyPending('V5.2 host-key attributes not yet available')
    except access.HostKeyPending as error:pending=error
    second=sample();current(provider,claim)
    need(first==second,'V5.2 guest observation changed')
    if provider.api.clock()>=deadline:raise TimeoutError('V5.2 guest observation deadline')
    if pending is not None:raise pending
    alias=access.alias(claim['requestSha256'],node,first['instanceId'])
    domain=p.api_domain(provider.api)
    return dict(schema=SCHEMA,execution=domain+'-v52-provider-observation',paidCloud=domain=='native',
        requestSha256=claim['requestSha256'],resourceClaimSha256=digest(encoded(claim)),
        resourceIdentitySha256=identity['resourceIdentitySha256'],node=node,
        source=deepcopy(claim['source']),attempt=claim['attempt'],configurationSha256=provider.request['configurationSha256'],
        guestAccessSha256=digest(encoded(provider.request['guestAccess'])),project=provider.config['project'],
        zone=provider.config['zone'],facts=first,hostKey=key,alias=alias,
        sshHostPinSha256=digest((alias+' '+key+'\n').encode()),guestObserved=False)


def observe_group(provider, expected, group_id, *, deadline):
    """Sequential fresh provider observations; not an atomic three-VM snapshot.

    SSH/guest identities and live rechecks still precede every original history.
    """
    from . import remote_topology as topology
    rows={node:observe(provider,expected,node,deadline=deadline) for node in topology.NODES}
    need(len({v['facts']['privateAddress'] for v in rows.values()})==3 and
         len({v['facts']['instanceId'] for v in rows.values()})==3 and
         len({v['hostKey'] for v in rows.values()})==3, 'V5.2 independent provider guests required')
    plan=dict(schema=topology.SCHEMA,placement='owned-private-hosts',groupId=group_id,
              members=[dict(node=n,host=rows[n]['facts']['privateAddress'],port=provider.config['port']) for n in topology.NODES])
    topology.validate(plan);current(provider,expected)
    need(provider.api.clock()<deadline,'V5.2 guest group late observation')
    domain=p.api_domain(provider.api)
    return dict(schema='gse-v52-provider-group-observation-v1',execution=domain+'-v52-provider-observation',
        paidCloud=domain=='native',guestObserved=False,resourceClaimSha256=digest(encoded(expected)),nodes=rows,topology=plan)
