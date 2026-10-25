"""Native maximum image, actual admitted storage and seven distinct physical copies.

The native backup writer counts its 32-byte request ID before normalization.
This qualifies 64 MiB minus 32 bytes, not every arbitrary 64 MiB container.
"""
import argparse
import json
import struct
import uuid
from pathlib import Path
from . import admitted_cross_view_evidence as q
from . import floor_evidence as floor
from .offline_fixture_image import application, image_members, uncheck
from .retirement_source_process_evidence import same, read

b,e,c,t,selection=q.b,q.e,q.c,q.t,q.selection
MAXIMUM=64*e.MIB
NATIVE_MAXIMUM=MAXIMUM-32
HISTORY=str(uuid.UUID(int=(8<<64)|640))


def documents(last):
    e.need(type(last) is int and 0<=last<=65531,'maximum document extent')
    return [(n,'x'*(65536-len(str(n))-1)) for n in range(1023)]+[(1023,'y'*last)]


def source(root):
    calibration=t.plans.read(root/'calibration.image',MAXIMUM)
    image=t.plans.read(root/'source.image',MAXIMUM);extra=NATIVE_MAXIMUM-len(calibration)
    e.need(len(image)==NATIVE_MAXIMUM and extra>0,'maximum native image extent')
    application(calibration,HISTORY,41,documents(0));application(image,HISTORY,41,documents(extra))
    members=image_members(image);original=c.inventory(root/'source-backup')
    e.need(set(original)==set(members),'maximum source backup inventory')
    for name in ('gse-backup-checkpoint','gse-backup-metadata'):
        e.need(original[name]==members[name],'maximum source backup payload')
    raw=original['gse-backup-manifest'];uncheck(raw,160,'maximum original manifest')
    prefix=len(members['gse-backup-manifest'])-16
    e.need(len(raw)==len(members['gse-backup-manifest'])+32 and raw[:prefix]==members['gse-backup-manifest'][:prefix],
           'maximum original manifest binding')
    timestamp,size=struct.unpack('>qI',raw[prefix:prefix+12]);request=raw[prefix+12:-4]
    e.need(timestamp>=0 and size==32 and len(request)==32 and all(v in b'0123456789abcdef' for v in request),
           'maximum original backup administration')
    e.need(sum(map(len,original.values()))+24==MAXIMUM,'maximum native backup exact budget')
    return image,extra


def peak_plan(group):
    """Derive the exact first seven-image floor from already verified originals."""
    copies={};references=[]
    for node in ('node-1','node-2','node-3'):
        prefix,members,packet=c.current(group[node]);manifest=group[node][prefix+'generation.gsr'];cap=packet['capsule']
        # current() validates the selected manifest separately from its members.
        # A complete floor copy needs both; preserve the original manifest bytes.
        copies[e.digest(manifest)]=dict(members,**{'generation.gsr':manifest})
        references.append(dict(voter=node,generation=e.digest(manifest),catalog=cap['catalog'],snapshot=cap['application']))
    raw=e.f.encode('records','FLOOR',dict(root=cap['root'],node='node-1',cut=cap['cut'],sources=references))
    events,files,_,directories=floor.transaction(copies,raw)
    state=dict(group['node-1'],**{n:None for n in directories},**files)
    return state,[v['event'] for v in events]


def peak_usage(files):
    images={n:len(v) for n,v in files.items() if n.endswith('.image')}
    e.need(len(images)==7 and set(images.values())=={NATIVE_MAXIMUM},'maximum seven complete images')
    sources=sum(len(v) for n,v in files.items() if v is not None and not n.endswith('.image') and
                (n.startswith('sources/') or (n.startswith('floor-copies/') and n.count('/')==2)))
    generations=sum(len(v) for n,v in files.items() if v is not None and n.startswith('generations/') and not n.endswith('.image'))
    # JOURNAL and current-authority MISC reserve complete existing unit allowances.
    metadata=34*e.MIB+sources+generations;staging=sum(images.values())+sources
    e.need(metadata<=384*e.MIB and staging<=512*e.MIB,'maximum shared resource bounds')
    return images,metadata,staging,16  # 7 images + 2 generations + 5 sources + JOURNAL + MISC


