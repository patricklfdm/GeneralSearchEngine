"""One complete 3-REPLACE history with FINAL adoption then same-view installation.

This checks the original semantic boundaries and selected receipt, not complete
physical maintenance, ancestry, transfer authorization or force qualification.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import joining_completion_evidence as complete
from . import joining_initialization_evidence as initialization
from . import joining_snapshot as snapshot

c,need=complete.c,complete.need
f,disk,sha=c.f,c.disk,c.sha
PROFILE='3-REPLACE'
EXTRA_NEGATIVES={
    'prefix-skipped':'joining same-view exact FINAL adoption',
    'prefix-claims-install':'joining same-view exact FINAL adoption',
    'prefix-promotes-ready':'joining same-view exact FINAL adoption',
    'recovery-before-JOINT':'joining same-view exact BARRIER installation',
    'recovery-claims-adoption':'joining same-view exact BARRIER installation',
    'recovery-promotes-ready':'joining same-view exact BARRIER installation',
    'selection-wrong-cut':'joining same-view original selection',
    'selection-wrong-proposer':'joining same-view original selection',
}
NEGATIVES={**complete.NEGATIVES,**EXTRA_NEGATIVES}


def boundaries(root,replay):
    root=Path(root);cuts=[replay.states[i]['cut'] for i in (9,10,11)]
    need(cuts[0]['view']!=cuts[1]['view']==cuts[2]['view'],'joining same-view derived authority change')
    prefix=c.collection.read_json(root,'joining-final-prefix.json',8192)
    need(prefix==dict(before=cuts[0],after=cuts[1],adopted=True,installed=False,publicReady=False),
         'joining same-view exact FINAL adoption')
    recovered=c.collection.read_json(root,'joining-final-recovery.json',8192)
    need(recovered==dict(before=cuts[1],after=cuts[2],adopted=False,installed=True,publicReady=False),
         'joining same-view exact BARRIER installation')
    identity=c.catalog.identities(replay.states[-1]['identities'])[replay.joining]
    originals={}
    for label,index in (('joining-before-final-prefix',9),('joining-after-final-prefix',10),
                        ('joining-before-final-recovery',10),('joining-after-final-recovery',11)):
        snap=c.joining.read(root/label);files=disk.inventory(snap.root/'replica');_,members,packet=disk.current(files)
        need(files['root.gsr']==replay.root_bytes and
             f.decode(files['node.gsr'],'records','NODE',replay.root)['identity']==identity and
             packet['capsule']['cut']==replay.states[index]['cut'],'joining same-view original boundary')
        replay.packet(packet,index);originals[label]=files
    raw=snapshot.s.regular(root/'joining-final-recovery-selection.gsr',65536)
    selected=f.decode(raw,'records','SELECTED',replay.root)
    ballot=initialization.next_ballot(originals['joining-before-final-recovery'])
    need(selected['root']==replay.root and selected['view']==c.catalog.authority(replay.root,cuts[1]['view']) and
         selected['ballot']==ballot and ballot['proposer']==replay.joining and
         selected['cut']==cuts[2] and selected['nextEntry'] is None,'joining same-view original selection')
    names=[v['voter'] for v in selected['sources']];c.catalog.majority(cuts[2]['view'],names)
    need(replay.joining in names and set(names)<=set(replay.targets),'joining same-view selected original owners')
    members=disk.current(originals['joining-after-final-recovery'])[1]
    need(members['selected.gsr']==raw,'joining same-view installed selection')
    return dict(fromCut=10,toCut=11,proposer=replay.joining,selectedVoters=names,selectionSha256=sha(raw),
                adoptedAtFinal=True,installedAtBarrier=True,publicReady=False)


def validate(root,profile):
    need(profile==PROFILE,'joining same-view declared profile');root=Path(root);before=c.collection.inventory(root)
    original=complete.validate(root,profile);replay=c.Replay(root,size=3,kind='REPLACE')
    for index in range(1,12):replay.step(index)
    result=boundaries(root,replay)
    need(c.collection.inventory(root)==before,'joining same-view original changed')
    return dict(original,sameViewSemanticQualified=True,sameViewRecovery=result,sameViewPhysicalQualified=False)


def mutate(root,name,profile=PROFILE):
    root=Path(root)
    if name in complete.NEGATIVES:complete.mutate(root,name,profile);return
    if name.startswith('selection-'):
        path=root/'joining-final-recovery-selection.gsr';value=f.decode(path.read_bytes(),'records','SELECTED')
        if name=='selection-wrong-cut':value['cut']['index']=10
        else:value['ballot']['proposer']='node-1'
        path.write_bytes(f.encode('records','SELECTED',value));return
    path=root/('joining-final-prefix.json' if name.startswith('prefix-') else 'joining-final-recovery.json')
    value=json.loads(path.read_bytes())
    if name=='prefix-skipped':value['adopted']=False
    elif name=='prefix-claims-install':value['installed']=True
    elif name=='recovery-before-JOINT':value['before']['index']=9
    elif name=='recovery-claims-adoption':value.update(adopted=True,installed=False)
    elif name.endswith('promotes-ready'):value['publicReady']=True
    else:raise ValueError('unknown same-view semantic mutation: '+name)
    path.write_bytes(f.canonical(value))


def qualify(root,profile):
    root=Path(root);original=validate(root,profile);before=c.collection.inventory(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-same-view-semantic-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,name,profile)
            try:validate(changed,profile)
            except ValueError as error:need(str(error)==reason,'joining same-view unrelated negative: '+name+': '+str(error))
            else:raise ValueError('joining same-view accepted mutation: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(c.collection.inventory(root)==before,'joining same-view qualification changed original')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('--profile',required=True,choices=(PROFILE,))
    p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps((qualify if a.qualify else validate)(a.root,a.profile),sort_keys=True))
