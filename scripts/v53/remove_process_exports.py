"""Original temporal export authority across interrupted and reopened owners.

Physical and attempted-network replay run first. No original history is rerun,
and snapshot bytes are never assumed available before their force boundaries.
"""
import argparse
import base64
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from . import remove_process_network as network
from . import joining_export_evidence as exports

n,e=network,exports
p,c,f,need,sha=n.p,n.c,n.f,n.need,n.e.digest


def lifetimes(events,profile):
    markers={name:[i for i,v in enumerate(events) if v['event']=='PROCESS_'+name] for name in ('OPEN','CUT','CLOSED')}
    need(len(markers['OPEN'])==2 and len(markers['CUT'])==len(markers['CLOSED'])==1,'REMOVE process export owner markers')
    first,second=markers['OPEN'];cut=markers['CUT'][0];closed=markers['CLOSED'][0]
    need(first<cut<second<closed and events[first]['value']==profile['mode'] and events[second]['value']=='resume' and
         events[closed]['value']=='resume','REMOVE process export owner order')
    live=[(first,cut),(second,closed)]
    for at,row in enumerate(events):
        if row['node']=='node-1' and row['event'].startswith(('NETWORK_','WIRE_','PUBLICATION_SEND_')):
            need(any(a<at<b for a,b in live),'REMOVE process network outside owner lifetime')
    return live


