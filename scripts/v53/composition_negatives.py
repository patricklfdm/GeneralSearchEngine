"""Original-first, reason-specific corruptions of retained composed histories."""
from copy import deepcopy
from . import composition_oracle as oracle
from .transition_model import encoded
from .membership_model import need


CASES=(
    ('accept-without-force','transition','late/foreign ACK'),
    ('proof-without-force','transition','late/foreign ACK'),
    ('remote-before-own-basis','transition','remote prepare before own basis'),
    ('catalog-rewrite','transition','catalog not derived from original bytes'),
    ('hidden-membership','transition','hidden membership boundary'),
    ('missing-descriptor','transition','missing original sealed descriptor'),
    ('foreign-learner','transition','stale/foreign learner materialization'),
    ('missing-proposer','transition','missing proposer/ordered sources'),
    ('retire-before-floor','transition','retirement before forced floor'),
    ('floor-before-selector','transition','wrong durable floor'),
    ('delete-before-inventory','transition','delete beyond forced retirement'),
    ('ack-before-install','transition','ACK before original installation force'),
    ('adoption-floor-omitted','transition','prefix before parent/adoption/certificate'),
    ('event-clock-drift','transition','event clock drift'),
    ('duplicate-resamples-basis','heterogeneous','nonoriginal duplicate basis'),
    ('carried-tail-rewrite','accepted','wrong highest original tail'),
    ('recovered-tail-ready','accepted','recovered tail advertised READY'),
)


def mutate(record,name):
    value=deepcopy(record);events=value['events']
    def first(kind,predicate=lambda e:True):
        return next(e for e in events if e['event']==kind and predicate(e))
    def remove(kind,predicate=lambda e:True):events.remove(first(kind,predicate))
    if name in ('accept-without-force','proof-without-force'):
        phase='ACCEPT' if name.startswith('accept') else 'PROOF';remove('vote-force',lambda e:e['body']['kind']==phase)
    elif name=='remote-before-own-basis':remove('basis-force')
    elif name=='catalog-rewrite':first('prefix-force')['state']['nextOperation']+=1
    elif name in ('hidden-membership','missing-descriptor'):
        base=first('generation-stage',lambda e:any(i['kind']=='membership' for i in e['base']['items']))['base']
        item=next(i for i in base['items'] if i['kind']=='membership')
        if name=='hidden-membership':item['kind']='range'
        else:item.pop('descriptor')
    elif name=='foreign-learner':first('learner-force')['receipt']['identity']['storage']='foreign-disk'
    elif name=='missing-proposer':
        selected=first('selection-stage')['selected'];selected['owners'].remove(selected['ballot']['proposer'])
    elif name=='retire-before-floor':remove('floor-force')
    elif name=='floor-before-selector':remove('selector-force')
    elif name=='delete-before-inventory':remove('retirement-force')
    elif name=='ack-before-install':remove('install-force')
    elif name=='adoption-floor-omitted':remove('adoption-force')
    elif name=='event-clock-drift':events[0]['time']+=1
    elif name=='duplicate-resamples-basis':first('basis-reply')['basis']=first('basis-force')['basis']
    elif name=='carried-tail-rewrite':
        selected=first('selection-stage',lambda e:e['selected']['carried'] is not None)['selected']
        entry=oracle.read(selected['carried']);entry['command']['value']='rewritten';selected['carried']=encoded(entry)
    elif name=='recovered-tail-ready':first('published',lambda e:not e['ready'] and oracle.read(e['certificate']['entry'])['command']['kind']=='DATA')['ready']=True
    else:raise ValueError('unknown composition negative '+name)
    return value


def run(originals):
    # A corrupt original or missing scenario aborts before any rejection can count.
    for family in sorted({family for _,family,_ in CASES}):oracle.check(originals[family])
    results=[]
    for name,family,expected in CASES:
        changed=mutate(originals[family],name)
        try:oracle.check(changed)
        except ValueError as error:
            need(expected in str(error),f'{name}: unrelated rejection: {error}')
            results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('composition mutation accepted: '+name)
    return results
