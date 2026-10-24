"""Three-owner publication after six protected installations and reclamations."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import context_installation_lifetime_evidence as lifetime

selection=lifetime.selection
e,owner,source=lifetime.e,lifetime.owner,lifetime.source
carried=selection.publication.carried
NODES=selection.NODES


def reclaim(before,reference):
    result={}
    for node,files in before.items():
        original=(reference/'reference/carried-snapshots/source-retired'/node/'pending.context').read_bytes()
        old=e.f.decode(e.decode(original)[0][3],'records','BASIS')
        rows=owner.journal(files['grants.gsr'],old['root'],node)
        selected=e.f.decode(carried.current(files)[1]['selected.gsr'],'records','SELECTED')
        e.need(old['ballot']['counter']==21 and selected['ballot']['counter']==27 and selected['cut']['index']==1,
               'installed publication covered source identity')
        prefix='sources/'+old['basisId']
        packet=e.p.decode(files[prefix+'/source.gscp']);e.p.bind(packet,e.decode(original)[0][3])
        current=carried.current(files)[2]['capsule']
        e.need(packet['capsule']['cut']['index']<current['cut']['index']==2,'installed publication covered source cut')
        result[node]={k:v for k,v in files.items() if k!=prefix and not k.startswith(prefix+'/')}
        result[node]['grants.gsr']=b''.join(raw for _,raw,value in rows if value['ballot']!=old['ballot'])
    return result


def snapshot(path,expected,label):
    selection.layout(path,NODES,'installed publication owners')
    for node,value in expected.items():
        e.need(carried.inventory(path/node)==value,'installed publication exact '+label)


def fresh(root,before):
    projected={}
    for node,files in before.items():
        _,members,packet=carried.current(files);cap=packet['capsule']
        previous=owner.journal(files['grants.gsr'],cap['root'],node)
        actual=carried.inventory(root/'carried-snapshots/fresh'/node)
        rows=owner.journal(actual['grants.gsr'],cap['root'],node)
        e.need(len(previous)==3 and rows[:3]==previous and [v[0] for v in rows[3:]]==['PROMISE','BASIS'],
               'installed publication fresh original groups')
        promise,basis=rows[-2:]
        ballot=dict(previous[0][2]['ballot'],counter=28)
        e.need(promise[2]==dict(previous[0][2],ballot=ballot,basisId=promise[2]['basisId'])
               and promise[2]['basisId']!=previous[0][2]['basisId'],'installed publication fresh promise')
        e.need(basis[2]==dict(promise[2],voter=node,cut=cap['cut'],capsule=e.digest(packet['capsuleBytes']),
                             inventory=e.digest(packet['indexBytes']),accepted=None),'installed publication empty fresh tail')
        prefix='sources/'+basis[2]['basisId']
        projected[node]=dict(files,**{'grants.gsr':b''.join(row[1] for row in rows),prefix:None,prefix+'/source.gscp':members['source.gscp']},
                             **{prefix+'/'+h+'.image':members[h+'.image'] for h in packet['images']})
    snapshot(root/'carried-snapshots/fresh',projected,'fresh')


def validate(root):
    root=Path(root);selection.layout(root,{'reference','originals','carried-snapshots','receipt.json'},'installed publication')
    selection.layout(root/'originals',{'slot-2','slot-3'},'installed publication originals')
    for slot in ('slot-2','slot-3'):selection.layout(root/'originals'/slot,NODES,'installed publication original owners')
    selection.layout(root/'carried-snapshots',{'published','reclaimed','continued','fresh'},'installed publication stages')
    lifetime.validate(root/'reference')
    before={n:carried.inventory(root/'reference/accepted'/n) for n in NODES}
    published,first=carried.publication(root,2,before,None)
    reclaimed=reclaim(published,root/'reference');snapshot(root/'carried-snapshots/reclaimed',reclaimed,'source reclamation')
    continued,_=carried.publication(root,3,reclaimed,first)
    for files in continued.values():
        e.need(sum(n.endswith('.image') for n in files)==2 and sum(n.startswith('sources/') and n.endswith('source.gscp') for n in files)==1,
               'installed publication steady inventory')
    fresh(root,continued)
    e.need(source.load(root/'receipt.json')==dict(schema='gse-v53-context-installed-publication-v1',status='PASS',nodes=3,
           entryOrigin=20,acceptBallot=27,publishedCut=3,applicationSequence=43,freshBallot=28,freshProcesses=False,runtimeEnabled=False),
           'installed publication receipt scope')
    return dict(status='PASS',nodes=3,nodePublications=6,entryOrigin=20,acceptBallot=27,publishedCut=3,applicationSequence=43,freshBallot=28,
                originalFirst=True,physicalBytes=True,typedImageSemantics='separate-core-producer',historicalBootstrap='conditional-fixture',
                freshProcesses=False,powerLoss=False,runtimeEnabled=False,maximalCapacity=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'original':'context publication exact source-retired: node-1','missing':'context selection installed publication inventory',
              'published':'carried exact publication/retirement bytes','reclaimed':'installed publication exact source reclamation',
              'continued':'carried exact publication/retirement bytes','fresh':'installed publication exact fresh',
              'ack':'carried original applied ends','origin':'carried first/subsequent origin',
              'tail':'installed publication empty fresh tail','source':'installed publication exact source reclamation',
              'scope':'installed publication receipt scope'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-installed-publication-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved)
            if name=='original':(moved/'reference/reference/carried-snapshots/source-retired/node-1/pending.accept').write_bytes(b'changed')
            elif name=='missing':shutil.rmtree(moved/'reference')
            elif name in ('published','reclaimed','continued','fresh'):(moved/'carried-snapshots'/name/'node-1/allocator.gsr').write_bytes(b'changed')
            elif name=='ack':(moved/'originals/slot-2/node-1/applied-end/ack.gsr').write_bytes(b'changed')
            elif name=='origin':
                path=moved/'originals/slot-3/node-1/pending.accept';frames,values=carried.pending(path.read_bytes(),('PROOF','CERTIFICATE'))
                frames['ENTRY']=e.f.encode('records','ENTRY',dict(values['ENTRY'],origin=dict(values['ENTRY']['origin'],counter=21)))
                first=e.container([frames[k] for k in ('SELECTOR','PROMISE','SELECTED','ENTRY','ACCEPT')],frames['PAYLOAD'])
                body=first[12:]+frames['PROOF']+frames['CERTIFICATE']
                path.write_bytes(struct.pack('>4sHHI',b'GSPV',1,3,12+len(body))+body)
            elif name=='tail':
                path=moved/'carried-snapshots/fresh/node-1/grants.gsr';rows=owner.journal(path.read_bytes(),result_root(moved),'node-1')
                path.write_bytes(b''.join(r[1] for r in rows[:-1])+e.f.encode('records','BASIS',dict(rows[-1][2],accepted='0'*64)))
            elif name=='source':next((moved/'carried-snapshots/reclaimed/node-1/sources').glob('*/source.gscp')).unlink()
            else:
                path=moved/'receipt.json';value=source.load(path);value['freshProcesses']=True;path.write_bytes(e.f.canonical(value))
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong installed publication negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted installed publication mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-installed-publication-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'installed publication portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


def result_root(root):
    return e.f.decode((root/'carried-snapshots/fresh/node-1/node.gsr').read_bytes(),'records','NODE')['root']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
