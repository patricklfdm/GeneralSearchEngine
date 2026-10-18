"""Whole-history backend over externally owned, pinned host routes.

The caller must retain fresh provider/lease authority and own the tunnels for the
entire history. This module creates no provider resource or tunnel, has no CLI,
and cannot turn supplied identity data into paid admission or cloud acceptance.
It replaces placement only, retaining the existing controllers and guest entries.
"""
from copy import deepcopy
from pathlib import Path
import threading
from . import remote_host_domains as domains,remote_python_runtime_qualification as installed
from . import remote_python_receiver as python
from . import remote_voter_ssh as ssh,remote_host as host
from .evidence import need,encoded,digest


class Placement:
    def __init__(self,binding,targets,roots,installations,descriptor,payload,*,java=None):
        # Copy every mutable input before using it; the owner cannot switch a
        # target, source or path after a capsule/stream has been selected.
        self.binding=deepcopy(binding);self.targets=deepcopy(targets);self.roots=deepcopy(roots)
        self.installations=deepcopy(installations);self.descriptor=deepcopy(descriptor);self.payload=payload
        self.java=deepcopy(java)
        self.claimed=False;self.lock=threading.Lock()
        value=domains.validate(self.binding);need(value is not None,'bound placement requires independent hosts')
        domains.routes(self.binding);python.descriptor(self.descriptor);python.payload(payload,self.descriptor)
        need(all(self.binding.get(k)==v for k,v in self.descriptor['source'].items()),'bound placement Python source changed')
        nodes=set(domains.topology.NODES)
        need(type(targets) is dict and type(roots) is dict and type(installations) is dict and
             set(targets)==set(roots)==set(installations)==nodes,'bound placement node set')
        for node in domains.topology.NODES:
            need(ssh.public_target(self.targets[node])==self.binding['remoteVoterTransport']['nodes'][node],
                 'bound placement pinned target changed')
            path=host.path(self.roots[node]);need(path.name==node,'bound placement receiver root')
            receipt=self.installations[node]
            need(type(receipt) is dict and set(receipt)=={'schema','descriptorSha256','root','host','filesSha256'} and
                 receipt['schema']==python.RECEIPT and receipt['descriptorSha256']==digest(encoded(self.descriptor)) and
                 receipt['filesSha256']==digest(encoded(self.descriptor['files'])),'bound placement Python receipt changed')
            own=host.path(receipt['root'])
            need(own.name=='python-'+self.descriptor['sha256'] and own!=path and own not in path.parents and
                 path not in own.parents,'bound placement installation overlaps receiver')
            domains.observed(self.binding,node,receipt['host'])
        if self.java is not None:
            from . import remote_java_evidence as j
            need(type(self.java) is dict and set(self.java)=={'descriptor','archive','installations'},'bound placement Java inputs')
            desc=self.java['descriptor'];scope=dict(schema=j.SCHEMA,descriptorSha256=digest(encoded(desc)),nodes=self.java['installations'])
            j.receipts(desc,scope,self.binding);j.r.verify_archive(self.java['archive'],desc)
            for node,receipt in self.java['installations'].items():
                own=host.path(receipt['root']);path=host.path(self.roots[node]);python_root=host.path(self.installations[node]['root'])
                need(own not in (path,python_root) and own not in path.parents and path not in own.parents and
                     own not in python_root.parents and python_root not in own.parents,'bound placement Java overlaps receiver')

    def factory(self,name):
        base=installed.receiver_type(name);placement=self
        class Receivers(base):
            def __init__(self,root,selected,expected):
                need(type(expected) is dict and set(expected)=={'source','checkoutSha256','java'} and
                     selected==name and all(placement.binding.get(k)==v for k,v in expected.items()),
                     'bound placement selected source/history changed')
                with placement.lock:
                    need(not placement.claimed,'bound placement already consumed');placement.claimed=True
                super().__init__(root,selected,expected,targets=deepcopy(placement.targets),
                    installations=deepcopy(placement.installations),descriptor=deepcopy(placement.descriptor),payload=placement.payload,
                    java=deepcopy(placement.java))
            def topology_plan(self):
                for node in domains.topology.NODES:
                    need(ssh.public_target(self.targets[node])==placement.binding['remoteVoterTransport']['nodes'][node],
                         'bound placement pinned target changed')
                self.binding[domains.FIELD]=deepcopy(placement.binding[domains.FIELD])
                return deepcopy(placement.binding['remoteTopology'])
            def receiver_root(self,node):return Path(placement.roots[node])
            def prepare(self):
                super().prepare()
                need(self.binding['remoteVoterTransport']==placement.binding['remoteVoterTransport'],
                     'bound placement prepared route changed')
                domains.chain(self.binding)
        return Receivers
