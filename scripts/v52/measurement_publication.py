"""Measurement local publication authority, including exact received snapshots.

The general physical validator and chosen application projection remain mandatory.
This adds the local durable boundary absent from the original short smoke profile.
No evidence directory is opened by the product runtime.
"""
from scripts.v51 import runtime_evidence as physical,recovery_inspector as recovery,rejoin_evidence
from . import public_reads_evidence as reads
from .evidence import need,digest,encoded

MAX_SELECTIONS=64
MAX_BASES=128
MAX_TRANSFER_BYTES=64<<20
MAX_TRANSFERS=128
MAX_SELECTORS=256


def selection_budget(traces,manifest):
    selections=set();bases=set();chunks={};total=0
    for rows in traces.values():
        for row in rows:
            if row['event'] not in ('REPLY','RECEIVED'):continue
            frame=physical.f.wire(physical.raw(row['frame']),manifest);p=frame['payload']
            if frame['type']=='SELECTED_OFFER' and p['response']:selections.add(digest(physical.raw(p['selected'])))
            for value in ([p['basis']] if frame['type']=='PROMISE' else p['bases'] if frame['type']=='SELECTED_OFFER' else []):
                bases.add(digest(physical.raw(value)))
            if frame['type']=='BASIS_CHUNK' and p['action']=='DATA':
                key=(frame['sender'],p['basisId'],p['offset']);data=physical.raw(p['chunk']);sha=digest(data)
                if key not in chunks:chunks[key]=sha;total+=len(data)
                else:need(chunks[key]==sha,'measurement changed basis chunk')
            need(len(selections)<=MAX_SELECTIONS and len(bases)<=MAX_BASES and total<=MAX_TRANSFER_BYTES,
                 'measurement selected authority budget')
    return dict(selections=len(selections),bases=len(bases),basisBytes=total)


class Transfers:
    def __init__(self):self.offers={};self.chunks={};self.bytes=0
    def offer(self,identity,value):
        need(type(value['imageBytes']) is int and 0<value['imageBytes']<=16<<20,'measurement snapshot offer byte bound')
        if identity in self.offers:need(self.offers[identity]==value,'measurement changed snapshot offer')
        else:
            need(len(self.offers)<MAX_TRANSFERS,'measurement snapshot transfer count')
            self.offers[identity]=dict(value);self.chunks[identity]={}
    def chunk(self,identity,offset,data):
        need(identity in self.offers,'measurement snapshot chunk without offer')
        need(type(offset) is int and offset>=0 and 0<len(data)<=65536 and offset+len(data)<=self.offers[identity]['imageBytes'],
             'measurement snapshot chunk range')
        parts=self.chunks[identity]
        if offset in parts:need(parts[offset]==data,'measurement changed snapshot chunk')
        else:
            # Offset count is bounded by bytes, including tiny adversarial chunks.
            need(sum(len(v) for v in self.chunks.values())<131072 and self.bytes+len(data)<=MAX_TRANSFER_BYTES,
                 'measurement snapshot transfer byte/count bound')
            parts[offset]=data;self.bytes+=len(data)
    def image(self,identity):
        need(identity in self.offers,'measurement install lacks snapshot offer')
        values=[];size=0
        for offset,data in sorted(self.chunks[identity].items()):
            need(offset==size,'measurement installed snapshot transfer hole');values.append(data);size+=len(data)
        value=b''.join(values);offer=self.offers[identity]
        need(size==offer['imageBytes'] and value[16:48].hex()==offer['imageDigest'],'measurement install differs from transferred image')
        return value


