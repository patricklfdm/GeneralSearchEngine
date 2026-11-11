"""Complete original copy authority across carried transition group restart.

Requires original storage, callback, transport and temporal export replay. Local
copy callbacks delimit acquisitions; startup discovery is not a complete copy.
"""
import argparse
import base64
from collections import Counter
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_carried_transition_exports as exports

x=exports; network=x.network; forces=network.forces; p=x.p; c=x.c; f=x.f; need=x.need; e=x.e; sha=x.sha
maintenance=x.shared.maintenance


def copy_of(files,node):
    prefix,members,packet=c.current(files)
    return dict(node=node,identity=network.d.future.identity(files),manifest=files[prefix+'generation.gsr'],
                members=members,packet=packet)


def expected_floors(root,history,*,stage_projector=None):
    """Predict floor owners and original copies before inspecting FLOOR events."""
    point=x.process.read(root/'process/result.json')['cut'];first=p.t.shape(x.process.read(root/'process/result.json')['carriedKind'])[0]
    result={}
    for ordinal,stage in enumerate(history.ranges):
        before=forces.group(root,stage['before']);campaign=stage['kind']=='campaign'
        after=forces.group(root,stage['after'])
        selected=f.decode(c.current((after if campaign else before)['node-1'])[1]['selected.gsr'],'records','SELECTED')
        voters=[v['voter'] for v in selected['sources']]
        if campaign:
            eligible=[n for n in before if n in voters or before[n]['grants.gsr']!=after[n]['grants.gsr']]
            current=p.t.t.reconcile(before,eligible)
        else:
            current=copy.deepcopy(before)
            initial=stage['kind']=='interrupted' or stage['index']==first
            if initial:
                for node in voters:
                    if stage['kind']=='interrupted' and point=='ACCEPT_RENAMED' and node!='node-1':continue
                    packet=c.current(before[node])[2];entry=packet['objects'][selected['nextEntry']]
                    payload=packet['objects'][f.decode(entry,'records','ENTRY')['payload']]
                    current[node]['pending.accept']=p.vote(before[node],entry,payload)
            eligible=voters if stage['kind']=='slot' else ['node-1'] if point=='PROOF_RENAMED' else []
        annotations={}
        if stage_projector is not None:
            current,eligible,annotations=stage_projector(before,current,eligible,stage,voters,point)
        for node in eligible:
            projected=p.maintain(current,(node,),campaign=campaign)[node]
            if projected==current[node]:continue
            copies={peer:copy_of(current[peer],peer) for peer in p.floors.floor_voters(current,node,prefer_installed=not campaign)}
            annotations.setdefault(node,dict(pinned=forces.pins_local_original(current,node,campaign=campaign)))
            old=f.decode(c.current(before[node])[1]['promise.gsr'],'records','PROMISE')['ballot']
            result[ordinal,node]=dict(copies=copies,ballot=old if campaign and node=='node-1' else selected['ballot'],
                phase=stage['kind'],life=stage['life'],**annotations.get(node,{}))
    return result


