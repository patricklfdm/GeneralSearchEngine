"""Time-bound current-generation and frozen-source exports in one native ADD.

The complete physical/network precondition runs first. Its checked snapshots
supply bytes; selectors, grant returns and source retirement delimit lifetimes.
Other export families are enumerated explicitly, never promoted to qualified.
"""
import argparse
import base64
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil
import tempfile

from . import joining_network_evidence as network
from . import native_dispatch_evidence as native

n=network; p=n.p; f=n.f; disk=n.disk; need=n.need; sha=n.sha
LABELS={0:'installed',2:'installed-2',4:'installed-3',6:'installed-4',9:'continuation-installed-9',10:'continuation-installed-10'}


def record_kind(raw):
    if len(raw)<48 or raw[:4]!=b'GSER':return None
    kind=next((k for k,v in f.catalog()['records'].items() if v['id']==int.from_bytes(raw[8:10],'big')),None)
    need(kind is not None,'joining export record kind');f.decode(raw,'records',kind);return kind


def generation_windows(root,events,replay,*,recovery=None,nodes=None,final_adoption=False):
    """Snapshots are accepted only after independent physical derivation."""
    result=[]
    for node in (('node-1','node-2','node-4') if nodes is None else nodes):
        changes=[];seen=set()
        for index,parts in enumerate(replay.phases,1):
            chosen=f.decode(parts['SELECTED'],'records','SELECTED')
            if sha(parts['SELECTED']) not in seen and node in [v['voter'] for v in chosen['sources']]:
                cut=chosen['cut']['index'];need(cut in LABELS,'joining export installation snapshot')
                path=f'joining-installed-{cut}/replica' if node==replay.joining else LABELS[cut]+'/'+node
                changes.append(('INSTALL_BEFORE_RETURN',path));seen.add(sha(parts['SELECTED']))
            cert=f.decode(parts['CERTIFICATE'],'records','CERTIFICATE')
            if node in [v['voter'] for v in cert['proofs']]:
                path=f'joining-published-{index}/replica' if node==replay.joining else f'published-{index}/{node}'
                changes.append(('PUBLICATION_BEFORE_RETURN',path))
            if recovery is not None and node==replay.joining and index==10:
                changes.append(('ADOPTION_INSTALL_BEFORE_RETURN','joining-after-final-prefix/replica'))
        if final_adoption and node==replay.joining:
            need(recovery is None,'joining export distinct recovery modes')
            current=0
            for parts in replay.phases:
                selected=f.decode(parts['SELECTED'],'records','SELECTED')
                if node in [v['voter'] for v in selected['sources']]:current=max(current,selected['cut']['index'])
                cert=f.decode(parts['CERTIFICATE'],'records','CERTIFICATE')
                if node in [v['voter'] for v in cert['proofs']]:current=max(current,cert['index'])
            if current<replay.states[-1]['cut']['index']:
                changes.append(('ADOPTION_INSTALL_BEFORE_RETURN','joining-after-final-recovery/replica'))
        if recovery is not None:
            chosen=f.decode(recovery,'records','SELECTED',replay.root)
            need(chosen['cut']==replay.states[11]['cut'] and chosen['ballot']['proposer']==replay.joining,
                 'joining export same-view recovery selection')
            if node in [v['voter'] for v in chosen['sources']]:
                path='joining-after-final-recovery/replica' if node==replay.joining else 'same-view-installed/'+node
                changes.append(('INSTALL_BEFORE_RETURN',path))
        renames=[at for at,row in enumerate(events) if row.get('node')==node and row['event']=='INSTALL_SELECTOR_RENAMED']
        returns=[(at,row['event']) for at,row in enumerate(events) if row.get('node')==node and
                 row['event'] in ('INSTALL_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN','ADOPTION_INSTALL_BEFORE_RETURN')]
        need(len(renames)==len(returns)==len(changes) and [point for _,point in returns]==[point for point,_ in changes],
             'joining export complete generation timeline')
        if node==replay.joining:
            starts=[at for at,row in enumerate(events) if row.get('node')==node and row.get('scope')=='initial-owner' and
                    row['event']=='CURRENT_DIRECTORY_FORCED']
            need(len(starts)==1,'joining export initial joining generation force')
            start=starts[0];path='joining-originals-native/replica'
        else:start=-1;path='before-network/'+node
        def add(path,start,end):
            need(start<end,'joining export generation lifetime')
            files=disk.inventory(Path(root)/path);prefix,members,packet=disk.current(files)
            identity=f.decode(files['node.gsr'],'records','NODE')['identity']
            need(identity['node']==node,'joining export generation owner')
            result.append(dict(node=node,start=start,end=end,path=path,members=members,packet=packet,
                               manifest=files[prefix+'generation.gsr'],identity=identity))
        add(path,start,renames[0] if renames else len(events))
        for i,((_,path),(at,_)) in enumerate(zip(changes,returns)):
            need(renames[i]<at and (i==0 or returns[i-1][0]<renames[i]),'joining export selector completion order')
            add(path,at,renames[i+1] if i+1<len(renames) else len(events))
    return result


