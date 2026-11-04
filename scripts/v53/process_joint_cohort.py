"""Source-bound admission of 32 complete joint-floor process histories.

Each death, original-directory recovery and FINAL/BARRIER continuation is one
member. Component admission does not qualify all Phase 3 resource/fault axes.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import json
from pathlib import Path
import re
import sys

from . import native_process_joint_floor as process
from . import process_joint_history as history
from . import process_joint_scratch as scratch
from . import remove_process_matrix as shared
from . import process_toolchain as tc

h=process.h;need=h.need;read=shared.read;reader_manifest=shared.reader_manifest
BUILDS=shared.BUILDS;CASES=process.CASES
SCHEMA='gse-v53-process-joint-cohort-v1'
capture=process.capture


def negative_cases(case):
    process.selected(case)
    return ([dict(suite='process',case=n,status='REJECTED',reason=r) for n,r in process.NEGATIVES.items()]+
            [dict(suite='composition',case=n,stage=stage,status='REJECTED',reason=r)
             for n,(stage,r) in history.NEGATIVES.items()]+
            [dict(suite='scratch',case=n,status='REJECTED',reason='joint scratch '+r)
             for n,r in scratch.negative_cases(case).items()])


def check_pins(source,build,toolchain,reader):
    need(all(shared.hash_field(v) for v in (source,build,toolchain,reader)),'joint cohort pinned hashes')
    manifest=reader_manifest();need(manifest['sha256']==reader,'joint cohort pinned reader');return manifest


def member(path,case,source,build,toolchain,reader):
    process.selected(case);manifest=check_pins(source,build,toolchain,reader);path=Path(path)
    need(path.is_dir() and not path.is_symlink(),'joint cohort producer directory');receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==process.EXECUTION_SCHEMA and receipt.get('case')==case and
         receipt.get('status')=='PARTIAL' and receipt.get('executionStatus')=='PASS' and receipt.get('collectionComplete') is True and
         all(receipt.get(k) is False for k in ('nativeHistoryQualified','processDeathQualified','phase3Complete')) and
         type(receipt.get('retries')) is int and receipt['retries']==0,'joint cohort successful unretried producer')
    for field,file in (('execution','execution.json'),('collectionExecution','collection-execution.json')):
        value=receipt.get(field)
        need(type(value) is dict and type(value.get('exit')) is int and value['exit']==0 and
             h.snapshot.f.canonical(read(path/file))==h.snapshot.f.canonical(value),'joint cohort successful process receipts')
    recorded,_=h.read_recorded_source(path);work=path/'workspace'
    need(receipt.get('sourceSha256')==source==h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead')==recorded['head'],'joint cohort exact source')
    need(receipt.get('readerSha256')==reader and read(path/'reader.json')==manifest and
         all(recorded['files'].get(k)==v for k,v in manifest['files'].items()),'joint cohort reader belongs to producer')
    args=receipt.get('command');wanted=process.command(case)
    need(type(args) is list and len(args)==len(wanted)+1 and type(args[0]) is str and Path(args[0]).name=='mvn' and
         args[1:]==wanted,'joint cohort exact complete command')
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (Path(name),*Path(name).parents)),
             'joint cohort linked generated parent')
    need(h.snapshot.f.canonical(receipt.get('junit'))==h.snapshot.f.canonical(process.junit(work/h.MODULE/'target/surefire-reports')),
         'joint cohort exact JUnit receipt')
    classes=read(path/'build.json')
    need(type(classes) is dict and set(classes)==set(BUILDS) and receipt.get('buildSha256')==build==h.digest((path/'build.json').read_bytes()),
         'joint cohort exact build manifest')
    for name in BUILDS:need(h.inventory(work/name)==classes[name],'joint cohort original compiled bytes')
    tc.validate(read(path/'toolchain.json'))
    need(receipt.get('toolchainSha256')==h.digest((path/'toolchain.json').read_bytes()) and
         tc.pin((path/'toolchain.json').read_bytes())==toolchain,'joint cohort portable toolchain')
    name=receipt.get('raw');base='workspace/'+h.MODULE+'/target/v53-native-dispatch'
    need(type(name) is str and re.fullmatch(re.escape(base)+r'/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'joint cohort exact raw path')
    need(all((path/p).is_dir() and not (path/p).is_symlink() for p in Path(name).parents),'joint cohort linked raw parent')
    raw=path/name;need({v.name for v in raw.parent.iterdir()}=={raw.name},'joint cohort exactly one original run')
    need(receipt.get('captures')==(raw/'source-retirement-captures').relative_to(path).as_posix(),'joint cohort exact captures path')
    need(process.producer_scope(raw,case)==process.scope(case,scratch_recovery=True),'joint cohort requires v2 scratch recovery')
    collection=process.collect(raw,case)
    need(receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         h.snapshot.f.canonical(read(path/'collection.json'))==h.snapshot.f.canonical(collection),
         'joint cohort independent original collection')
    return dict(raw=raw,plans={case:collection['originalPlanSha256']},inventory=collection['inventory'],
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def check_result(value,case):
    ordinal,_,_=process.selected(case)
    need(type(value) is dict and set(value)=={'original','negatives','originalPreserved'} and value['originalPreserved'] is True,
         'joint cohort preserved original replay')
    original=value['original']
    keys={'status','case','precondition','physical','network','exports','controls','maintenance','ledgers',
          'wholePhysicalNetworkLedgerReplayChecked','processDeathQualified','phase3Complete','outstanding'}
    need(type(original) is dict and set(original)==keys and original.get('status')=='PARTIAL' and
         original.get('case')==case and original.get('wholePhysicalNetworkLedgerReplayChecked') is True and
         original.get('phase3Complete') is False and original.get('processDeathQualified') is False,
         'joint cohort complete history scope')
    need(original['outstanding']==['expanded-process-negative-matrix','remaining-transfer-publication-resources','final-source-process-matrix'],
         'joint cohort preserves outstanding qualification')
    physical=original['physical'];network=original['network']
    need(type(physical) is dict and set(physical)=={'prefix','continuation','governingFloors','sourceRetirementPrefixes','sourceRetirementTransactions'},
         'joint cohort complete physical layers')
    for key,status in (('prefix','PASS'),('continuation','PARTIAL')):
        row=physical[key]
        need(type(row) is dict and row.get('status')==status and row.get('profile')=='5-REPLACE' and
             row.get('phase3Complete') is False and row.get('processDeathQualified') is False,'joint cohort physical scope')
    need(physical['prefix'].get('throughIntentPhysicalQualified') is True and
         type(physical['continuation'].get('finalCut')) is int and physical['continuation']['finalCut']==11,
         'joint cohort FINAL and stable BARRIER')
    need(type(network) is dict and network and all(type(v) is int and v>=0 for v in network.values()) and
         network.get('slots')==11,'joint cohort complete network counts')
    for name,status in (('exports','PARTIAL'),('controls','PASS'),('maintenance','PASS')):
        row=original[name]
        need(type(row) is dict and row.get('status')==status and row.get('phase3Complete') is False and
             row.get('processDeathQualified') is False,'joint cohort complete layer: '+name)
    need(original['controls'].get('observedControlExportsQualified') is True and
         original['controls'].get('observedLearnerRetentionQualified') is True and
         original['maintenance'].get('maintenanceForceQualified') is True and
         original['controls'].get('observedCommittedContents')==network.get('committedTransfers') and
         original['controls'].get('observedContentSessions')==network.get('transferSessions',-1)-network.get('rejectedTransferAttempts',0),
         'joint cohort whole export and maintenance coverage')
    need(type(original['ledgers']) is dict and set(original['ledgers'])==set(history.READERS) and
         all(type(v) is dict and v.get('status')=='PASS' and v.get('phase3Complete') is False and
             shared.hash_field(v.get('chainSha256')) for v in original['ledgers'].values()),
         'joint cohort all continuous ledgers')
    for name,flag in (('peers','peerLedgerCompositionQualified'),('learner','learnerLedgerCompositionQualified'),
                      ('future','futureLedgerCompositionQualified'),('ballot','ballotForceQualified')):
        need(original['ledgers'][name].get(flag) is True,'joint cohort ledger derivation: '+name)
    focused=original['precondition']
    need(type(focused) is dict and focused.get('case')==case and focused.get('status')=='PARTIAL' and
         all(focused.get(k) is True for k in ('processBoundaryChecked','interruptedBytesChecked','scratchRetained')) and
         all(focused.get(k) is False for k in ('nativeHistoryQualified','processDeathQualified','phase3Complete')),
         'joint cohort original process boundary')
    recovery=focused.get('scratchRecovery',{})
    need(type(recovery) is dict and recovery.get('status')=='PARTIAL' and recovery.get('sameScratchRecoveryChecked') is True and
         all(recovery.get(k) is False for k in ('liveWriterResourcesQualified','processDeathQualified','phase3Complete')) and
         type(recovery.get('discardedFiles')) is int and recovery['discardedFiles']==4-ordinal,
         'joint cohort cut-bound scratch recovery')
    need(h.snapshot.f.canonical(value['negatives'])==h.snapshot.f.canonical(negative_cases(case)),
         'joint cohort exact negative vector')


def replay(raw,case,progress=None):
    raw=Path(raw);before=process.collect(raw,case)
    need(process.producer_scope(raw,case)==process.scope(case,scratch_recovery=True),'joint cohort requires v2 scratch recovery')
    # Complete original first. No mutation may turn an unrelated original error
    # into a successful rejection. Individual suites repeat their prerequisites.
    original=history.validate(raw,progress);rows=[]
    for name,reader in (('process',process),('composition',history),('scratch',scratch)):
        value=reader.qualify(raw,case) if name=='process' else reader.qualify(raw,progress)
        expected=original if name=='composition' else original['precondition']
        need(h.snapshot.f.canonical(value['original'])==h.snapshot.f.canonical(expected),'joint cohort original stage drift: '+name)
        rows.extend(dict(suite=name,**v) for v in value['negatives'])
        if progress:progress(dict(stage='joint-process-qualified',case=case,suite=name,negatives=len(value['negatives'])))
    need(process.collect(raw,case)==before,'joint cohort replay changed original')
    result=dict(original=original,negatives=rows,originalPreserved=True);check_result(result,case);return result


def qualify_member(path,case,*pins):
    before=member(path,case,*pins);result=replay(before['raw'],case);check_result(result,case)
    need(member(path,case,*pins)==before,'joint cohort changed during replay');check_pins(*pins)
    return dict(case=case,status='PASS',plans=before['plans'],producerReceiptSha256=before['receiptSha256'],qualification=result,
                **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),phase3Complete=False)


def aggregate(paths,*pins,workers=1,progress=None):
    check_pins(*pins);need(type(workers) is int and 1<=workers<=4,'joint cohort replay workers')
    need(type(paths) is dict and set(paths)==set(CASES),'joint cohort complete 32 histories')
    need(len({Path(v).resolve() for v in paths.values()})==len(CASES),'joint cohort distinct producers')
    originals={k:member(paths[k],k,*pins) for k in CASES};plans=[v for k in CASES for v in originals[k]['plans'].values()]
    need(len(plans)==len(set(plans))==len(CASES),'joint cohort distinct original histories')
    outcomes={}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        tasks={pool.submit(qualify_member,paths[k],k,*pins):k for k in CASES};pending=set(tasks)
        while pending:
            done,pending=wait(pending,timeout=60,return_when=FIRST_COMPLETED)
            for task in done:
                case=tasks[task]
                try:value=task.result()
                except Exception as error:value=dict(case=case,status='FAIL',failure=dict(type=type(error).__name__,message=str(error)))
                outcomes[case]=value
                if progress:progress(dict(stage='member-terminal',completed=len(outcomes),total=len(CASES),case=case,status=value['status']))
            if not done and progress:progress(dict(stage='joint-process-replay',completed=len(outcomes),total=len(CASES)))
    for k in CASES:need(member(paths[k],k,*pins)==originals[k],'joint cohort original changed before aggregate')
    check_pins(*pins);passed=all(outcomes[k]['status']=='PASS' for k in CASES)
    return dict(schema=SCHEMA,status='PASS' if passed else 'FAIL',scope='declared-native-joint-floor-process-histories',
        cases=[outcomes[k] for k in CASES],wholeOwnershipHistories=len(CASES),nativeCases=len(CASES),
        negativeCases=sum(len(v.get('qualification',{}).get('negatives',[])) for v in outcomes.values()),
        **dict(zip(('sourceSha256','buildSha256','toolchainSha256','readerSha256'),pins)),
        declaredJointFloorProcessHistoriesQualified=passed,processDeathQualified=False,combinedPeakResourcesQualified=False,
        allMembershipProfilesQualified=False,powerLossQualified=False,phase3Complete=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('plan')
    for mode in ('capture','member','aggregate'):
        p=sub.add_parser(mode);p.add_argument('output')
        if mode!='aggregate':p.add_argument('--case',required=True,choices=CASES)
        if mode=='capture':p.add_argument('--maven',default='mvn');p.add_argument('--source-from')
        else:
            if mode=='member':p.add_argument('--producer',required=True)
            else:p.add_argument('--inputs',required=True);p.add_argument('--workers',type=int,default=1)
            for pin in ('source','build','toolchain','reader'):p.add_argument('--'+pin+'-sha256',required=True)
    a=parser.parse_args()
    if a.command=='plan':
        print(json.dumps(dict(cases=[dict(case=k,command=process.command(k),negatives=len(negative_cases(k))) for k in CASES],
                              reader=reader_manifest(),phase3Complete=False),sort_keys=True));return
    if a.command=='capture':result=capture(a.output,a.maven,a.case,a.source_from)
    else:
        output=Path(a.output);output.mkdir(parents=True,exist_ok=False);result=dict(schema=SCHEMA,status='FAIL',phase3Complete=False)
        try:
            pins=[getattr(a,k+'_sha256') for k in ('source','build','toolchain','reader')]
            from .remove_process_hosted import progress as heartbeat
            with heartbeat('joint-process-'+a.command,getattr(a,'case',None)),(output/'progress.jsonl').open('x') as stream:
                def progress(v):stream.write(json.dumps(v,sort_keys=True)+'\n');stream.flush();print(json.dumps(v),file=sys.stderr,flush=True)
                if a.command=='member':result=qualify_member(a.producer,a.case,*pins)
                else:
                    inputs=Path(a.inputs);need(inputs.is_dir() and not inputs.is_symlink() and {v.name for v in inputs.iterdir()}==set(CASES),
                        'joint cohort exact input directories')
                    result=aggregate({k:inputs/k for k in CASES},*pins,workers=a.workers,progress=progress)
            need(result['status']=='PASS','joint cohort failed originals')
        except BaseException as error:result.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
        finally:h.save(output/'receipt.json',result)
    print(json.dumps(dict(status=result['status'],phase3Complete=False,output=a.output),sort_keys=True))


if __name__=='__main__':main()
