"""All six admitted initial profiles through covered bare-vote settlement."""
import argparse
import json
import shutil
import tempfile
import uuid
from pathlib import Path
from . import covered_minority_evidence as model

e=model.e;c=model.c;t=model.t;selection=model.selection


def validate(root):
    root=Path(root);names={f'size-{n}-{s}' for n in (3,4,5) for s in ('empty','backup')};selection.layout(root,names|{'receipt.json'},'covered profiles')
    receipt=e.parse(t.plans.read(root/'receipt.json',65536));e.exact(receipt,'schema status cases publicBootstrap freshProcesses publicRuntime')
    expected=dict(schema='gse-v53-covered-minority-profiles-v1',status='PASS',cases=receipt['cases'],publicBootstrap=True,freshProcesses=False,publicRuntime=False)
    e.need(e.f.canonical(receipt)==e.f.canonical(expected),'covered profiles receipt scope')
    e.need(type(receipt['cases']) is list and len(receipt['cases'])==6,'covered profiles complete receipt');histories=set();ordinal=0
    for size in (3,4,5):
        for backup in (False,True):
            name=f"size-{size}-{'backup' if backup else 'empty'}";path=root/name;model.clean(path,size,backup)
            history=e.f.decode((path/'initial/target-0/root.gsr').read_bytes(),'records','ROOT')['historyId']
            e.need(uuid.UUID(history).version==4 and history not in histories,'covered profiles distinct histories');histories.add(history)
            row=receipt['cases'][ordinal];ordinal+=1;e.exact(row,'case status voters minority nodePublications peakImages sequence')
            e.need(type(row['peakImages']) is int and 0<row['peakImages']<=7,'covered profiles image bound')
            wanted=dict(case=name,status='PASS',voters=size,minority=size-(size//2+1),nodePublications=size+size//2+1,peakImages=row['peakImages'],sequence=42 if backup else 1)
            e.need(e.f.canonical(row)==e.f.canonical(wanted),'covered profiles exact receipt row')
    return dict(status='PASS',cases=6,voters=24,minorityVotes=8,nodePublications=40,publicBootstrap=True,freshProcesses=False,publicRuntime=False,maximalCapacity=False,independentImageSemantics=False)


VARIANTS={
    'missing-profile':'context selection covered profiles inventory',
    'numeric-flag':'covered profiles receipt scope',
    'profile-count':'covered profiles complete receipt',
    'backup-sequence':'covered profiles exact receipt row',
    'capacity':'covered profiles image bound',
    'backup-original':'admitted original public bootstrap',
    'second-minority-vote':'admitted exact minority-accepted: node-2',
    'second-minority-early-clear':'admitted exact before-install: node-2',
    'second-minority-uncleared':'admitted exact round-4-installed: node-2',
    'second-minority-source':'admitted exact round-4-settled: node-2',
    'second-minority-force':'covered exact settlement force order',
    'majority-proof':'admitted exact slot-1-proved: node-3',
    'unselected-minority':'admitted exact slot-1-published: node-2',
    'published-application':'admitted exact slot-1-applied: node-4',
    'old-generation':'admitted exact round-4-installed: node-2',
    'observations':'covered actual owner observations',
    'backup-inspection':'admitted exact typed inspection image',
}


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    for name,reason in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-covered-profiles-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'size-5-backup'
            if name=='missing-profile':shutil.rmtree(moved/'size-4-empty')
            elif name in ('numeric-flag','profile-count','backup-sequence','capacity'):
                path=moved/'receipt.json';rows=e.parse(path.read_bytes())
                if name=='numeric-flag':rows['freshProcesses']=0
                elif name=='profile-count':rows['cases'].pop()
                elif name=='backup-sequence':rows['cases'][1]['sequence']=1
                else:rows['cases'][0]['peakImages']=8
                path.write_bytes(e.f.canonical(rows))
            elif name=='backup-original':(case/'initial/target-0/bootstrap-seal.gsbp').write_bytes(b'changed')
            elif name=='second-minority-vote':(case/'minority-accepted/node-2/pending.accept').write_bytes(c.EMPTY)
            elif name=='second-minority-early-clear':(case/'before-install/node-2/pending.accept').write_bytes(c.EMPTY)
            elif name=='second-minority-uncleared':(case/'round-4-installed/node-2/pending.accept').write_bytes((case/'before-install/node-2/pending.accept').read_bytes())
            elif name=='second-minority-source':next((case/'round-4-settled/node-2/sources').glob('*/source.gscp')).unlink()
            elif name=='second-minority-force':
                path=case/'calls.json';rows=e.parse(path.read_bytes());next(row['events'] for row in rows if row['node']=='node-2' and row['operation']=='install-4').remove('SETTLED_VOTE_PARENT_FORCED');path.write_bytes(e.f.canonical(rows))
            elif name=='majority-proof':(case/'slot-1-proved/node-3/pending.accept').write_bytes((case/'slot-1-accepted/node-3/pending.accept').read_bytes())
            elif name=='unselected-minority':(case/'slot-1-published/node-2/pending.accept').write_bytes(c.EMPTY)
            elif name=='published-application':(case/'slot-1-applied/node-4/applied-end/application.image').write_bytes(b'changed')
            elif name=='old-generation':
                prefix=c.current(c.inventory(case/'before-install/node-2'))[0];shutil.rmtree(case/'round-4-installed/node-2'/prefix)
            elif name=='observations':
                path=case/'observations.json';rows=e.parse(path.read_bytes());rows.pop();path.write_bytes(e.f.canonical(rows))
            elif name=='backup-inspection':(case/'typed-2-node-5/gse-backup-checkpoint').write_bytes(b'changed')
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong covered profile rejection: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted covered profile mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-covered-profiles-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'covered profiles portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
