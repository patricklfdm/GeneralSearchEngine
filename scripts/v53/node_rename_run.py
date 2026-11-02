"""Capture one whole two-lifetime node rename history, with no native retries.

Collection only checks original process observations. Independent physical and
network replay in node_rename_matrix is required before accepting a member.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from . import joining_history_run as h
from . import node_process_evidence as process
from . import process_toolchain

CLASS='io.github.patricklfdm.generalsearch.replication.V53NodeRenameProcessTest'
METHODS={point+','+mode:mode+'After'+name+'Rename'
         for point,name in (('ACCEPT_RENAMED','Accept'),('PROOF_RENAMED','Proof')) for mode in ('halt','kill')}
CASES=tuple(METHODS)
SCHEMA='gse-v53-node-rename-execution-v1'
BUILDS=('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')


def selected(case):
    h.need(type(case) is str and case in METHODS,'node rename exact case')
    cut,mode=case.split(',');return dict(cut=cut,mode=mode)


def command(case):
    selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
            '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHODS[case],'test']


def junit(reports,case):
    selected(case);paths=sorted(reports.glob('TEST-*.xml'))
    h.need(len(paths)==1,'node rename exact report')
    suite=ET.fromstring(h.snapshot.s.regular(paths[0],8*h.snapshot.MIB));cases=suite.findall('testcase')
    h.need(suite.get('name')==CLASS and suite.get('tests')=='1' and len(cases)==1 and
           all(suite.get(k)=='0' for k in ('failures','errors','skipped')) and
           cases[0].get('classname')==CLASS and cases[0].get('name')==METHODS[case] and
           not any(v.tag in {'failure','error','skipped'} or v.tag.startswith(('flaky','rerun')) for v in suite.iter()),
           'node rename exact passing unretried test')
    return dict(className=CLASS,method=METHODS[case],tests=1,failures=0,errors=0,skipped=0,retries=0)


def collect(raw,case):
    expected=selected(case);raw=Path(raw);before=h.inventory(raw);process.inventory(raw)
    result=process.n.read(raw/'process/result.json')
    h.need({k:result.get(k) for k in expected}==expected,'node rename original case')
    rows=process.children(result,cut=expected['cut'])
    # These are observation checks only, never authority for durable history.
    messages=process.observations(raw,rows,cut=expected['cut'],reconciled=True)
    h.need(h.inventory(raw)==before,'node rename changed during collection')
    return dict(status='PARTIAL',case=case,collectionComplete=True,physicalHistoryQualified=False,
                processDeathQualified=False,phase3Complete=False,childMessages=messages,inventory=before)


def run(output,maven,case,*,source_from=None):
    selected(case);output=Path(output).absolute()
    h.need(source_from is None or not output.resolve().is_relative_to(Path(source_from).resolve()),'node rename source separation')
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
        execution=h.execute(receipt['command'],work,output/'maven.log',stage='node-rename-'+case)
        receipt['execution']=execution;h.save(output/'execution.json',execution);h.check_source(work,source)
        h.need(type(execution['exit']) is int and execution['exit']==0,'node rename Maven failed; original retained')
        receipt['junit']=junit(work/h.MODULE/'target/surefire-reports',case);receipt['executionStatus']='PASS'
        h.save(output/'build.json',{name:h.inventory(work/name) for name in BUILDS})
        receipt['buildSha256']=h.digest((output/'build.json').read_bytes())
        roots=sorted((work/h.MODULE/'target/v53-node-process').iterdir())
        h.need(len(roots)==1,'node rename exact original history')
        raw=roots[0];collection=collect(raw,case);h.save(output/'collection.json',collection)
        h.check_source(work,source);h.need(h.inventory(raw)==collection['inventory'],'node rename original changed')
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
