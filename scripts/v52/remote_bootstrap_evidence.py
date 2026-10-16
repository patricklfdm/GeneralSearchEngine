"""Inspect immutable collected authority against receiver-local sealed paths.

The caller supplies the independently retained receiver bindings. This mapping
never authorizes reopening collected files as a live voter.
"""
from pathlib import Path, PurePosixPath
import re
from scripts.v51 import storage_inspector as storage
from . import measurement_bundle as bundle, remote_topology as topology
from .evidence import need


class EvidenceLocation:
    def __init__(self,root,receivers):
        root=Path(root);need(not root.is_symlink(),'remote collected root type')
        self.root=root.resolve();self.index=bundle.inventory(self.root)
        need(type(receivers) is dict and set(receivers)==set(topology.NODES),'remote receiver binding set')
        self.receivers={};identities=set()
        for node,value in receivers.items():
            need(type(value) is dict and set(value)=={'originalRoot','manifestSha256','genesisSha256'},'remote receiver binding fields')
            original=value['originalRoot']
            need(type(original) is str and 0<len(original)<=4096,'remote receiver original root')
            path=PurePosixPath(original)
            need(path.is_absolute() and str(path)==original and '..' not in path.parts and '\\' not in original and '\x00' not in original,
                 'remote receiver original root')
            for key in ('manifestSha256','genesisSha256'):
                need(type(value[key]) is str and re.fullmatch('[0-9a-f]{64}',value[key]),'remote receiver authority digest')
            identities.add((value['manifestSha256'],value['genesisSha256']))
            self.receivers[node]=dict(value)
        need(len(identities)==1,'remote receiver group authority differs')

    def inspect(self,directory,maximum_bytes=8<<30,maximum_frame=8<<20):
        directory=Path(directory)
        need(directory.parent==self.root and directory.name in self.receivers,'remote receiver authority scope')
        node=directory.name;value=self.receivers[node];prefix=node+'/'
        expected={name[len(prefix):]:dict(size=v['bytes'],sha256=v['sha256']) for name,v in self.index.items() if name.startswith(prefix)}
        need(expected and expected==storage.inventory(directory),'remote receiver authority inventory differs')
        need(all(bundle.sha_file(directory/(kind+'.gsr'))==value[kind+'Sha256'] for kind in ('manifest','genesis')),
             'remote receiver authority identity changed')
        result=storage._inspect(directory,maximum_bytes,maximum_frame,Path(value['originalRoot'])/node)
        need(result['node']==node,'remote receiver voter identity changed')
        return result
