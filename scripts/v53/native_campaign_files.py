"""Exact campaign file prefixes from independently validated original snapshots.

No captured prefix supplies expected bytes. The enclosing reader must first run
its complete original history/snapshot and continuous retention replay.
"""
import hashlib
from . import format_fixture as f
from . import grant_evidence as g
from . import generation_install_evidence as install
from .membership_model import need

GRANTS=('PROMISE_','CAPTURE_INTENT_','SOURCE_BEFORE_','SOURCE_CREATED','SOURCE_PACKET_',
        'SOURCE_IMAGE_','SOURCE_FILES_','SOURCE_DIRECTORY_','BASIS_','GRANT_')
SELECTED=('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN')
KINDS={'allocator':('ALLOCATOR_',),'grant':GRANTS,'selected':SELECTED,'install':('INSTALL_',)}
LEDGER='peer-retention.gspr'


def physical(files):
    return {key:dict(directory=True) if raw is None else dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for key,raw in files.items()}


def observed(rows):
    """Bind installation only to the same owner's completed durable selection."""
    waiting=set();result=[]
    for at,row in enumerate(rows):
        node,point=row.get('node'),row['event']
        kind=next((kind for kind,prefixes in KINDS.items() if point.startswith(prefixes)),None)
        if kind is None:continue
        if kind=='install' and node not in waiting:continue
        if point=='SELECTED_BEFORE_WRITE':need(node not in waiting,'campaign prefix selection before prior install')
        if point=='SELECTED_BEFORE_RETURN':
            need(node not in waiting,'campaign prefix duplicate selection return');waiting.add(node)
        if point=='INSTALL_BEFORE_RETURN':waiting.remove(node)
        result.append((at,kind,row))
    need(not waiting,'campaign prefix selected installation missing')
    return result


def transaction(initial,final,node,selected):
    """Create, prefix-write, force, rename and release states, in original order."""
    state=dict(initial);steps=[]
    def event(kind,point):steps.append((kind,point,physical(state)))
    def at(point):event('grant',point)
    root=initial['root.gsr'][16:48].hex()
    prior=g.journal(initial['grants.gsr'],root,node);rows=g.journal(final['grants.gsr'],root,node)
    need(rows[:len(prior)]==prior and [v[0] for v in rows[len(prior):]]==['PROMISE','BASIS']+(['SELECTED'] if selected else []),
         'campaign prefix original grant extension')
    promise,basis=rows[len(prior):len(prior)+2];identifier=basis[2]['basisId'];source='sources/'+identifier
    need(source not in state and 'source.capture.gsr' not in state,'campaign prefix original empty capture')
    if node=='node-1':
        old=f.decode(state['allocator.gsr'],'records','ALLOCATOR');new=f.decode(final['allocator.gsr'],'records','ALLOCATOR')
        need(new==dict(old,counter=promise[2]['ballot']['counter']) and new['counter']>old['counter'],'campaign prefix next allocator')
        event('allocator','ALLOCATOR_BEFORE_WRITE');state['allocator.pending.gsr']=b'';event('allocator','ALLOCATOR_CREATED')
        state['allocator.pending.gsr']=final['allocator.gsr'];event('allocator','ALLOCATOR_WRITTEN');event('allocator','ALLOCATOR_FORCED')
        state['allocator.gsr']=state.pop('allocator.pending.gsr');event('allocator','ALLOCATOR_RENAMED')
        event('allocator','ALLOCATOR_DIRECTORY_FORCED');event('allocator','ALLOCATOR_BEFORE_RETURN')
    else:need(state['allocator.gsr']==final['allocator.gsr'],'campaign prefix remote allocator changed')
    at('PROMISE_BEFORE_WRITE');state['grants.gsr']+=promise[1];at('PROMISE_WRITTEN');at('PROMISE_FORCED')
    intent=state['selector.gsr']+promise[1]+basis[1]
    state['source.capture.gsr']=b'';at('CAPTURE_INTENT_CREATED')
    state['source.capture.gsr']=intent[:len(intent)//2];at('CAPTURE_INTENT_PREFIX_WRITTEN')
    state['source.capture.gsr']=intent
    for point in ('CAPTURE_INTENT_WRITTEN','CAPTURE_INTENT_FORCED','CAPTURE_INTENT_PARENT_FORCED'):at(point)
    at('SOURCE_BEFORE_CREATE');state[source]=None;at('SOURCE_CREATED')
    members={key[len(source)+1:]:value for key,value in final.items() if key.startswith(source+'/')}
    need('source.gscp' in members and all(key=='source.gscp' or key.endswith('.image') for key in members),'campaign prefix source members')
    for name in ['source.gscp',*sorted(set(members)-{'source.gscp'})]:
        point='SOURCE_PACKET' if name=='source.gscp' else 'SOURCE_IMAGE';key=source+'/'+name;raw=members[name]
        state[key]=b'';at(point+'_CREATED');state[key]=raw[:len(raw)//2];at(point+'_PREFIX_WRITTEN')
        state[key]=raw;at(point+'_WRITTEN');at(point+'_FORCED')
    at('SOURCE_FILES_DIRECTORY_FORCED');at('SOURCE_DIRECTORY_FORCED');at('BASIS_BEFORE_WRITE')
    journal=state['grants.gsr'];state['grants.gsr']=journal+basis[1][:len(basis[1])//2];at('BASIS_PREFIX_WRITTEN')
    state['grants.gsr']=journal+basis[1];at('BASIS_WRITTEN');at('BASIS_FORCED')
    del state['source.capture.gsr'];at('CAPTURE_INTENT_DELETED');at('CAPTURE_INTENT_CLEARED');at('GRANT_BEFORE_RETURN')
    if selected:
        event('selected','SELECTED_BEFORE_WRITE');state['grants.gsr']+=rows[-1][1]
        for point in SELECTED[1:]:event('selected',point)
        selector=f.decode(final['selector.gsr'],'records','SELECTOR');prefix='generations/'+selector['generation']
        need(prefix not in state and 'selector.pending.gsr' not in state,'campaign prefix inactive generation not empty')
        members={key[len(prefix)+1:]:value for key,value in final.items() if key.startswith(prefix+'/')}
        need('generation.gsr' in members,'campaign prefix installed manifest missing')
        points,writes=install.transaction(members)
        for at_,point in enumerate(points):
            if point=='INSTALL_DIRECTORY_CREATED':state[prefix]=None
            for name,index in writes.items():
                if index==at_:state[prefix+'/'+name]=members[name]
            if point=='INSTALL_SELECTOR_WRITTEN':state['selector.pending.gsr']=final['selector.gsr']
            if point=='INSTALL_SELECTOR_RENAMED':state['selector.gsr']=state.pop('selector.pending.gsr')
            event('install',point)
        # Selected-retention completion occurs after INSTALL_PARENT_FORCED.
        # Its original individual writes remain mandatory in the ledger reader.
        state[LEDGER]=final[LEDGER]
        event('install','INSTALL_BEFORE_RETURN')
    need(state==final,'campaign prefix complete installed projection')
    return steps
