"""Temporal export authority across the two original carried-context JVM lives.

Always require original physical, callback and attempted-transport replay first.
Process-local availability is rebuilt at each cold open; final snapshots never
authorize an earlier transfer. This remains a development component.
"""
import argparse
import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from . import native_carried_transition_network as network
from . import remove_export_evidence as shared
from . import remove_process_exports as sources

p=network.p; process=network.process; c=network.c; f=network.f; need=network.need
e=shared.e; sha=e.sha


def lifetimes(events):
    deaths=[i for i,v in enumerate(events) if v['event']=='GROUP_CRASH']
    need(len(deaths)==1,'transition export exact group death');death=deaths[0];result={}
    for node in process.NODES:
        opens=[i for i,v in enumerate(events) if v.get('node')==node and v['event']=='NODE_OPEN']
        need(len(opens)==2 and opens[0]<death<opens[1],'transition export original owner lifetimes')
        result[node]=[(opens[0],death),(opens[1],len(events))]
    return result


def snapshots(root,events):
    """Locate parent snapshots in the exact child transcript, without new events."""
    result=[(-1,'before-network')];at=-1
    for life in (1,2):
        ordinal=0
        messages=process.process.process.transcript(root/f'process/life-{life}.jsonl')
        for row in messages:
            action=row['action']
            if action in ('event','response'):at+=1
            elif action=='opened':result.append((at,f'life-{life}-opened'))
            elif action=='installed':
                ordinal+=1;result.append((at,f'life-{life}-installed-{ordinal}'))
            elif action=='snapshot':result.append((at,row['value']))
        if life==1:result.append((at,'at-cut'));at+=1
    result.append((len(events),'after-close'))
    need(at==len(events)-1 and all(a[0]<b[0] for a,b in zip(result,result[1:])),
         'transition export exact snapshot positions')
    return result


def generation_windows(root,events,history,live):
    result=[]
    for node in process.NODES:
        changes=[]
        for stage in history.ranges:
            if stage['kind']=='interrupted':continue
            raw=c.current(c.inventory(root/stage['after']/'node-1'))[1]['selected.gsr']
            if node not in [s['voter'] for s in f.decode(raw,'records','SELECTED')['sources']]:continue
            changes.append(('INSTALL_BEFORE_RETURN' if stage['kind']=='campaign' else 'PUBLICATION_BEFORE_RETURN',stage['after']))
        renames=[i for i,v in enumerate(events) if v.get('node')==node and v['event']=='INSTALL_SELECTOR_RENAMED']
        returns=[(i,v['event']) for i,v in enumerate(events) if v.get('node')==node and
                 v['event'] in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN')]
        need(len(renames)==len(returns)==len(changes) and [v for _,v in returns]==[v for v,_ in changes],
             'transition export complete generation timeline')
        def add(path,start,end):
            files=c.inventory(root/path/node);prefix,members,packet=c.current(files)
            identity=f.decode(files['node.gsr'],'records','NODE')['identity']
            need(identity['node']==node and start<end,'transition export original generation owner')
            for opened,closed in live[node]:
                lower,upper=max(start,opened),min(end,closed)
                if lower<upper:result.append(dict(node=node,start=lower,end=upper,path=path+'/'+node,
                    members=members,packet=packet,manifest=files[prefix+'generation.gsr'],identity=identity))
        add('before-network',-1,renames[0] if renames else len(events))
        for index,((_,path),(returned,_)) in enumerate(zip(changes,returns)):
            need(renames[index]<returned and (index==0 or returns[index-1][0]<renames[index]),
                 'transition export selector completion order')
            add(path,returned,renames[index+1] if index+1<len(renames) else len(events))
    return result


def model(root,history):
    phases=[]
    for ordinal,parts in enumerate(history.phases,1):
        packet=c.current(history.installed[ordinal,'node-1'])[2]
        entry=f.decode(parts['ENTRY'],'records','ENTRY')
        catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
        operation=catalog['results'][-1]
        if entry['kind']=='INTENT':payload=f.canonical(dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}))
        elif entry['kind']=='FINAL':payload=f.canonical(dict(binding=operation['binding']))
        else:need(entry['kind']=='BARRIER','transition export original command');payload=b''
        need(sha(payload)==entry['payload'],'transition export original payload')
        phases.append(dict(parts,PAYLOAD=payload))
    return SimpleNamespace(root=entry['root'],phases=phases,old=history.old,joining=None,owner=history.owner)