def current(windows,node,lower,upper):
    found=[v for v in windows if v['node']==node and v['start']<lower<=upper<v['end']]
    need(len(found)==1,'joining export inactive current generation');return found[0]


def source_windows(root,events):
    captures=p.captures.collect(root,events);retirements=n.physical.observed.collect(root,events);ends={}
    for transaction in retirements:
        step=next(v for v in transaction['steps'] if v['point']=='SOURCE_RETIREMENT_WRITTEN')
        raw=step['files'][n.physical.observed.release.AUTHORITY];size=48+int.from_bytes(raw[12:16],'big')
        decision=f.decode(raw[:size],'records','RETIREMENT')
        sources={v['path'].split('/')[1] for v in decision['files'] if v['path'].startswith('sources/')}
        need(len(sources)==1,'joining export retired original source identity')
        key=transaction['node'],sources.pop();need(key not in ends,'joining export duplicate source retirement')
        ends[key]=transaction['steps'][0]['event']
    result=[]
    for capture in captures:
        node=capture['node'];files=disk.inventory(Path(root)/capture['capture']/'replica')
        journal=disk.journal(files['grants.gsr'],capture['root'],node);promise,basis=journal[-2][1],journal[-1][1]
        value=f.decode(basis,'records','BASIS');prefix='sources/'+capture['basisId']+'/'
        packet=disk.p.decode(files[prefix+'source.gscp'])
        result.append(dict(node=node,start=capture['capturedEvent'],returnEvent=capture['returnEvent'],end=ends.get((node,capture['basisId']),len(events)),
            basis=basis,promise=promise,value=value,packet=packet,members={k.removeprefix(prefix):v for k,v in files.items() if k.startswith(prefix)}))
    need(set(ends)<={(v['node'],v['value']['basisId']) for v in result},'joining export retirement without original grant')
    return result


def sessions(contents):
    grouped=defaultdict(list)
    for value in contents:
        q=value['offer']['request'];grouped[q['sender']['node'],q['recipient']['node'],q['trace']].append(value)
    return [sorted(values,key=lambda v:v['offer']['sent']) for values in grouped.values()]


def exact(values,expected,reason):
    """Reference aliases and content kinds must match bytes, not merely hashes."""
    actual=[(v['offer']['request']['payload']['digest'],v['raw'],v['kind']) for v in values]
    need(actual==expected,reason)