def generation_windows(root,events,history,activation,profile,live):
    windows=[]
    for node in history.old:
        changes=[]
        if (1,node) in activation.installed:
            changes.append(('INSTALL_BEFORE_RETURN',activation.installed[1,node],profile['mode']+'-installed-1/'+node))
        for ordinal in range(1,4):
            if (ordinal,node) in history.installed:
                changes.extend([('INSTALL_BEFORE_RETURN',history.installed[ordinal,node],f'resume-installed-{ordinal}/{node}'),
                    ('PUBLICATION_BEFORE_RETURN',history.published[ordinal,node],f'resume-published-{ordinal+4}/{node}')])
        renames=[i for i,v in enumerate(events) if v['node']==node and v['event']=='INSTALL_SELECTOR_RENAMED']
        returns=[(i,v['event']) for i,v in enumerate(events) if v['node']==node and v['event'] in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN')]
        need(len(renames)==len(returns)==len(changes) and [v for _,v in returns]==[v for v,_,_ in changes],
             'REMOVE process export complete generation timeline')
        def add(files,path,start,end):
            need(start<end,'REMOVE process export generation lifetime')
            prefix,members,packet=c.current(files);identity=f.decode(files['node.gsr'],'records','NODE')['identity']
            need(identity['node']==node,'REMOVE process export generation owner')
            spans=[(max(start,a),min(end,b)) for a,b in live] if node=='node-1' else [(start,end)]
            for lower,upper in spans:
                if lower>=upper:continue
                windows.append(dict(node=node,start=lower,end=upper,path=path,members=members,packet=packet,
                    manifest=files[prefix+'generation.gsr'],identity=identity))
        add(c.inventory(root/'before-network'/node),'before-network/'+node,-1,renames[0] if renames else len(events))
        for at,((_,files,path),(returned,_)) in enumerate(zip(changes,returns)):
            need(renames[at]<returned and (at==0 or returns[at-1][0]<renames[at]),'REMOVE process export selector completion order')
            add(files,path,returned,renames[at+1] if at+1<len(renames) else len(events))
    return windows


def frozen_sources(files,node):
    root=files['root.gsr'][16:48].hex();journal=c.journal(files['grants.gsr'],root,node)
    promises={v['basisId']:raw for kind,raw,v in journal if kind=='PROMISE' and v['basisId'] is not None};result={}
    for kind,raw,value in journal:
        prefix='sources/'+str(value.get('basisId'))+'/'
        if kind!='BASIS' or prefix+'source.gscp' not in files:continue
        members={k[len(prefix):]:v for k,v in files.items() if k.startswith(prefix)};packet=c.p.decode(members['source.gscp']);c.p.bind(packet,raw)
        result[value['basisId']]=dict(node=node,basis=raw,promise=promises[value['basisId']],value=value,packet=packet,members=members)
    need(set(result)=={k.split('/')[1] for k in files if k.startswith('sources/') and k.endswith('/source.gscp')},
         'REMOVE process export original source inventory')
    return result


def source_windows(root,events,history,activation):
    grants={};prior=-1
    for ordinal,parts in enumerate(activation.phases,1):
        selected=f.decode(parts['SELECTED'],'records','SELECTED');digest=sha(parts['SELECTED'])
        end=next(i for i,v in enumerate(events) if v['event']=='ROUND_INSTALLED' and v['record']==digest)
        for row in selected['sources']:
            found=[i for i,v in enumerate(events) if prior<i<end and v['node']==row['voter'] and v['event']=='GRANT_BEFORE_RETURN']
            need(len(found)==1,'REMOVE process export original source grant')
            grants[row['voter'],row['basisId']]=(found[0],row['basisDigest'])
        prior=end
    snapshots=[(-1,'before-network')]+[(i,v['value']) for i,v in enumerate(events) if v['event']=='PROCESS_SNAPSHOT']+[(len(events),'after-close')]
    windows={};used_grants=set();used_retirements=set()
    for node in history.old:
        before={};lower=-2
        for at,path in snapshots:
            current=frozen_sources(c.inventory(root/path/node),node)
            removed=before.keys()-current.keys()
            retirements=[i for i,v in enumerate(events) if lower<i<at and v['node']==node and v['event']=='SOURCE_RETIREMENT_CREATED']
            if removed:
                # One independently derived source transaction may remove several
                # original sources. Do not infer identities from callback counts.
                need(len(retirements)==1,'REMOVE process export original source retirement interval')
                end=retirements[0];used_retirements.add(end)
                for identifier in removed:
                    own=windows[node,identifier];need(own['start']<end and own['end']==len(events),'REMOVE process export retired source order')
                    own['end']=end
            else:need(not retirements,'REMOVE process export retirement without removed source')
            for identifier,value in current.items():
                key=node,identifier
                if key in windows:
                    own=windows[key]
                    need(own['end']==len(events) and all(own[k]==v for k,v in value.items()),'REMOVE process export immutable source')
                else:
                    if at==-1:start=-1
                    else:
                        need(key in grants,'REMOVE process export source without grant');start,digest=grants[key]
                        need(lower<start<at and digest==sha(value['basis']),'REMOVE process export source grant boundary');used_grants.add(start)
                    windows[key]=dict(value,start=start,end=len(events))
            before=current;lower=at
    need(used_grants=={v[0] for v in grants.values()} and used_retirements=={i for i,v in enumerate(events) if v['event']=='SOURCE_RETIREMENT_CREATED'},
         'REMOVE process export unbound source lifetime')
    return list(windows.values())


class Replay:
    def __init__(self,root,profile):
        self.root=Path(root)/'history';self.profile=profile;self.history=n.History(root,profile)
        self.events,wires=n.observations(root,profile);self.live=lifetimes(self.events,profile)
        activation=self.history.activations(root,profile)
        ids={node:n.d.future.identity(c.inventory(self.root/'before-network'/node)) for node in self.history.old}
        root_id=f.decode(self.history.phases[0]['SELECTED'],'records','SELECTED')['root']
        self.rows=n.n.transcript.causal(self.events,wires,ids,root_id);contents=[];n.n.transcript.transfers(self.rows,contents=contents)
        self.groups=e.sessions(contents);self.windows=generation_windows(self.root,self.events,self.history,activation,profile,self.live)
        self.sources=source_windows(self.root,self.events,self.history,activation)
        # Reconstruct the control payload from the independently derived
        # installed catalog, then bind the ENTRY's original digest.
        phases=[]
        for i,parts in enumerate(self.history.phases,1):
            packet=c.current(self.history.installed[i,'node-1'])[2];entry=f.decode(parts['ENTRY'],'records','ENTRY')
            catalog=f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG');operation=catalog['results'][-1]
            if entry['kind']=='INTENT':payload=f.canonical(dict(sealed={k:operation[k] for k in ('request','prepared','receipt')}))
            elif entry['kind']=='FINAL':payload=f.canonical(dict(binding=operation['binding']))
            else:need(entry['kind']=='BARRIER','REMOVE process export command');payload=b''
            need(sha(payload)==entry['payload'],'REMOVE process export original payload');phases.append(dict(parts,PAYLOAD=payload))
        self.model=SimpleNamespace(root=root_id,phases=phases,old=self.history.old,joining=None,owner=self.history.owner)
        self.records=e.record_windows(self.root,self.events,self.model,self.windows,self.sources,nodes=self.history.old,
            selection_records=[v['SELECTED'] for v in activation.phases])

    def run(self):
        families=Counter();counts=Counter()
        for values in self.groups:
            kind=e.record_kind(values[0]['raw'])
            if kind=='GENERATION' or values[0]['kind']=='CAPSULE':scope=e.authorize_generation(values,self.windows)
            elif kind=='BASIS':e.authorize_source(values,self.windows,self.sources);scope='frozen-source'
            else:scope=e.authorize_record(values,self.windows,self.records)
            families[scope]+=1;counts[scope]+=len(values)
        need(families['current-generation'] and families['frozen-source'] and sum(families.values())==len(self.groups),
             'REMOVE process export complete observed families')
        return dict(status='PARTIAL',generationWindows=len(self.windows),sourceWindows=len(self.sources),recordWindows=len(self.records),
            boundSessions=dict(families),boundTransfers=dict(counts),unqualifiedTransfers=0,proposerLifetimes=len(self.live),
            observedExportAuthorityQualified=True,maintenanceCompositionQualified=False,phase3Complete=False)


def replay(root,profile):return Replay(root,profile).run()


def validate(root):
    root=Path(root);before=p.run.h.inventory(root);original=n.validate(root);result=replay(root,original['physical']['profile'])
    need(p.run.h.inventory(root)==before,'REMOVE process export original changed')
    return dict(result,precondition=original)


NEGATIVES={k:v for k,v in e.NEGATIVES.items() if k!='pending-after-retain'}


def movable_source(reader):
    for values in reader.groups:
        if e.record_kind(values[0]['raw'])!='BASIS':continue
        first,last=values[0]['offer'],values[-1]['commit'];q=first['request']
        source=next(v for v in reader.sources if v['node']==q['recipient']['node'] and sha(v['basis'])==q['payload']['digest'])
        # Move a complete exchange only inside its original proposer lifetime.
        # Moving the killed child's output after CUT would fail the physical
        # precondition, not demonstrate rejection of an expired source.
        if any(a<first['sent']<last['delivered']<source['end']<b for a,b in reader.live):return values,source['end']
    raise ValueError('REMOVE process mutation needs same-lifetime source retirement')


def mutate(root,profile,name):
    root=Path(root);reader=Replay(root,profile)
    shared=[n.e.parse(v) for v in (root/'history/process-trace.jsonl').read_bytes().splitlines()]
    if name in ('source-after-retirement','receipt-before-force'):
        if name=='source-after-retirement':group,target=movable_source(reader)
        else:group=next(v for v in reader.groups if e.native_receipt(v[0]['raw']))
        first=group[0]['offer'];q=first['request'];node=q['recipient']['node']
        if name=='receipt-before-force':target=next(i for i,v in enumerate(reader.events) if v['node']==node and v['event']=='ACCEPT_BEFORE_RETURN')
        exchanges=[v for v in reader.rows if v['request']['trace']==q['trace'] and v['request']['recipient']['node']==node]
        requests={v['requestHash'] for v in exchanges};responses={v['responseHash'] for v in exchanges}
        moving=[];kept=[];at=0;marker=None
        for row in shared:
            normalized=[row['value']] if row['origin']=='parent' else n.normalize(row['value']['kind'],row['value']['value'])[0]
            if at<=target<at+len(normalized):marker=row
            (moving if any(v.get('request') in requests or v.get('response') in responses for v in normalized) else kept).append(row)
            at+=len(normalized)
        need(marker is not None and any(v is marker for v in kept) and moving,'REMOVE process export exact mutation boundary')
        index=next(i for i,v in enumerate(kept) if v is marker)+int(name=='source-after-retirement');kept[index:index]=moving
        n.rewrite(root,kept);return
    with tempfile.TemporaryDirectory(prefix='v53-process-export-wire-') as temp:
        virtual=Path(temp);_,wires=n.observations(root,profile)
        (virtual/'events.json').write_bytes(f.canonical(reader.events));(virtual/'wire.json').write_bytes(f.canonical(wires))
        e.mutate(virtual,name,reader=reader)
        changed=n.d.read(virtual/'wire.json');need(len(changed)==len(wires),'REMOVE process export wire mutation count')
        mapping={}
        for before,after in zip(wires,changed):
            for side in ('request','response'):
                if before[side]==after[side]:continue
                for old,new in ((before[side],after[side]),(sha(base64.b64decode(before[side])),sha(base64.b64decode(after[side])))):
                    need(old not in mapping or mapping[old]==new,'REMOVE process export consistent wire mutation');mapping[old]=new
        need(mapping,'REMOVE process export empty wire mutation')
        n.rewrite(root,n.replace_strings(shared,mapping))
        for name in ('wire.json','failures.json'):
            path=root/'history'/name;path.write_bytes(f.canonical(n.replace_strings(n.d.read(path),mapping)))


def negative(root,profile,before,name):
    with tempfile.TemporaryDirectory(prefix='v53-process-export-negative-') as temp:
        changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,profile,name);after=p.run.h.inventory(changed)
        protected=lambda inv:{k:v for k,v in inv['files'].items() if k not in n.OBSERVATIONS}
        need(protected(before)==protected(after) and before['directories']==after['directories'],'REMOVE process export negative changed physical inputs')
        n.validate(changed)
        try:replay(changed,profile)
        except ValueError as error:need(str(error)==NEGATIVES[name],'REMOVE process unrelated export negative: '+name+': '+str(error))
        else:raise ValueError('REMOVE process export mutation accepted: '+name)
    return dict(case=name,status='REJECTED',reason=NEGATIVES[name],physicalAndNetworkPrecondition='PASS')


def qualify(root,*,workers=1):
    need(type(workers) is int and 1<=workers<=4,'REMOVE process export replay workers')
    root=Path(root);original=validate(root);before=p.run.h.inventory(root);outcomes=[]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(negative,root,original['precondition']['physical']['profile'],before,name):name for name in NEGATIVES}
        for task in as_completed(tasks):
            name=tasks[task]
            try:result=task.result()
            except Exception as error:result=dict(case=name,status='FAIL',type=type(error).__name__,failure=str(error))
            outcomes.append(result);print(json.dumps(dict(result,completed=len(outcomes),total=len(tasks))),file=sys.stderr,flush=True)
    need(p.run.h.inventory(root)==before,'REMOVE process export negatives changed original')
    need(all(v['status']=='REJECTED' for v in outcomes),'REMOVE process export negative matrix failed')
    return dict(original=original,negatives=sorted(outcomes,key=lambda v:v['case']))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true')
    parser.add_argument('--workers',type=int,default=1);args=parser.parse_args()
    print(json.dumps(qualify(args.root,workers=args.workers) if args.qualify else validate(args.root),sort_keys=True))
