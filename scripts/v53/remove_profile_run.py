"""One immutable 4/5 REMOVE execution and original-first physical/lifecycle replay.

Independent profiles may run concurrently. A member always starts from its own
bootstrap and retains the entire same-store history; no stage reuse or retries.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import transition_round_evidence as reader

CLASS='io.github.patricklfdm.generalsearch.replication.V53TransitionRoundDriverTest'
METHOD='removalProfileCompletesOneOriginalRoundLifetime'
SCHEMA='gse-v53-remove-profile-execution-v1'


def junit(reports):
    paths=sorted(reports.glob('TEST-*.xml'));h.need(len(paths)==1,'REMOVE exact test report')
    suite=ET.parse(paths[0]).getroot();cases=suite.findall('testcase')
    h.need(suite.get('name')==CLASS and suite.get('tests')=='1' and len(cases)==1 and
           all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
           cases[0].get('classname')==CLASS and cases[0].get('name')==METHOD and
           not any(cases[0].find(k) is not None for k in ('failure','error','skipped')),'REMOVE exact passing test')
    return dict(className=CLASS,method=METHOD,tests=1,failures=0,errors=0,skipped=0)


def run(output,maven,profile,*,source_from=None,retirement_captures=False,portable_toolchain=False):
    h.need(profile in reader.PROFILES,'REMOVE exact profile')
    h.need(type(portable_toolchain) is bool,'REMOVE portable toolchain option')
    h.need(type(retirement_captures) is bool,'REMOVE capture option')
    output=Path(output).absolute()
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'REMOVE source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema=SCHEMA,status='RUNNING',profile=profile,retries=0,executionStatus='NOT_RUN',
        continuousOriginalQualified=False,automaticOperationCompletion=False,publicRuntimeQualified=False,
        completeNetworkQualified=False,processDeathQualified=False,phase3Complete=False)
    if retirement_captures:receipt.update(retirementCapturesRequested=True,transientRetirementBytesQualified=False)
    try:
        work=output/'workspace'
        source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()))
        if portable_toolchain:
            from . import process_toolchain
            h.save(output/'toolchain.json',process_toolchain.capture(maven,work))
        else:
            toolchain=subprocess.run([maven,'-version'],cwd=work,text=True,capture_output=True,timeout=30)
            h.save(output/'toolchain.json',dict(exit=toolchain.returncode,stdout=toolchain.stdout,stderr=toolchain.stderr))
            h.need(toolchain.returncode==0,'REMOVE toolchain unavailable')
        receipt['toolchainSha256']=h.digest((output/'toolchain.json').read_bytes())
        command=[maven,'-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
                 '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHOD,
                 '-Dv53.remove.profile='+profile,'test']
        if retirement_captures:command.insert(-1,'-Dv53.remove.retirement.captures=true')
        receipt['command']=command;h.save(output/'receipt.json',receipt)
        execution=h.execute(command,work,output/'maven.log',stage='REMOVE-'+profile)
        receipt['execution']=execution;h.save(output/'execution.json',execution);h.check_source(work,source)
        h.need(execution['exit']==0,'REMOVE Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports');receipt['executionStatus']='PASS'
        build={name:h.inventory(work/name) for name in ('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')}
        h.save(output/'build.json',build);receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=sorted((work/h.MODULE/'target/v53-native-dispatch').glob('run-*'))
        h.need(len(roots)==1,'REMOVE exact original history');raw=roots[0];receipt['raw']=raw.relative_to(output).as_posix()
        original=h.inventory(raw);h.save(output/'inventory.json',original)
        replay=h.execute([sys.executable,'-B','-m','scripts.v53.transition_round_evidence',str(raw),'--profile',profile,'--qualify'],
                         work,output/'replay.json',stage='REMOVE-original-first-'+profile)
        receipt['replayExecution']=replay;h.need(replay['exit']==0,'REMOVE original replay failed; evidence retained')
        result=json.loads((output/'replay.json').read_bytes())
        h.need(result['original'].get('status')=='PASS' and result['original'].get('profile')==profile and
               result['original'].get('automaticOperationCompletion') is True and result['original'].get('phase3Complete') is False and
               result['original'].get('publicReady') is False and result['negatives']==
               [dict(case=k,status='REJECTED',reason=v) for k,v in reader.negative_cases(profile).items()],'REMOVE replay scope')
        h.check_source(work,source);h.need(h.inventory(raw)==original,'REMOVE original changed')
        receipt.update(status='PARTIAL',continuousOriginalQualified=True,automaticOperationCompletion=True,
                       negativeCases=len(result['negatives']),replaySha256=h.digest((output/'replay.json').read_bytes()))
        if retirement_captures:
            captures=raw.with_name('retirement-captures-'+raw.name)
            captured=h.inventory(captures);h.save(output/'capture-inventory.json',captured)
            receipt['captures']=captures.relative_to(output).as_posix()
            execution=h.execute([sys.executable,'-B','-m','scripts.v53.remove_retirement_prefixes',str(raw),str(captures),'--profile',profile],
                                work,output/'retirement-prefixes.json',stage='REMOVE-original-prefixes-'+profile)
            receipt['prefixExecution']=execution;h.need(execution['exit']==0,'REMOVE prefix replay failed; original retained')
            result=json.loads((output/'retirement-prefixes.json').read_bytes())
            h.need(result['status']=='PARTIAL' and result['profile']==profile and result['transientRetirementBytesQualified'] is True and
                   result['processDeathQualified'] is False and result['phase3Complete'] is False,'REMOVE prefix replay scope')
            h.check_source(work,source);h.need(h.inventory(captures)==captured and h.inventory(raw)==original,'REMOVE captured original changed')
            receipt.update(transientRetirementBytesQualified=True,capturedPrefixes=result['capturedPrefixes'],
                           prefixReplaySha256=h.digest((output/'retirement-prefixes.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        h.save(output/'receipt.json',receipt);print(json.dumps(receipt,sort_keys=True),flush=True)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');p.add_argument('--profile',required=True,choices=reader.PROFILES)
    p.add_argument('--maven',default='mvn');p.add_argument('--source-from');p.add_argument('--retirement-captures',action='store_true');p.add_argument('--portable-toolchain',action='store_true');a=p.parse_args()
    run(a.output,a.maven,a.profile,source_from=a.source_from,retirement_captures=a.retirement_captures,portable_toolchain=a.portable_toolchain)
