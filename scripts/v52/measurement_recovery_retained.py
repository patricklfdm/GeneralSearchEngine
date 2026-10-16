"""Bind generation-2 restoration to independently inspected pre-reopen authority."""
import base64
from pathlib import Path
from scripts.v51 import storage_inspector as storage,recovery_inspector as recovery,runtime_evidence as physical
from . import measurement_bundle as bundle,measurement_identity as identities
from .evidence import need,digest,encoded


def validate(root,binding,scenario,traces,manifest,genesis,projection):
    node=scenario['leader'];crash=scenario['crash'];directory=Path(root)/'pre-reopen'/node
    inventory=bundle.members(directory)
    need(inventory==crash['preReopen'] and 0<len(inventory)<=4096 and
         sum(v['bytes'] for v in inventory.values())<=64<<20 and all(v['bytes']<=8<<20 for v in inventory.values()),
         'recovery pre-reopen inventory/bound')
    report=storage._inspect(directory,64<<20,8<<20,identities.original_root(binding,node)/node)
    need(report['node']==node and report['manifestDigest']==manifest['digest'] and report['applicationSequence']==4 and
         report['provenThrough']>=scenario['initialIndex'],'recovery pre-reopen committed cut')
    active,base,_,_=recovery.state(directory,manifest,node,genesis)
    proofs=set();terminal=base['terminalProof']
    if terminal:proofs.add(digest(physical.raw(terminal)))
    with (active/'proofs.gsr').open('rb') as stream:
        first=True
        while True:
            header=stream.read(48)
            if not header:break
            need(len(header)==48,'recovery pre-reopen proof header')
            size=int.from_bytes(header[12:16],'big',signed=True)
            need(0<size<=(8<<20)-48,'recovery pre-reopen proof bound')
            body=stream.read(size);need(len(body)==size,'recovery pre-reopen proof body')
            value=header+body;physical.f.contextual_frame(value,'JOURNAL' if first else 'PROOF',manifest)
            if not first:
                terminal=base64.b64encode(value).decode();proofs.add(digest(value))
            first=False
    restored=None
    for row in traces[node]:
        if row['generation']==2 and row['event']=='APPLICATION_RESTORED':
            need(restored is None,'recovery missing/duplicate retained restoration');restored=row
    need(restored is not None,'recovery missing/duplicate retained restoration')
    snapshot=recovery.snapshot(physical.raw(restored['snapshot']),manifest);projection.publication(snapshot)
    need([a['entryDigest'] for a in snapshot['anchors']]==report['acceptedDigests'][:report['provenThrough']] and
         snapshot['applicationSequence']==report['applicationSequence'] and snapshot['terminalProof']==terminal,
         'recovery restoration differs from retained proven prefix')
    expected=[dict(entryDigest=d,operation=projection.chosen[d]['operation'],originEpoch=projection.chosen[d]['originEpoch'],
                   originIncarnation=projection.chosen[d]['originIncarnation'],payloadDigest=digest(physical.raw(projection.chosen[d]['payload'])))
              for d in report['acceptedDigests'][:report['provenThrough']]]
    need(snapshot['anchors']==expected,'recovery restored anchor metadata differs')
    return {(node,2):dict(promisedEpoch=report['promisedEpoch'],snapshotSha256=digest(encoded(snapshot)),proofs=proofs)},report
