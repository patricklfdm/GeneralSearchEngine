"""Original-first mutation checks; replay immutable original authority before cases."""
from pathlib import Path
import shutil
import tempfile
from . import selection_evidence as e
from . import capsule_evidence as caps
from . import source_packet as p
from . import format_fixture as f
from .context_evidence import parse,sha
from .membership_model import need

CASES=('wrong-longest','wrong-tail','original-basis-digest','missing-proposer','duplicate-source',
       'missing-basis-force','basis-before-tail','wrong-parent','missing-bridge','wrong-bridge-catalog',
       'missing-bridge-force','runtime-relabel','linked-source')


def mutate(root,case):
    path=root/'selected.bin'; selected=f.decode(path.read_bytes(),'records','SELECTED')
    manifest=parse((root/'manifest.json').read_bytes())
    if case=='wrong-longest': selected['cut']['index']-=1
    elif case=='wrong-tail': selected['nextEntry']='fa'*32
    elif case=='original-basis-digest': selected['sources'][0]['basisDigest']='fa'*32
    elif case=='missing-proposer': selected['sources'].pop(0)
    elif case=='duplicate-source': selected['sources'][1]=selected['sources'][0]
    elif case in ('missing-basis-force','missing-bridge-force'):
        name='sources/node-1/basis.bin' if case=='missing-basis-force' else 'bridge/node-1.bin'
        manifest['forces']=[v for v in manifest['forces'] if v['path']!=name]
    elif case=='basis-before-tail':
        events=manifest['forces'];a=next(i for i,v in enumerate(events) if v['path']=='sources/node-1/accepted.bin');b=next(i for i,v in enumerate(events) if v['path']=='sources/node-1/basis.bin');events[a],events[b]=events[b],events[a]
    elif case=='wrong-parent':
        name='sources/node-1/parent.json';value=parse((root/name).read_bytes());value['cut']['index']-=1;data=f.canonical(value);(root/name).write_bytes(data)
        next(v for v in manifest['forces'] if v['path']==name)['sha256']=sha(data)
    elif case=='missing-bridge': (root/'bridge/statement.bin').unlink()
    elif case=='wrong-bridge-catalog':
        path2=root/'bridge/statement.bin';value=f.decode(path2.read_bytes(),'records','CHECKPOINT');value['catalogBefore']='fa'*32;path2.write_bytes(f.encode('records','CHECKPOINT',value))
    elif case=='runtime-relabel':manifest['runtimeEnabled']=True
    elif case=='linked-source':
        path2=root/'sources/node-1/packet.bin';path2.unlink();path2.symlink_to(root/'sources/node-2/packet.bin')
    else: raise ValueError('unknown selection negative')
    for i,v in enumerate(manifest['forces'],1):v['sequence']=i
    path.write_bytes(f.encode('records','SELECTED',selected));(root/'manifest.json').write_bytes(f.canonical(manifest))


def run(original):
    original=Path(original).resolve();expected=e.validate(original);results=[]
    sources=caps.source(original/'baseline/source');profile='5-REPLACE'
    baseline={i:p.decode((original/'baseline/capsules'/profile/('cut-'+str(i))/'packet.bin').read_bytes()) for i in range(10)}
    with tempfile.TemporaryDirectory(prefix='v53-selection-negatives-') as temp:
        copied=Path(temp)/'relocated';shutil.copytree(original,copied);need(e.validate(copied)==expected,'portable selection replay')
        for case in CASES:
            scenario='highest-tail' if case=='basis-before-tail' else 'heterogeneous'
            target=Path(temp)/case;shutil.copytree(original/'selections'/profile/scenario,target);mutate(target,case)
            try:e.validate_case(target,profile,scenario,sources[profile],baseline)
            except ValueError as error:results.append(dict(case=case,status='REJECT',reason=str(error)))
            else:raise ValueError('accepted selection negative: '+case)
    need(tuple(r['case'] for r in results)==CASES,'selection negative inventory');return results