def peak(root,expected,events):
    e.need(c.inventory(root/'seven-image-floor')==expected,'maximum exact seven-image floor')
    images,metadata,staging,leases=peak_usage(expected);value=read(root/'peak.json')
    e.exact(value,'node operation event metadata staging images leases')
    rows=value['images'];e.need(type(rows) is list and len(rows)==7,'maximum physical image inventory')
    actual=[]
    for name,size in sorted(images.items()):
        path=root/'seven-image-floor'/name
        e.need(path.is_file() and not path.is_symlink() and path.stat().st_nlink==1,'maximum physical image alias')
        actual.append(dict(path=name,bytes=size,links=1))
    e.need(sorted(rows,key=lambda v:v['path'])==actual,'maximum physical image inventory')
    same({k:v for k,v in value.items() if k!='images'},dict(node='node-1',operation='campaign-3-settled-maintain',
         event='FLOOR_BEFORE_RETURN',metadata=metadata,staging=staging,leases=leases),'maximum exact reservation accounting')
    calls=read(root/'publication/calls.json');selected=[v for v in calls if v['node']=='node-1' and v['operation']==value['operation']]
    e.need(len(selected)==1 and [v for v in selected[0]['events'] if v in set(events)]==events,'maximum floor force order')
    return dict(imageBytes=sum(images.values()),metadataBytes=metadata,stagingBytes=staging,leases=leases)


def observations(root,w):
    rows=read(root/'observations.json')
    e.need(len(rows)==len(w.observed) and {e.f.canonical(v) for v in rows}==w.observed,'maximum original observations')
    calls=read(root/'calls.json')
    names=w.active;expected=[]
    def many(label):expected.extend((n,label) for n in names)
    def campaign(counter,stage):
        expected.append(('node-1','allocate-'+str(counter)))
        for phase in ('prepare','select','install'):many(phase+'-'+str(counter))
        many(stage+'-copy');many(stage+'-maintain')
    campaign(1,'round-1-settled')
    for slot in (1,2):
        expected.append(('node-1','inspect-context'))
        for phase in ('accept','proof','certificate','apply','publish'):many(phase+'-'+str(slot))
        many(f'slot-{slot}-settled-copy');many(f'slot-{slot}-settled-maintain')
        campaign(slot+2,f'campaign-{slot+2}-settled')
    many('inspect-maximum')
    e.need(type(calls) is list and len(calls)==len(expected),'maximum complete call inventory')
    for value,(node,operation) in zip(calls,expected):
        e.exact(value,'node operation events')
        e.need((value['node'],value['operation'])==(node,operation) and type(value['events']) is list and
               0<len(value['events'])<=4096 and all(type(v) is str for v in value['events']),'maximum exact call order')
    critical={'accept':['ACCEPT_ACTIVE_FORCED','ACCEPT_BEFORE_RETURN','ACCEPT_BEFORE_RETURN'],
              'proof':['PROOF_CANDIDATE_FORCED','PROOF_PARENT_FORCED','PROOF_BEFORE_RETURN'],
              'certificate':['CERTIFICATE_CANDIDATE_FORCED','CERTIFICATE_PARENT_FORCED','CERTIFICATE_BEFORE_RETURN'],
              'apply':['APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN','APPLY_ACK_DIRECTORY_FORCED','APPLY_BEFORE_RETURN'],
              'publish':['PUBLICATION_SELECTOR_FORCED','PUBLICATION_BEFORE_RETURN','PUBLICATION_BEFORE_RETURN'],
              'prepare':['PROMISE_FORCED','BASIS_FORCED','GRANT_BEFORE_RETURN'],
              'select':['SELECTED_FORCED','SELECTED_BEFORE_RETURN'],'install':['INSTALL_SELECTOR_FORCED','INSTALL_BEFORE_RETURN']}
    for label,nodes in w.phases.items():
        selected=[v for v in calls if v['operation']==label];e.need([v['node'] for v in selected]==nodes,'maximum force owner coverage')
        required=critical[label.rsplit('-',1)[0]]
        for row in selected:e.need([v for v in row['events'] if v in set(required)]==required,'maximum force before return')


