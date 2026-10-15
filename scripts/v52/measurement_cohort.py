"""Serial complete local M01-M04 cohort, admitted by the committed machine freeze."""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from . import measurement_machine as machine,measurement_runtime as runtime,measurement_bundle as bundle
from . import measurement_m01 as m01,measurement_m01_set as m01_set,measurement_minimum as minimum
from . import measurement_minimum_evidence as minimum_evidence,measurement_recovery as recovery,measurement_recovery_evidence as recovery_evidence
from .evidence import need,digest,encoded


def replay_member(root,binding,spec,output):
    if spec['family']=='M01':return m01_set.portable_member(root,binding,output)
    if spec['family'] in ('M02','M03'):return minimum_evidence.portable_member(root,binding,output)
    return recovery_evidence.portable_member(root,binding,output)


def validate_results(value,actual,expected,results):
    """Only accepts values returned by independent member replays in this process."""
    machine.validate_plan(value);specs=value['contract']['members']
    need(set(expected)==set(results)==set(specs),'measurement incomplete full cohort')
    groups=set();histories=set();manifests=set();outcomes={};bindings={};m01_results={};run_attempt=None;reads=updates=0
    for name in value['contract']['execution']['order']:
        binding=expected[name];spec=machine.check_binding(value,actual,name,binding);result=results[name]
        need(result['status']=='PASS' and result['binding']==binding and result['qualifiedMeasurement'] is False and result['paidCloud'] is False,
             'measurement cohort unqualified member')
        identity=binding['run'],binding['attempt']
        need(isinstance(identity[0],str) and identity[0] and type(identity[1]) is int and identity[1]>=1,'measurement cohort run/attempt shape')
        if run_attempt is None:run_attempt=identity
        else:need(identity==run_attempt,'measurement cohort mixed run/attempt')
        group,history,manifest=result['domain']['groupId'],result['domain']['historyId'],result['manifestSha256']
        need(group not in groups and history not in histories and manifest not in manifests,'measurement cohort reused domain/history')
        groups.add(group);histories.add(history);manifests.add(manifest)
        body=result['result'];need(body['status']=='PASS' and body['negatives']==value['contract']['negativeRules'][name],
                                  'measurement cohort incomplete exact negatives')
        family=spec['family'];execution={'M01':'m01-member-physical-replay','M02':'minimum-member-physical-replay',
                                         'M03':'minimum-member-physical-replay','M04':'recovery-member-physical-replay'}[family]
        need(result['execution']==execution.replace('member-physical-replay','portable-member'),
             'measurement cohort portable execution identity')
        need(body['execution']==execution and body['qualifiedMeasurement'] is False and body['paidCloud'] is False,
             'measurement cohort member execution identity')
        if family=='M01':bindings[name]=binding;m01_results[name]=result
        else:need(body['case']==name,'measurement cohort member case identity')
        outcomes[name]=body['ledger']['outcomes'];reads+=sum(outcomes[name]['read'].values());updates+=sum(outcomes[name]['update'].values())
    healthy=m01_set.validate_results(m01_results,bindings)
    need(reads==27373 and updates==2745,'measurement cohort complete original call counts')
    return dict(status='PASS',execution='complete-local-m01-m04-measurement',qualifiedMeasurement=True,paidCloud=False,
        hostedAcceptance=False,cloudAcceptance=False,machineSha256=digest(encoded(value)),binding=actual,histories=28,
        originalReads=reads,originalUpdates=updates,nominalM01Seconds=2700,m01=healthy,outcomes=outcomes,
        boundary='Local measurement only; exact-source protected full CI and fresh cloud admission still required.')


