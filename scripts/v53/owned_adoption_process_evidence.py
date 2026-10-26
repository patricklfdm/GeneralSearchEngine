"""Native cross-view crashes against complete, independently replayed actual originals."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import admitted_adoption_process_evidence as a
from . import owned_cross_view_evidence as v

e=a.e;c=a.c


def validate(directory):
    root=Path(directory);a.selection.layout(root,{'reference','cases','inputs.json','receipt.json'},'owned adoption crash root')
    a.q.validate_case(root/'reference',4,False)
    original=c.inventory(root/'reference/slot-7-settled/node-4');final=c.inventory(root/'reference/removed-1-adopted/node-4')
    plan=a.t.plans.decode((root/'reference/original-plan.gsbp').read_bytes(),(root/'reference/original-application.image').read_bytes(),details=True,size=4,source='EMPTY')
    descriptor=plan['plan']['descriptor'];owner=a.target_paths(descriptor,'node-4');source=a.target_paths(descriptor,'node-1')
    inputs=v.load(root/'inputs.json',65536)
    v.same(inputs,dict(**owner,source=source['node'],sourceMaterialization=source['materialization']),'owned adoption exact paths without supplied history')
    a.selection.layout(root/'cases',{mode+'-'+cut for mode in ('halt','kill') for cut in a.CUTS},'owned adoption crash cases')
    rows=[];peaks=[]
    for mode in ('halt','kill'):
        for cut in a.CUTS:
            row,peak=a.validate_case(root/'cases',original,final,inputs,mode,cut);rows.append(row);peaks.append(peak)
    v.same(v.load(root/'receipt.json',65536),dict(schema='gse-v53-owned-adoption-process-v1',status='PASS',cases=rows,freshProcesses=114,
           lockProbes=19,historicalObservationsSupplied=False,publicRuntime=False,powerLoss=False),'owned adoption crash receipt')
    result=dict(status='PASS',cases=38,freshProcesses=114,lockProbes=19,peakImages=max(peaks),publicRuntime=False,powerLoss=False,originalFirst=True)
    return result,(original,final,inputs)


def qualify(directory):
    result,(original,final,inputs)=validate(directory);rows=[]
    mode='kill';cut='ADOPTION_INSTALL_FENCED';name=mode+'-'+cut
    variants={'first-journal':'admitted adoption exact first','second-selector':'admitted adoption exact second','final-extra':'admitted adoption exact final',
              'force':'context process exact force/death order','lock':'admitted adoption lock path','exit':'admitted adoption exact first exit'}
    for variant,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-native-adoption-negative-') as tmp:
            target=Path(tmp);case=target/name;shutil.copytree(Path(directory)/'cases'/name,case)
            if variant=='first-journal':(case/'first/grants.gsr').write_bytes(original['grants.gsr'])
            elif variant=='second-selector':(case/'second/selector.gsr').write_bytes(final['selector.gsr'])
            elif variant=='final-extra':(case/'final/extra').write_bytes(b'unowned')
            elif variant=='force':
                path=case/'fault.stdout';values=a.trace(path);values.pop(0);path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in values))
            elif variant=='lock':
                path=case/'lock.stdout';values=a.trace(path);values[0]['path']+='/changed';path.write_bytes(b''.join(e.f.canonical(r)+b'\n' for r in values))
            else:
                path=case/'fault.exit.json';value=v.load(path);value['exitCode']=0;path.write_bytes(e.f.canonical(value))
            try:a.validate_case(target,original,final,inputs,mode,cut)
            except ValueError as error:e.need(str(error)==reason,'owned adoption unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('owned adoption accepted negative: '+variant)
            rows.append(dict(case=variant,status='REJECTED',reason=reason))
    return dict(original=result,negatives=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');args=p.parse_args()
    print(json.dumps(qualify(args.directory) if args.qualify else validate(args.directory)[0],sort_keys=True))
