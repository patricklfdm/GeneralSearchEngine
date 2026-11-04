"""One immutable complete native 5-REPLACE history per partial floor writer cut.

Collection is PARTIAL. Final-source cohort admission and process-death coverage
remain separate; every failed execution retains its source, log and raw output.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import joint_floor_recovery_evidence as floor
from . import joint_ledger_evidence as ledger
from . import process_toolchain as tc
from .remove_process_matrix import BUILDS, reader_manifest

need=h.need
CLASS='io.github.patricklfdm.generalsearch.replication.V53NativePartialJointFloorTest'
METHOD='originalPartialCopyResumesBeforeFinalAndStableBarrier'
CASES=tuple(str(n)+','+cut for n in range(1,5) for cut in floor.PARTIAL_CUTS)


def selected(case):
    need(type(case) is str and case in CASES,'native partial joint exact case')
    ordinal,cut=case.split(',');return int(ordinal),cut


def command(case):
    selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
        '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHOD,
        '-Dv53.native.partial.joint='+case,'test']


def junit(reports):
    paths=sorted(Path(reports).glob('TEST-*.xml'))
    need(len(paths)==1,'native partial joint exact JUnit report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));tests=suite.findall('testcase')
    need(suite.get('name')==CLASS and suite.get('tests')=='1' and len(tests)==1 and
        all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
        tests[0].get('classname')==CLASS and tests[0].get('name')==METHOD and
        not any(v.tag in ('failure','error','skipped') or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
        'native partial joint one unretried passing test')
    return dict(className=CLASS,method=METHOD,tests=1,failures=0,errors=0,skipped=0,retries=0)


def collect(raw,case):
    raw=Path(raw);ordinal,cut=selected(case);before=h.inventory(raw)
    floor.same(floor.read(raw/'joint-floor-recovery/receipt.json'),floor.partial_scope(ordinal,cut),
               'native partial joint exact producer cut')
    # Prefix capture belongs to the same indivisible history. It may not be
    # silently discarded by a later artifact download.
    captures=raw/'source-retirement-captures'
    original_plan=h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB)
    result=dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,
        processDeathQualified=False,phase3Complete=False,inventory=before,captureInventory=h.inventory(captures),
        originalPlanSha256=h.digest(original_plan))
    need(h.inventory(raw)==before,'native partial joint collection changed original')
    return result


def capture(output,maven,case,source_from=None):
    selected(case);output=Path(output).absolute()
    need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),
         'native partial joint source separation')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(schema='gse-v53-native-partial-joint-execution-v1',case=case,status='RUNNING',
        executionStatus='NOT_RUN',collectionComplete=False,nativeHistoryQualified=False,
        processDeathQualified=False,phase3Complete=False,retries=0)
    try:
        work=output/'workspace';source=h.source_copy(h.ROOT,work) if source_from is None else h.recorded_source(source_from,work)
        h.save(output/'source.json',source);reader=reader_manifest()
        need(all(source['files'].get(k)==v for k,v in reader['files'].items()),'native partial joint reader belongs to source')
        h.save(output/'toolchain.json',tc.capture(maven,work));h.save(output/'reader.json',reader)
        receipt.update(baseHead=source['head'],sourceSha256=h.digest((output/'source.json').read_bytes()),
            toolchainSha256=h.digest((output/'toolchain.json').read_bytes()),readerSha256=reader['sha256'],command=[maven,*command(case)])
        h.save(output/'receipt.json',receipt)
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='native-partial-joint-'+case)
        h.save(output/'execution.json',execution);receipt['execution']=execution;h.check_source(work,source)
        need(type(execution['exit']) is int and execution['exit']==0,'native partial joint execution failed; evidence retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports');receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        parent=work/h.MODULE/'target/v53-native-dispatch';roots=list(parent.glob('run-*'))
        need(len(roots)==1,'native partial joint exact original directory');raw=roots[0]
        captures=raw/'source-retirement-captures'
        need({v.name for v in parent.iterdir()}=={raw.name},'native partial joint exact original and captures')
        receipt.update(raw=raw.relative_to(output).as_posix(),captures=captures.relative_to(output).as_posix())
        execution=h.execute([sys.executable,'-B','-m','scripts.v53.native_joint_floor_history','collect',
            str(output/'collection.json'),'--case',case,'--raw',str(raw)],work,output/'collection.log',stage='native-partial-joint-collection')
        h.save(output/'collection-execution.json',execution);receipt['collectionExecution']=execution
        need(type(execution['exit']) is int and execution['exit']==0,'native partial joint collection failed; evidence retained')
        need(floor.read(output/'collection.json')==collect(raw,case),'native partial joint immutable collection')
        h.check_source(work,source);receipt.update(status='PARTIAL',collectionComplete=True,
            collectionSha256=h.digest((output/'collection.json').read_bytes()))
    except BaseException as error:
        if receipt['executionStatus']=='NOT_RUN':receipt['executionStatus']='FAIL'
        receipt.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:h.save(output/'receipt.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    sub.add_parser('plan')
    for mode in ('capture','collect','validate'):
        c=sub.add_parser(mode);c.add_argument('output');c.add_argument('--case',required=True,choices=CASES)
        if mode=='capture':c.add_argument('--maven',default='mvn');c.add_argument('--source-from')
        else:c.add_argument('--raw',required=True)
    args=p.parse_args()
    if args.mode=='plan':
        print(json.dumps(dict(cases=list(CASES),wholeHistories=len(CASES),processDeathQualified=False,phase3Complete=False)));return
    if args.mode=='capture':result=capture(args.output,args.maven,args.case,args.source_from)
    else:
        output=Path(args.output);need(not output.exists(),'native partial joint refuses overwrite')
        original=collect(args.raw,args.case)
        if args.mode=='collect':result=original
        else:
            result=ledger.validate(args.raw,lambda row:print(json.dumps(row),file=sys.stderr,flush=True))
            need(collect(args.raw,args.case)==original,'native partial joint replay changed original')
        h.save(output,result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
