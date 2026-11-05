"""Mutate coherent accounting observations while preserving original TCP bytes."""
import argparse
import copy
import json
from pathlib import Path

from . import transport_resource_evidence as r

NEGATIVES={
    'request-size':'transport resources original send buffer',
    'response-size':'transport resources original send buffer',
    'request-read-size':'transport resources original frame extent',
    'response-read-size':'transport resources original frame extent',
    'header-size':'transport resources original receive header',
    'missing-frame':'transport resources missing original frame lease',
    'crossed-retry':'transport resources reused frame lease',
    'caller-release-order':'transport resources caller nested release order',
    'receiver-release-order':'transport resources receiver nested release order',
    'live-failed-caller':'transport resources frame not closed at terminal',
    'dead-failed-receiver':'transport resources frame not live at boundary',
    'unobserved-allocation':'transport resources unobserved frame lifetimes',
    'legacy-lease':'transport resources unbound legacy frame lease',
    'missing-checkpoint':'transport resources complete checkpoints',
    'foreign-checkpoint':'transport resources exact checkpoint',
    'receive-before-send':'transport resources receive before request send',
}


def rebuild(traces,boundaries):
    """Repair only observer arithmetic, so wire/lifetime checks must do the rejection."""
    for node,trace in traces.items():
        state={};limits=tuple(trace[k] for k in ('metadataLimit','stagingLimit','queueLimit'))
        for index,row in enumerate(trace['changes']):
            row['sequence']=index
            for value in row['removed']:state.pop(r.accounting.transitions.key(value))
            for value in row['added']:state[r.accounting.transitions.key(value)]=value
            row['usage']=r.accounting.transitions.usage(state,limits)
        trace['transitions']=len(trace['changes']);trace['current']=copy.deepcopy(trace['changes'][-1]['usage'])
    for row in boundaries:row['usage']=copy.deepcopy(traces[row['node']]['changes'][row['sequence']]['usage'])


def mutate(data,name):
    events,wires,traces,boundaries,identities,root=data
    network=r.connections.replay(events,wires,identities,root);leases,_=r.lifetimes(traces)
    failure=network['failed'][0];success=next(v for v in network['rows'] if v['delivered'] is not None)
    client=failure['sender'];server=failure['recipient'];client_id=failure['clientConnection'];server_id=failure['serverConnection']
    def full_name(role,identifier):return r.PREFIX+role+'-'+identifier
    def rewrite(node,key,update):
        for row in traces[node]['changes']:
            for value in row['removed']+row['added']:
                if value['owner']==key:update(value)
    if name in ('request-size','response-size','request-read-size','response-read-size','header-size'):
        role={'request-size':'request-send','response-size':'response-send','request-read-size':'request-read',
              'response-read-size':'response-read','header-size':'request-read'}[name]
        life=next(v for v in leases.values() if v['role']==role and (role!='response-read' or v['growth']))
        key=full_name(role,life['connection'])
        def change(value):
            selected=(value['bytes']==r.HEADER) if name=='header-size' else (role.endswith('-send') or value['bytes']!=r.HEADER)
            if selected:value['bytes']+=1
        rewrite(life['node'],key,change);rebuild(traces,boundaries)
    elif name in ('missing-frame','legacy-lease','crossed-retry'):
        identifier=success['clientConnection'] if name=='crossed-retry' else client_id
        key=full_name('request-send',identifier)
        replacement=(full_name('request-send',client_id) if name=='crossed-retry' else
                     client_id if name=='legacy-lease' else full_name('request-send','00000000-0000-0000-0000-ffffffffffff'))
        rewrite(client,key,lambda value:value.update(owner=replacement));rebuild(traces,boundaries)
    elif name in ('caller-release-order','receiver-release-order'):
        outbound=name=='caller-release-order';node=client if outbound else server;identifier=success['clientConnection' if outbound else 'serverConnection']
        roles=('request-send','response-read') if outbound else ('request-read','response-send')
        a,b=[leases[node,role,identifier]['end'] for role in roles];rows=traces[node]['changes'];rows[a],rows[b]=rows[b],rows[a];rebuild(traces,boundaries)
    elif name in ('live-failed-caller','dead-failed-receiver','receive-before-send'):
        if name=='live-failed-caller':at=failure['clientFailed'];sequence=leases[client,'request-send',client_id]['end']-1
        elif name=='dead-failed-receiver':at=failure['serverFailed'];sequence=leases[server,'request-read',server_id]['end']
        else:at=failure['sent'];sequence=leases[client,'response-read',client_id]['start']
        boundaries[at]['sequence']=sequence;boundaries[at]['usage']=copy.deepcopy(traces[boundaries[at]['node']]['changes'][sequence]['usage'])
    elif name=='unobserved-allocation':
        value=dict(unit='CONTROL',owner=full_name('request-send','00000000-0000-0000-0000-ffffffffffff'),bytes=100,claimSource='')
        traces[client]['changes'] += [dict(event='RESERVE',removed=[],added=[value]),dict(event='RELEASE',removed=[value],added=[])]
        rebuild(traces,boundaries)
    elif name=='missing-checkpoint':boundaries.pop()
    elif name=='foreign-checkpoint':boundaries[failure['sent']]['node']=server
    else:raise ValueError('unknown transport resource negative')


def replay(data):
    r.replay(*data);results=[]
    for name,reason in NEGATIVES.items():
        changed=copy.deepcopy(data);mutate(changed,name)
        try:r.replay(*changed)
        except ValueError as error:
            r.need(str(error)==reason,'transport resources unrelated negative: '+name+': '+str(error))
            results.append(dict(case=name,status='REJECTED',reason=reason))
        else:raise ValueError('transport resources accepted negative: '+name)
    return results


def qualify(directory):
    root=Path(directory);before=r.accounting.collection.inventory(root);original=r.validate(root);cases={}
    for name in r.component.CASES:
        case=root/name;index,traces,boundaries,events=r.accounting.load(case)
        group=r.component.n.b.original(case,3,False)
        identities={node:r.component.f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in group.items()}
        authority=r.component.n.b.c.current(group['node-1'])[2]['capsule']['root']
        wires=r.accounting.collection.read_json(case,'wire.json',r.accounting.collection.WIRE_BYTES)
        cases[name]=replay((events,wires,traces,boundaries,identities,authority))
    r.need(r.accounting.collection.inventory(root)==before,'transport resources negative original changed')
    return dict(status='PASS',original=original,negatives=cases,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(qualify(a.root),sort_keys=True))
