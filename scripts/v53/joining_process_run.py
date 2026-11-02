"""Capture one whole joining initialization crash and original transition.

Collection only checks original process observations. Independent physical and
network/process composition is still required before accepting a member.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import joining_profile_evidence as profiles
from . import remove_process_matrix as metadata
from . import process_toolchain

CLASS=h.CLASS
METHOD='joiningRetentionResumesAfterNativeProcessDeathThenCompletesFinal'
POINTS=tuple('JOINING_RETENTION_'+part+'_'+cut for part in ('SEED','PEERS','FUTURE','LEARNER','DONE')
             for cut in ('CREATED','PREFIX_WRITTEN','WRITTEN','FORCED','CANDIDATE_PARENT_FORCED','RENAMED','PARENT_FORCED'))+('JOINING_RETENTION_BEFORE_RETURN',)
CASES=tuple(','.join((profile,point,mode)) for profile in profiles.PROFILES for point in POINTS for mode in ('halt','kill'))
SCHEMA='gse-v53-joining-process-execution-v1'
BUILDS=('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')


def selected(case):
    h.need(type(case) is str and case in CASES,'joining process exact case')
    profile,point,mode=case.split(',');return dict(profile=profile,point=point,mode=mode)


def command(case):
    value=selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHOD,
            '-Dv53.joining.profile='+value['profile'],'-Dv53.joining.process='+value['point']+','+value['mode'],'test']


def junit(reports,case):
    selected(case);paths=sorted(reports.glob('TEST-*.xml'))
    h.need(len(paths)==1,'joining process exact report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));cases=suite.findall('testcase')
    h.need(suite.get('name')==CLASS and suite.get('tests')=='1' and len(cases)==1 and
           all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
           cases[0].get('classname')==CLASS and cases[0].get('name')==METHOD and
           not any(v.tag in {'failure','error','skipped'} or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
           'joining process exact passing unretried test')
    return dict(className=CLASS,method=METHOD,tests=1,failures=0,errors=0,skipped=0,retries=0)


def lines(path):
    raw=h.snapshot.s.regular(path,64*h.snapshot.MIB)
    h.need(raw and raw.endswith(b'\n'),'joining process complete original lines')
    rows=raw.splitlines();h.need(len(rows)<=65536 and all(rows),'joining process line capacity')
    parsed=[]
    for row in rows:
        value=h.snapshot.s.e.parse(row)
        h.need(row==h.snapshot.f.canonical(value),'joining process canonical original line');parsed.append(value)
    return parsed


def collect(raw,case):
    expected=selected(case);raw=Path(raw);before=h.inventory(raw);area=raw/'joining-process'
    h.need({v.name for v in area.iterdir()}=={'spec.json','result.json',expected['mode'],'resume'},'joining process observation inventory')
    result=metadata.read(area/'result.json')
    h.need(result.get('schema')=='gse-v53-joining-initialization-process-v1' and result.get('status')=='PARTIAL' and
           result.get('mode')==expected['mode'] and result.get('point')==expected['point'] and
           all(result.get(k) is False for k in ('processDeathQualified','physicalReplay','phase3Complete')),'joining process producer scope')
    children=result.get('children');h.need(type(children) is list and len(children)==2 and all(type(v) is dict for v in children),'joining process children')
    h.need(all(type(v.get('pid')) is int and v['pid']>0 for v in children) and children[0]['pid']!=children[1]['pid'],'joining process distinct children')
    trace=lines(raw/'process-trace.jsonl')
    h.need(all(type(v) is dict and set(v)=={'origin','value'} and v['origin'] in {'parent',expected['mode'],'resume'} for v in trace),
           'joining process trace origins')
    h.need([v['value'] for v in trace if v['origin']=='parent']==h.read_json(raw,'events.json',h.EVENT_BYTES),
           'joining process exact parent observations')
    counts=[]
    for child,mode in zip(children,(expected['mode'],'resume')):
        wanted=dict(mode=mode,pid=child['pid'],exit=(73 if mode=='halt' else 137) if mode!='resume' else 0,lockReleased=True)
        wanted.update(dict(liveLockRefused=True) if mode!='resume' else dict(ready=child.get('ready'),drained=True))
        h.need(child==wanted and h.snapshot.f.canonical(child)==h.snapshot.f.canonical(wanted),'joining process exact death and drain')
        rows=lines(area/mode/'stdout')
        h.need(all(type(v) is dict and set(v)=={'kind','value'} and v['kind'] in {'STARTED','CUT','READY','CLOSED','EVENT','WIRE'} for v in rows),
               'joining process child message')
        h.need(rows==[v['value'] for v in trace if v['origin']==mode],'joining process original shared child order')
        h.need((area/mode/'stderr').read_bytes()==b'','joining process child stderr')
        controls=[v for v in rows if v['kind'] not in ('EVENT','WIRE')]
        expected_controls=[dict(kind='STARTED',value=dict(mode=mode,pid=child['pid']))]
        if mode!='resume':
            expected_controls.append(dict(kind='CUT',value=dict(point=expected['point'],mode=mode,pid=child['pid'])))
        else:
            ready=child['ready']
            h.need(type(ready) is dict and set(ready)=={'mode','pid','cut','state','publicReady'} and
                   ready['mode']==mode and type(ready['pid']) is int and ready['pid']==child['pid'] and
                   ready['state']=='ACTIVE' and ready['publicReady'] is False,'joining process recovered endpoint observation')
            expected_controls.extend([dict(kind='READY',value=ready),dict(kind='CLOSED',value=dict(mode=mode,pid=child['pid'],leases=0,queued=0))])
        h.need(controls==expected_controls and h.snapshot.f.canonical(controls)==h.snapshot.f.canonical(expected_controls),
               'joining process exact child controls');counts.append(len(rows))
    final=metadata.read(raw/'joining-continuation-result.json')
    h.need(final.get('status')=='PASS' and final.get('profile')==expected['profile'] and final.get('stableColdReopened') is True and
           final.get('automaticFinalAndBarrier') is True and final.get('publicReady') is False,'joining process original full continuation')
    for stage in ('before-process','interrupted','resumed-active','resumed-closed'):
        h.need((raw/('process-'+stage)).is_dir() and (raw/('joining-process-'+stage)/'inventory.json').is_file(),'joining process original snapshots')
    h.need(h.inventory(raw)==before,'joining process changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,physicalHistoryQualified=False,
                processDeathQualified=False,phase3Complete=False,childMessages=counts,inventory=before)


def run(output,maven,case,*,source_from=None):
    selected(case);output=Path(output).absolute()
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'joining process source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,case=case,status='RUNNING',executionStatus='NOT_RUN',collectionComplete=False,
                 physicalHistoryQualified=False,processDeathQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace'
        source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source)
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()))
        h.save(output/'toolchain.json',process_toolchain.capture(maven,work))
        receipt['toolchainSha256']=h.digest((output/'toolchain.json').read_bytes())
        receipt['command']=[maven,*command(case)];h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='joining-process-'+case)
        receipt['execution']=execution;h.save(output/'execution.json',execution);h.check_source(work,source)
        h.need(type(execution['exit']) is int and execution['exit']==0,'joining process Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=sorted((work/h.MODULE/'target/v53-native-dispatch').iterdir())
        h.need(len(roots)==1,'joining process exact original history')
        raw=roots[0];collection=collect(raw,case);h.save(output/'collection.json',collection)
        h.check_source(work,source);h.need(h.inventory(raw)==collection['inventory'],'joining process original changed')
        receipt.update(status='PARTIAL',collectionComplete=True,raw=raw.relative_to(output).as_posix(),
                       collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(output/'receipt.json',receipt);print(json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output')
    parser.add_argument('--case',required=True,choices=CASES);parser.add_argument('--maven',default='mvn')
    parser.add_argument('--source-from');args=parser.parse_args()
    run(args.output,args.maven,args.case,source_from=args.source_from)