def run():
    value,actual=machine.admit();machine.verify_launch(value,actual)
    root=Path(value['storageRoot']);history_root=root/'histories';replay_root=root/'portable'
    need(not history_root.exists() and not replay_root.exists() and not (root/'cohort.json').exists(),'measurement cohort must be fresh; no retries/resume')
    history_root.mkdir();replay_root.mkdir();expected={};results={};started=time.time()
    record=dict(schema='gse-v52-measurement-cohort-v1',status='RUNNING',qualifiedMeasurement=False,paidCloud=False,
        machineSha256=digest(encoded(value)),binding=actual,run=os.environ.get('GITHUB_RUN_ID','local'),attempt=int(os.environ.get('GITHUB_RUN_ATTEMPT','1')),
        startedUnixSeconds=started,expected=expected,completed=[],current=None)
    runtime.save(root/'cohort.json',record)
    try:
        for name in value['contract']['execution']['order']:
            spec=value['contract']['members'][name];case=history_root/name;record['current']=name
            need(machine.admit()==(value,actual),'measurement machine/source changed between histories')
            need(shutil.disk_usage(root).free>=machine.MINIMUM_FREE_BYTES,'measurement insufficient free storage before history')
            print(json.dumps(dict(member=name,stage='preparation',status='RUNNING')),flush=True);runtime.save(root/'cohort.json',record)
            if spec['family']=='M01':binding,cp,_=runtime.prepare(case,spec['mode'],m01_repetition=spec['profile']['repetition']);owner=m01
            elif spec['family'] in ('M02','M03'):binding,cp,_=minimum.prepare(case,name);owner=minimum
            else:binding,cp,_=recovery.prepare(case,name);owner=recovery
            machine.check_binding(value,actual,name,binding)
            need((binding['run'],binding['attempt'])==(record['run'],record['attempt']),'measurement launch run/attempt changed')
            expected[name]=binding;runtime.save(root/'cohort.json',record)
            print(json.dumps(dict(member=name,stage='original-workload',status='RUNNING')),flush=True)
            owner.execute_prepared(case,binding,cp)
            need(machine.admit()==(value,actual),'measurement machine/source changed during history')
            runtime.save(case/bundle.INDEX,bundle.members(case))
            print(json.dumps(dict(member=name,stage='portable-validation',status='RUNNING')),flush=True)
            results[name]=replay_member(case,binding,spec,replay_root/name);record['completed'].append(name);runtime.save(root/'cohort.json',record)
            print(json.dumps(dict(member=name,status='PASS',completed=len(results),total=28)),flush=True)
        need(machine.admit()==(value,actual),'measurement final machine/source changed')
        qualified=validate_results(value,actual,expected,results);runtime.save(root/'qualification.json',qualified)
        record.update(status='PASS',qualifiedMeasurement=True,qualificationSha256=bundle.sha_file(root/'qualification.json'))
        return qualified
    except BaseException as error:record.update(status='FAIL',failure=dict(type=type(error).__name__,message=str(error)));raise
    finally:
        record['elapsedSeconds']=round(time.time()-started,3);runtime.save(root/'cohort.json',record)


def replay(source,output):
    source=Path(source).resolve();output=Path(output).resolve()
    need(source!=output and source not in output.parents and output not in source.parents,'measurement full replay location overlap')
    value=machine.validate_plan(runtime.evidence.reads.read(source/'frozen-machine.json'));launch=runtime.evidence.reads.read(source/'cohort.json')
    need(launch['schema']=='gse-v52-measurement-cohort-v1' and launch['machineSha256']==digest(encoded(value)) and launch['paidCloud'] is False,
         'measurement replay machine/launch binding')
    actual=machine.verify_launch(value,launch['binding']);expected=launch['expected']
    need(set(expected)==set(value['contract']['members']),'measurement replay incomplete input set')
    for name,binding in expected.items():machine.check_binding(value,actual,name,binding)
    output.mkdir(parents=True,exist_ok=False);results={};receipt=dict(status='FAIL',qualifiedMeasurement=False,paidCloud=False)
    try:
        for name in value['contract']['execution']['order']:
            results[name]=replay_member(source/'histories'/name,expected[name],value['contract']['members'][name],output/name)
        receipt=validate_results(value,actual,expected,results);return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:runtime.save(output/'receipt.json',receipt)


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True);sub.add_parser('run');r=sub.add_parser('replay');r.add_argument('source',type=Path);r.add_argument('output',type=Path)
    args=p.parse_args();result=run() if args.action=='run' else replay(args.source,args.output);print(json.dumps(result,sort_keys=True))
