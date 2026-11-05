"""Original-first store close failures, including original cross-process lock observations."""
import argparse
import copy
import json
from pathlib import Path
from . import pending_drain_evidence as r
from . import pending_drain_negatives as pending

NEGATIVES={**pending.NEGATIVES,'early-return':'store drain resources released before return',
           'early-lock-release':'store drain lock lifetime',
           'lock-not-released':'store drain lock lifetime',
           'foreign-lock':'store drain original lock identity',
           'missing-lock':'store drain exact original locks',
           'missing-probe':'store drain complete lock observations',
           'boolean-lock-key':'store drain exact original locks'}


def mutate(data,name):
    if name in pending.NEGATIVES:pending.mutate(data,name);return
    locks=data[1]['locks']
    if name=='early-lock-release':locks['afterFailure'][0]['held']=False
    elif name=='lock-not-released':locks['afterSuccess'][1]['held']=True
    elif name=='foreign-lock':locks['afterFailure'][0]['key']+='-copy'
    elif name=='missing-lock':locks['before'].pop()
    elif name=='missing-probe':del locks['afterFailure']
    elif name=='boolean-lock-key':locks['before'][0]['key']=True
    else:raise ValueError('unknown store drain mutation: '+name)


def replay(data):
    r.replay(*data,store=True);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed,store=True)
        except ValueError as error:r.need(str(error)==reason,'store drain unrelated negative: '+name+': '+str(error))
        else:raise ValueError('store drain negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return results


def qualify(root):
    root=Path(root);before=r.t.collection.inventory(root);data=r.load(root)
    result=dict(original=r.replay(*data,store=True),negatives=replay(data))
    r.need(before==r.t.collection.inventory(root),'store drain changed original')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root),sort_keys=True))
