"""Bind every complete SELECTED append to one original selected record.

The caller independently derives bytes/authority and supplies the original
force occurrence plus causal bounds. This is the uninterrupted append contract;
interrupted journal prefixes require their own recovery derivation.
"""
import re
from .membership_model import need

WRITES=('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN')
# These are separate selector-coupled retention transactions, checked by their
# owning continuous ledger readers; they are not journal append observations.
RETENTION={'SELECTED_RETENTION_COMPLETED','SELECTED_LEARNER_RETENTION_COMPLETED'}


def validate(events,bindings):
    owners={v['node'] for v in bindings};pending={};actual={}
    for at,row in enumerate(events):
        point=row.get('event','')
        need(type(point) is str,'selection journal callback shape')
        if not point.startswith('SELECTED_') or point in RETENTION:continue
        need(point in WRITES,'selection journal unsupported callback')
        node=row.get('node');scope=row.get('scope')
        need(type(node) is str and node in owners and (scope is None or type(scope) is str and bool(scope)) and
             row==dict(node=node,event=point,**({'scope':scope} if scope is not None else {})),
             'selection journal callback shape')
        current=pending.setdefault(node,[])
        need(point==WRITES[len(current)] and (not current or scope==current[0][1]),
             'selection journal complete write order')
        current.append((at,scope))
        if len(current)==len(WRITES):
            actual[current[2][0]]=dict(node=node,scope=scope,start=current[0][0],end=at)
            del pending[node]
    need(not pending,'selection journal incomplete transaction')
    forced=[v['forced'] for v in bindings];identities=[(v['node'],v['selection']) for v in bindings]
    need(len(set(forced))==len(forced) and len(set(identities))==len(identities),
         'selection journal reused original selection')
    need(set(actual)==set(forced),'selection journal unbound original selection')
    for bound in bindings:
        row=actual[bound['forced']]
        need(type(bound['lower']) is int and type(bound['upper']) is int and
             -1<=bound['lower']<row['start']<row['end']<bound['upper']<=len(events) and
             row['node']==bound['node'] and row['scope']==bound['scope'] and
             type(bound['selection']) is str and re.fullmatch('[0-9a-f]{64}',bound['selection']),
             'selection journal original authority interval')
    return dict(selections=len(actual),callbacks=len(actual)*len(WRITES))


SPECS={'missing-before-write':('SELECTED_BEFORE_WRITE','missing'),
       'missing-written':('SELECTED_WRITTEN','missing'),
       'duplicate-written':('SELECTED_WRITTEN','duplicate'),
       'write-after-force':('SELECTED_WRITTEN','reorder'),
       'foreign-write-scope':('SELECTED_WRITTEN','scope'),
       'extra-write-field':('SELECTED_WRITTEN','shape'),
       'writes-before-authority':('SELECTED_BEFORE_WRITE','early')}
def reason(mode):
    return 'selection journal '+{'shape':'callback shape','early':'original authority interval'}.get(mode,'complete write order')
NEGATIVES={'selection-'+role+'-'+name:reason(mode) for role in ('proposer','remote') for name,(_,mode) in SPECS.items()}
NEGATIVES.update({'selection-unbound-write':'selection journal complete write order',
                  'selection-unknown-callback':'selection journal unsupported callback'})
RECOVERY_NEGATIVES={'selection-recovery-'+name:reason(mode) for name,(_,mode) in SPECS.items()}


def mutate(events,name):
    need(name in {**NEGATIVES,**RECOVERY_NEGATIVES},'selection journal unknown mutation')
    if name in ('selection-unbound-write','selection-unknown-callback'):
        events.append(dict(node='node-1',event='SELECTED_WRITTEN' if name=='selection-unbound-write' else 'SELECTED_UNKNOWN'));return
    _,role,suffix=name.split('-',2);point,mode=SPECS[suffix]
    if role=='recovery':
        forced=max(i for i,v in enumerate(events) if v['event']=='SELECTED_FORCED' and v.get('scope')=='continuation-owner')
        node=events[forced]['node']
    else:
        node='node-1' if role=='proposer' else 'node-2'
        forced=next(i for i,v in enumerate(events) if v.get('node')==node and v['event']=='SELECTED_FORCED')
    at=max(i for i,v in enumerate(events) if i<forced and v.get('node')==node and v['event']==point)
    if mode=='missing':events.pop(at)
    elif mode=='duplicate':events.insert(at,dict(events[at]))
    elif mode=='reorder':events[at],events[forced]=events[forced],events[at]
    elif mode=='scope':events[at]['scope']='foreign-owner'
    elif mode=='shape':events[at]['claimedWrite']=True
    else:
        # Joining endpoints retain raw transport callbacks; older voters and
        # normalized process traces retain their NETWORK_* projection. In raw
        # callbacks kind is the request kind, not the received response kind.
        boundary=max(i for i,v in enumerate(events) if i<at and v.get('node')==node and
            (v['event'] in ('NETWORK_REQUEST','AFTER_REQUEST_READ') and v.get('kind')=='SELECTED' if role=='remote' else
             v['event']=='NETWORK_RECEIVED' and v.get('kind')=='PROMISE' or
             v['event']=='AFTER_RESPONSE_READ' and v.get('responseKind')=='PROMISE'))
        written=next(i for i,v in enumerate(events) if at<i<forced and v.get('node')==node and v['event']=='SELECTED_WRITTEN')
        rows=[events[at],events[written]];events.pop(written);events.pop(at);events[boundary:boundary]=rows
