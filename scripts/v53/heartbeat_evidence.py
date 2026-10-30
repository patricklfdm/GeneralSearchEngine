"""Original-first replay of native heartbeat-only TCP component evidence."""
import argparse
import base64
import json
from pathlib import Path
import shutil
import tempfile
import uuid
from . import native_dispatch_evidence as n
from .discovered_selection_evidence import inventory

b,c,e,f,need = n.b,n.c,n.e,n.f,n.need


def validate(root):
    root = Path(root); inventory(root)
    b.selection.layout(root,{'initial','original-plan.gsbp','original-application.image','before-network',
        'after-close','calls.json','events.json','wire.json','failures.json'},'heartbeat history')
    size = len(list((root/'before-network').iterdir()))
    need(size in (3,4,5),'heartbeat stable size')
    group = n.s.initialize(b.original(root,size,False))
    group = {node:dict(files,**{n.future.FILE:n.future.frame(n.future.initial(files),{})}) for node,files in group.items()}
    b.match(root,'before-network',group); b.match(root,'after-close',group)
    names = sorted(group); ids = {node:n.future.identity(files) for node,files in group.items()}
    calls = n.read(root/'calls.json')
    need(type(calls) is list and len(calls) == size and all(set(v) == {'node','operation','events'} for v in calls)
         and [(v['node'],v['operation']) for v in calls] == [(node,'initialize-retention') for node in names],
         'heartbeat original initialization')
    for row in calls: n.s.ordered(row['events'],['RETENTION_PARENT_FORCED','FUTURE_RETENTION_PARENT_FORCED'],'heartbeat initialization')
    rows = n.read(root/'wire.json'); pairs = [(a,z) for a in names for z in names if a != z]
    need(type(rows) is list and len(rows) == len(pairs),'heartbeat complete peer exchanges')
    traces = set(); events = []
    for ordinal,(row,(sender,recipient)) in enumerate(zip(rows,pairs),11):
        need(set(row) == {'request','response','withheld'} and row['withheld'] is False,'heartbeat original wire row')
        request_raw,reply_raw = (base64.b64decode(row[k],validate=True) for k in ('request','response'))
        request = f.decode(request_raw,'wire','HEARTBEAT'); reply = f.decode(reply_raw,'wire','HEARTBEAT_ACK')
        trace = request['trace']; need(trace not in traces and uuid.UUID(trace).int != 0,'heartbeat unique trace'); traces.add(trace)
        cap = c.current(group[sender])[2]['capsule']; target = c.current(group[recipient])[2]['capsule']
        fields = dict(root=cap['root'],view=e.authority(cap['root'],cap['cut']['view']),
            ballot=dict(counter=ordinal,proposer=sender,incarnation=ids[sender]['storage']),trace=trace,sequence=1)
        need(request == dict(fields,sender=ids[sender],recipient=ids[recipient],payload=dict(cut=cap['cut'],activated=True)) and
             reply == dict(fields,sender=ids[recipient],recipient=ids[sender],payload=dict(cut=target['cut'])),
             'heartbeat exact original identity/cut/correlation')
        events.extend([dict(node=recipient,event='WIRE_RESPONSE',request=e.digest(request_raw),response=e.digest(reply_raw)),
                       dict(node=sender,event='NETWORK_RECEIVED',kind='HEARTBEAT_ACK',response=e.digest(reply_raw))])
    need(n.read(root/'events.json') == events,'heartbeat only complete network events')
    need(n.read(root/'failures.json') == [],'heartbeat no hidden failed exchange')
    return dict(status='PASS',scope='native-heartbeat-component',size=size,exchanges=len(rows),
        originalFirst=True,authorityWrites=False,autonomousElection=False,publicRuntime=False,phase3Complete=False)


NEGATIVES = {
    'changed-selector':'admitted exact after-close: node-1',
    'changed-ledger':'admitted exact after-close: node-2',
    'missing-heartbeat':'heartbeat complete peer exchanges',
    'foreign-root':'heartbeat exact original identity/cut/correlation',
    'forged-peer-cut':'heartbeat exact original identity/cut/correlation',
    'stale-response':'heartbeat exact original identity/cut/correlation',
    'hidden-force':'heartbeat only complete network events',
    'missing-delivery':'heartbeat only complete network events',
    'hidden-failure':'heartbeat no hidden failed exchange',
}


def qualify(root):
    original = validate(root); negatives = []
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-heartbeat-negative-') as temp:
            path = Path(temp)/'raw'; shutil.copytree(root,path)
            if name == 'changed-selector': (path/'after-close/node-1/selector.gsr').write_bytes(b'changed')
            elif name == 'changed-ledger': (path/'after-close/node-2'/n.s.FILE).write_bytes(b'changed')
            elif name in ('hidden-force','missing-delivery'):
                rows=n.read(path/'events.json')
                if name == 'hidden-force': rows.append(dict(node='node-1',event='PROMISE_FORCED'))
                else: rows.pop()
                (path/'events.json').write_bytes(f.canonical(rows))
            elif name == 'hidden-failure': (path/'failures.json').write_bytes(f.canonical([dict(failure='hidden')]))
            else:
                rows=n.read(path/'wire.json')
                if name == 'missing-heartbeat': rows.pop()
                else:
                    response=f.decode(base64.b64decode(rows[0]['response']),'wire','HEARTBEAT_ACK')
                    if name == 'foreign-root': response['root']='0'*64
                    elif name == 'forged-peer-cut': response['payload']['cut']['index']+=1
                    else: response['sequence']+=1
                    rows[0]['response']=base64.b64encode(f.encode('wire','HEARTBEAT_ACK',response)).decode()
                (path/'wire.json').write_bytes(f.canonical(rows))
            try: validate(path)
            except ValueError as error: need(str(error)==reason,'heartbeat unrelated negative: '+name+': '+str(error))
            else: raise ValueError('heartbeat accepted negative: '+name)
        negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.directory),sort_keys=True))
