"""Shared immutable artifact, JVM and stopped-process identity for measurements."""
from pathlib import Path
from scripts.v51.performance_model import strict_json
from . import measurement_model as model,measurement_bundle as bundle,measurement_generations as generations
from .evidence import need


def metadata(root,name,maximum,*,label="measurement M01"):
    path=root/name
    need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=maximum,label+' metadata bound: '+name)
    with path.open('rb') as source:raw=source.read(maximum+1)
    need(0<len(raw)<=maximum and len(raw)==path.stat().st_size,label+' metadata changed/bound: '+name)
    return strict_json(raw)


def original_root(binding,node):
    if 'remoteTopology' in binding or 'remoteReceivers' in binding:
        from . import remote_identity
        need('remoteTopology' in binding and 'remoteReceivers' in binding,'remote measurement binding fields')
        return remote_identity.original_root(binding,node)
    return Path(binding['origin'])


def evidence_location(root,binding):
    if 'remoteTopology' in binding or 'remoteReceivers' in binding:
        from . import remote_identity
        return remote_identity.location(root,binding)
    return bundle.EvidenceLocation(root,binding['origin'])


def identity(root,expected,check_profile,*,label,restarted=None):
    model.load();binding=metadata(root,'binding.json',4<<20,label=label)
    need(binding==expected,label+' source/build/attempt binding')
    inventory=bundle.inventory(root);mode=binding['mode'];check_profile(binding,inventory)
    need(binding['artifacts'] and binding['classes'],label+' missing artifacts/consumers')
    for name,sha in binding['artifacts'].items():
        need(Path(name).name==name and 'artifacts/'+name in inventory and inventory['artifacts/'+name]['sha256']==sha,
             label+' artifact binding')
    for name,sha in binding['classes'].items():
        need(name in inventory and name.endswith('.class') and inventory[name]['sha256']==sha,label+' consumer binding')
    cores=[name for name in binding['artifacts'] if name.startswith('general-search-engine-') and
           not name.startswith('general-search-engine-replication-') and name!='general-search-engine-4.4.0.jar']
    need(len(cores)==1,label+' runtime core identity');version=cores[0][len('general-search-engine-'):-4]
    need(version=='5.1.0' if mode.startswith('published') else version in ('5.2.0-SNAPSHOT','5.2.0'),label+' mode artifact version')
    need(set(binding['artifacts'])=={cores[0],'general-search-engine-replication-'+version+'.jar','general-search-engine-4.4.0.jar'},
         label+' artifact set')
    processes=metadata(root,'processes.json',64<<10,label=label)
    if restarted is None:
        need(len(processes)==3 and len({p['pid'] for p in processes})==3 and {p['node'] for p in processes}=={'node-1','node-2','node-3'} and
             all(p['generation']==1 and p['exitCode']==0 for p in processes),label+' three stopped JVMs')
    generations.validate(processes,restarted,label=label)
    if 'remoteTopology' in binding or 'remoteReceivers' in binding:
        # Validate the retained map before using receiver-local loaded paths.
        evidence_location(root,binding)
    for process in processes:
        value=process['identity']
        need(all(value[k]==process[k] for k in ('node','pid')) and value['mode']==mode,label+' startup identity')
        need(value['javaRuntime']==binding['java']['java.runtime.version'] and value['javaVendor']==binding['java']['java.vendor'],
             label+' JVM differs from build identity')
        need(value.get('readParameters')==binding['readParameters'],label+' observed read parameters differ')
        for component,name in (('core',cores[0]),('replication','general-search-engine-replication-'+version+'.jar')):
            need(value[component+'Source']==str(original_root(binding,process['node'])/'artifacts'/name),label+' loaded artifact source')
    return binding,processes