def interrupted_records(root,events,history,windows,model):
    stage=next(s for s in history.ranges if s['kind']=='interrupted');result=[]
    selected=f.decode((root/(stage['before']+'.gsr')).read_bytes(),'records','SELECTED')
    parts=model.phases[0];entry=f.decode(parts['ENTRY'],'records','ENTRY')
    accept=f.encode('records','ACCEPT',dict(root=selected['root'],authority=selected['view'],
        ballot=selected['ballot'],index=entry['index'],entry=sha(parts['ENTRY'])))
    for source in selected['sources']:
        node=source['voter']
        returns=[at for at,v in enumerate(events) if stage['start']<at<stage['stop'] and
                 v.get('node')==node and v['event']=='ACCEPT_BEFORE_RETURN']
        need(len(returns)<=1,'transition export interrupted acceptance boundary')
        if not returns:continue  # Rename without return cannot authorize an ACK.
        at=returns[0];own=e.current(windows,node,at,at)
        frames,_=p.data.pending(c.inventory(root/'at-cut'/node))
        need(frames['ENTRY']==parts['ENTRY'] and frames['ACCEPT']==accept,
             'transition export original interrupted vote')
        end=min(own['end'],stage['stop']);live_end=e.next_promise(events,node,at,end)
        def add(raw,family,*,reference=None,ballot=None,view=None,stop=end):
            result.append(dict(node=node,start=at,end=stop,raw=raw,reference=reference or sha(raw),
                ballot=ballot,view=view,family=family))
        add(parts['ENTRY'],'pending-record');add(accept,'pending-record')
        add(parts['PAYLOAD'],'pending-payload',ballot=selected['ballot'],view=selected['view'],stop=live_end)
        receipt=f.canonical(dict(root=selected['root'],voter=node,incarnation=own['identity']['storage'],
            phase='ACCEPT',record=sha(accept)))
        reference=sha(f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=sha(receipt))))
        add(receipt,'native-vote-receipt',reference=reference,ballot=selected['ballot'],view=selected['view'],stop=live_end)
    return result


def transfer_lifetimes(groups,live):
    for values in groups:
        first,last=values[0]['offer'],values[-1]['commit']
        for side in ('sender','recipient'):
            node=first['request'][side]['node']
            need(any(a<first['sent']<=last['delivered']<b for a,b in live[node]),
                 'transition export transfer outside owner lifetime')


class Replay(shared.Replay):
    expected_floor_counts=None
    expected_status_count=None

    def __init__(self,root,kind):
        self.root=Path(root);self.kind=kind
        original=process.read(self.root/'events.json');self.history=network.History(self.root,kind,original)
        self.events,self.rows,_,_=network.transport(self.root,self.history,original)
        contents=[];network.network.transcript.transfers(self.rows,contents=contents);self.groups=e.sessions(contents)
        self.live=lifetimes(self.events)
        self.windows=generation_windows(self.root,self.events,self.history,self.live)
        activation=self.history.activations()
        self.sources=sources.source_windows(self.root,self.events,self.history,activation,
            snapshots=snapshots(self.root,self.events))
        self.model=model(self.root,self.history)
        # Interrupted callbacks belong to the mandatory crash reducer, not to
        # the complete successor slots. Keep journal/fencing events in place.
        critical=set(network.network.phase.force_names())|set(network.network.phase.force_names(nonvoting=True))
        slots=[v for v in self.history.ranges if v['kind']=='slot']
        records_events=[dict(node=v.get('node'),event='OUTSIDE_SLOT') if v['event'] in critical and
            not any(s['start']<at<s['stop'] for s in slots) else v for at,v in enumerate(self.events)]
        self.records=e.record_windows(self.root,records_events,self.model,self.windows,self.sources,nodes=self.history.old,
            selection_records=[v['SELECTED'] for v in activation.phases])
        self.records+=interrupted_records(self.root,self.events,self.history,self.windows,self.model)

    def run(self):
        transfer_lifetimes(self.groups,self.live)
        result=self.exports()
        return dict(status='PARTIAL',kind=self.kind,**result,ownerLifetimes=sum(map(len,self.live.values())),
            observedExportAuthorityQualified=True,completeCopyFloorLifetimesQualified=False,
            transientBytesCaptured=False,cohortAdmitted=False,phase3Complete=False)


def replay(root,kind):return Replay(root,kind).run()


def validate(root):
    root=Path(root);before=process.collection.inventory(root);original=network.validate(root)
    result=replay(root,original['original']['original']['physical']['kind'])
    need(process.collection.inventory(root)==before,'transition export original changed')
    return dict(original=original,exports=result,status='PARTIAL',phase3Complete=False)