def learner_alias(own,request):
    cap=own['packet']['capsule'];catalog=f.decode(own['packet']['objects'][cap['catalog']],'records','CATALOG')
    reader=request['sender'];reference=request['payload']['digest']
    for result in catalog['results']:
        change=result['request']
        if change['kind']=='REMOVE' or reader not in change['target']:continue
        modes=[]
        voters=set(cap['cut']['view']['old'])|set(cap['cut']['view']['new'])
        if reader['node'] not in voters and catalog['active']==change['number'] and cap['cut']['view']['operation'] is None:modes.append('source')
        prepared=result.get('prepared')
        if prepared is not None and reader['node'] not in prepared['cut']['view']['old'] and result['phase'] in ('PREPARING','READY','SEALED','JOINT','COMPLETED','CANCELLED'):modes.append('progress')
        for mode in modes:
            for scope in ('prefix','ancestry','generation'):
                alias=sha(f.canonical(dict(schema='gse-v53-learner-'+mode+'-reference/1.3',root=cap['root'],
                    learner=reader,request=change,cut=cap['cut'],scope=scope)))
                if reference==alias:
                    need(request['view']==change['expected'] and request['ballot']==dict(counter=1,proposer=reader['node'],incarnation=reader['storage']),
                         'joining export learner original correlation')
                    return scope
    return None


def authorize_generation(values,windows):
    first,last=values[0]['offer'],values[-1]['commit'];q=first['request'];node=q['recipient']['node']
    own=current(windows,node,first['received'],last['offered']);cap=own['packet']['capsule'];members=own['members']
    identities=n.s.catalog.identities(f.decode(own['packet']['objects'][cap['catalog']],'records','CATALOG')['identities'])
    proposer=identities.get(q['ballot']['proposer'])
    need(q['sender']==identities.get(q['sender']['node']) and q['recipient']==own['identity'] and
         proposer is not None and q['ballot']['incarnation']==proposer['storage'],
         'joining export current permanent identities')
    reference=q['payload']['digest'];original_reference=reference;learner=learner_alias(own,q)
    generation=native.current_reference(cap,'retained-current-generation')
    metadata=native.current_reference(cap,'retained-current-generation-metadata')
    ancestry=native.current_reference(cap,'retained-current-ancestry')
    packet_only=native.current_reference(cap,'retained-current-packet');cut=sha(f.canonical(cap['cut']))
    if learner:reference={'prefix':cut,'generation':generation,'ancestry':ancestry}[learner]
    expected=[]
    if reference in (generation,metadata):
        expected=next(v for v in native.maintenance_generations(own['manifest'],members,own['packet']) if v[0][0]==reference)
    elif reference==ancestry:
        expected=[(reference,own['manifest'],'RECORD')]
        if 'ancestry.gsr' in members:expected.append((sha(members['ancestry.gsr']),members['ancestry.gsr'],'RECORD'))
    elif reference in (packet_only,cut):
        expected=[(reference,members['source.gscp'],'CAPSULE')]
        if reference==cut:expected += [(h,members[h+'.image'],'APPLICATION') for h in sorted(own['packet']['images'])]
    else:raise ValueError('joining export current generation alias')
    expected[0]=(original_reference,*expected[0][1:])
    exact(values,expected,'joining export exact current generation')
    return 'learner-current-content' if learner else 'current-generation'


def authorize_source(values,windows,sources):
    first,last=values[0]['offer'],values[-1]['commit'];q=first['request'];node=q['recipient']['node']
    matches=[v for v in sources if v['node']==node and sha(v['basis'])==q['payload']['digest']]
    need(len(matches)==1,'joining export original source alias');source=matches[0]
    need(source['start']<first['received']<=last['offered']<source['end'],'joining export inactive frozen source')
    own=current(windows,node,first['received'],first['offered'])
    cap=own['packet']['capsule'];view=n.s.catalog.authority(cap['root'],cap['cut']['view'])
    need(q['view']==source['value']['view']==view and q['ballot']==source['value']['ballot'],
         'joining export original source view/ballot')
    members=source['members'];packet=source['packet']
    expected=[(sha(source['basis']),source['basis'],'RECORD'),(sha(source['promise']),source['promise'],'RECORD'),
              (sha(packet['capsuleBytes']),members['source.gscp'],'CAPSULE')]
    receiver=current(windows,q['sender']['node'],first['received'],last['offered'])
    for h in sorted(packet['images']):
        if receiver['members'].get(h+'.image')!=members[h+'.image']:expected.append((h,members[h+'.image'],'APPLICATION'))
    exact(values,expected,'joining export exact frozen source')
    return source


