"""Additional immutable SSH route/cursor binding; no remote host admission."""
import re
from pathlib import Path
from . import remote_command as c,remote_topology as topology
from .evidence import need,digest,encoded

SCHEMA='gse-v52-voter-ssh-binding-v1'
EXECUTION='loopback-ssh-persistent-voters-only'
BOUND_EXECUTION='bound-host-ssh-persistent-voters-only'


def target(value):
    need(type(value) is dict and set(value)=={'host','port','user','alias','hostPinSha256'},'SSH voter retained target fields')
    need(value['host']=='127.0.0.1' and type(value['port']) is int and 1024<=value['port']<=65535,'SSH voter retained local target')
    need(type(value['user']) is str and re.fullmatch('[a-z_][a-z0-9_-]{0,63}',value['user']) and
         type(value['alias']) is str and re.fullmatch('gse-v52-[0-9a-f]{32}',value['alias']),'SSH voter retained target identity')
    c.hex_value(value['hostPinSha256'],64,'SSH voter host pin')


def binding(value):
    need(type(value) is dict and set(value)=={'schema','execution','nodes'} and value['schema']==SCHEMA and
         value['execution'] in (EXECUTION,BOUND_EXECUTION) and type(value['nodes']) is dict and set(value['nodes'])==set(topology.NODES),
         'SSH voter transport binding')
    for row in value['nodes'].values():target(row)
    need(len({row['alias'] for row in value['nodes'].values()})==3,'SSH voter duplicate route alias')


def channels(value,expected,sha,events,*,crashed=False):
    query=value.get('terminalQuery')
    need(type(value) is dict and set(value)=={'schema','target','configSha256','channels'}|({'terminalQuery'} if query is not None else set()) and
         value['schema']=='gse-v52-voter-ssh-streams-v1' and value['target']==expected and value['configSha256']==sha,
         'SSH voter retained channel identity')
    rows=value['channels'];need(type(rows) is list and 1<=len(rows)<=4,'SSH voter channel count')
    previous=0
    for ordinal,row in enumerate(rows):
        need(type(row) is dict and set(row)=={'configSha256','after','through','terminal'} and row['configSha256']==sha,
             'SSH voter channel configuration')
        need(type(row['after']) is int and type(row['through']) is int and row['after']==previous and
             previous<=row['through']<=len(events),'SSH voter channel cursor gap/regression')
        need(type(row['terminal']) is bool and row['terminal']==(ordinal==len(rows)-1 and query is None),'SSH voter channel terminal order')
        need(row['terminal']==(row['through']==len(events)),'SSH voter terminal cursor mismatch')
        previous=row['through']
    if query is not None:
        need(crashed and events[-1]['kind']=='STOPPED' and events[-1]['exitCode']==-9 and
             previous==len(events)-1 and query==dict(configSha256=sha,after=previous,through=len(events),
             eventSha256=digest(encoded(events[-1]))),'SSH voter original crash terminal query')
        previous+=1
    need(previous==len(events) and events[-1]['kind']=='STOPPED','SSH voter incomplete terminal stream')
    return len(rows)


def validate(root,full_binding,config,sha,events):
    root=Path(root);transport=full_binding.get('remoteVoterTransport');binding(transport)
    from . import remote_host_domains as domains
    if domains.validate(full_binding) is None:need(transport['execution']==EXECUTION,'SSH voter local scope changed')
    else:domains.routes(full_binding)
    value=c.read(root/'ssh-streams.json',64<<10)
    from . import remote_voter_scope as scope
    crashed=domains.matches(full_binding,'remoteRestart',scope.RESTART_EXECUTION) and scope.generation(config)==1
    return channels(value,transport['nodes'][config['node']],sha,events,crashed=crashed)
