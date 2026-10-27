"""Native pending-context replay from actual bootstrap, phases and physical originals.

All stored histories are reconstructed before independent core-image decoding.
These internal histories do not qualify automatic elections or public operations.
"""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import covered_context_evidence as q
from . import offline_fixture_image as image
from .owned_cross_view_evidence import same

e=q.e;c=q.c
PROFILES=[(size,backup,phase) for size in (3,4,5) for backup in (False,True)
          for phase in ('ACCEPT','PROOF','CERTIFICATE') if phase=='CERTIFICATE' or (size==3 and not backup)]


def name(size,backup,phase):return f'{size}-'+('backup' if backup else 'empty')+'-'+phase


def images(root,size,backup,complete=True):
    root=Path(root);names=[f'node-{n}' for n in range(1,size+1)];majority=names[size-(size//2+1):]
    original=c.inventory(root/'round-1-settled/node-1');history=e.f.decode(original['root.gsr'],'records','ROOT')['historyId']
    base=41 if backup else 0;documents=[(7,'original'),(2,'你好')] if backup else []
    image.application(q.t.plans.read(root/'original-application.image',64*e.MIB),history,base,documents)
    for slot in range(1,5 if complete else 4):
        if slot==2:documents.append((303,'admitted-original'))
        if slot==3:documents.append((404,'majority-selected'))
        for node in majority if slot==3 else names:
            _,members,packet=c.current(c.inventory(root/f'slot-{slot}-settled'/node))
            sequence=base+(slot>=2)+(slot>=3)
            e.need(packet['capsule']['cut']['index']==slot,'native context image position')
            catalog=e.f.decode(packet['objects'][packet['capsule']['catalog']],'records','CATALOG')
            e.need(catalog['applicationSequence']==sequence,'native context image sequence')
            image.application(members[packet['capsule']['application']+'.image'],history,sequence,documents)


def profile(root,size,backup,phase, *, selected_prefix=None):
    result=q.clean(root,2,selected_prefix=selected_prefix)
    same({k:result[k] for k in ('size','backup','phase')},dict(size=size,backup=backup,phase=phase),'native context original profile')
    images(root,size,backup)
    return result


def validate(directory, *, selected_prefix=None):
    root=Path(directory);q.b.selection.layout(root,{name(*p) for p in PROFILES}|{'receipt.json'},'native context profiles')
    rows=[];publications=0;peaks=[];histories=set()
    for size,backup,phase in PROFILES:
        label=name(size,backup,phase);raw=root/label;result=profile(raw,size,backup,phase,selected_prefix=selected_prefix)
        original=c.inventory(raw/'round-1-settled/node-1');history=e.f.decode(original['root.gsr'],'records','ROOT')['historyId']
        e.need(history not in histories,'native context reused history');histories.add(history)
        rows.append(dict(case=label,status='PASS',size=size,backup=backup,phase=phase))
        publications+=result['nodePublications'];peaks.append(result['peakPhysicalImages'])
    same(q.read(root/'receipt.json'),dict(schema='gse-v53-owned-context-profiles-v1',status='PASS',cases=rows,
         historicalObservationsSupplied=False,publicRuntime=False),'native context receipt')
    return dict(status='PASS',profiles=len(rows),nodePublications=publications,peakPhysicalImages=max(peaks),independentImageSemantics=True,publicRuntime=False)


VARIANTS={
    'original-context':('contexts/node-1/pending.context','admitted exact contexts: node-1'),
    'retired-backing':('original-retired/node-1/grants.gsr','admitted exact original-retired: node-1'),
    'rebound-context':('round-4-prepared/node-1/pending.context','admitted exact round-4-prepared: node-1'),
    'covered-vote':('covered-installed/node-1/pending.accept','admitted exact covered-installed: node-1'),
    'retained-source':('round-5-installed/node-1/grants.gsr','admitted exact round-5-installed: node-1'),
    'final-image':('slot-4-settled/node-1/selector.gsr','admitted exact slot-4-settled: node-1'),
}


def qualify(directory, *, selected_prefix=None):
    original=validate(directory,selected_prefix=selected_prefix);results=[];sample=Path(directory)/name(3,False,'CERTIFICATE')
    for variant,(path,reason) in VARIANTS.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-context-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(sample,target);(target/path).write_bytes(b'changed')
            try:profile(target,3,False,'CERTIFICATE',selected_prefix=selected_prefix)
            except ValueError as error:e.need(reason in str(error),'native context unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('native context accepted negative: '+variant)
            results.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');p.add_argument('--reachable-selection',action='store_true');a=p.parse_args()
    from .selected_prefix_evidence import prefix
    print(json.dumps((qualify if a.qualify else validate)(a.directory,selected_prefix=prefix if a.reachable_selection else None),sort_keys=True))