def next_promise(events,node,start,end):
    return min([end]+[at for at,row in enumerate(events) if at>start and row.get('node')==node and row['event']=='PROMISE_FORCED'])


def record_windows(root,events,model,windows,sources,*,recovery=None,nodes=('node-1','node-2','node-4'),selection_records=None,old_owner_lifetimes=None):
    result=[]
    def add(node,start,end,raw,*,reference=None,ballot=None,view=None,family='record'):
        if raw:result.append(dict(node=node,start=start,end=end,raw=raw,reference=reference or sha(raw),
                                 ballot=ballot,view=view,family=family))
    # Journal records are supported by their captured exact bytes. A frozen
    # source's retirement boundary is conservative for its journal records too.
    for source in sources:
        add(source['node'],source['start'],source['end'],source['promise'],family='journal')
    selected={sha(raw):raw for raw in (selection_records if selection_records is not None else
                                      [parts['SELECTED'] for parts in model.phases])}
    if recovery is not None:
        need(sha(recovery) not in selected,'joining export duplicate recovery selection')
        selected[sha(recovery)]=recovery
    for node in nodes:
        originals=[raw for raw in selected.values() if node in [s['voter'] for s in f.decode(raw,'records','SELECTED')['sources']]]
        forced=[at for at,row in enumerate(events) if row.get('node')==node and row['event']=='SELECTED_FORCED']
        need(len(originals)==len(forced),'joining export journal selection timeline')
        for raw,at in zip(originals,forced):
            value=f.decode(raw,'records','SELECTED');source=next(v for v in sources if v['node']==node and v['value']['ballot']==value['ballot'])
            add(node,at,source['end'],raw,family='journal')
    phases=n.phase.blocks(events,model,old_owner_lifetimes=old_owner_lifetimes)
    for (index,node),points in phases.items():
        parts=model.phases[index-1];selected=f.decode(parts['SELECTED'],'records','SELECTED')
        before=current(windows,node,points['ACCEPT_BEFORE_RETURN'],points['ACCEPT_BEFORE_RETURN'])
        end=before['end'];ballot=selected['ballot'];view=selected['view']
        live_end=next_promise(events,node,points['ACCEPT_BEFORE_RETURN'],end)
        for kind,phase in [('ENTRY','ACCEPT'),('ACCEPT','ACCEPT'),('PROOF','PROOF'),('CERTIFICATE','CERTIFICATE')]:
            add(node,points[phase+'_BEFORE_RETURN'],end,parts[kind],family='pending-record')
        add(node,points['ACCEPT_BEFORE_RETURN'],live_end,parts['PAYLOAD'],ballot=ballot,view=view,family='pending-payload')
        for phase in ('ACCEPT','PROOF'):
            receipt=f.canonical(dict(root=model.root,voter=node,incarnation=before['identity']['storage'],phase=phase,record=sha(parts[phase])))
            reference=sha(f.canonical(dict(schema='gse-v53-vote-observation/1.3',receipt=sha(receipt))))
            add(node,points[phase+'_BEFORE_RETURN'],live_end,receipt,reference=reference,ballot=ballot,view=view,family='native-vote-receipt')
        files=model.owner('applied',index,node)
        published=current(windows,node,points['PUBLICATION_BEFORE_RETURN']+1,points['PUBLICATION_BEFORE_RETURN']+1)
        published_end=next_promise(events,node,points['PUBLICATION_BEFORE_RETURN'],published['end'])
        for name,raw in files.items():
            if name.startswith('applied-end/') and name.endswith('.gsr') and raw is not None and record_kind(raw) in ('CHECKPOINT','CHECKPOINT_ACK'):
                add(node,points['APPLY_BEFORE_RETURN'],live_end,raw,family='native-applied-checkpoint')
                add(node,points['PUBLICATION_BEFORE_RETURN'],published_end,raw,ballot=ballot,view=view,family='published-local-checkpoint')
    return result


