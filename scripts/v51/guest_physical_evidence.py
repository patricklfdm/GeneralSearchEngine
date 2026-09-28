"""Joint immutable evidence inspection for three automatic healthy guests.

No authority is opened by a JVM. Original sealed paths are checked from the
controller configs while retained bytes are inspected at their download location.
"""
import tempfile
import time
from pathlib import Path
from . import guest_evidence as guest, guest_authority as authority, cloud_package as package
from . import remote_command as c, remote_collection as parts, performance_model as m
from . import remote_rich_evidence as rich, remote_rich_physical as history
from . import performance_physical as physical, storage_inspector as storage, format_inspector as f
from . import cloud_workload_contract as contract

NEGATIVES = dict(zip(('missing-invocation','borrowed-invocation','unknown-read-id','changed-cut','changed-release',
    'missing-release','resealed-answer','missing-leader-proof','missing-proof-ack','failed-original-call'),
    ('read cut without original invocation identity','read invocation ownership','read cut without original invocation identity',
     'read validation/capture mismatch','release changed captured prefix','read response before its release',
     'answer differs from exact concurrent captured cut','publish before own force and remote proof acknowledgement',
     'publish before own force and remote proof acknowledgement','unsuccessful cloud API call')))


def converge(members, active, status, deadline, *, clock=time.monotonic, sleep=time.sleep):
    """Observe durability only; never issue a read, mutation, activation or replay."""
    end=min(deadline,clock()+30)
    leader=status(active,end)
    m.need(leader['state']=='LEADER_READY' and leader['provenIndex']>0, 'guest final leader status')
    target=leader['provenIndex']; pending=list(members)
    while pending:
        member=pending[0]; value=status(member,end)
        m.need(value['state']!='FAILED', 'guest final voter failed')
        if value['provenIndex']>=target:pending.pop(0)
        else:sleep(.05)
        m.need(clock()<end, 'guest final durable observation deadline')


class Location:
    def __init__(self, root, original, indexes):
        self.root,self.original,self.indexes=Path(root),Path(original),indexes

    def inspect(self, directory, maximum_bytes, maximum_frame):
        node=Path(directory).name
        m.need(Path(directory)==self.root/node and node in self.indexes, 'guest physical inspection owner')
        expected={n:dict(size=v['bytes'],sha256=v['sha256']) for n,v in self.indexes[node].items()}
        m.need(expected==storage.inventory(directory), 'guest relocated authority inventory differs')
        return storage._inspect(directory,maximum_bytes,maximum_frame,self.original/node)


def validate(members, manifest_bytes):
    m.need(type(members) is list and len(members)==3, 'guest physical member count')
    configs=[v['controller']['config'] for v in members]
    nodes=[cfg['binding']['node'] for cfg in configs]
    m.need(set(nodes)=={'node-1','node-2','node-3'}, 'guest physical member identities')
    common=lambda cfg:dict(cfg,binding={k:v for k,v in cfg['binding'].items() if k!='node'})
    m.need(all(common(cfg)==common(configs[0]) and cfg['mode']==package.MODES[2] for cfg in configs), 'guest physical group/config binding')
    m.need(sum(v['controller']['active'] is True for v in members)==1, 'guest physical issuer coverage')
    reports=[];calls=[];traces={};indexes={};bindings={}
    # The same existing per-member decoded limit is shared across logical and
    # physical streams within each pass. No cross-machine timestamps are ordered.
    with tempfile.TemporaryDirectory(prefix='gse-v51-guest-physical-') as scratch:
        root=Path(scratch)
        for member,cfg,node in zip(members,configs,nodes):
            replay=c.directory(member['root']); controller=member['controller']
            reports.append(guest.validate(replay,cfg,manifest_bytes,controller['packageRoot'],controller['transcript'],
                active=controller['active'],healthy=True,physical=True))
            budget=[contract.load()['evidence']['perNodePerCellTraceBytes']]
            results=rich.lines(replay,node+'-results',budget)
            rich.lines(replay,node+'-samples',budget)
            traces[node]=rich.lines(replay,node+'-trace',budget)
            calls.extend(dict(row['call'],opId=row['opId'],node=node,pid=row['pid']) for row in results if row['command']=='call')
            index=c.read(replay/parts.INDEX);prefix='authority/'+node+'/'
            indexes[node]={n[len(prefix):]:v for n,v in index.items() if n.startswith(prefix)}
            authority.capture(replay/'authority',node,root/node)
            raw=(root/node/'manifest.gsr').read_bytes(); genesis=(root/node/'genesis.gsr').read_bytes()
            manifest=f.inspect(raw,'MANIFEST')
            m.need(manifest['groupId']==cfg['groupId'] and manifest['members']==[
                dict(node='node-'+str(i+1),host=host,port=port) for i,(host,port) in enumerate(zip(cfg['hosts'],cfg['ports']))],
                'guest physical manifest topology')
            bindings[node]=(m.sha(raw),m.sha(genesis))
        m.need(len(set(bindings.values()))==1, 'guest physical manifest/genesis agreement')
        m.need(len(calls)==90, 'guest physical healthy call count')
        location=Location(root,configs[0]['root'],indexes)
        result=physical.automatic(root,calls,traces,evidence_location=location,
            cloud_calls=history.Calls(calls,auxiliary_backups=0))
        from . import remote_rich_negatives
        negatives=remote_rich_negatives.verify_observations(root,calls,traces,location,auxiliary_backups=0)
        m.need(negatives==[dict(case=name,status='REJECTED',reason=reason) for name,reason in NEGATIVES.items()],
               'guest physical negative qualification')
    return dict(status='PASS',execution='guest-automatic-healthy-physical-evidence-only',physicalHistoryQualified=True,
        paidCloud=False,fullRemoteQualification=False,calls=len(calls),physical=result,members=reports,negatives=negatives,
        source=configs[0]['binding']['source'],bundleSha256=configs[0]['binding']['bundleSha256'],
        manifestSha256=bindings['node-1'][0],genesisSha256=bindings['node-1'][1])


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    # Each relative member root is resolved from this replay descriptor, so the
    # whole downloaded set remains portable without rewriting original configs.
    spec=c.read(a.input)
    members=[dict(root=a.input.parent/v['root'],controller=c.read(a.input.parent/v['controller'])) for v in spec['members']]
    result=validate(members,(a.input.parent/spec['manifest']).read_bytes());c.write_once(a.output,result)
    print(m.canonical(result).decode())
