"""Run one immutable ADD/REPLACE history; preserve failures and minute progress.

Each invocation is a fresh whole prefix, without retries or shared lease/history.
The default ends at JOINT; --complete includes FINAL and retaining cold recovery.
Both remain separate from complete physical/network/process qualification.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import joining_profile_evidence as e
from . import joining_completion_evidence as complete_reader

METHOD='joiningProfilePublishesOriginalJointCheckpoint'
TEST=h.CLASS.rsplit('.',1)[-1]+'#'+METHOD
COMPLETE_METHOD='joiningProfileCompletesFinalAndRetainingColdRecovery'
SAME_VIEW_METHOD='joiningProfileRequiresSameViewFinalRecovery'


def junit(reports,method=METHOD):
    paths=sorted(reports.glob('TEST-*.xml'));h.need(len(paths)==1,'joining prefix exact test report')
    suite=ET.parse(paths[0]).getroot();cases=suite.findall('testcase')
    h.need(suite.get('name')==h.CLASS and suite.get('tests')=='1' and
           all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and len(cases)==1 and
           cases[0].get('classname')==h.CLASS and cases[0].get('name')==method and
           not any(cases[0].find(k) is not None for k in ('failure','error','skipped')),'joining prefix exact passing test')
    return dict(className=h.CLASS,method=method,tests=1,failures=0,errors=0,skipped=0)


def run(output,maven,profile,*,source_from=None,complete=False,same_view=False):
    e.topology(profile);output=Path(output).absolute()
    h.need(not same_view or (complete and profile=='3-REPLACE'),'same-view execution requires complete 3-REPLACE')
    method=COMPLETE_METHOD if complete else METHOD
    reader=complete_reader if complete else e
    if same_view:
        from . import joining_same_view_semantics as reader
        method=SAME_VIEW_METHOD
    stage='joining-complete' if complete else 'joining-prefix'
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'recorded source execution separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-joining-profile-'+('completion' if complete else 'prefix')+'-v1',status='RUNNING',profile=profile,retries=0,
        completeExecutionRequested=complete,semanticFinalAndColdQualified=False,
        executionStatus='NOT_RUN',semanticChainQualified=False,finalAndColdReopenQualified=False,
        forceAndNetworkQualified=False,phase3Complete=False)
    if same_view:receipt.update(sameViewRecoveryRequested=True,sameViewSemanticQualified=False,sameViewPhysicalQualified=False)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()))
        toolchain=subprocess.run([maven,'-version'],cwd=work,text=True,capture_output=True,timeout=30)
        h.save(output/'toolchain.json',dict(exit=toolchain.returncode,stdout=toolchain.stdout,stderr=toolchain.stderr))
        h.need(toolchain.returncode==0,'joining prefix toolchain unavailable')
        receipt['toolchainSha256']=h.digest((output/'toolchain.json').read_bytes())
        command=[maven,'-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
                 '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+h.CLASS.rsplit('.',1)[-1]+'#'+method,'-Dv53.joining.profile='+profile,'test']
        receipt['command']=command;h.save(output/'receipt.json',receipt)
        execution=h.execute(command,work,output/'maven.log',stage=stage+'-'+profile)
        receipt['execution']=execution;h.save(output/'execution.json',execution);h.check_source(work,source)
        h.need(execution['exit']==0,'joining prefix Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',method);receipt['executionStatus']='PASS'
        build={name:h.inventory(work/name) for name in ('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')}
        h.save(output/'build.json',build);receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=sorted((work/h.MODULE/'target/v53-native-dispatch').glob('run-*'))
        h.need(len(roots)==1,'joining prefix exact original history');receipt['raw']=roots[0].relative_to(output).as_posix()
        # Replay uses its frozen reader, never the possibly edited working tree.
        replay=h.execute([sys.executable,'-B','-m',reader.__name__,str(roots[0]),'--profile',profile,'--qualify'],
                         work,output/'replay.json',stage=stage+'-replay')
        receipt['replayExecution']=replay;h.need(replay['exit']==0,'joining prefix replay failed; original retained')
        result=json.loads((output/'replay.json').read_bytes())
        h.need(result['original']['status']=='PASS' and result['original']['profile']==profile and
               result['original']['phase3Complete'] is False and result['original']['finalAndColdReopenQualified'] is False and
               result['original'].get('semanticFinalAndColdQualified',False)==complete and
               result['negatives']==[dict(case=k,status='REJECTED',reason=v) for k,v in reader.NEGATIVES.items()], 'joining prefix replay scope')
        if same_view:
            h.need(result['original'].get('sameViewSemanticQualified') is True and
                   result['original'].get('sameViewPhysicalQualified') is False,'joining same-view replay scope')
        h.check_source(work,source)
        receipt.update(status='PARTIAL',semanticChainQualified=True,semanticFinalAndColdQualified=complete,negativeCases=len(result['negatives']),
                       replaySha256=h.digest((output/'replay.json').read_bytes()))
        if same_view:receipt['sameViewSemanticQualified']=True
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(output/'receipt.json',receipt);print(json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--profile',required=True,choices=e.PROFILES)
    p.add_argument('--maven',default='mvn');p.add_argument('--source-from');p.add_argument('--complete',action='store_true')
    p.add_argument('--same-view',action='store_true');a=p.parse_args()
    run(a.output,a.maven,a.profile,source_from=a.source_from,complete=a.complete,same_view=a.same_view)
