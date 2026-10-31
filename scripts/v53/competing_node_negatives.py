"""Mutations of complete raw histories, not changes to replay expectations."""
import base64
import copy
import json
from . import competing_node_evidence as p
n,c,e,f,need=p.n,p.c,p.e,p.f,p.need

CASES={
 'initial-image':'bootstrap original image binding',
 'before-ledger':'admitted exact before-network: {leader}',
 'unselected-write':'admitted exact after-close: {unused}',
 'final-retention':'admitted exact after-close: {peer}',
 'final-selector':'admitted exact after-close: {peer}',
 'invented-ready':'competing exact round lifecycle',
 'client-completion':'competing original completion',
 'duplicate-client':'competing original client observations',
 'wrong-slot-quorum':'competing original slot hooks',
 'bootstrap-force':'closed election wait initialization',
 'unselected-force':'competing unselected owner remains nonwriting',
 'missing-send':'competing request without original send',
 'early-request':'competing request without original send',
 'duplicate-delivery':'restart network delivery without original response',
 'excessive-sends':'competing bounded send attempts',
 'send-identity':'competing original send binding',
 'heartbeat-cut':'competing heartbeat original reply cut',
 'missing-heartbeat-contact':'competing original heartbeat contact before continuation',
 'control-ack':'restart network exact delivered control',
 'missing-original-vote':'restart network required original source',
 'missing-floor-force':'restart network one force: {leader}: FLOOR_PARENT_FORCED',
 'missing-observation-force':'competing exact observation forces',
 'premature-publish-send':'competing every publication send after quorum',
 'hidden-failure':'competing retained execution failure',
 'producer-pass':'competing producer scope',
 'remaining-lease':'competing exact drain receipt',
 'scratch-file':'competing exact drained scratch',
 'scratch-owner':'competing scratch identity',
 'scratch-claim':'competing exact drain receipt',
 'clock-order':'competing monotonic owned events',
 'unknown-work':'competing unknown owner event',
 'extra-slot-hook':'competing exact slot hook inventory',
}


