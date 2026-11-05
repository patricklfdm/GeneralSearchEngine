"""Original-first receiving journal mutations; original transfer/file bytes stay fixed."""
import argparse
import copy
import json
from pathlib import Path
import sys
from uuid import UUID

from . import receive_resource_evidence as r
from . import native_resource_evidence as native
from .floor_resource_negatives import recount

NEGATIVES={
    'source-short':'receive resources original initial extent',
    'source-long':'receive resources original initial extent',
    'image-short':'receive resources original initial extent',
    'image-long':'receive resources original initial extent',
    'learner-initial-short':'receive resources original initial extent',
    'learner-metadata-short':'receive resources original learner metadata extent',
    'learner-metadata-long':'receive resources original learner metadata extent',
    'foreign-transfer':'receive resources unbound staging lease',
    'reservation-before-offer':'receive resources packet reservation before first chunk',
    'reservation-after-first-chunk':'receive resources packet reservation before first chunk',
    'released-before-commit':'receive resources staging not live at original boundary',
    'image-after-packet-commit':'receive resources image reserved before packet commit',
    'metadata-before-original':'receive resources original learner metadata extent',
    'metadata-after-reservation':'receive resources original learner metadata extent',
    'metadata-released-before-force':'receive resources staging not live at original boundary',
    'floor-released-before-force':'receive resources staging not live at original boundary',
    'floor-held-after-handoff':'receive resources forced floor handoff interval',
    'staging-lifetime-gap':'receive resources reused staging lease',
    'unbound-temporary-staging':'receive resources unbound staging lease',
}


def mutate(data,name):
    plan,events,traces,boundaries=data
    r.need(name in NEGATIVES,'receive resources declared negative')
    expected={(v['node'],v['id']):v for v in plan['transfers']}
    leases,_=r.lifetimes(traces,expected,plan['bases'])
    unit='APPLICATION' if name.startswith('image-') else 'LEARNER' if name.startswith(('learner-','metadata-')) else 'SOURCE'
    row=next(v for v in plan['transfers'] if v['unit']==unit and (not name.startswith('floor-') or v['floor']))
    node=row['node'];lease=leases[node,row['id']];changes=traces[node]['changes']
    def at(point,sequence):boundaries[point]['sequence']=sequence
    if name.endswith(('short','long')):
        # Mutate all equal extents in this budget coherently, including any
        # atomic successor categories. Equal sizes are not custody evidence.
        size=row['metadata']['size'] if name.startswith('learner-metadata-') else row['size']
        for change in changes:
            for charge in change['removed']+change['added']:
                if charge['bytes']==size and (name.startswith('learner-metadata-') or charge['unit']==unit):
                    charge['bytes']+=-1 if name.endswith('short') else 1
    elif name=='foreign-transfer':
        replacement=str(UUID(int=1))
        r.need((node,replacement) not in expected and (node,replacement) not in plan['bases'],'receive negative UUID collision')
        for change in changes:
            for charge in change['removed']+change['added']:
                if charge['owner']==row['id']:charge['owner']=replacement
    elif name=='reservation-before-offer':at(row['offerDelivered'],lease['start'])
    elif name=='reservation-after-first-chunk':at(row['firstChunkSent'],lease['start']-1)
    elif name=='released-before-commit':at(row['commitDelivered'],lease['end'])
    elif name=='image-after-packet-commit':at(row['imageReservation'][1],lease['start']-1)
    elif name=='metadata-before-original':at(row['metadata']['delivered'],lease['growth'][0][0])
    elif name=='metadata-after-reservation':at(row['metadata']['reserved'],lease['growth'][0][0]-1)
    elif name=='metadata-released-before-force':at(row['metadata']['forced'],lease['end'])
    elif name=='floor-released-before-force':at(row['floor']['forced'],lease['end'])
    elif name=='floor-held-after-handoff':at(row['floor']['handed'],lease['end']-1)
    elif name=='staging-lifetime-gap':
        value=copy.deepcopy(changes[lease['start']]['added'][0]);seq=lease['start']
        changes[seq+1:seq+1]=[dict(event='RELEASE',removed=[value],added=[]),dict(event='RESERVE',removed=[],added=[value])]
        for point in boundaries:
            if point['node']==node and point['sequence']>seq:point['sequence']+=2
    elif name=='unbound-temporary-staging':
        identifier=str(UUID(int=2));r.need((node,identifier) not in expected|dict.fromkeys(plan['bases']),'receive negative UUID collision')
        value=dict(unit='SOURCE',owner=identifier,bytes=1,claimSource='')
        changes.extend([dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])])
    recount(traces,boundaries)


def replay(data,progress=None):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=(*data[:2],*copy.deepcopy(data[2:]));mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:r.need(str(error)==reason,'receive resources unrelated negative: '+name+': '+str(error))
        else:raise ValueError('receive resources mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
        if progress:progress(dict(case=name,completed=len(results),total=len(NEGATIVES)))
    return results


def qualify(root,progress=None):
    root=Path(root);before=native.collection.inventory(root)
    original=native.validate(root,'5-REPLACE-required-four',progress)
    if progress:progress(dict(stage='original',status='PASS'))
    _,traces,boundaries,events=native.load(root)
    reader=r.maintenance.Replay(root);reader.run()
    results=replay((r.derive(reader),events,traces,boundaries),progress)
    r.need(native.collection.inventory(root)==before,'receive resources qualification changed original')
    return dict(status='PASS',original=original,negatives=results,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    progress=lambda row:print(json.dumps(row,sort_keys=True),file=sys.stderr,flush=True)
    print(json.dumps(qualify(a.root,progress),sort_keys=True))
