"""Closed three-voter topology input; it grants no remote or provider authority."""
import ipaddress
from pathlib import Path
import uuid
from .evidence import need, encoded
from scripts.v51.performance_model import strict_json

FILE='remote-topology.json'
SCHEMA='gse-v52-remote-topology-v1'
NODES=('node-1','node-2','node-3')
NETWORKS=tuple(ipaddress.ip_network(v) for v in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))
MAX_BYTES=4096


def validate(value):
    need(type(value) is dict and set(value)=={'schema','placement','groupId','members'},'remote topology fields')
    need(value['schema']==SCHEMA and value['placement'] in ('local-no-gcp','owned-private-hosts'),'remote topology domain')
    raw=value['groupId']
    need(type(raw) is str and len(raw)==36,'remote topology group')
    try:group=uuid.UUID(raw)
    except ValueError:raise ValueError('remote topology group') from None
    need(str(group)==raw and group.int!=0,'remote topology group')
    members=value['members'];need(type(members) is list and len(members)==3,'remote topology voter count')
    hosts=set();endpoints=set()
    for node,row in zip(NODES,members):
        need(type(row) is dict and set(row)=={'node','host','port'} and row['node']==node,'remote topology ordered voter')
        host,port=row['host'],row['port']
        need(type(host) is str and 7<=len(host)<=15,'remote topology address')
        try:address=ipaddress.IPv4Address(host)
        except ipaddress.AddressValueError:raise ValueError('remote topology address') from None
        need(str(address)==host,'remote topology canonical address')
        need(address.is_loopback if value['placement']=='local-no-gcp' else any(address in network for network in NETWORKS),
             'remote topology placement/address')
        need(type(port) is int and 1024<=port<=65535,'remote topology port')
        need((host,port) not in endpoints,'remote topology duplicate endpoint')
        hosts.add(host);endpoints.add((host,port))
    need(value['placement']=='local-no-gcp' or len(hosts)==3,'remote topology requires three private hosts')
    need(len(encoded(value))+1<=MAX_BYTES,'remote topology byte bound')
    return value


def read(root):
    path=Path(root)/FILE
    need(not path.is_symlink() and path.is_file() and 0<path.stat().st_size<=MAX_BYTES,'remote topology file bound/type')
    with path.open('rb') as stream:raw=stream.read(MAX_BYTES+1)
    need(len(raw)<=MAX_BYTES,'remote topology byte bound')
    return validate(strict_json(raw))
