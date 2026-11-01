"""Original same-view recovery export and complete-copy maintenance authority.

One indivisible 3-REPLACE original, with physical and attempted-network replay
first. Exported copies retain their own cut; discovery alone grants no authority.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_same_view_network as network
from . import joining_maintenance_evidence as maintenance
from . import joining_peer_evidence as peer

physical=network.physical
c,e,n=maintenance.c,maintenance.e,maintenance.n
f,disk,need,sha=c.f,c.disk,c.need,c.sha
EXTRA={
    'adoption-return-before-selector':('exports','joining export selector completion order'),
    'adoption-return-omitted':('exports','joining export complete generation timeline'),
    'latest-probe-after-packet':('maintenance','joining maintenance acquisition before discovery'),
    'future-copy-extra-local-observation':('peers','joining peer maintenance durable write count'),
    'recovery-peer-write-after-return':('peers','joining peer selected durable write count'),
    'recovery-export-closed-owner':('exports','joining control original owner lifetime'),
}


class Replay(maintenance.Replay):
    # These were observed counts of an older ADD fixture, not protocol limits.
    # All original STATUS replies and every FLOOR event still require replay.
    expected_status_count=None
    expected_floor_counts=None

    def __init__(self,root):
        raw=physical.semantic.snapshot.s.regular(Path(root)/network.SELECTION,65536)
        super().__init__(root,kind='REPLACE',recovery=raw)
        self.recovery=raw;self.floor_inputs=[]

    def governing(self,copies,own):
        local=disk.inventory(self.root/own['path'])
        physical.covering_floor(local,{node:disk.inventory(self.root/v['path']) for node,v in copies.items()},own['node'])

    def discovery(self,statuses,packet,q,remote):
        need(statuses,'joining maintenance acquisition before discovery')
        # Prefix discovery can precede the maintenance probe in the same
        # generation. Bind the most recent original request, never an older
        # convenient hint or a later/undelivered response.
        return super().discovery([max(statuses,key=lambda v:v['sent'])],packet,q,remote)

    def acquired(self,own,lower,start):
        copies,used=super().acquired(own,lower,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies,used

    def direct(self,own,start):
        copies=super().direct(own,start)
        self.floor_inputs.append(dict(start=start,own=own,copies=copies,order=list(copies)))
        return copies

    def run(self,prior):
        controls=c.Replay.run(self,prior)
        self.statuses();floors=self.floors()
        return dict(controls=controls,maintenance=floors,discoveryHints=len(self.status_rows))

    def floors(self):
        self.maintenance_result=super().floors()
        return self.maintenance_result


class PeerReplay(peer.Replay,Replay):
    expected_write_counts=None

    # Both parent classes record inputs; record each governing floor only once.
    def acquired(self,own,lower,start):return Replay.acquired(self,own,lower,start)
    def direct(self,own,start):return Replay.direct(self,own,start)

    def floor(self,row):
        own=row['own'];node=own['node'];start=row['start'];copies=row['copies'];changes=[]
        lower=next(i for i in range(start+1,len(self.events)) if self.events[i].get('node')==node and self.events[i]['event']=='FLOOR_BEFORE_RETURN')
        upper=next(i for i in range(lower+1,len(self.events)) if self.events[i].get('node')==node and
                   self.events[i]['event'] in ('RETIREMENT_RESERVED','FLOOR_RELEASE_AUTHORITY_CREATED'))
        files=dict(self.files(own),**{peer.FILE:self.state[node]})
        view=own['packet']['capsule']['cut']['view'];plan=peer.peers.decode(self.state[node])['plan']
        wanted=set(view['old']+view['new']);known={v['identity']['node'] for v in plan['peers']}
        if plan['view']!=view:
            if wanted-known:
                need(wanted-known=={self.model.joining} and self.model.joining in copies,'joining peer reconcile original joining copy')
                changed=peer.init.reconcile(self.state[node],files,self.files(copies[self.model.joining]))
            else:changed=physical.c.reconcile(files)[peer.FILE]
            self.change(node,changed,'reconcile',changes)
        for remote in row['order']:
            # A covering future copy proves retention, not a local same-cut
            # observation. Keep the lagging owner's original debt unchanged.
            if disk.anchor(copies[remote]['packet']['capsule'])!=disk.anchor(own['packet']['capsule']):continue
            files[peer.FILE]=self.state[node]
            after=peer.t.observation.observe_same_cut(self.state[node],files,self.files(copies[remote]),defer_renewal=True)
            self.change(node,after,'observe:'+remote,changes)
        self.sequence(node,changes,lower,upper,'maintenance')


def export_replay(root,reader):
    prior=e.replay(root,kind='REPLACE',recovery=reader.recovery)
    bound=0
    for values in reader.groups:
        first=values[0]['offer'];last=values[-1]['commit'];node=first['request']['recipient']['node']
        if node!=reader.model.joining:continue
        if values[0]['raw']==e.pending_ack(reader.model):continue  # separately checked pending-listener authority
        scope={'initial-endpoint':'initial-owner','continuation-endpoint':'continuation-owner'}.get(reader.events[first['received']].get('scope'))
        need(scope is not None,'joining authority export owner scope')
        c.owner_lifetime(reader.events,node,scope,first['received'],last['offered']);bound+=1
    prior['joiningExportLifetimes']=bound
    return prior


def replay(root):
    reader=PeerReplay(root)
    prior=export_replay(root,reader)
    controls=c.Replay.run(reader,prior)
    ledgers=reader.run()
    return dict(exports=prior,controls=controls,maintenance=reader.maintenance_result,
                discoveryHints=len(reader.status_rows),peers=ledgers)


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root)
    original=network.validate(root);result=replay(root)
    counts=original['network'];controls=result['controls']
    need(controls['observedCommittedContents']==counts['committedTransfers'] and
         controls['observedContentSessions']==counts['transferSessions']-counts['rejectedTransferAttempts'],
         'joining same-view complete export authority coverage')
    need(n.s.collection.inventory(root)==before,'joining same-view authority original changed')
    return dict(status='PARTIAL',scope='original-same-view-export-and-maintenance-authority',profile='3-REPLACE',
        precondition=original,**result,observedExportAuthorityQualified=True,maintenanceForceQualified=True,
        peerLedgerCompositionQualified=True,learnerLedgerCompositionQualified=False,sameViewPhysicalQualified=False,
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


def mutate(root,stage,name):
    root=Path(root);raw=(root/network.SELECTION).read_bytes()
    if name not in EXTRA:
        if name=='completion-closed-owner':c.mutate(root,name,kind='REPLACE',recovery=raw)
        elif stage=='exports':e.mutate(root,name,kind='REPLACE',recovery=raw)
        elif stage=='controls':c.mutate(root,name,kind='REPLACE',recovery=raw)
        elif stage=='maintenance':maintenance.mutate(root,name,reader=Replay(root))
        else:peer.mutate(root,name,reader=PeerReplay(root))
        return
    reader=PeerReplay(root);reader.run();events=reader.events;joining=reader.model.joining
    def move(values,target,after=False):
        ids={id(v) for v in values};events[:]=[v for v in events if id(v) not in ids]
        at=next(i for i,v in enumerate(events) if v is target)+int(after);events[at:at]=values
    if name=='recovery-export-closed-owner':
        values=max((v for v in reader.groups if v[0]['offer']['request']['recipient']['node']==joining and
                    e.record_kind(v[0]['raw'])=='BASIS'),key=lambda v:v[0]['offer']['sent'])
        trace=values[0]['offer']['request']['trace']
        hashes={v['requestHash'] for v in reader.rows if v['request']['trace']==trace}
        for event in events:
            if event.get('node')==joining and event.get('request') in hashes and event.get('scope')=='continuation-endpoint':
                event['scope']='initial-endpoint'
    elif name.startswith('adoption-'):
        index=next(i for i,v in enumerate(events) if v.get('node')==joining and v['event']=='ADOPTION_INSTALL_BEFORE_RETURN')
        if name.endswith('omitted'):events[index]['event']='REMOVED_ADOPTION_RETURN'
        else:
            rename=max(i for i,v in enumerate(events[:index]) if v.get('node')==joining and v['event']=='INSTALL_SELECTOR_RENAMED')
            move([events[index]],events[rename])
    elif name=='recovery-peer-write-after-return':
        step=max((v for v in reader.steps if v['node']==joining and v['kind']=='selected'),key=lambda v:v['start'])
        values=[v for v in events[step['start']:step['end']+1] if v.get('node')==joining and v['event'] in peer.WRITES]
        target=next(v for i,v in enumerate(events) if i>step['end'] and v.get('node')==joining and v['event']=='INSTALL_BEFORE_RETURN')
        move(values,target,True)
    else:
        floor=next(v for v in reader.floor_inputs if v['own']['node']==joining and
                   any(w['packet']['capsule']['cut']!=v['own']['packet']['capsule']['cut'] for w in v['copies'].values()))
        if name=='future-copy-extra-local-observation':
            target=next(v for i,v in enumerate(events) if i>floor['start'] and v.get('node')==joining and v['event']=='FLOOR_BEFORE_RETURN')
            extra=[dict(node=joining,scope='continuation-owner',event=point) for point in peer.WRITES]
            move(extra,target,True)
        else:
            own=floor['own'];start=floor['start']
            packet=next(v for v in reader.groups if v[0]['offer']['request']['sender']['node']==joining and
                        own['start']<v[0]['offer']['sent']<start and v[0]['kind']=='CAPSULE')
            q=packet[0]['offer']['request']
            status=max((v for v in reader.status_rows if v['request']['sender']==q['sender'] and
                        v['request']['recipient']==q['recipient'] and v['sent']<packet[0]['offer']['sent']),key=lambda v:v['sent'])
            move([events[status['delivered']]],events[packet[0]['offer']['sent']],True)
    (root/'events.json').write_bytes(f.canonical(events))


def stages(root,stage):
    """Run each preceding authority layer before the designated negative gate."""
    network.observed(root)
    def exports():return export_replay(root,Replay(root))
    if stage=='exports':return exports
    reader=Replay(root);prior=export_replay(root,reader)
    if stage=='controls':return lambda:c.Replay.run(reader,prior)
    c.Replay.run(reader,prior)
    def floors():reader.statuses();return reader.floors()
    if stage=='maintenance':return floors
    floors();return lambda:PeerReplay(root).run()


def cases(root):
    result=[('exports',name,reason) for name,reason in e.NEGATIVES.items() if name!='pending-after-retain']
    # The same-view original may finish joining without an exported pending
    # ACK. Do not fabricate that session or claim its absent negative passed.
    reader=Replay(root);pending=e.pending_ack(reader.model)
    if any(v[0]['raw']==pending for v in reader.groups):result.append(('exports','pending-after-retain',e.NEGATIVES['pending-after-retain']))
    result += [('exports' if name=='completion-closed-owner' else stage,name,reason)
               for stage,module in [('controls',c),('maintenance',maintenance),('peers',peer)]
               for name,reason in module.NEGATIVES.items()]
    result += [(stage,name,reason) for name,(stage,reason) in EXTRA.items()]
    return result


def negative(root,before,case):
    stage,name,reason=case
    with tempfile.TemporaryDirectory(prefix='v53-same-view-authority-') as temp:
        copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,stage,name)
        after=n.s.collection.inventory(copied)
        protected=lambda v:{k:h for k,h in v['files'].items() if k not in ('events.json','wire.json')}
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'joining same-view authority negative changed physical inputs')
        target=stages(copied,stage)
        try:target()
        except ValueError as error:need(str(error)==reason,'joining same-view unrelated authority negative: '+name+': '+str(error))
        else:raise ValueError('joining same-view authority mutation accepted: '+name)
    return dict(stage=stage,case=name,status='REJECTED',reason=reason,precedingLayers='PASS')


def qualify(root,*,workers=1,progress=None):
    need(type(workers) is int and 1<=workers<=4,'joining authority replay workers')
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root);matrix=cases(root);results=[]
    if progress:progress(dict(stage='original',status='PASS',negativeCases=len(matrix)))
    # Only independent disposable evidence copies are parallel. The actual
    # native history is never divided, rerun or measured here.
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,before,case):case for case in matrix}
        for future in as_completed(tasks):
            stage,name,reason=tasks[future]
            try:result=future.result()
            except Exception as error:result=dict(stage=stage,case=name,status='FAIL',failure=str(error),type=type(error).__name__)
            results.append(result)
            if progress:progress(dict(result,completed=len(results),total=len(matrix)))
    need(n.s.collection.inventory(root)==before,'joining same-view authority qualification changed original')
    need(all(v['status']=='REJECTED' for v in results),'joining same-view authority negative matrix failed')
    return dict(original=original,negatives=sorted(results,key=lambda v:(v['stage'],v['case'])),
                absentPendingACKNegative=not any(v[1]=='pending-after-retain' for v in matrix))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--qualify',action='store_true');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    result=qualify(a.root,workers=a.workers,progress=lambda v:print(json.dumps(v),file=sys.stderr,flush=True)) if a.qualify else validate(a.root)
    print(json.dumps(result,sort_keys=True))
