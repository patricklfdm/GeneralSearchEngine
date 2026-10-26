"""Fresh native-owner crash replay without supplied historical vote observations."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import covered_context_process_evidence as p
from . import owned_context_evidence as q

e=p.e;c=p.c


def validate(directory):
    root=Path(directory);p.selection.layout(root,{'reference','inputs.json','receipt.json'}|
                     {mode+'-'+cut for mode in ('halt','kill') for cut in p.CUTS},'native context process')
    initial,installed=p.original(root/'reference',2);q.images(root/'reference',3,False,False)
    raw=p.t.plans.read(root/'inputs.json',e.MIB);inputs=e.parse(raw);e.exact(inputs,'targets')
    plan=p.t.plans.decode(p.t.plans.read(root/'reference/original-plan.gsbp',2*e.MIB),
                         p.t.plans.read(root/'reference/original-application.image',64*e.MIB),details=True,size=3,source='EMPTY')
    paths=plan['plan']['descriptor']['paths'];targets=[dict(node=paths[1+2*i]['path'],materialization=paths[2+2*i]['path']) for i in range(3)]
    p.same(inputs,dict(targets=targets),'native context process exact inputs')
    results,peaks=p.validate_cases(root,initial,installed,targets)
    p.same(p.read(root/'receipt.json'),dict(schema='gse-v53-owned-context-process-v1',status='PASS',cases=results,
           freshProcesses=66,lockProbes=11,inputsSha256=e.digest(raw),publicBootstrap=True,powerLoss=False,runtimeEnabled=False),'native context process receipt')
    return dict(status='PASS',cases=22,freshProcesses=66,lockProbes=11,peakImages=max(peaks),originalFirst=True,
                historicalObservationsSupplied=False,independentImageSemantics=True,publicRuntime=False,powerLoss=False)


def qualify(directory):
    original=validate(directory);results=[]
    variants={'scope':'native context process receipt','inputs':'native context process exact inputs',
              'context':'context process exact first snapshot','vote':'context process exact second snapshot',
              'source':'context process exact final snapshot','force':'context process exact force/death order',
              'exit':'context process exact first exit','lock':'context process lock probe'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-context-process-negative-') as temp:
            root=Path(temp)/'raw';shutil.copytree(directory,root);case=root/'kill-CONTEXT_SETTLEMENT_VALIDATED'
            if name=='scope':
                path=root/'receipt.json';value=p.read(path);value['runtimeEnabled']=True;path.write_bytes(e.f.canonical(value))
            elif name=='inputs':
                path=root/'inputs.json';value=p.read(path);value['targets'][0]['node']+='/foreign';path.write_bytes(e.f.canonical(value))
            elif name=='context':(case/'first/pending.context').unlink()
            elif name=='vote':(case/'second/pending.accept').write_bytes(b'changed')
            elif name=='source':next((case/'final/sources').glob('*/source.gscp')).unlink()
            elif name=='force':
                path=case/'fault.stdout';rows=p.trace(path);rows.pop(0);path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in rows))
            elif name=='exit':
                path=case/'fault.exit.json';value=p.read(path);value['exitCode']=0;path.write_bytes(e.f.canonical(value))
            elif name=='lock':
                path=case/'lock.stdout';rows=p.trace(path);rows[0]['path']+='/foreign';path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in rows))
            try:validate(root)
            except ValueError as error:e.need(str(error)==reason,'native context process unrelated negative: '+name+': '+str(error))
            else:raise ValueError('native context process accepted negative: '+name)
            results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__=='__main__':
    p0=argparse.ArgumentParser();p0.add_argument('directory');p0.add_argument('--qualify',action='store_true');a=p0.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
