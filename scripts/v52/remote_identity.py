"""Receiver-local pipe qualification identity; live cloud admission is separate."""
from pathlib import Path
from scripts.v51 import storage_inspector as storage
from . import remote_topology as topology,remote_bootstrap_evidence as authority,measurement_bundle as bundle
from .evidence import need
from .measurement_identity import metadata


def location(root,binding):
    need('remoteTopology' in binding and 'remoteReceivers' in binding,'remote measurement binding fields')
    value=topology.validate(binding['remoteTopology'])
    # This first bridge proves separate receiver roots and real TCP locally.
    # It cannot silently promote that to three owned cloud hosts.
    need(value['placement']=='local-no-gcp','remote runtime host qualification not implemented')
    need(topology.read(root)==value,'remote retained topology changed')
    need(metadata(Path(root),'execution.json',1<<20,label='remote measurement')==dict(status='STOPPED',failure=None,closeErrors=[],qualifiedMeasurement=False,paidCloud=False),
         'remote receiver execution incomplete')
    if ('remoteVoterControl' in binding or 'remoteVoterTransport' in binding or 'remoteVoterLifecycle' in binding or (Path(root)/'controller-domain.json').exists() or
        any((Path(root)/(node+'-control')).exists() for node in topology.NODES)):
        from . import remote_voter_evidence
        remote_voter_evidence.validate(root,binding)
    if 'remoteDelivery' in binding or (Path(root)/'delivery-package.tar.gz').exists() or any(
        (Path(root)/(node+'-delivery.json')).exists() for node in topology.NODES):
        from . import remote_delivery_evidence
        remote_delivery_evidence.validate(root,binding)
    result=authority.EvidenceLocation(root,binding['remoteReceivers'])
    for node in topology.NODES:
        path=Path(root)/node/'manifest.gsr'
        need(path.is_file() and not path.is_symlink() and 0<path.stat().st_size<=65536,'remote manifest bound/type')
        manifest=storage.f.inspect(path.read_bytes(),'MANIFEST')
        need(manifest['groupId']==value['groupId'] and manifest['members']==value['members'] and
             manifest['configurationId']=='v52-measurement','remote topology differs from authority')
    return result


def original_root(binding,node):
    return Path(binding['remoteReceivers'][node]['originalRoot'])