class Replay(x.Replay):
    def __init__(self,root,kind,*,export_options=None,floor_projector=expected_floors):
        super().__init__(root,kind,**({} if export_options is None else export_options))
        self.expected=floor_projector(self.root,self.history)
        sizes=[len(v['copies']) for v in self.expected.values()]
        self.expected_floor_counts=(len(sizes),0,sum(sizes),sum(n-1 for n in sizes))
        self.expected_status_count=None
        self.copy_callbacks=set();self.used_floors=set();self.acquired_statuses=set();self.discovery_statuses=set()

    def stage(self,at):
        found=[(i,s) for i,s in enumerate(self.history.ranges) if s['start']<at<s['stop']]
        need(len(found)==1,'transition maintenance original phase');return found[0]

    def expected_events(self,copies,own,network,start,end):
        ordinal,_=self.stage(start)
        return maintenance.floor_events(copies,own['node'],network,pinned=self.expected[ordinal,own['node']]['pinned'])

    def statuses(self):
        super().statuses()
        # Exactly one initial discovery pass per real JVM open. Later ballots
        # follow native command completion, not another cold discovery.
        for life in (1,2):
            ordinal,stage=next((i,s) for i,s in enumerate(self.history.ranges) if s['life']==life and s['kind']=='campaign')
            group=forces.group(self.root,stage['before']);local=copy_of(group['node-1'],'node-1');cap=local['packet']['capsule']
            peers=sorted(set(cap['cut']['view']['old']+cap['cut']['view']['new'])-{'node-1'})
            stop=min(at for at,v in enumerate(self.events) if stage['start']<at<stage['stop'] and
                     v.get('node')=='node-1' and v['event']=='ALLOCATOR_BEFORE_WRITE')
            rows=[v for v in self.status_rows if stage['start']<v['sent']<stop and
                  v['request']['sender']['node']=='node-1'][:len(peers)]
            need(len(rows)==len(peers) and [v['request']['recipient']['node'] for v in rows]==peers,
                 'transition maintenance exact startup discovery')
            ballot=f.decode(c.current(group['node-1'])[1]['promise.gsr'],'records','PROMISE')['ballot']
            previous=self.live['node-1'][life-1][0]
            for row,peer in zip(rows,peers):
                q=row['request']
                need(previous<row['sent']<row['delivered']<stop and q['sender']==local['identity'] and
                     q['ballot']==ballot and row['response']['payload']['cut']==c.current(group[peer])[2]['capsule']['cut'],
                     'transition maintenance original startup correlation')
                self.discovery_statuses.add(row['requestHash']);previous=row['delivered']

    def acquired(self,own,lower,start):
        node=own['node'];ordinal,stage=self.stage(start);key=ordinal,node
        need(key in self.expected and key not in self.used_floors,'transition maintenance unexpected floor')
        points=[at for at,v in enumerate(self.events) if max(lower,stage['start'])<at<start and
                v.get('node')==node and v['event']=='FLOOR_COPY_BEFORE_RETURN']
        # run() captures its local copy before discovery; establishMaintenanceFloor
        # rereads the same current generation after all remote acquisitions.
        need(len(points)==2 and not self.copy_callbacks.intersection(points),
             'transition maintenance exact local copy boundaries')
        copied,rechecked=points;expected=self.expected[key]
        need(all(v['delivered']<copied for v in self.status_rows if v['requestHash'] in self.discovery_statuses and
                 stage['start']<v['sent']<start),'transition maintenance copy before startup discovery')
        self.active_floor=(copied,rechecked,expected)
        copies,statuses=super().acquired(own,copied,start)
        need(set(copies)==set(expected['copies']),'transition maintenance original governing owners')
        for peer,value in copies.items():
            need(all(value[k]==v for k,v in expected['copies'][peer].items()),
                 'transition maintenance exact original copy bytes')
        need(not self.acquired_statuses.intersection(statuses) and not self.discovery_statuses.intersection(statuses),
             'transition maintenance discovery reused as copy authority')
        self.copy_callbacks.update(points);self.used_floors.add(key);self.acquired_statuses.update(statuses)
        return copies,statuses

    def discovery(self,statuses,packet,q,remote):
        copied,rechecked,expected=self.active_floor
        need(q['ballot']==expected['ballot'],'transition maintenance original acquisition ballot')
        row=super().discovery(statuses,packet,q,remote)
        need(copied<row['sent']<row['delivered']<packet[0]['offer']['sent']<packet[-1]['commit']['delivered']<rechecked,
             'transition maintenance original acquisition lifetime')
        metadata=[v for v in self.groups if v[0]['offer']['request']==q]
        need(len(metadata)==1 and metadata[0][-1]['commit']['delivered']<rechecked,
             'transition maintenance local recheck before complete acquisition')
        return row

    def declined_hints(self):
        used=self.discovery_statuses|self.acquired_statuses;declined=set();peers={}
        for row in self.status_rows:
            if row['requestHash'] in used:continue
            need(all(k in row for k in ('sent','delivered','request','response')),'transition maintenance unbound discovery')
            ordinal,stage=self.stage(row['sent']);q=row['request'];node=q['sender']['node'];peer=q['recipient']['node']
            expected=self.expected.get((ordinal,node))
            need(expected is not None and peer not in expected['copies'],'transition maintenance unexplained discovery')
            own=expected['copies'][node];cut=own['packet']['capsule']['cut']
            before=forces.group(self.root,stage['before']);remote=copy_of(before[peer],peer)
            observed=row['response']['payload']['cut']
            points=[i for i,v in enumerate(self.events) if stage['start']<i<stage['stop'] and
                    v.get('node')==node and v['event']=='FLOOR_COPY_BEFORE_RETURN']
            need(len(points)==2 and points[0]<row['sent']<row['delivered']<points[1] and
                 peer in set(cut['view']['old']+cut['view']['new']) and q['sender']==own['identity'] and
                 q['recipient']==remote['identity'] and q['ballot']==expected['ballot'] and
                 observed==remote['packet']['capsule']['cut'] and
                 (observed['view']!=cut['view'] or observed['index']<cut['index']),
                 'transition maintenance exact declined hint')
            key=ordinal,node,peer
            need(peers.setdefault(key,row['requestHash'])==row['requestHash'],'transition maintenance repeated declined discovery')
            declined.add(row['requestHash'])
        return declined

    def run(self):
        self.statuses();result=self.floors()
        need(self.used_floors==set(self.expected),'transition maintenance missing required floor')
        need(self.copy_callbacks=={at for at,v in enumerate(self.events) if v['event']=='FLOOR_COPY_BEFORE_RETURN'},
             'transition maintenance unbound local copy')
        declined=self.declined_hints()
        need(self.discovery_statuses|self.acquired_statuses|declined=={v['requestHash'] for v in self.status_rows},
             'transition maintenance unbound discovery')
        return dict(status='PARTIAL',kind=self.kind,**result,initialDiscoveryHints=len(self.discovery_statuses),
            acquisitionHints=len(self.acquired_statuses),declinedDiscoveryHints=len(declined),localCopyCallbacks=len(self.copy_callbacks),
            floorsByPhase=dict(Counter(v['phase'] for v in self.expected.values())),
            completeCopyFloorLifetimesQualified=True,transientBytesCaptured=False,retentionRevisionCompositionQualified=False,
            cohortAdmitted=False,phase3Complete=False)


