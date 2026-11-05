"""Real original reserved-but-unwritten failures and identical connected retry."""
import argparse
import json
from pathlib import Path
from . import transport_resource_evidence as r

CASES=('refused-direct','refused-decorated','rejected-direct','rejected-decorated')
need=r.need


def case(root,name):
    need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','after','wire.json','events.json',r.accounting.DIRECTORY},
         'unsent original case inventory')
    n=r.component.n;before=n.b.original(root,3,False);n.b.match(root,'after',before)
    cap=n.b.c.current(before['node-1'])[2]['capsule']
    identities={node:r.component.f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in before.items()}
    index,traces,boundaries,events=r.accounting.load(root)
    r.accounting.replay(index,traces,boundaries,events,{node:identities[node] for node in ('node-1','node-2')},cap['root'])
    wires=r.accounting.collection.read_json(root,'wire.json',r.accounting.collection.WIRE_BYTES)
    network=r.connections.replay(events,wires,identities,cap['root'])
    need(network['attempts']==network['receivedAttempts']==1 and len(network['rows'])==1 and not network['failed'],
         'unsent original connected retry')
    row=network['rows'][0];need(row['delivered'] is not None and row['kind']=='STATUS_PROBE' and row['answer']=='STATUS' and
         row['request']['sender']==identities['node-1'] and row['request']['recipient']==identities['node-2'] and
         row['response']['payload']==dict(nonce=row['request']['payload']['nonce'],cut=cap['cut'],ready=False),
         'unsent original status reply')
    result=r.replay(events,wires,traces,boundaries,identities,cap['root']);failed=result['unsentAttempts']
    need(len(failed)==2 and all(v['node']=='node-1' and v['reason']=='IO' and v['request']==row['requestHash'] for v in failed) and
         failed[0]['eventIndex']<failed[1]['eventIndex']<row['sent'] and failed[0]['end']<failed[1]['start'] and
         all(events[v['eventIndex']].get('scope')==('unsent-test' if name.endswith('decorated') else 'connection-test') for v in failed),
         'unsent original distinct sequential failures')
    need(result['boundFrameLifetimes']==6 and result['otherControlReservations']==0,'unsent original complete buffers')
    return result,(events,wires,traces,boundaries,identities,cap['root'])


def validate(directory):
    root=Path(directory);before=r.accounting.collection.inventory(root)
    need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={'receipt.json',*CASES},'unsent complete cases')
    cases=[dict(case=name,unsentAttempts=2,connectedAttempts=1,frameLifetimes=6,storageUnchanged=True) for name in CASES]
    expected=dict(schema='gse-v53-unsent-resources-v1',status='PASS',cases=cases,execution='loopback-tcp-component',
                  completeMembershipHistory=False,phase3Complete=False)
    need(r.accounting.collection.read_json(root,'receipt.json',65536)==expected,'unsent receipt scope')
    results=[dict(case=name,resources=case(root/name,name)[0]) for name in CASES]
    need(r.accounting.collection.inventory(root)==before,'unsent original changed')
    return dict(status='PASS',cases=results,wholeRuntimeResourcesQualified=False,phase3Complete=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');a=p.parse_args()
    print(json.dumps(validate(a.root),sort_keys=True))