def mutate(root,name):
 original=p.record(next(v for v in n.read(root/'events.json') if v['event']=='ROUND_INSTALLED'),'records','SELECTED')[1]
 leader=original['ballot']['proposer'];voters=[v['voter'] for v in original['sources']];peer=next(v for v in voters if v!=leader);unused=next(v for v in c.NODES if v not in voters)
 if name=='initial-image':(root/'original-application.image').write_bytes(b'changed');return
 if name=='before-ledger':(root/'before-network'/leader/n.s.FILE).write_bytes(b'changed');return
 if name in ('unselected-write','final-retention','final-selector'):
  path={'unselected-write':unused+'/allocator.gsr','final-retention':peer+'/'+n.s.FILE,'final-selector':peer+'/selector.gsr'}[name]
  (root/'after-close'/path).write_bytes(b'changed');return
 if name in ('hidden-failure','producer-pass'):
  if name=='hidden-failure':(root/'failure.txt').write_text('retained failure')
  else:
   v=n.read(root/'result.json');v.update(status='PASS',physicalReplay=True);(root/'result.json').write_bytes(f.canonical(v))
  return
 if name=='duplicate-client':
  v=n.read(root/'observations.json');v.append(copy.deepcopy(v[-1]));(root/'observations.json').write_bytes(f.canonical(v));return
 if name=='bootstrap-force':
  v=n.read(root/'calls.json');v[0]['events'].remove('RETENTION_PARENT_FORCED');(root/'calls.json').write_bytes(f.canonical(v));return
 if name.startswith('scratch-') or name=='remaining-lease':
  rows=n.read(root/'drains.json');row=next(v for v in rows if v['node']==peer)
  if name=='remaining-lease':row['leases']=1
  elif name=='scratch-file':(root/'drain-scratch'/peer/'incoming/leftover.bin').write_bytes(b'leftover')
  elif name=='scratch-claim':row['files'][0]['sha256']='0'*64
  else:
   path=root/'drain-scratch'/peer/'incoming/owner.json';v=n.read(path);v['identity']['node']=unused;path.write_bytes(f.canonical(v))
   item=next(v for v in row['files'] if v['path']=='incoming/owner.json');item.update(bytes=path.stat().st_size,sha256=e.digest(path.read_bytes()))
  (root/'drains.json').write_bytes(f.canonical(rows));return
 rows=n.read(root/'events.json');wire=n.read(root/'wire.json')
 def event(kind,node=leader):return next(v for v in rows if v['event']==kind and v['node']==node)
 def rewrite_reply(row,fn):
  kind,value=n.transfer.t.wire(row['response']);old=e.digest(base64.b64decode(row['response']));fn(value)
  raw=f.encode('wire',kind,value);row['response']=base64.b64encode(raw).decode();new=e.digest(raw)
  for v in rows:
   if v.get('response')==old:v['response']=new
 if name=='invented-ready':
  v=event('ROUND_BEFORE_READY');rows.remove(v);rows.insert(rows.index(event('ROUND_SLOT_COMPLETE')),v)
 elif name=='client-completion':
  v=event('ROUND_SLOT_COMPLETE');raw,ack=p.record(v,'wire','PUBLISH_ACK');ack['payload']['certificate']='0'*64;raw=f.encode('wire','PUBLISH_ACK',ack)
  v.update(bytes=base64.b64encode(raw).decode(),record=e.digest(raw))
 elif name=='wrong-slot-quorum':event('SLOT_FUTURE_QUORUM_COMPLETE')['voters']=sorted([leader,unused])
 elif name=='unselected-force':rows.append(dict(node=unused,event='PROMISE_FORCED'))
 elif name=='missing-send':rows.remove(event('NETWORK_SEND'))
 elif name=='early-request':
  v=event('NETWORK_REQUEST',peer);rows.remove(v);rows.insert(rows.index(event('NETWORK_SEND')),v)
 elif name=='duplicate-delivery':
  v=next(v for v in rows if v['event']=='NETWORK_RECEIVED' and v['kind']=='PROMISE');rows.insert(rows.index(v)+1,copy.deepcopy(v))
 elif name=='excessive-sends':
  v=event('NETWORK_SEND');at=rows.index(v);rows[at:at]=[copy.deepcopy(v) for _ in range(3)]
 elif name=='send-identity':event('NETWORK_SEND')['node']=peer
 elif name in ('heartbeat-cut','control-ack'):
  wanted='HEARTBEAT' if name=='heartbeat-cut' else 'ACCEPT'
  originals=[v for v in wire if n.transfer.t.wire(v['request'])[0]==wanted];request=originals[0]['request']
  for row in originals:
   if row['request']==request:
    rewrite_reply(row,lambda v:v['payload']['cut'].update(index=99) if name=='heartbeat-cut' else v['payload'].update(receipt='0'*64))
 elif name=='missing-heartbeat-contact':
  trace=n.transfer.t.wire(next(v for v in wire if n.transfer.t.wire(v['request'])[0]=='HEARTBEAT')['request'])[1]['trace']
  hashes={e.digest(base64.b64decode(v['response'])) for v in wire if n.transfer.t.wire(v['request'])[1]['trace']==trace}
  rows=[v for v in rows if not(v['event']=='NETWORK_RECEIVED' and v.get('response') in hashes)]
 elif name=='missing-original-vote':
  row=next(v for v in wire if n.transfer.t.wire(v['request'])[0]=='CHUNK' and n.transfer.t.wire(v['request'])[1]['sender']['node']==peer
           and n.transfer.t.wire(v['response'])[0]=='SOURCE_OFFER' and n.transfer.t.wire(v['response'])[1]['payload']['kind']=='RECORD'
           and n.transfer.t.wire(v['request'])[1]['payload']['digest']!=n.transfer.t.wire(v['response'])[1]['payload']['digest'])
  trace=n.transfer.t.wire(row['request'])[1]['trace'];deleted=[v for v in wire if n.transfer.t.wire(v['request'])[1]['trace']==trace]
  qh={e.digest(base64.b64decode(v['request'])) for v in deleted};rh={e.digest(base64.b64decode(v['response'])) for v in deleted}
  wire=[v for v in wire if v not in deleted];rows=[v for v in rows if v.get('request') not in qh and v.get('response') not in rh]
 elif name=='missing-floor-force':rows.remove(event('FLOOR_PARENT_FORCED'))
 elif name=='missing-observation-force':
  at=next(i for i,v in enumerate(rows) if v['event']=='ROUND_SLOT_BEGIN' and p.record(v,'records','ENTRY')[1]['index']==2)
  target=next(v for v in rows[at:] if v['node']==leader and v['event']=='RETENTION_FORCED');rows.remove(target)
 elif name=='premature-publish-send':
  target=next(v for v in rows if v['event']=='NETWORK_SEND' and v['kind']=='PUBLISH');rows.remove(target);rows.insert(rows.index(event('SLOT_FUTURE_QUORUM_COMPLETE')),target)
 elif name=='clock-order':rows[-1]['nanoTime']=0
 elif name=='unknown-work':rows.append(dict(node=leader,event='UNACCOUNTED_WRITE'))
 elif name=='extra-slot-hook':rows.append(copy.deepcopy(event('SLOT_PUBLISHED')))
 else:raise ValueError('unknown competing mutation')
 if name!='clock-order':
  start=rows[0]['nanoTime']
  for i,v in enumerate(rows):v['nanoTime']=start+i
 (root/'events.json').write_bytes(f.canonical(rows));(root/'wire.json').write_bytes(f.canonical(wire))