def publication(root,extra):
    w=q.Walk.__new__(q.Walk);w.root=root
    w.required={'original-plan.gsbp','original-application.image','initial','calls.json','observations.json'}
    w.required|={'round-1-'+s for s in ('prepared','selected','installed','settled')}
    original=b.original(root,5,True);record=e.f.decode(original['node-1']['root.gsr'],'records','ROOT')
    plan=t.plans.decode((root/'original-plan.gsbp').read_bytes(),(root/'original-application.image').read_bytes(),details=True,size=5,source='VERIFIED_DURABLE_BACKUP')
    backup=c.inventory(root.parent/'source-backup')
    same(plan['plan']['descriptor']['sourceInventory'],[dict(path=n,kind=1,size=len(v),sha256=e.digest(v)) for n,v in sorted(backup.items())],
         'maximum original source admission binding')
    del backup
    history=record['historyId'];e.need(history!=HISTORY and uuid.UUID(history).version==4 and record['baseSequence']==41,'maximum new history')
    projected=(root/'original-application.image').read_bytes();e.need(len(projected)==NATIVE_MAXIMUM,'maximum projected image extent')
    application(projected,history,41,documents(extra))
    w.group=b.campaign(root,original,1);w.active=sorted(w.group);w.slot=0;w.counter=2;w.first=None;w.observed=set();w.phases={}
    for label in ('prepare-1','select-1','install-1'):w.phase(label,w.active)
    w.publish('BARRIER');w.campaign()
    # Read only the exact installed snapshot already replayed by campaign().
    installed={n:c.inventory(root/'campaign-3-installed'/n) for n in w.active};expected,events=peak_plan(installed)
    del installed
    w.publish('BARRIER');w.campaign();observations(root,w);selection.layout(root,w.required,'maximum publication')
    _,members,packet=c.current(w.group['node-1'])
    e.need(members[packet['capsule']['application']+'.image']==projected,'maximum final unchanged image')
    return expected,events,projected


def receipt(value,extra):
    same(value,dict(schema='gse-v53-maximum-application-v1',status='PASS',imageBytes=NATIVE_MAXIMUM,
         administrationBytes=32,finalValueBytes=extra,documents=1024,voters=5,slots=2,peakImages=7,publicRuntime=False),'maximum receipt')


def validate(root):
    root=Path(root);selection.layout(root,{'calibration.image','source.image','source-backup','publication','seven-image-floor','peak.json','typed-final','receipt.json'},'maximum application')
    _,extra=source(root);expected,events,projected=publication(root/'publication',extra)
    usage=peak(root,expected,events);b.typed_image(root/'typed-final',projected)
    receipt(read(root/'receipt.json'),extra)
    return dict(status='PASS',nativeImageBytes=NATIVE_MAXIMUM,containerLimit=MAXIMUM,documents=1024,voters=5,
                slots=2,peakImages=7,**usage,publicBootstrap=True,publicRuntime=False,maximumCapsule=False,powerLoss=False)


def qualify(root):
    # Full original replay is mandatory before small targeted evidence mutations.
    # Negatives operate on components without copying the multi-GiB archive.
    root=Path(root);result=validate(root);negative=[]
    def reject(name,reason,action):
        try:action()
        except ValueError as error:e.need(str(error)==reason,'maximum unrelated negative: '+name)
        else:raise ValueError('maximum accepted mutation: '+name)
        negative.append(dict(case=name,status='REJECTED',reason=reason))
    raw=(root/'source.image').read_bytes();docs=documents(read(root/'receipt.json')['finalValueBytes'])
    reject('history','cross-view application identity',lambda:application(raw,str(uuid.UUID(int=1)),41,docs))
    reject('sequence','cross-view application sequence/documents',lambda:application(raw,HISTORY,42,docs))
    reject('documents','cross-view application sequence/documents',lambda:application(raw,HISTORY,41,docs[:-1]))
    changed=docs[:-1]+[(1023,'z'*len(docs[-1][1]))]
    reject('document-bytes','cross-view application document bytes',lambda:application(raw,HISTORY,41,changed))
    corrupt=bytearray(raw);corrupt[100]^=1
    reject('checkpoint-crc','cross-view checkpoint CRC32C mismatch',lambda:application(bytes(corrupt),HISTORY,41,docs))
    oversized=bytearray(raw+b'\0'*33);struct.pack_into('>I',oversized,8,len(oversized)-12)
    reject('container-limit','bootstrap validation image header',lambda:image_members(bytes(oversized)))
    files=c.inventory(root/'seven-image-floor');missing=dict(files);missing.pop(next(n for n in files if n.endswith('.image')))
    reject('missing-image','maximum seven complete images',lambda:peak_usage(missing))
    extra=dict(files);extra['extra.image']=raw
    reject('eighth-image','maximum seven complete images',lambda:peak_usage(extra))
    short=dict(files);key=next(n for n in files if n.endswith('.image'));short[key]=raw[:-1]
    reject('short-image','maximum seven complete images',lambda:peak_usage(short))
    original=read(root/'receipt.json')
    for key,value in [('publicRuntime',True),('peakImages',6),('imageBytes',MAXIMUM),('administrationBytes',0)]:
        changed_receipt=dict(original,**{key:value})
        reject('receipt-'+key,'maximum receipt',lambda:receipt(changed_receipt,original['finalValueBytes']))
    return dict(**result,negativeCases=negative,negativeScope='original-first-component-mutations')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root),sort_keys=True))