# Wrong view is already rejected by the mandatory transport reader. It cannot
# earn export-negative credit. Source-retirement/cross-death boundaries also
# have focused tests; moving a whole campaign's source to another campaign
# would break its prior transport proof rather than isolate this component.
NEGATIVES={k:v for k,v in e.NEGATIVES.items() if k not in ('pending-after-retain','source-after-retirement','record-view')}


def mutate(root,kind,name):
    root=Path(root);reader=Replay(root,kind)
    if name=='receipt-before-force':
        group=next(v for v in reader.groups if e.native_receipt(v[0]['raw']))
        q=group[0]['offer']['request'];node=q['recipient']['node']
        raw=json.loads(group[0]['raw']);records=[v for v in reader.records if v['node']==node and
             v['reference']==q['payload']['digest'] and v['start']<group[0]['offer']['received']<v['end']]
        need(len(records)==1 and raw['phase']=='ACCEPT','transition export mutation original receipt')
        boundary=records[0]['start']
        rows=[v for v in reader.rows if v['request']['trace']==q['trace'] and v['request']['recipient']['node']==node]
        requests={v['requestHash'] for v in rows};responses={v['responseHash'] for v in rows}
        def edit(lives):
            moved=[];target=None;at=-1
            for messages in lives:
                for message in list(messages):
                    event=message['value'].get('event') if message['action']=='response' else message['value'] if message['action']=='event' else None
                    if event is None:continue
                    at+=1
                    if at==boundary:target=(messages,message)
                    if event.get('request') in requests or event.get('response') in responses:
                        moved.append(message);messages.remove(message)
                at+=1  # Exact parent GROUP_CRASH between the two child streams.
            need(target is not None and moved,'transition export mutation receipt boundary')
            messages,marker=target;at=messages.index(marker);messages[at:at]=moved
        process.process.rewrite_lives(root,edit);return
    # Reuse the byte mutation driver on a virtual transcript. Only original
    # child observations change; physical snapshots/spec/result remain exact.
    with tempfile.TemporaryDirectory(prefix='v53-transition-export-wire-') as temporary:
        virtual=Path(temporary);wires=process.read(root/'wire.json')
        (virtual/'events.json').write_bytes(f.canonical(reader.events));(virtual/'wire.json').write_bytes(f.canonical(wires))
        e.mutate(virtual,name,reader=reader);changed=process.read(virtual/'wire.json')
        need(len(changed)==len(wires),'transition export mutation wire count');mapping={}
        for before,after in zip(wires,changed):
            for side in ('request','response'):
                if before[side]==after[side]:continue
                for old,new in ((before[side],after[side]),(sha(base64.b64decode(before[side])),sha(base64.b64decode(after[side])))):
                    need(old not in mapping or mapping[old]==new,'transition export inconsistent wire mutation');mapping[old]=new
        need(mapping,'transition export empty mutation')
        def replace(value):
            if isinstance(value,str):return mapping.get(value,value)
            if isinstance(value,list):return [replace(v) for v in value]
            if isinstance(value,dict):return {k:replace(v) for k,v in value.items()}
            return value
        def edit(lives):
            for messages in lives:messages[:]=replace(messages)
        process.process.rewrite_lives(root,edit)


def negative(root,kind,before,name):
    observations={'events.json','wire.json','process/life-1.jsonl','process/life-2.jsonl'}
    protected=lambda inventory:{k:v for k,v in inventory['files'].items() if k not in observations}
    with tempfile.TemporaryDirectory(prefix='v53-transition-export-negative-') as temporary:
        copied=Path(temporary)/'raw';shutil.copytree(root,copied);mutate(copied,kind,name)
        after=process.collection.inventory(copied)
        need(protected(before)==protected(after) and before['directories']==after['directories'],
             'transition export negative changed storage input')
        network.validate(copied)
        try:replay(copied,kind)
        except ValueError as error:need(str(error)==NEGATIVES[name],'transition export wrong negative '+name+': '+str(error))
        else:raise ValueError('transition export accepted mutation '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],physicalAndNetworkPrecondition='PASS')


def qualify(root):
    root=Path(root);original=validate(root);before=process.collection.inventory(root);results=[]
    for name in NEGATIVES:
        results.append(negative(root,original['exports']['kind'],before,name))
        print(json.dumps(dict(stage='export-negative',case=name,completed=len(results),total=len(NEGATIVES))),file=sys.stderr,flush=True)
    need(process.collection.inventory(root)==before,'transition export qualification changed original')
    return dict(original=original,negatives=results,originalStorageUnchanged=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root) if args.qualify else validate(args.root),sort_keys=True))
