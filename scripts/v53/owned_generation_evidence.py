"""Original-publication replay for exclusive-owner selected-history reopening.

Rebuild actual original force/certificate/ancestry state before checking the fresh
reader outputs. Neither a reader's PASS nor its claimed hashes establish history.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import bootstrap_publication_evidence as b
e=b.e;c=b.c


def load(path):
    return json.loads(b.t.plans.read(path,65536))


def publication(root,size,extra):
    names={f'node-{n}' for n in range(1,size+1)}
    expected={'original-plan.gsbp','original-application.image','initial'} | set(extra)
    expected|={f'round-1-{stage}' for stage in ('prepared','selected','installed','settled')}
    expected|={f'slot-{slot}-{stage}' for slot in (1,2) for stage in ('accepted','proved','certified','applied','published','settled')}
    expected|={f'typed-{slot}-{node}' for slot in (1,2) for node in names}
    expected|={f'{kind}-{slot}.{ext}' for slot in (1,2) for kind,ext in (('entry','gsr'),('payload','bin'))}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}==expected,'owned generation case inventory')
    group=b.campaign(root,b.original(root,size,False),1);first=None;observations=[]
    for slot in (1,2):
        group,first=b.publication(root,group,slot,first,observations)
        for node,files in group.items():
            _,members,packet=c.current(files)
            b.typed_image(root/f'typed-{slot}-{node}',members[packet['capsule']['application']+'.image'])
    return group


def reader(files):
    prefix,members,packet=c.current(files)
    return dict(status='PASS',cut=packet['capsule']['cut'],packet=e.digest(members['source.gscp']),
                manifest=e.digest(files[prefix+'generation.gsr']),ancestry=e.digest(members.get('ancestry.gsr',b'')),
                images=[dict(digest=h,actual=h) for h in sorted(packet['images'])],copiedObservations=0)


def case(root,size):
    group=publication(root,size,{'before-read','after-read','reads.json'}|{f'read-{n}.log' for n in range(1,size+1)})
    b.match(root,'before-read',group);b.match(root,'after-read',group)
    receipts=[]
    for number,node in enumerate(sorted(group),1):
        expected=reader(group[node])
        e.need(load(root/f'read-{number}.log')==expected,'owned generation original reader output: '+node)
        receipts.append(expected)
    e.need(load(root/'reads.json')==receipts,'owned generation reader inventory')
    return dict(size=size,freshReaders=size)


CUTS=('CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED')


def validate_crashes(directory):
    root=Path(directory);extra={'before-read','cases.json'}
    for mode in ('halt','kill'):
        for cut in CUTS:
            label=mode+'-'+cut
            extra|={label+'.log','death-'+label,'recovered-'+label,'recovered-'+label+'.log'}
    group=publication(root,3,extra);b.match(root,'before-read',group);expected=[]
    for mode in ('halt','kill'):
        for cut in CUTS:
            label=mode+'-'+cut
            e.need(b.t.plans.read(root/(label+'.log'),65536)==('CUT '+cut+'\n').encode(),'owned generation crash cut')
            b.match(root,'death-'+label,group);b.match(root,'recovered-'+label,group)
            e.need(load(root/('recovered-'+label+'.log'))==reader(group['node-1']),'owned generation recovered reader')
            expected.append(dict(mode=mode,cut=cut,exit=23 if mode=='halt' else 137))
    e.need(load(root/'cases.json')==expected,'owned generation crash outcomes')
    return dict(status='PASS',cases=expected,powerLoss=False,scope='selected-history-reseal-process-death')


def qualify_crashes(directory):
    original=validate_crashes(directory);negatives=[]
    variants=[('cut','owned generation crash cut'),('death','admitted exact death-halt-CURRENT_VALIDATED'),
              ('recovery','owned generation recovered reader'),('exit','owned generation crash outcomes')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-owned-history-crash-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target)
            if name=='cut':(target/'halt-CURRENT_VALIDATED.log').write_text('CUT WRONG\n')
            elif name=='death':(target/'death-halt-CURRENT_VALIDATED/node-1/grants.gsr').write_bytes(b'changed')
            elif name=='recovery':(target/'recovered-halt-CURRENT_VALIDATED.log').write_text('{}')
            else:
                path=target/'cases.json';value=load(path);value[0]['exit']=0;path.write_text(json.dumps(value))
            try:validate_crashes(target)
            except ValueError as error:e.need(reason in str(error),'owned generation unrelated crash negative: '+name+': '+str(error))
            else:raise ValueError('owned generation accepted crash negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


def validate(directory):
    root=Path(directory)
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={'receipt.json','stable-3','stable-4','stable-5'},'owned generation complete inventory')
    cases=[case(root/f'stable-{n}',n) for n in (3,4,5)]
    expected=dict(schema='gse-v53-owned-generation-v1',status='PASS',cases=cases,scope='owned-selected-history-reopen',publicRuntime=False,freshVotes=False)
    e.need(load(root/'receipt.json')==expected,'owned generation scope/receipt')
    return expected


def qualify(directory):
    original=validate(directory);negatives=[]
    variants=[('scope','owned generation scope/receipt'),('missing-profile','owned generation complete inventory'),
              ('before','admitted exact before-read'),('after','admitted exact after-read'),
              ('selection','admitted exact round-1-selected'),('certificate','admitted exact slot-2-certified'),
              ('packet','owned generation original reader output'),('cut','owned generation original reader output'),
              ('manifest','owned generation original reader output'),('ancestry','owned generation original reader output'),
              ('images','owned generation original reader output'),('fresh-votes','owned generation original reader output'),
              ('reader-inventory','owned generation reader inventory')]
    for name,reason in variants:
        with tempfile.TemporaryDirectory(prefix='v53-owned-history-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(directory,target);root=target/'stable-3'
            if name=='scope':
                path=target/'receipt.json';value=load(path);value['freshVotes']=True;path.write_text(json.dumps(value))
            elif name=='missing-profile':shutil.rmtree(target/'stable-5')
            elif name in ('before','after','selection','certificate'):
                stage={'before':'before-read','after':'after-read','selection':'round-1-selected','certificate':'slot-2-certified'}[name]
                (root/stage/'node-1/grants.gsr').write_bytes(b'changed')
            elif name=='reader-inventory':(root/'reads.json').write_text('[]')
            else:
                path=root/'read-1.log';value=load(path)
                if name=='cut':value['cut']['index']+=1
                elif name=='images':value['images']={}
                elif name=='fresh-votes':value['copiedObservations']=1
                else:value[name]='a'*64
                path.write_text(json.dumps(value))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'owned generation unrelated negative: '+name+': '+str(error))
            else:raise ValueError('owned generation accepted negative: '+name)
            negatives.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=negatives)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');p.add_argument('--crashes',action='store_true');a=p.parse_args()
    check=(qualify_crashes if a.qualify else validate_crashes) if a.crashes else (qualify if a.qualify else validate)
    print(json.dumps(check(a.directory),sort_keys=True))
