"""Bound host/process domains for replay; this module grants no provider access.

The expected binding must be supplied by the admitted owner, not inferred from
collected JSON. A domain map alone does not enable private-host execution.
"""
from pathlib import Path
import uuid
from . import remote_topology as topology
from .evidence import need

SCHEMA='gse-v52-host-domains-v1'
FIELD='remoteHostDomains'
HOST_FIELDS={'resourceIdentitySha256','privateAddress','bootId','uid','sshHostPinSha256'}


def boot(value):
    need(type(value) is str and len(value)==36,'host domain boot identity')
    try:parsed=uuid.UUID(value)
    except ValueError:raise ValueError('host domain boot identity') from None
    need(str(parsed)==value and parsed.int!=0,'host domain boot identity')
    return value


def validate(binding):
    from . import remote_command as c
    value=binding.get(FIELD);plan=binding.get('remoteTopology')
    if FIELD not in binding:
        need(plan is None or plan.get('placement')=='local-no-gcp','missing independent host domains')
        return None
    need(type(value) is dict and set(value)=={'schema','source','attempt','leaseSha256','nodes'} and
         value['schema']==SCHEMA,'host domain fields')
    plan=topology.validate(plan)
    need(plan['placement']=='owned-private-hosts','host domains cannot promote local execution')
    need(type(value['source']) is dict and set(value['source'])=={'source','checkoutSha256'} and
         all(binding.get(k)==v for k,v in value['source'].items()),'host domain source binding')
    for k,n in (('source',40),('checkoutSha256',64)):c.hex_value(value['source'][k],n,'host domain source')
    c.hex_value(value['attempt'],32,'host domain attempt');c.hex_value(value['leaseSha256'],64,'host domain lease')
    nodes=value['nodes'];need(type(nodes) is dict and set(nodes)==set(topology.NODES),'host domain voter set')
    resources=set();boots=set();pins=set()
    for member in plan['members']:
        row=nodes[member['node']]
        need(type(row) is dict and set(row)==HOST_FIELDS,'host domain identity fields')
        c.hex_value(row['resourceIdentitySha256'],64,'host domain resource')
        c.hex_value(row['sshHostPinSha256'],64,'host domain SSH pin')
        boot(row['bootId'])
        need(type(row['uid']) is int and 0<=row['uid']<1<<32 and row['privateAddress']==member['host'],
             'host domain placement/user')
        resources.add(row['resourceIdentitySha256']);boots.add(row['bootId']);pins.add(row['sshHostPinSha256'])
    need(len(resources)==len(boots)==len(pins)==3,'host domains require three independent owners')
    return value


def routes(binding):
    """Require every bound host key to equal its retained pinned SSH route."""
    from . import remote_voter_ssh_evidence as ssh
    value=validate(binding);need(value is not None,'host routes require bound domains')
    transport=binding.get('remoteVoterTransport');ssh.binding(transport)
    need(transport['execution']==ssh.BOUND_EXECUTION and all(
        transport['nodes'][node]['hostPinSha256']==value['nodes'][node]['sshHostPinSha256'] for node in topology.NODES),
        'host domain SSH route changed')
    return transport


def process_key(value):
    from . import remote_command as c
    need(type(value) is dict and set(value)=={'resourceIdentitySha256','bootId','pid','startTicks'},'host process fields')
    c.hex_value(value['resourceIdentitySha256'],64,'host process resource');boot(value['bootId'])
    c.validate_process({k:value[k] for k in ('bootId','pid','startTicks')},value)
    return tuple(value[k] for k in ('resourceIdentitySha256','bootId','pid','startTicks'))


def processes(root,binding,rows):
    """Bind each JVM's logical generation to an explicit externally bound host.

    Full lifecycle/physical validation remains mandatory. These identity records
    cannot themselves certify clean exit, force history or provider ownership.
    """
    from . import remote_command as c,remote_host as host_identity
    value=validate(binding)
    if value is None:return None
    root=Path(root);result={};seen=set()
    for row in rows:
        node,generation=row['node'],row['generation'];logical=(node,generation)
        need(node in value['nodes'] and type(generation) is int and generation in (1,2) and logical not in result,
             'host process generation set')
        name=node+'-control'+('' if generation==1 else '-g2')
        identity=c.read(root/name/'identity.json')
        need(type(identity) is dict and 'host' in identity and 'jvm' in identity,'host process retained identity')
        expected=value['nodes'][node];host=identity['host'];jvm=identity['jvm'];host_identity.validate_pin(host)
        need(type(host) is dict and all(host.get(k)==expected[k] for k in ('bootId','uid')),'host process owner changed')
        c.validate_process(jvm,expected);need(jvm['pid']==row['pid'],'host process PID differs from ledger')
        domain=dict(resourceIdentitySha256=expected['resourceIdentitySha256'],**jvm)
        key=process_key(domain);need(key not in seen,'host process reused identity')
        seen.add(key);result[logical]=domain
    return result


def check_processes(rows,domains):
    """Validate a process-domain map already obtained from expected host binding."""
    expected={(p['node'],p['generation']) for p in rows}
    need(type(domains) is dict and set(domains)==expected and len(expected)==len(rows),'host process domain set')
    keys=[];nodes={}
    for row in rows:
        value=domains[row['node'],row['generation']];key=process_key(value)
        need(value['pid']==row['pid'],'host process PID differs from ledger')
        owner=key[:2]
        previous=nodes.setdefault(row['node'],owner);need(previous==owner,'host process restart moved owner')
        keys.append(key)
    need(len(set(keys))==len(rows) and len({v[0] for v in nodes.values()})==len(nodes) and
         len({v[1] for v in nodes.values()})==len(nodes),'host process ownership collision')
    for node in nodes:
        if (node,2) in domains:
            need((node,1) in domains and domains[node,2]['startTicks']>domains[node,1]['startTicks'],
                 'host process restart precedes original owner')
    return keys
