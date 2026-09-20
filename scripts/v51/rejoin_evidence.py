"""Independent reconstruction of transferred generations and two-source retirement evidence."""
import copy
import json
import tempfile
from pathlib import Path
from . import runtime_evidence as runtime,recovery_inspector as recovery,format_inspector as f


def packet(value,manifest):
    f.need(set(value)=={'files'} and len(value['files'])==5,'source packet inventory')
    files={}
    for row in value['files']:
        f.need(set(row)=={'name','bytes'} and row['name'] not in files,'source packet duplicate/fields');files[row['name']]=runtime.raw(row['bytes'])
    f.need(set(files)=={'current.gsr','generation.gsr','snapshot.gsr','accepted.gsr','proofs.gsr'},'source packet file names')
    with tempfile.TemporaryDirectory(prefix='gse-v51-source-') as directory:
        root=Path(directory)
        for name,data in files.items():(root/name).write_bytes(data)
        return recovery.source(root,manifest)


def validate(root,traces=None):
    root=Path(root);encoded=(root/'node-1/manifest.gsr').read_bytes();manifest=dict(f.inspect(encoded,'MANIFEST'),digest=encoded[16:48].hex())
    if traces is None:traces={f'node-{i}':[json.loads(line) for line in (root/f'node-{i}-trace.jsonl').read_text().splitlines()] for i in range(1,4)}
    offers={};chunks={};images={};image_offers={};downloaded=set();floors=installs=deletions=0
    for node,rows in traces.items():
        for row in rows:
            if row['event']!='RECEIVED':continue
            value=f.wire(runtime.raw(row['frame']),manifest);p=value['payload'];key=(value['sender'],node,p.get('transferId'))
            request=f.wire(runtime.raw(row['request']),manifest);body=request['payload'];image_key=(request['recipient'],body.get('transferId'))
            if value['type']=='SNAPSHOT_OFFER':image_offers[image_key]=body
            if value['type']=='SNAPSHOT_CHUNK' and p['action']=='ACK':
                ranges=images.setdefault(image_key,{});data=runtime.raw(body['chunk']);f.need(body['offset'] not in ranges or ranges[body['offset']]==data,'changed snapshot retry');ranges[body['offset']]=data
            if value['type']=='SOURCE_OFFER' and p['response']:offers[key]=p
            if value['type']=='SOURCE_CHUNK' and p['action']=='DATA':
                ranges=chunks.setdefault(key,{});data=runtime.raw(p['chunk']);f.need(p['offset'] not in ranges or ranges[p['offset']]==data,'changed source chunk retry');ranges[p['offset']]=data
    for key,offer in offers.items():
        data=b''
        for offset,value in sorted(chunks.get(key,{}).items()):
            if offset!=len(data):break
            data+=value
        if len(data)!=offer['sourceBytes']:continue # Interrupted attempts never qualify as sources.
        f.need(recovery.sha(data)==offer['sourceDigest'],'source transfer digest');source=packet(json.loads(data),manifest)
        f.need(source['seal']['node']==key[0] and len(source['snapshot']['anchors'])==offer['index'],'source transfer owner/cut')
        downloaded.add((key[1],recovery.sha(data)))
    for node,rows in traces.items():
        floor_forced=False;source_forced=False;selector_forced=False
        for row in rows:
            if row['event']=='STORAGE_CUT':
                cut=row['cut']
                if cut=='FLOOR_BEFORE_ACK':floor_forced=True
                if cut=='SOURCE_BEFORE_ACK':source_forced=True
                if cut=='SELECTOR_BEFORE_ACK':selector_forced=True
                if cut.startswith('DELETE_AFTER_'):
                    f.need(floor_forced,'physical deletion before durable floor');deletions+=1
            if row['event']=='RECOVERY_FLOOR':
                local=packet(row['local'],manifest);remote=packet(row['remote'],manifest)
                f.need(floor_forced and source_forced,'floor lacks durable local source/marker')
                f.need(local['seal']['node']==node and remote['seal']['node']!=node and (node,recovery.sha(runtime.storage.canonical(row['remote']))) in downloaded,'floor lacks actual peer transfer')
                f.need(len(local['snapshot']['anchors'])==len(remote['snapshot']['anchors'])==row['index'],'floor source cuts')
                recovery.agree(local['snapshot'],remote['snapshot'],row['index']);floors+=1
            if row['event']=='REJOIN_INSTALLED':
                f.need(selector_forced,'rejoin before durable selector');snapshot=f.contextual_frame(runtime.raw(row['snapshot']),'SNAPSHOT',manifest)
                key=(node,row['transferId']);data=b''
                for offset,part in sorted(images.get(key,{}).items()):f.need(offset==len(data),'snapshot transfer gap');data+=part
                f.need(key in image_offers and len(data)==image_offers[key]['imageBytes'] and data[16:48].hex()==image_offers[key]['imageDigest'],'rejoin lacks exact transferred image')
                image=f.contextual_frame(data,'IMAGE',manifest);f.need(not image['acceptances'] and image['snapshot']==row['snapshot'],'rejoin image substituted')
                ballot=f.contextual_frame(runtime.raw(row['ballot']),'PROMISE',manifest)
                f.need(snapshot['terminalProof'] is not None and f.inspect(runtime.raw(snapshot['terminalProof']),'PROOF')['epoch']<=ballot['epoch'],'rejoin promise/proof');installs+=1
    f.need(floors>=6 and installs>=4 and deletions>=6 and len(downloaded)>=3,'incomplete rejoin/retirement execution')
    return dict(status='PASS',floors=floors,installs=installs,deletedBoundaries=deletions,transferredSources=len(downloaded))


def negatives(root):
    root=Path(root);traces={f'node-{i}':[json.loads(line) for line in (root/f'node-{i}-trace.jsonl').read_text().splitlines()] for i in range(1,4)}
    cases=[]
    for name in ('missing-source-chunks','missing-snapshot-chunks','missing-floor-force','duplicate-source-owner','changed-source-file'):
        changed=copy.deepcopy(traces)
        if name in ('missing-source-chunks','missing-snapshot-chunks'):
            kind='SOURCE_CHUNK' if name=='missing-source-chunks' else 'SNAPSHOT_CHUNK'
            for node in changed:changed[node]=[row for row in changed[node] if row['event']!='RECEIVED' or json.loads(runtime.raw(row['frame'])[48:])['type']!=kind]
        elif name=='missing-floor-force':
            for node in changed:changed[node]=[row for row in changed[node] if row['event']!='STORAGE_CUT' or row['cut']!='FLOOR_BEFORE_ACK']
        else:
            row=next(row for rows in changed.values() for row in rows if row['event']=='RECOVERY_FLOOR')
            if name=='duplicate-source-owner':row['remote']=copy.deepcopy(row['local'])
            else:row['remote']['files'][0]['bytes']=row['remote']['files'][1]['bytes']
        try:validate(root,changed)
        except (ValueError,KeyError) as error:cases.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('rejoin negative accepted: '+name)
    return cases