def current_records(own):
    packet=own['packet'];cap=packet['capsule'];records={}
    allowed={'PROMISE','BASIS','SELECTED','ENTRY','ACCEPT','PROOF','CERTIFICATE'}
    for digest,raw in packet['objects'].items():
        if record_kind(raw) in allowed:records[digest]=raw
    # Unreferenced packet ACKs never become authenticated checkpoint evidence.
    for item in cap['items']:
        for digest in [item['statement'],*item['endorsements']]:records[digest]=packet['objects'][digest]
    for raw in n.s.frames(own['members']['ancestry.gsr']) if own['members'].get('ancestry.gsr') else ():
        need(record_kind(raw) in ('CHECKPOINT','CHECKPOINT_ACK'),'joining export typed original ancestry')
        records[sha(raw)]=raw
    return records


def authorize_record(values,windows,records):
    need(len(values)==1,'joining export singleton record session')
    value=values[0]
    return authorize_record_interval(value,windows,records,value['commit']['offered'])


def authorize_record_interval(value,windows,records,through):
    """Authorize bytes through an actual response; this does not prove COMMIT.

    Callers must first validate the original transport. An incomplete transfer
    can use its last DATA response without manufacturing a commit response.
    """
    values=[value];first=value['offer'];q=first['request'];node=q['recipient']['node']
    own=current(windows,node,first['received'],through);cap=own['packet']['capsule']
    identities=n.s.catalog.identities(f.decode(own['packet']['objects'][cap['catalog']],'records','CATALOG')['identities'])
    voters=set(cap['cut']['view']['old'])|set(cap['cut']['view']['new']);proposer=q['ballot']['proposer']
    need(q['sender']==identities.get(q['sender']['node']) and q['recipient']==own['identity'] and proposer in voters and
         q['ballot']['incarnation']==identities[proposer]['storage'],
         'joining export record original context')
    reference=q['payload']['digest'];available=current_records(own)
    candidates=[v for v in records if v['node']==node and v['reference']==reference and
                v['start']<first['received']<=through<v['end']]
    if q['view']!=n.s.catalog.authority(cap['root'],cap['cut']['view']):
        # Completed native publication may serve only its own retained local
        # checkpoint through the original request view, until a fresh promise.
        permitted=[v for v in candidates if v['family']=='published-local-checkpoint' and
                   q['view']==v['view'] and q['ballot']==v['ballot'] and available.get(reference)==v['raw']]
        need(permitted,'joining export record original context')
        exact(values,[(reference,permitted[0]['raw'],'RECORD')],'joining export exact completed checkpoint')
        return 'published-local-checkpoint'
    if reference in available:
        exact(values,[(reference,available[reference],'RECORD')],'joining export exact published record');return 'published-record'
    need(candidates,'joining export unavailable original record')
    need(any(value['raw']==v['raw'] and value['kind']=='RECORD' and (v['ballot'] is None or
             q['ballot']==v['ballot'] and q['view']==v['view']) for v in candidates),'joining export exact live record')
    return next(v['family'] for v in candidates if value['raw']==v['raw'])


def pending_ack(model):
    start,_,scope=n.s.capsules.spans(model.entries,9)[-1]
    statement=f.encode('records','CHECKPOINT',model.checkpoint(start,9,scope))
    return model.acks[sha(statement),model.joining]


def native_receipt(raw):
    return raw.startswith(b'{') and set(json.loads(raw))=={'root','voter','incarnation','phase','record'}


