"""Ownership mutations after unchanged physical/native original admission."""
import argparse
import copy
import json
from pathlib import Path
from . import native_resource_evidence as native
from . import control_close_evidence as close
from . import session_export_evidence as reader

NEGATIVES={
    'missing-attachment':'control close complete export attachments',
    'duplicate-attachment':'control close original export attachment',
    'empty-owned-group':'control close original export attachment',
    'duplicate-handle':'control close exact ordered row',
    'unknown-handle':'control close original export allocation',
    'session-as-export':'control close original export allocation',
    'boolean-resource-point':'control close exact ordered row',
    'wrong-attachment-call':'control close original export attachment',
    'missing-close-return':'control close complete cleanup intervals',
    'truncated':'control close complete bounded recorder',
    'failed':'control close complete bounded recorder',
    'unclaimed-export':'session export unclaimed allocation',
}


def renumber(value):
    calls={}
    for seq,row in enumerate(value['rows']):
        row['sequence']=seq
        if row['event']=='ATTACHED':row['call']=seq
        elif row['event'] in ('BEGIN','EXPORT_ROLLBACK_BEGIN') or row['event'] in close.DIRECT_EVENTS and close.DIRECT_EVENTS[row['event']][1]=='ACQUIRED':
            calls[row['owner']]=seq;row['call']=seq
        else:row['call']=calls[row['owner']]
    value['observations']=len(value['rows'])


def mutate(traces,closes,name):
    node=next(n for n,value in closes.items() if any(row['event']=='ATTACHED' for row in value['rows']))
    value=closes[node];rows=value['rows'];row=next(v for v in rows if v['event']=='ATTACHED')
    if name=='missing-attachment':rows.remove(row);renumber(value)
    elif name=='duplicate-attachment':rows.insert(row['sequence']+1,copy.deepcopy(row));renumber(value)
    elif name=='empty-owned-group':row['children']=[]
    elif name=='duplicate-handle':row['children']*=2
    elif name=='unknown-handle':row['children']=['absent-export']
    elif name=='session-as-export':row['children']=[row['owner']]
    elif name=='boolean-resource-point':row['resourceSequence']=True
    elif name=='wrong-attachment-call':row['call']=-1
    elif name=='missing-close-return':
        rows.remove(next(v for v in rows if v['event']=='RETURNED' and v['owner']==row['owner']));renumber(value)
    elif name in ('truncated','failed'):value[name]=True
    elif name=='unclaimed-export':
        # Add a distinct valid reservation lifetime, then recompute counters
        # without dropping original storage/claim units or observation bounds.
        from . import resource_transitions as resources
        export=row['children'][0];allocations=close.allocations(traces[node]);salt=99
        while True:
            new=export[:-36]+f'00000000-0000-0000-0000-{salt:012x}'
            if new not in allocations:break
            salt+=1
        life=allocations[export];first,last=life['start'],life['end']
        changes=traces[node]['changes'];start=copy.deepcopy(changes[first]);end=copy.deepcopy(changes[last])
        for change in (start,end):
            for charge in change['added']+change['removed']:charge['owner']=new
        changes.insert(last+1,end);changes.insert(first+1,start)
        limits=tuple(traces[node][k] for k in ('metadataLimit','stagingLimit','queueLimit'));state={}
        for seq,change in enumerate(changes):
            change['sequence']=seq
            for charge in change['removed']:del state[resources.key(charge)]
            for charge in change['added']:state[resources.key(charge)]=charge
            change['usage']=resources.usage(state,limits)
        traces[node]['transitions']=len(changes);traces[node]['current']=copy.deepcopy(changes[-1]['usage'])
        for marker in rows:
            old=marker['resourceSequence'];marker['resourceSequence']+=int(old>=first)+int(old>=last)
    else:raise AssertionError(name)


def replay(traces,closes,*,inspect=False):
    validate=reader.inspect if inspect else reader.replay
    original=validate(traces,closes) # An invalid original must never count as rejection qualification.
    results=[]
    for name,expected in NEGATIVES.items():
        if inspect and name=='unclaimed-export':expected='session export unattached inventory changed'
        altered=copy.deepcopy((traces,closes));mutate(*altered,name)
        try:
            result=validate(*altered)
            reader.need(result['unattachedExports']==original['unattachedExports'],'session export unattached inventory changed')
        except ValueError as error:
            reader.need(str(error)==expected,f'session export negative {name}: {error}')
            results.append(dict(case=name,status='REJECT',reason=str(error)))
        else:raise ValueError('session export negative accepted: '+name)
    return results


def validate(root):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,control_closes=True,export_ownership=True)
    index,traces,_,_=native.load(root);closes=close.load(root,index)
    results=replay(traces,closes,inspect=True)
    reader.need(native.collection.inventory(root)==before,'session export original changed')
    return dict(status=original['status'],negativeQualification='PASS',precondition=original,negatives=results,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');args=p.parse_args()
    print(json.dumps(validate(args.root),sort_keys=True))