def replay(root,kind):return Replay(root,kind).run()


def validate(root):
    root=Path(root);before=x.process.collection.inventory(root);original=x.validate(root)
    result=replay(root,original['exports']['kind'])
    need(x.process.collection.inventory(root)==before,'transition maintenance original changed')
    return dict(original=original,maintenance=result,status='PARTIAL',phase3Complete=False)


NEGATIVES={
    'local-copy-missing':'transition maintenance exact local copy boundaries',
    'local-recheck-missing':'transition maintenance exact local copy boundaries',
    'local-copy-duplicate':'transition maintenance exact local copy boundaries',
    'local-copy-after-packet':'joining maintenance complete packet acquisition',
    'local-recheck-before-metadata':'transition maintenance local recheck before complete acquisition',
    'metadata-after-floor':'joining maintenance copy delivered after floor',
    'startup-discovery-missing':'transition maintenance exact startup discovery',
    'startup-discovery-duplicate':'transition maintenance exact startup discovery',
    'startup-hint-is-not-copy':'joining maintenance acquisition before discovery',
    'acquisition-ballot':'transition maintenance original acquisition ballot',
    'packet-after-metadata':'joining maintenance complete packet acquisition',
}


def edit_observations(root,edit):
    def changed(lives):
        at=-1;indexed={}
        for life in lives:
            for message in life:
                if message['action'] in ('event','response'):at+=1;indexed[at]=message
            at+=1  # Parent GROUP_CRASH, without creating a child observation.
        edit(lives,indexed)
    x.process.process.rewrite_lives(root,changed)


