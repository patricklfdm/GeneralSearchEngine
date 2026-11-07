"""Derive governing copies and transient retirements inside one joining history."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile

from . import joining_preparation_evidence as preparation
from . import joining_source_retirement as observed

p=preparation; c=p.c; init=p.init; t=init.transition
s,f,disk,need,sha=p.s,p.f,p.disk,p.need,p.sha


def governing(files,copies,node):
    """Use preceding derived generations, never a captured FLOOR or its digest."""
    files=copy.deepcopy(files); own_prefix,own,packet=disk.current(files); cap=packet['capsule']
    need(node in copies,'joining retirement exact local governing copy')
    copy_prefix,copy_members,_=disk.current(copies[node])
    need(own==copy_members and files[own_prefix+'generation.gsr']==copies[node][copy_prefix+'generation.gsr'],
         'joining retirement exact local governing copy')
    s.catalog.majority(cap['cut']['view'],sorted(copies))
    need(not any(name=='floor-copies' or name.startswith('floor-copies/') for name in files),
         'joining retirement previous floor not released')
    identities=s.catalog.identities(f.decode(packet['objects'][cap['catalog']],'records','CATALOG')['identities'])
    references=[];members={}
    for peer,source in sorted(copies.items()):
        prefix,members_for_copy,original=disk.current(source);other=original['capsule']
        generation=dict(members_for_copy, **{'generation.gsr':source[prefix+'generation.gsr']})
        identity=f.decode(source['node.gsr'],'records','NODE')['identity']
        need(identity==identities[peer] and other['root']==cap['root'] and disk.anchor(other)==disk.anchor(cap),
             'joining retirement governing original cut/identity')
        digest=sha(generation['generation.gsr'])
        references.append(dict(voter=peer,generation=digest,catalog=other['catalog'],snapshot=other['application']))
        members['floor-copies/'+digest]=None
        members.update({'floor-copies/'+digest+'/'+name:raw for name,raw in generation.items()})
    floor=f.encode('records','FLOOR',dict(root=cap['root'],node=node,cut=cap['cut'],sources=references))
    files.update({'floor-copies':None,'floor-copies/proposal.gsr':floor,'floor-copies/floor.gsr':floor,**members})
    return files


def published_tail(source,tail,files,node,cap):
    accept=f.decode(source['objects'][tail],'records','ACCEPT')
    floor=f.decode(files['floor-copies/floor.gsr'],'records','FLOOR')
    need(accept['root']==floor['root']==cap['root'] and floor['node']==node and floor['cut']==cap['cut'] and
         accept['index']<=floor['cut']['index'], 'joining retirement uncovered source tail')


def decision(files,node,identifier,*,coverage=None,allow_published_tail=False,tail_check=None):
    """Exact old grant plus a new decision, derived before any deletion."""
    _,current,packet=disk.current(files);cap=packet['capsule']
    rows=disk.journal(files['grants.gsr'],cap['root'],node)
    groups=[]
    for row in rows:
        if row[0]=='PROMISE':groups.append([])
        need(groups,'joining retirement original grant group');groups[-1].append(row)
    target=[group for group in groups if group[0][2]['basisId']==identifier]
    need(len(target)==1 and len(target[0])>=2 and target[0][1][0]=='BASIS', 'joining retirement original source group')
    group=target[0];promise,basis=group[0][1],group[1][1]
    need(group is not groups[-1] and promise!=current['promise.gsr'] and basis!=current.get('basis.gsr'),
         'joining retirement pinned original source')
    prefix='sources/'+identifier+'/'
    source=disk.p.decode(files[prefix+'source.gscp']);disk.p.bind(source,basis)
    available=t.require_coverage(files) if coverage is None else coverage
    point=disk.anchor(source['capsule'])
    need(available.get(point['cut']['index'])==point and source['capsule']['root']==cap['root'],
         'joining retirement governing source coverage')
    tail=group[1][2]['accepted']
    if tail is not None and tail_check is not None:
        # A caller owning an independently replayed transferred vote must prove
        # that succession explicitly. Ordinary joining readers retain their
        # unresolved-tail refusal; a Boolean cannot waive it.
        tail_check(source,tail,files,node,cap)
    elif tail is not None and allow_published_tail:
        published_tail(source,tail,files,node,cap)
    else:need(tail is None, 'joining retirement joining fixture unresolved tail')
    expected_names={prefix+'source.gscp',*[prefix+h+'.image' for h in source['images']]}
    need({n for n in files if n.startswith(prefix)}==expected_names,'joining retirement complete original source files')
    for digest,size in source['images'].items():
        raw=files[prefix+digest+'.image']
        need(len(raw)==size and sha(raw)==digest,'joining retirement original source image')
    record=f.encode('records','RETIREMENT',dict(root=cap['root'],node=node,
        floor=sha(files['floor-copies/floor.gsr']),selector=sha(files['selector.gsr']),
        files=[dict(path=n,size=len(files[n]),sha256=sha(files[n])) for n in sorted(expected_names)]))
    authority=record+promise+basis+source['capsuleBytes']
    remaining={name.split('/')[1] for name in files if name.startswith('sources/') and name.endswith('/source.gscp')}-{identifier}
    protected={current['promise.gsr']}
    compact=b''.join(raw for group in groups if group is not target[0] and
        (group is groups[-1] or group[0][1] in protected or group[0][2]['basisId'] in remaining)
        for _,raw,_ in group)
    return authority,compact


def floor_order(events,node,before):
    """The derived floor must have completed its local durable boundary."""
    rows=[(at,row['event']) for at,row in enumerate(events[:before]) if row.get('node')==node]
    starts=[at for at,point in rows if point=='FLOOR_RESERVED']
    need(starts,'joining retirement governing floor force absent')
    start=starts[-1];window=[point for at,point in rows if at>=start]
    required=['FLOOR_AUTHORITY_WRITTEN','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED','FLOOR_BEFORE_RETURN']
    need([point for point in window if point in required]==required,'joining retirement governing floor force order')
    need(not any(point.startswith('FLOOR_RELEASE_') for point in window),'joining retirement released governing floor')
    return start


class Retirements:
    def __init__(self,root,events,*,voters=c.VOTERS,bootstrap_source='EMPTY',wire_layout='JSON'):
        self.events=events;self.rows=observed.collect(root,events,**observed.policy.options(bootstrap_source,wire_layout));self.positions={};self.transactions=0;self.prefixes=0;self.floors=set()
        self.by_node={node:[v for v in self.rows if v['node']==node] for node in voters}
        need(sum(map(len,self.by_node.values()))==len(self.rows),'joining retirement foreign transaction owner')

    def compare(self,node,files,copies,identifiers):
        files=governing(files,copies,node)
        for identifier in sorted(identifiers):
            position=self.positions.get(node,0)
            need(position<len(self.by_node[node]),'joining retirement original transaction absent')
            row=self.by_node[node][position];authority,compact=decision(files,node,identifier)
            self.floors.add((node,floor_order(self.events,node,row['steps'][0]['event'])))
            initial={n:dict(directory=True) if raw is None else observed.release.r.entry(raw) for n,raw in files.items() if n!='.'}
            self.prefixes+=observed.compare(row,initial,authority,compact,identifier)
            self.positions[node]=position+1;self.transactions+=1
            files={n:raw for n,raw in files.items() if not (n=='sources/'+identifier or n.startswith('sources/'+identifier+'/'))}
            files['grants.gsr']=compact

    def complete(self):
        need(all(self.positions.get(n,0)==len(rows) for n,rows in self.by_node.items()),'joining retirement underived transaction')


class History(p.History):
    def __init__(self,root,replay,grants,retirements):
        self.retirements=retirements;super().__init__(root,replay,grants)
    def maintain(self):self.group=t.maintenance(self.group,self.retirements.compare)


class Initialization(p.Initialization):
    def __init__(self,root,handoff,grants,retirements):
        self.retirements=retirements;super().__init__(root,handoff,grants)
    def maintain(self,copies):self.group=t.maintenance(self.group,self.retirements.compare,copies)


class Continuation(p.Continuation):
    def __init__(self,root,initialization,grants,retirements):
        self.retirements=retirements;super().__init__(root,initialization,grants)
    def maintenance(self,group,node):return c.maintenance(group,node,self.retirements.compare)


def validate(root):
    root=Path(root);original=s.collection.inventory(root)
    events=s.collection.read_json(root,'events.json',s.collection.EVENT_BYTES)
    grants=p.Captures(root,events);retirements=Retirements(root,events)
    c.t.publication.validate(root);replay=s.Replay(root)
    for index in range(1,12):replay.step(index)
    history=History(root,replay,grants,retirements);history.run()
    owner=init.placement.Placement(root,history);owner.run()
    handoff=init.retirement.Retirement(root,owner);handoff.run()
    initialization=Initialization(root,handoff,grants,retirements);initialization.run()
    result=Continuation(root,initialization,grants,retirements).run();retirements.complete()
    need(s.collection.inventory(root)==original,'joining original changed during retirement replay')
    result.update(scope='native-ADD-derived-governing-floor-and-source-retirement',
        precedingOwnerSnapshotComparisons=history.comparisons+3,sourceRetirementTransactions=retirements.transactions,
        sourceRetirementPrefixes=retirements.prefixes,governingFloorForceWindows=len(retirements.floors),sourceRetirementPhysicalQualified=True)
    return result


NEGATIVES = {
    'wrong-floor':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-selector':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-source-file':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-original-promise':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'early-journal':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-deletion':'retirement capture exact prefix: SOURCE_RETIREMENT_FILE_DELETED',
    'early-floor-release':'retirement capture exact prefix: SOURCE_RETIREMENT_FILE_DELETED',
    'retained-decision':'retirement capture exact prefix: SOURCE_RETIREMENT_CLEARED',
    'missing-floor-force':'joining retirement governing floor force order',
    'released-floor':'joining retirement released governing floor',
}


def mutate(root,name):
    events=json.loads((root/'events.json').read_bytes());rows=[row for row in events if row.get('event')==observed.EVENT]
    first=rows[0];node=first['node']
    if name in ('missing-floor-force','released-floor'):
        before=events.index(first)
        start=max(at for at,row in enumerate(events[:before]) if row.get('node')==node and row['event']=='FLOOR_RESERVED')
        at=next(at for at in range(start,before) if events[at].get('node')==node and events[at]['event']=='FLOOR_AUTHORITY_FORCED')
        if name=='missing-floor-force':events.pop(at)
        else:events.insert(before-1,dict(node=node,event='FLOOR_RELEASE_CLEARED'))
        (root/'events.json').write_bytes(f.canonical(events));return
    def at(point):return next(row for row in rows if row['node']==node and row['point']==point)
    def metadata(row):return json.loads((root/row['capture']).read_bytes())
    def entries(row):return {v['name']:v['identity'] for v in metadata(row)['files']}
    point='SOURCE_RETIREMENT_FILE_DELETED' if name in ('wrong-deletion','early-floor-release') else 'SOURCE_RETIREMENT_CLEARED' if name=='retained-decision' else 'SOURCE_RETIREMENT_WRITTEN'
    event=at(point);meta=metadata(event);files=entries(event);objects=root/observed.DIRECTORY/'objects'
    def read(n):return (objects/files[n]['sha256']).read_bytes()
    def store(n,data):
        (objects/sha(data)).write_bytes(data);files[n]=dict(size=len(data),sha256=sha(data))
    if name in ('wrong-floor','wrong-selector','wrong-source-file','wrong-original-promise'):
        raw=read(observed.release.AUTHORITY);size=48+int.from_bytes(raw[12:16],'big')
        record=f.decode(raw[:size],'records','RETIREMENT')
        if name=='wrong-original-promise':
            length=48+int.from_bytes(raw[size+12:size+16],'big');promise=f.decode(raw[size:size+length],'records','PROMISE')
            promise['basisId']='00000000-0000-0000-0000-000000000001'
            changed=raw[:size]+f.encode('records','PROMISE',promise)+raw[size+length:]
        else:
            if name=='wrong-source-file':record['files'][0]['sha256']='0'*64
            else:record[name.removeprefix('wrong-')]='0'*64
            changed=f.encode('records','RETIREMENT',record)+raw[size:]
        store(observed.release.AUTHORITY,changed)
    elif name=='early-journal': files['grants.gsr']=entries(at('SOURCE_RETIREMENT_JOURNAL_PRUNED'))['grants.gsr']
    elif name=='wrong-deletion':
        before=entries(at('SOURCE_RETIREMENT_JOURNAL_PRUNED'));removed=next(n for n in before if n.startswith('sources/') and n not in files)
        files[removed]=before[removed]
    elif name=='early-floor-release':files={n:v for n,v in files.items() if n!='floor-copies' and not n.startswith('floor-copies/')}
    elif name=='retained-decision':files[observed.release.AUTHORITY]=entries(at('SOURCE_RETIREMENT_FORCED'))[observed.release.AUTHORITY]
    else:raise ValueError('unknown joining retirement mutation')
    meta['files']=[dict(name=n,identity=files[n]) for n in sorted(files)]
    encoded=f.canonical(meta);(root/event['capture']).write_bytes(encoded);event['sha256']=sha(encoded)
    (root/'events.json').write_bytes(f.canonical(events))


def qualify(root,progress=None):
    root=Path(root);original=validate(root);outcomes=[]
    if progress:progress(dict(stage='original',status='PASS'))
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joining-retirement-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(root,target);mutate(target,name);observed.validate(target)
            try:validate(target)
            except ValueError as error:need(str(error)==reason,'unrelated joining retirement negative: '+name+': '+str(error))
            else:raise ValueError('joining retirement mutation accepted: '+name)
        outcomes.append(dict(case=name,status='REJECTED',reason=reason,captureCollection='PASS'))
        if progress:progress(outcomes[-1])
    return dict(original=original,negatives=outcomes)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify(args.root,lambda row:print(json.dumps(row),file=sys.stderr,flush=True)) if args.qualify else validate(args.root),sort_keys=True))