def validate(traces,manifest,projection,mode,*,selector_limit=MAX_SELECTORS,restorations=None):
    need(type(selector_limit) is int and 0<selector_limit<=8192,'measurement selector profile limit')
    budget=selection_budget(traces,manifest);selections=reads.selected_prefixes(traces,manifest)
    transfers=Transfers();selectors=installs=local_publications=0;restorations=restorations or {};observed_restorations=set()
    for node,rows in traces.items():
        forced=set();installed=set();promised=0;restored=False;generation=0
        for row in rows:
            if row['generation']!=generation:
                need(row['generation']==generation+1 and (generation==0 or restored),'measurement publication process sequence')
                generation=row['generation'];forced=set();installed=set();promised=0;restored=False
                if generation!=1:
                    need((node,generation) in restorations,'measurement publication missing retained authority')
                    prior=restorations[node,generation];forced=set(prior['proofs']);promised=prior['promisedEpoch']
            event=row['event']
            if event=='FORCE':
                value=physical.frame(row['record'],row['kind'],manifest)
                if row['kind']=='PROOF':forced.add(digest(physical.raw(row['record'])))
                if row['kind']=='PROMISE':promised=value['epoch']
            elif event=='STORAGE_CUT' and row['cut']=='SELECTOR_BEFORE_ACK':
                selectors+=1;need(selectors<=selector_limit,'measurement selector observation count')
                need('readGeneration' in row,'measurement selector lacks generation bytes')
                source=rejoin_evidence.packet(dict(files=row['readGeneration']),manifest)
                need(source['seal']['node']==node,'measurement forced generation voter')
                snapshot=source['snapshot'];projection.publication(snapshot)
                selected=source['seal']['selectedDigest']
                if selected is not None:
                    need(selected in selections,'measurement generation lacks verified selection')
                    recovery.agree(snapshot,selections[selected],len(snapshot['anchors']))
                installed.add(digest(encoded(snapshot)))
            elif event=='REPLY' and 'request' in row:
                request=physical.f.wire(physical.raw(row['request']),manifest);response=physical.f.wire(physical.raw(row['frame']),manifest)
                if request['type'] not in ('SNAPSHOT_OFFER','SNAPSHOT_CHUNK') or response['type']!=request['type']:continue
                need(all(request[k]==response[k] for k in ('traceId','eventSequence','epoch','incarnationId','proposer')) and
                     request['recipient']==node==response['sender'] and request['sender']==response['recipient'],
                     'measurement snapshot response correlation')
                body=request['payload'];answer=response['payload'];key=(node,generation,body['transferId'])
                if request['type']=='SNAPSHOT_OFFER':
                    need(body['response'] is False and answer==dict(body,response=True),'measurement snapshot offer ACK')
                    transfers.offer(key,dict(imageBytes=body['imageBytes'],imageDigest=body['imageDigest'],
                                             epoch=request['epoch'],incarnation=request['incarnationId'],proposer=request['proposer']))
                else:
                    need(body['action']=='DATA' and answer==dict(body,action='ACK',chunk=''),'measurement snapshot chunk ACK')
                    need(key in transfers.offers and all(request[k]==transfers.offers[key][v] for k,v in
                         (('epoch','epoch'),('incarnationId','incarnation'),('proposer','proposer'))),'measurement snapshot chunk changed ballot')
                    transfers.chunk(key,body['offset'],physical.raw(body['chunk']))
            elif event=='REJOIN_INSTALLED':
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest)
                need(digest(encoded(snapshot)) in installed,'measurement rejoin lacks forced generation')
                key=(node,generation,row['transferId']);image=physical.f.contextual_frame(transfers.image(key),'IMAGE',manifest)
                need(not image['acceptances'] and image['snapshot']==row['snapshot'],'measurement installed snapshot substituted')
                ballot=physical.frame(row['ballot'],'PROMISE',manifest);offer=transfers.offers[key]
                need(all(ballot[k]==offer[k] for k in ('epoch','incarnation','proposer')) and ballot['epoch']==promised,
                     'measurement installed snapshot ballot')
                need(snapshot['terminalProof'] is not None and physical.frame(snapshot['terminalProof'],'PROOF',manifest)['epoch']<=promised,
                     'measurement installed snapshot proof exceeds promise');installs+=1
            elif event in ('APPLICATION_RESTORED','PUBLISHED','LOCAL_PUBLISHED'):
                snapshot=recovery.snapshot(physical.raw(row['snapshot']),manifest)
                if event=='APPLICATION_RESTORED':
                    if generation==1:need(not restored and not snapshot['anchors'],'measurement fresh runtime restored non-genesis')
                    else:
                        need(not restored and digest(encoded(snapshot))==restorations[node,generation]['snapshotSha256'],
                             'measurement restored snapshot differs from retained authority');observed_restorations.add((node,generation))
                        installed.add(digest(encoded(snapshot)))
                    restored=True
                else:
                    # Published V5.1 predates both APPLICATION_RESTORED and
                    # follower-local reads. Do not invent that observation.
                    need(restored or mode=='published-v51-legacy-strong','measurement publication before restoration')
                    if event=='LOCAL_PUBLISHED' and snapshot['anchors']:
                        need(digest(physical.raw(snapshot['terminalProof'])) in forced or digest(encoded(snapshot)) in installed,
                             'measurement local publication lacks forced authority');local_publications+=1
        need(restored or mode=='published-v51-legacy-strong','measurement missing initial restoration')
    need(observed_restorations==set(restorations),'measurement unused retained restoration')
    return dict(status='PASS',profile='forced-generation-v1',restorationObservable=mode!='published-v51-legacy-strong',selectors=selectors,installs=installs,
                localPublications=local_publications,transfers=len(transfers.offers),snapshotBytes=transfers.bytes,**budget)