def mutate(root,kind,name,*,reader_factory=Replay):
    root=Path(root);reader=reader_factory(root,kind);reader.run()
    floors=[at for at,v in enumerate(reader.events) if v['event']=='FLOOR_RESERVED' and v.get('node')=='node-1']
    start=next(at for at in floors if reader.stage(at)[1]['kind']=='campaign' and reader.stage(at)[1]['life']==2)
    _,stage=reader.stage(start)
    copied,rechecked=[at for at,v in enumerate(reader.events) if stage['start']<at<start and
                       v.get('node')=='node-1' and v['event']=='FLOOR_COPY_BEFORE_RETURN']
    groups=[v for v in reader.groups if copied<v[0]['offer']['sent']<start and v[0]['offer']['request']['sender']['node']=='node-1']
    metadata=next(v for v in groups if e.record_kind(v[0]['raw'])=='GENERATION')
    q=metadata[0]['offer']['request'];peer=q['recipient']['node']
    packet=next(v for v in groups if v[0]['offer']['request']['recipient']['node']==peer and v[0]['kind']=='CAPSULE')
    status=next(v for v in reader.status_rows if copied<v['sent']<packet[0]['offer']['sent'] and
                v['request']['sender']['node']=='node-1' and v['request']['recipient']['node']==peer)
    initial=next(v for v in reader.status_rows if v['requestHash'] in reader.discovery_statuses)
    def exchanges(group):
        request=group[0]['offer']['request']
        return [v for v in reader.rows if v['request']['sender']==request['sender'] and v['request']['recipient']==request['recipient']
                and v['request']['trace']==request['trace']]
    def indices(rows):return sorted({v[k] for v in rows for k in ('sent','received','offered','delivered')})
    def edit(lives,indexed):
        def locate(message):return next(life for life in lives if any(v is message for v in life))
        def remove(message):
            life=locate(message);life.pop(next(i for i,v in enumerate(life) if v is message))
        def move(positions,target,*,after=False,duplicate=False):
            selected=[indexed[at] for at in positions];marker=indexed[target];life=locate(marker)
            need(all(locate(v) is life for v in selected),'transition maintenance mutation crossed process')
            if not duplicate:
                for v in selected:remove(v)
            else:selected=copy.deepcopy(selected)
            at=next(i for i,v in enumerate(life) if v is marker)+int(after);life[at:at]=selected
        if name in ('local-copy-missing','local-recheck-missing'):
            remove(indexed[copied if name=='local-copy-missing' else rechecked])
        elif name=='local-copy-duplicate':move([copied],copied,after=True,duplicate=True)
        elif name=='local-copy-after-packet':move([copied],packet[-1]['commit']['delivered'],after=True)
        elif name=='local-recheck-before-metadata':move([rechecked],metadata[-1]['commit']['delivered'])
        elif name=='metadata-after-floor':move([metadata[-1]['commit']['delivered']],start,after=True)
        elif name in ('startup-discovery-missing','startup-hint-is-not-copy'):
            for at in indices([initial if name=='startup-discovery-missing' else status]):remove(indexed[at])
        elif name=='startup-discovery-duplicate':move(indices([initial]),initial['delivered'],after=True,duplicate=True)
        elif name=='packet-after-metadata':move(indices(exchanges(packet)),metadata[-1]['commit']['delivered'],after=True)
        elif name=='acquisition-ballot':
            rows=[status,*exchanges(packet),*exchanges(metadata)];mapping={}
            for row in rows:
                message=indexed[row['offered']];wire=message['value']['wire']
                for side in ('request','response'):
                    old=wire[side];wire_kind,body=e.n.wire(old);body['ballot']['counter']+=1
                    new=base64.b64encode(f.encode('wire',wire_kind,body)).decode()
                    for a,b in ((old,new),(sha(base64.b64decode(old)),sha(base64.b64decode(new)))):
                        need(a not in mapping or mapping[a]==b,'transition maintenance consistent mutation');mapping[a]=b
            def replace(value):
                if isinstance(value,str):return mapping.get(value,value)
                if isinstance(value,list):return [replace(v) for v in value]
                if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
                return value
            for life in lives:life[:]=replace(life)
        else:raise ValueError('unknown transition maintenance mutation '+name)
    edit_observations(root,edit)


def negative(root,kind,before,name):
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-transition-maintenance-negative-') as temporary:
        changed=Path(temporary)/'raw';shutil.copytree(root,changed);mutate(changed,kind,name)
        after=x.process.collection.inventory(changed)
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'transition maintenance negative changed storage input')
        x.validate(changed)
        try:replay(changed,kind)
        except ValueError as error:need(str(error)==NEGATIVES[name],'transition maintenance wrong negative '+name+': '+str(error))
        else:raise ValueError('transition maintenance accepted mutation '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],physicalNetworkExportPrecondition='PASS')


def qualify(root):
    root=Path(root);original=validate(root);before=x.process.collection.inventory(root);results=[]
    for name in NEGATIVES:
        results.append(negative(root,original['maintenance']['kind'],before,name))
        print(json.dumps(dict(stage='maintenance-negative',case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(x.process.collection.inventory(root)==before,'transition maintenance qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
