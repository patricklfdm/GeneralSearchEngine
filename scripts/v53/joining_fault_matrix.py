"""Original-first three-reply qualification on one immutable producer/build.

Each member is an indivisible native ADD history. Collection receipts alone do
not pass; replay the complete originals and exact negatives again at aggregation.
"""
import argparse
import json
from pathlib import Path
import re
import sys

from . import joining_history_run as h
from . import joining_fault_evidence as gate

KINDS=gate.loss.KINDS
BUILDS=('target/classes',h.MODULE+'/target/classes',h.MODULE+'/target/test-classes')
need=h.need


def read(path):
    def unique(rows):
        need(len(rows)==len(dict(rows)),'joining matrix duplicate metadata key');return dict(rows)
    return json.loads(h.snapshot.s.regular(path,8*h.snapshot.MIB),object_pairs_hook=unique)


def hash_field(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def member(path,kind,source_sha256,build_sha256):
    path=Path(path);receipt=read(path/'receipt.json')
    need(type(receipt) is dict and receipt.get('schema')==h.SCHEMA and receipt.get('status')=='PARTIAL' and
         receipt.get('executionStatus')=='PASS' and receipt.get('sourceFault')==kind and
         receipt.get('collectionComplete') is True and receipt.get('nativeHistoryQualified') is False and
         receipt.get('phase3Complete') is False and type(receipt.get('retries')) is int and receipt['retries']==0,
         'joining matrix successful whole member: '+kind)
    need(all(type(receipt.get(k)) is dict and type(receipt[k].get('exit')) is int and receipt[k]['exit']==0 for k in ('execution','collectionExecution')),
         'joining matrix successful processes: '+kind)
    source,_=h.read_recorded_source(path)
    need(receipt.get('sourceSha256')==source_sha256==h.digest((path/'source.json').read_bytes()) and
         receipt.get('baseHead')==source['head'],'joining matrix exact producer source: '+kind)
    command=receipt.get('command');wanted=['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
        '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+h.TEST,'-Dv53.transport.connections=true','-Dv53.joining.sourceFault='+kind,'test']
    need(type(command) is list and len(command)==len(wanted)+1 and type(command[0]) is str and
         Path(command[0]).name=='mvn' and command[1:]==wanted,'joining matrix exact whole command: '+kind)
    work=path/'workspace'
    for name in (*BUILDS,h.MODULE+'/target/surefire-reports'):
        relative=Path(name)
        need(all((work/p).is_dir() and not (work/p).is_symlink() for p in (relative,*relative.parents)),
             'joining matrix linked generated parent: '+kind)
    reports=work/h.MODULE/'target/surefire-reports'
    for report in reports.glob('TEST-*.xml'):h.snapshot.s.regular(report,8*h.snapshot.MIB)
    junit=h.junit(reports)
    need(receipt.get('junit')==junit,'joining matrix exact JUnit receipt: '+kind)
    build=read(path/'build.json')
    need(type(build) is dict and set(build)==set(BUILDS) and receipt.get('buildSha256')==build_sha256==h.digest((path/'build.json').read_bytes()),
         'joining matrix exact build manifest: '+kind)
    for name in BUILDS:need(h.inventory(work/name)==build[name],'joining matrix original built bytes: '+kind)
    toolchain=read(path/'toolchain.json');toolchain_hash=h.digest((path/'toolchain.json').read_bytes())
    need(type(toolchain) is dict and type(toolchain.get('exit')) is int and toolchain['exit']==0 and
         receipt.get('toolchainSha256')==toolchain_hash,'joining matrix toolchain receipt: '+kind)
    name=receipt.get('raw')
    need(type(name) is str and re.fullmatch('workspace/'+h.MODULE+r'/target/v53-native-dispatch/run-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',name),
         'joining matrix original history path: '+kind)
    raw=path/name
    need(all((path/parent).is_dir() and not (path/parent).is_symlink() for parent in Path(name).parents),
         'joining matrix linked history parent: '+kind)
    need({v.name for v in raw.parent.iterdir()}=={raw.name},'joining matrix exact original history directory: '+kind)
    collection=read(path/'collection.json');inventory=h.inventory(raw)
    need(type(collection) is dict and receipt.get('collectionSha256')==h.digest((path/'collection.json').read_bytes()) and
         collection.get('status')=='PARTIAL' and collection.get('collectionComplete') is True and
         all(collection.get(k) is False for k in ('nativeHistoryQualified','forceAndNetworkQualified','phase3Complete')) and
         collection.get('inventory')==inventory,'joining matrix original collection: '+kind)
    # Original plan includes original execution paths. Its physical validity is
    # checked downstream; distinct copies of one history cannot fill the matrix.
    plan_hash=h.digest(h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB))
    return dict(raw=raw,toolchain=toolchain_hash,plan=plan_hash,inventory=inventory,
                receiptSha256=h.digest((path/'receipt.json').read_bytes()))


def validate(paths,source_sha256,build_sha256,progress=None):
    need(hash_field(source_sha256) and hash_field(build_sha256),'joining matrix pinned source/build hashes')
    need(set(paths)==set(KINDS) and len(paths)==3,'joining matrix complete reply set')
    need(len({Path(v).resolve() for v in paths.values()})==3,'joining matrix distinct producer directories')
    members={kind:member(paths[kind],kind,source_sha256,build_sha256) for kind in KINDS}
    need(len({v['toolchain'] for v in members.values()})==1,'joining matrix exact toolchain cohort')
    need(len({v['plan'] for v in members.values()})==3,'joining matrix distinct original histories')
    outcomes=[]
    for kind in KINDS:
        value=members[kind]
        if progress:progress(dict(stage='original-first-replay',case=kind))
        result=gate.qualify(value['raw'],None if progress is None else lambda row:progress(dict(row,member=kind)))
        original=result['original'];expected=[dict(case=name,status='REJECTED',reason=reason) for name,reason in gate.negative_reasons(original.get('transportFormat','legacy')).items()]
        need(original.get('status')=='PASS' and original.get('sourceFault')==kind and original.get('joiningSourceFaultQualified') is True and
             original.get('lostReplies')==original.get('recoveredLostReplies')==1 and original.get('phase3Complete') is False and
             result.get('originalPreserved') is True and result.get('negatives')==expected,'joining matrix complete replay result: '+kind)
        need(h.inventory(value['raw'])==value['inventory'],'joining matrix original history changed: '+kind)
        # Recheck provenance after all semantic work, including sources/classes.
        need(member(paths[kind],kind,source_sha256,build_sha256)==value,'joining matrix producer changed during replay: '+kind)
        outcomes.append(dict(case=kind,status='PASS',producerReceiptSha256=value['receiptSha256'],originalPlanSha256=value['plan'],qualification=result))
    for kind in KINDS:
        need(member(paths[kind],kind,source_sha256,build_sha256)==members[kind],
             'joining matrix producer changed before completion: '+kind)
    return dict(schema='gse-v53-joining-fault-matrix-v1',status='PASS',scope='complete-3-ADD-initial-learner-three-reply-losses',
                sourceSha256=source_sha256,buildSha256=build_sha256,toolchainSha256=members[KINDS[0]]['toolchain'],
                cases=outcomes,wholeHistories=3,negativeCases=3*len(gate.NEGATIVES),joiningSourceFaultMatrixQualified=True,
                allMembershipProfilesQualified=False,processDeathQualified=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offer',required=True);parser.add_argument('--chunk',required=True)
    parser.add_argument('--commit',required=True);parser.add_argument('--source-sha256',required=True);parser.add_argument('--build-sha256',required=True)
    args=parser.parse_args()
    result=validate(dict(zip(KINDS,(args.offer,args.chunk,args.commit))),args.source_sha256,args.build_sha256,
                    lambda row:print(json.dumps(row),file=sys.stderr,flush=True))
    print(json.dumps(result,sort_keys=True))
