"""Original public-bootstrap TCP failures, identical retries and unchanged storage."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile

from . import transport_evidence as transport
from . import joining_transcript as transcript
from . import joining_attempts as attempts
from . import joining_history_run as collection

b, e = transport.b, transport.e
need, f, sha = e.need, e.f, e.digest
CASES = tuple(scope+'-'+mode for scope in ('old','scoped') for mode in ('handler-io','handler-protocol','send-guard'))


def case(root, name):
    need({p.name for p in root.iterdir()}=={'original-plan.gsbp','original-application.image','initial','after','wire.json','events.json'},
         'transport attempt case inventory')
    before=b.original(root,3,False);b.match(root,'after',before)
    cap=b.c.current(before['node-1'])[2]['capsule']
    identities={node:f.decode(files['node.gsr'],'records','NODE')['identity'] for node,files in before.items()}
    events=transport.load(root/'events.json');wires=transport.load(root/'wire.json');failed=[]
    rows=transcript.causal(events,wires,identities,cap['root'],failed=failed)
    allowed=attempts.SENDS|attempts.READS|{attempts.EVENT,'BEFORE_RESPONSE_WRITE','WIRE_RESPONSE','AFTER_RESPONSE_READ','NETWORK_RECEIVED'}
    need(all(row['event'] in allowed and row.get('scope')==('attempt-test' if name.startswith('scoped-') else None) for row in events),
         'transport attempt original lifetime')
    need(len(rows)==len(failed)==1 and not failed[0]['withheldResponse'],'transport attempt exact failure and retry')
    failed=failed[0];row=rows[0];q,a=row['request'],row['response'];guard=name.endswith('send-guard')
    need(failed['requestHash']==row['requestHash'] and failed['finished']<row['sent'] and
         failed['clientReason']=='IO' and failed['serverReason']==(None if guard else 'PROTOCOL' if name.endswith('handler-protocol') else 'IO') and
         (failed['received'] is None)==guard,'transport attempt original classified retry')
    need(row['kind']=='STATUS_PROBE' and row['answer']=='STATUS' and q['sender']==identities['node-1'] and
         q['recipient']==identities['node-2'] and a['payload']==dict(nonce=q['payload']['nonce'],cut=cap['cut'],ready=False),
         'transport attempt original status reply')
    return dict(case=name,failedWrites=1,successfulReplies=1,storageUnchanged=True)


def validate(directory):
    root=Path(directory)
    need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={'receipt.json',*CASES},'transport attempt complete cases')
    before=collection.inventory(root)
    results=[case(root/name,name) for name in CASES]
    expected=dict(schema='gse-v53-transport-attempts-v1',status='PASS',cases=results,network=True,
                  phase3Complete=False,completeMembershipHistory=False)
    need(transport.load(root/'receipt.json')==expected,'transport attempt receipt scope')
    need(collection.inventory(root)==before,'transport attempt original changed')
    return expected


NEGATIVES = {
    'missing-caller-terminal':'joining failure missing caller terminal',
    'missing-server-terminal':'joining failure missing receiver terminal',
    'foreign-caller':'joining failure sender lifetime',
    'foreign-receiver':'joining failure receiver lifetime',
    'wrong-request-kind':'joining failure original request identity',
    'unknown-reason':'joining failure observation shape',
    'duplicate-caller':'joining duplicate outbound terminal',
    'duplicate-receiver':'joining duplicate inbound terminal',
    'terminal-before-send':'joining failure without attempted send',
    'lost-observations':'joining network ambiguous overlapping retry',
    'different-retry':'transport attempt original classified retry',
    'rewritten-storage':'admitted exact after: node-1',
    'claims-membership-complete':'transport attempt receipt scope',
}


def mutate(root,name):
    target=root/'scoped-handler-io';path=target/'events.json';events=transport.load(path)
    if name=='rewritten-storage':(target/'after/node-1/grants.gsr').write_bytes(b'changed');return
    if name=='claims-membership-complete':
        path=root/'receipt.json';v=transport.load(path);v['completeMembershipHistory']=True;path.write_bytes(f.canonical(v));return
    outbound=next(i for i,v in enumerate(events) if v.get('direction')=='OUTBOUND')
    inbound=next(i for i,v in enumerate(events) if v.get('direction')=='INBOUND')
    if name=='missing-caller-terminal':events.pop(outbound)
    elif name=='missing-server-terminal':events.pop(inbound)
    elif name=='foreign-caller':events[outbound]['node']='node-3'
    elif name=='foreign-receiver':events[inbound]['node']='node-3'
    elif name=='wrong-request-kind':events[outbound]['kind']='ACCEPT'
    elif name=='unknown-reason':events[outbound]['reason']='SUCCESS'
    elif name=='duplicate-caller':events.insert(outbound,dict(events[outbound]))
    elif name=='duplicate-receiver':events.insert(inbound,dict(events[inbound]))
    elif name=='terminal-before-send':events.insert(0,events.pop(outbound))
    elif name=='lost-observations':events=[v for v in events if v['event']!=attempts.EVENT]
    elif name=='different-retry':
        wires=transport.load(target/'wire.json');old_q=sha(base64.b64decode(wires[0]['request']));old_a=sha(base64.b64decode(wires[0]['response']))
        for side in ('request','response'):
            kind,value=attempts.wire(wires[0][side]);value['trace']='00000000-0000-0000-0000-000000000099'
            wires[0][side]=base64.b64encode(f.encode('wire',kind,value)).decode()
        new_q=sha(base64.b64decode(wires[0]['request']));new_a=sha(base64.b64decode(wires[0]['response']))
        for row in events[outbound+1:]:
            if row.get('request')==old_q:row['request']=new_q
            if row.get('response')==old_a:row['response']=new_a
            if row.get('event') in attempts.SENDS:row['bytes']=wires[0]['request']
        (target/'wire.json').write_bytes(f.canonical(wires))
    else:raise ValueError('unknown transport attempt mutation')
    path.write_bytes(f.canonical(events))


def qualify(directory):
    root=Path(directory);original=validate(root);before=collection.inventory(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-transport-attempt-negative-') as temp:
            copied=Path(temp)/'raw';shutil.copytree(root,copied);mutate(copied,name)
            try:validate(copied)
            except ValueError as error:need(str(error)==reason,'transport attempt unrelated negative: '+name+': '+str(error))
            else:raise ValueError('transport attempt accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(collection.inventory(root)==before,'transport attempt qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.directory),sort_keys=True))
