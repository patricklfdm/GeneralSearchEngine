"""Fresh application-end and publication prefixes of an original carried slot.

The caller must independently validate the complete history and snapshots first.
This models bytes at callbacks, not crash durability or partial-end recovery.
"""
from .native_campaign_files import physical
from .generation_install_evidence import transaction as install
from .published_generation_evidence import OPEN
from .pending_accept_evidence import EMPTY
from . import format_fixture as f
from .membership_model import need

PUBLICATION=('PUBLICATION_VALIDATED','PUBLICATION_SELECTOR_FORCED','PUBLICATION_COVERAGE_VALIDATED',
             'PUBLICATION_RETIRED','PUBLICATION_BEFORE_RETURN')
KINDS={'application':('APPLY_',),'publication':PUBLICATION+('INSTALL_','CURRENT_','COVERED_')}
LEDGERS=('peer-retention.gspr','future-retention.gsft')


def observed(rows):
    """INSTALL/CURRENT are publication only inside that owner's publication."""
    active={};result=[]
    for at,row in enumerate(rows):
        node,point=row.get('node'),row['event']
        if point in ('APPLY_VALIDATED','PUBLICATION_VALIDATED'):
            need(node not in active,'completion overlapping transaction')
            active[node]='application' if point=='APPLY_VALIDATED' else 'publication'
        kind=active.get(node)
        if point.startswith('APPLY_'):
            need(kind=='application','completion application outside transaction')
        elif point in PUBLICATION or point.startswith('COVERED_'):
            need(kind=='publication','completion publication outside transaction')
        elif not (kind=='publication' and point.startswith(('INSTALL_','CURRENT_'))):continue
        result.append((at,kind,row))
        if point in ('APPLY_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'):del active[node]
    need(not active,'completion incomplete transaction')
    return result


def application(initial,applied):
    """Fresh full end, including optional parent/ancestor and nonvoting forms."""
    need(not any(k=='applied-end' or k.startswith('applied-end/') for k in initial),
         'completion fresh application end')
    end={k.removeprefix('applied-end/'):v for k,v in applied.items() if k.startswith('applied-end/')}
    metadata=['selector.gsr','certificate.gsr','catalog.gsr','statement.gsr']
    order=[('plan.json','APPLY_PLAN')]+[(n,'APPLY_METADATA') for n in metadata]
    if 'parent-statement.gsr' in end:order.append(('parent-statement.gsr','APPLY_PARENT_STATEMENT'))
    ancestors=[]
    for i in range(5):
        name=f'ancestor-{i}-statement.gsr'
        if name in end:
            need(i==len(ancestors),'completion ancestor gap');ancestors.append(i)
            order.append((name,f'APPLY_ANCESTOR_{i}_STATEMENT'))
    order.append(('application.image','APPLY_IMAGE'))
    acks=[]
    if 'ack.gsr' in end:
        acks=[('ack.gsr','APPLY_ACK')]
        if 'parent-statement.gsr' in end:acks.append(('parent-ack.gsr','APPLY_PARENT_ACK'))
        acks += [(f'ancestor-{i}-ack.gsr',f'APPLY_ANCESTOR_{i}_ACK') for i in ancestors]
    need(set(end)=={n for n,_ in order+acks} and all(type(v) is bytes and len(v)>0 for v in end.values()),
         'completion exact end inventory')
    need(dict(initial,**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})==applied,
         'completion application outside end')
    state=dict(initial);steps=[]
    def event(point):steps.append(('application',point,physical(state)))
    def write(name,label):
        key='applied-end/'+name;raw=end[name];state[key]=b'';event(label+'_CREATED')
        state[key]=raw[:len(raw)//2];event(label+'_PREFIX_WRITTEN')
        state[key]=raw;event(label+'_WRITTEN');event(label+'_FORCED')
    event('APPLY_VALIDATED');state['applied-end']=None;event('APPLY_DIRECTORY_CREATED')
    for name,label in order:write(name,label)
    event('APPLY_END_FORCED')
    for name,label in acks:write(name,label)
    event('APPLY_ACK_DIRECTORY_FORCED' if acks else 'APPLY_NONVOTING_DIRECTORY_FORCED')
    event('APPLY_BEFORE_RETURN');return steps


def publication(initial,published):
    """Install, reload, end deletion and covered-vote replacement in order.

    Only the two independently replayed retention ledgers may change between
    PUBLICATION_RETIRED and BEFORE_RETURN. Their intervening writes are a
    separate ledger-prefix obligation, not observations supplied by this model.
    """
    selector=published['selector.gsr'];generation=f.decode(selector,'records','SELECTOR')['generation']
    prefix='generations/'+generation+'/';directory=prefix[:-1]
    members={k.removeprefix(prefix):v for k,v in published.items() if k.startswith(prefix)}
    need(directory not in initial and members and 'selector.pending.gsr' not in initial and
         'pending.accept.next' not in initial and initial.get('applied-end','missing') is None and
         initial.get('pending.accept') not in (None,EMPTY),'completion fresh publication')
    state=dict(initial);steps=[]
    def event(point):steps.append(('publication',point,physical(state)))
    event('PUBLICATION_VALIDATED');events,writes=install(members)
    for at,point in enumerate(events):
        if point=='INSTALL_DIRECTORY_CREATED':state[directory]=None
        for name,index in writes.items():
            if index==at:state[prefix+name]=members[name]
        if point=='INSTALL_SELECTOR_WRITTEN':state['selector.pending.gsr']=selector
        if point=='INSTALL_SELECTOR_RENAMED':state['selector.gsr']=state.pop('selector.pending.gsr')
        event(point)
    for point in OPEN:event(point)
    event('PUBLICATION_SELECTOR_FORCED');event('PUBLICATION_COVERAGE_VALIDATED');event('COVERED_END_VALIDATED')
    names=sorted(k for k in state if k.startswith('applied-end/') and k!='applied-end/plan.json')
    need('applied-end/plan.json' in state,'completion end plan');names.append('applied-end/plan.json')
    for name in names:
        event('COVERED_END_BEFORE_DELETE');del state[name];event('COVERED_END_FILE_DELETED')
    event('COVERED_END_BEFORE_DIRECTORY_DELETE');del state['applied-end'];event('COVERED_END_DIRECTORY_DELETED')
    state['pending.accept.next']=b'';event('COVERED_VOTE_CANDIDATE_CREATED')
    state['pending.accept.next']=EMPTY[:len(EMPTY)//2];event('COVERED_VOTE_PREFIX_WRITTEN')
    state['pending.accept.next']=EMPTY;event('COVERED_VOTE_CANDIDATE_WRITTEN')
    event('COVERED_VOTE_CANDIDATE_FORCED');event('COVERED_VOTE_CANDIDATE_PARENT_FORCED')
    state['pending.accept']=state.pop('pending.accept.next');event('COVERED_VOTE_RENAMED')
    event('COVERED_VOTE_PARENT_FORCED');event('PUBLICATION_RETIRED')
    for name in LEDGERS:
        if name in published:state[name]=published[name]
    need(state==published,'completion publication outside transaction')
    event('PUBLICATION_BEFORE_RETURN');return steps
