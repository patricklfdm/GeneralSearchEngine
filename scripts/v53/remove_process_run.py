"""Collect one indivisible REMOVE retirement process history; never full qualification.

The explicit members may later run on separate workers. A successful JUnit result
and consistent collection are not independent physical/process qualification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import transition_process_evidence as process

CLASS='io.github.patricklfdm.generalsearch.replication.V53RemoveRetirementProcessTest'
METHOD='originalRetirementRecoversInFreshProcess'
POINTS=('RETIREMENT_BORROW_PREFIX_WRITTEN','RETIREMENT_PROPOSAL_FORCED','RETIREMENT_AUTHORITY_FORCED',
        'RETIREMENT_FILE_DELETED','RETIREMENT_DIRECTORY_DELETED','RETIREMENT_BORROW_CLEARED',
        'RETIREMENT_AUTHORITY_CLEARED','SOURCE_RETIREMENT_WRITTEN','SOURCE_RETIREMENT_FORCED',
        'JOURNAL_ROTATION_WRITTEN','JOURNAL_ROTATION_RENAMED','SOURCE_RETIREMENT_FILE_DELETED',
        'SOURCE_RETIREMENT_CLEARED')
CASES=tuple(','.join((profile,point,mode)) for profile in ('4-REMOVE','5-REMOVE')
            for point in POINTS for mode in ('halt','kill'))


def selected(case):
    h.need(type(case) is str and case in CASES,'REMOVE process exact case')
    profile,point,mode=case.split(',')
    return dict(schema='gse-v53-remove-retirement-process-v1',profile=profile,index=5,point=point,mode=mode)


def junit(reports):
    paths=sorted(reports.glob('TEST-*.xml'));h.need(len(paths)==1,'REMOVE process exact report')
    suite=ET.parse(paths[0]).getroot();cases=suite.findall('testcase')
    h.need(suite.get('name')==CLASS and suite.get('tests')=='1' and len(cases)==1 and
           all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
           cases[0].get('classname')==CLASS and cases[0].get('name')==METHOD and
           not any(v.tag in {'failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'}
                   for v in suite.iter()),'REMOVE process exact passing unretried test')
    return dict(className=CLASS,method=METHOD,tests=1,failures=0,errors=0,skipped=0,retries=0)


def collect(raw,case):
    expected=selected(case);original=h.inventory(raw)
    read=lambda name:json.loads((raw/name).read_bytes())
    h.need(read('profile.json')==expected,'REMOVE process original profile')
    process.process_outcome(read('process.json'),{k:expected[k] for k in ('index','point','mode')})
    interrupted=process.trace(raw/'interrupted-worker/stdout');resumed=process.trace(raw/'resumed-worker/stdout')
    h.need([v for k,v in interrupted if k=='CUT']==[dict(index=5,event=expected['point'])] and
           not any(k in {'READY','CLOSED'} for k,v in interrupted),'REMOVE process original interruption')
    h.need(not (raw/'interrupted-worker/ready.json').exists() and not (raw/'interrupted-worker/ready.gsrp').exists(),
           'REMOVE process interrupted readiness')
    h.need([v for k,v in resumed if k=='READY']==['resume'] and [v for k,v in resumed if k=='CLOSED']==['resume'] and
           not any(k=='CUT' for k,v in resumed) and resumed[-1]==('CLOSED','resume'),'REMOVE process continuation terminal')
    for name,rows in ((expected['mode'],interrupted),('resume',resumed)):
        h.need([v for k,v in rows if k=='SNAPSHOT' and v.endswith('-opened-0')]==[name+'-opened-0'],
               'REMOVE process original open observation')
        h.need((raw/'history'/f'{name}-opened-0').is_dir(),'REMOVE process opened inventory')
    ready=read('resumed-worker/ready.json')
    h.need(set(ready)=={'state','cut','operation','publicReady'} and ready['state']=='READY' and ready['publicReady'] is False and
           type(ready['cut']['index']) is int and ready['cut']['index']==7 and ready['cut']['view']['operation'] is None and
           ready['operation']['phase']=='COMPLETED','REMOVE process original completion observation')
    h.need((raw/'resumed-worker/ready.gsrp').is_file(),'REMOVE process readiness bytes')
    return dict(status='PARTIAL',collectionComplete=True,processDeathQualified=False,
                physicalHistoryQualified=False,phase3Complete=False,case=case,inventory=original)


def run(output,maven,case,*,source_from=None):
    selected(case);output=Path(output).absolute()
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'REMOVE process source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-remove-process-execution-v1',case=case,status='RUNNING',executionStatus='NOT_RUN',
                 collectionComplete=False,processDeathQualified=False,physicalHistoryQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace'
        source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()))
        version=subprocess.run([maven,'-version'],cwd=work,text=True,capture_output=True,timeout=30)
        h.save(output/'toolchain.json',dict(exit=version.returncode,stdout=version.stdout,stderr=version.stderr))
        h.need(version.returncode==0,'REMOVE process toolchain unavailable')
        receipt['toolchainSha256']=h.digest((output/'toolchain.json').read_bytes())
        command=[maven,'-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
                 '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHOD,
                 '-Dv53.remove.retirement.process='+case,'test']
        receipt['command']=command;h.save(output/'receipt.json',receipt)
        execution=h.execute(command,work,output/'maven.log',stage='REMOVE-process-'+case)
        receipt['execution']=execution;h.save(output/'execution.json',execution);h.check_source(work,source)
        h.need(execution['exit']==0,'REMOVE process Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports');receipt['executionStatus']='PASS'
        build={name:h.inventory(work/name) for name in ('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')}
        h.save(output/'build.json',build);receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=sorted((work/h.MODULE/'target/v53-remove-retirement-process').glob('run-*'))
        h.need(len(roots)==1,'REMOVE process exact original history');raw=roots[0]
        result=collect(raw,case);h.save(output/'collection.json',result)
        h.check_source(work,source);h.need(h.inventory(raw)==result['inventory'],'REMOVE process original changed')
        receipt.update(status='PARTIAL',collectionComplete=True,raw=raw.relative_to(output).as_posix(),
                       collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(output/'receipt.json',receipt);print(json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--case',required=True,choices=CASES)
    p.add_argument('--maven',default='mvn');p.add_argument('--source-from');a=p.parse_args()
    run(a.output,a.maven,a.case,source_from=a.source_from)