def authorize_pending(values,events,model):
    need(len(values)==1,'joining export singleton pending ACK')
    value=values[0];first,last=value['offer'],value['commit'];q=first['request'];raw=pending_ack(model)
    points=[(at,row['event']) for at,row in enumerate(events) if row.get('node')==model.joining and row.get('scope')=='pending-intent']
    returned=[at for at,point in points if point=='LEARNER_JOINING_ACK_BEFORE_RETURN' and at<first['received']]
    end=[at for at,point in points if point=='LEARNER_JOINING_RETAIN_CREATED']
    need(returned and len(end)==1 and returned[-1]<first['received']<=last['offered']<end[0],
         'joining export pending ACK lifetime')
    forced=[at for at,point in points if point=='LEARNER_JOINING_ACK_FORCED' and at<returned[-1]]
    parents=[at for at,point in points if point=='LEARNER_JOINING_ACK_PARENT_FORCED' and at<returned[-1]]
    need(forced and parents and forced[-1]<parents[-1]<returned[-1], 'joining export pending ACK durability')
    selected=f.decode(model.phases[8]['SELECTED'],'records','SELECTED')
    identities=n.s.catalog.identities(model.states[9]['identities']);view=model.states[8]['cut']['view']
    need(q['recipient']==identities[model.joining] and q['sender']==identities.get(q['sender']['node']) and
         q['sender']['node'] in view['old'] and q['view']==selected['view'] and q['ballot']==selected['ballot'] and
         events[first['received']].get('scope')=='pending-listener','joining export pending ACK original scope')
    exact(values,[(sha(raw),raw,'RECORD')],'joining export exact pending ACK')


def replay(root,*,kind='ADD',recovery=None):
    root=Path(root);model=n.s.Replay(root,kind=kind)
    for index in range(1,12):model.step(index)
    events=n.s.collection.read_json(root,'events.json',n.s.collection.EVENT_BYTES)
    wires=n.s.collection.read_json(root,'wire.json',n.s.collection.WIRE_BYTES)
    identities=n.s.catalog.identities(model.states[-1]['identities'])
    rows=n.causal(events,wires,identities,model.root);contents=[];n.transfers(rows,contents=contents)
    generations=generation_windows(root,events,model,recovery=recovery);sources=source_windows(root,events)
    records=record_windows(root,events,model,generations,sources,recovery=recovery)
    return authorize_contents(model,events,contents,generations,sources,records)


def authorize_contents(model,events,contents,generations,sources,records):
    """Shared capability checks after the caller derives its original windows."""
    covered=Counter();transfers=Counter();remaining=[]
    for values in sessions(contents):
        first=values[0];kind=record_kind(first['raw']);scope=None
        if kind=='GENERATION' or first['kind']=='CAPSULE':
            scope=authorize_generation(values,generations)
        elif kind=='BASIS':authorize_source(values,generations,sources);scope='frozen-source'
        elif first['offer']['request']['payload']['digest']==sha(pending_ack(model)):
            authorize_pending(values,events,model);scope='pending-joining-checkpoint'
        elif kind in ('PROMISE','SELECTED','ENTRY','ACCEPT','PROOF','CERTIFICATE','CHECKPOINT','CHECKPOINT_ACK') or \
                native_receipt(first['raw']) or first['raw'] in [v['PAYLOAD'] for v in model.phases] or \
                first['offer']['request']['payload']['digest'] in {v['reference'] for v in records}:
            scope=authorize_record(values,generations,records)
        if scope:covered[scope]+=1;transfers[scope]+=len(values)
        else:
            q=first['offer']['request']
            remaining.append(dict(owner=q['recipient']['node'],reader=q['sender']['node'],trace=q['trace'],
                firstEvent=first['offer']['sent'],reference=q['payload']['digest'],firstKind=kind or 'unframed-record',transfers=len(values)))
    need(covered['current-generation']>0 and covered['frozen-source']>0,'joining export target families absent')
    return dict(status='PARTIAL',scope='native-'+model.kind+'-temporal-exports-and-original-record-capabilities',
        generationWindows=len(generations),sourceWindows=len(sources),recordWindows=len(records),boundSessions=dict(covered),
        boundTransfers=dict(transfers),unqualifiedSessions=remaining,unqualifiedSessionCount=len(remaining),
        unqualifiedTransfers=sum(v['transfers'] for v in remaining),allExportFamiliesQualified=False,
        learnerRetentionAuthorizationQualified=False,
        completePhysicalQualified=False,forceAndNetworkQualified=False,processDeathQualified=False,phase3Complete=False)


def validate(root):
    root=Path(root);before=n.s.collection.inventory(root);n.validate(root);result=replay(root)
    need(n.s.collection.inventory(root)==before,'joining export original changed');return result


NEGATIVES={
    'generation-alias':'joining export current generation alias',
    'generation-bytes':'joining export exact current generation',
    'source-alias':'joining export original source alias',
    'source-ballot':'joining export original source view/ballot',
    'source-promise':'joining export exact frozen source',
    'source-after-retirement':'joining export inactive frozen source',
    'receipt-alias':'joining export unavailable original record',
    'receipt-voter':'joining export exact live record',
    'receipt-before-force':'joining export unavailable original record',
    'record-view':'joining export record original context',
    'completed-checkpoint-voter':'joining export exact completed checkpoint',
    'pending-after-retain':'joining export pending ACK lifetime',
}


def mutate(root,name,*,kind='ADD',recovery=None,reader=None):
    events=n.s.collection.read_json(root,'events.json',n.s.collection.EVENT_BYTES)
    wires=n.s.collection.read_json(root,'wire.json',n.s.collection.WIRE_BYTES)
    if reader is None:
        model=n.s.Replay(root,kind=kind)
        for index in range(1,12):model.step(index)
        rows=n.causal(events,wires,n.s.catalog.identities(model.states[-1]['identities']),model.root)
        contents=[];n.transfers(rows,contents=contents);groups=sessions(contents)
    else:model,rows,groups=reader.model,reader.rows,reader.groups
    if name.startswith('generation-'):values=next(v for v in groups if record_kind(v[0]['raw'])=='GENERATION')
    elif name.startswith('source-'):
        candidates=[v for v in groups if record_kind(v[0]['raw'])=='BASIS']
        if name=='source-after-retirement' and reader is not None:
            # A carried selection can leave the first responding peer's source
            # retained. Mutate an actually retired original, regardless of reply
            # arrival order; never invent a retirement for the first response.
            candidates=[v for v in candidates if any(s['node']==v[0]['offer']['request']['recipient']['node'] and
                        sha(s['basis'])==v[0]['offer']['request']['payload']['digest'] and s['end']<len(events)
                        for s in reader.sources)]
        need(candidates,'export mutation requires actually retired source');values=candidates[0]
    elif name.startswith('receipt-'):values=next(v for v in groups if native_receipt(v[0]['raw']))
    elif name=='record-view':values=next(v for v in groups if record_kind(v[0]['raw'])=='ENTRY')
    elif name=='pending-after-retain':values=next(v for v in groups if v[0]['raw']==pending_ack(model))
    else:
        windows=generation_windows(root,events,model,recovery=recovery) if reader is None else reader.windows
        values=next(v for v in groups if record_kind(v[0]['raw'])=='CHECKPOINT_ACK' and
            v[0]['offer']['request']['recipient']['node']!=model.joining and v[0]['offer']['request']['view']!=
            n.s.catalog.authority(model.root,current(windows,v[0]['offer']['request']['recipient']['node'],
                v[0]['offer']['received'],v[-1]['commit']['offered'])['packet']['capsule']['cut']['view']))
    first=values[0]['offer'];q=first['request'];trace=q['trace'];owner=q['recipient']['node']
    def replace(row,side,kind,value):
        old=sha(base64.b64decode(row[side]));raw=f.encode('wire',kind,value);row[side]=base64.b64encode(raw).decode()
        for event in events:
            if event.get(side)==old:
                event[side]=sha(raw)
                if side=='request' and event['event'] in n.SENDS:event['bytes']=row[side]
    if name in ('source-after-retirement','receipt-before-force','pending-after-retain'):
        retirement=None
        if name=='source-after-retirement' and reader is not None:
            source=next(v for v in reader.sources if v['node']==owner and sha(v['basis'])==q['payload']['digest'])
            need(source['end']<len(events),'export mutation requires actually retired source');retirement=events[source['end']]
        exchanges=[v for v in rows if v['request']['trace']==trace and v['request']['recipient']['node']==owner]
        requests={v['requestHash'] for v in exchanges};responses={v['responseHash'] for v in exchanges}
        moving=[v for v in events if v.get('request') in requests or v.get('response') in responses]
        events=[v for v in events if v.get('request') not in requests and v.get('response') not in responses]
        point='SOURCE_RETIREMENT_CREATED' if name=='source-after-retirement' else 'ACCEPT_BEFORE_RETURN' if name=='receipt-before-force' else 'LEARNER_JOINING_RETAIN_CREATED'
        at=next(i for i,v in enumerate(events) if v is retirement) if retirement is not None else next(i for i,v in enumerate(events) if v.get('node')==owner and v['event']==point)
        if name!='receipt-before-force':at+=1
        events[at:at]=moving
    elif name in ('generation-alias','source-alias','receipt-alias'):
        row=next(v for v in wires if sha(base64.b64decode(v['request']))==first['requestHash']);kind,value=n.wire(row['request'])
        value['payload']['digest']='f'*64;replace(row,'request',kind,value)
    elif name in ('source-ballot','record-view'):
        for row in wires:
            kind,value=n.wire(row['request'])
            if value['trace']!=trace or value['recipient']['node']!=owner:continue
            answer,response=n.wire(row['response'])
            if name=='source-ballot':value['ballot']['counter']+=1;response['ballot']['counter']+=1
            else:value['view']=response['view']='f'*64
            replace(row,'request',kind,value);replace(row,'response',answer,response)
    else:
        target=values[1] if name=='source-promise' else values[0];raw=target['raw'];kind=record_kind(raw)
        if kind:
            value=f.decode(raw,'records',kind)
            if name=='generation-bytes':value['node']='node-3' if value['node']!='node-3' else 'node-2'
            elif name=='source-promise':value['basisId']='00000000-0000-0000-0000-000000000001' if value['basisId']!='00000000-0000-0000-0000-000000000001' else '00000000-0000-0000-0000-000000000002'
            else:value['voter']='node-3' if value['voter']!='node-3' else 'node-2'
            changed=f.encode('records',kind,value)
        else:
            value=json.loads(raw);value['voter']='node-3' if value['voter']!='node-3' else 'node-2';changed=f.canonical(value)
        identifier=target['offer']['request']['payload']['id'];data_rows=0
        for row in wires:
            request_kind,request=n.wire(row['request']);answer,response=n.wire(row['response'])
            if request['trace']!=trace or request['payload'].get('id')!=identifier:continue
            if answer=='SOURCE_OFFER':response['payload'].update(digest=sha(changed),bytes=len(changed))
            elif answer=='CHUNK':
                need(request['payload']['offset']==0,'joining export mutation single chunk');data_rows+=1
                request['payload']['digest']=sha(changed);response['payload'].update(digest=sha(changed),bytes=base64.b64encode(changed).decode())
            else:request['payload']['digest']=response['payload']['digest']=sha(changed)
            replace(row,'request',request_kind,request);replace(row,'response',answer,response)
        need(data_rows==1,'joining export mutation complete chunk')
    (root/'events.json').write_bytes(f.canonical(events));(root/'wire.json').write_bytes(f.canonical(wires))


def qualify(root):
    root=Path(root);original=validate(root);before=n.s.collection.inventory(root);results=[]
    protected={k:v for k,v in before['files'].items() if k not in ('events.json','wire.json')}
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-export-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name)
            after=n.s.collection.inventory(changed)
            need({k:v for k,v in after['files'].items() if k not in ('events.json','wire.json')}==protected and after['directories']==before['directories'],
                 'joining export negative changed physical inputs')
            n.network(changed)  # A broken transcript cannot count as an authority rejection.
            try:replay(changed)
            except ValueError as error:need(str(error)==reason,'joining unrelated export negative: '+name+': '+str(error))
            else:raise ValueError('joining export mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',networkPrecondition='PASS',reason=reason))
    need(n.s.collection.inventory(root)==before,'joining export negative changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
