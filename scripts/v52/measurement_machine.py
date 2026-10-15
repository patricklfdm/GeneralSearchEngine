"""Exact local machine freeze; commit its sole JSON change before measurements.

The JSON names its already committed implementation parent. The next commit must
change only this file, avoiding a self-referential commit hash. Actual histories
bind the resulting freeze commit and its full checkout hash, separately.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import time
from scripts import ci_v51_bundle as build
from . import measurement_runtime as runtime,measurement_model as model,measurement_options as options
from . import measurement_m01 as m01,measurement_m01_evidence as m01_evidence,measurement_m01_set as m01_set
from . import measurement_minimum as minimum,measurement_minimum_evidence as minimum_evidence
from . import measurement_recovery as recovery,measurement_recovery_evidence as recovery_evidence
from . import measurement_trace as trace,measurement_bundle as bundle,measurement_authority_budget as budget,measurement_oracle as oracle
from .evidence import need,digest,encoded

ROOT=Path(__file__).resolve().parents[2]
PLAN='docs/v5x/v5.2/phase6-local-machine.json'
SCHEMA='gse-v52-local-machine-v1'
MINIMUM_FREE_BYTES=16<<30


def members():
    result={m01_set.name(mode,rep):dict(family='M01',mode=mode,profile=m01.profile(mode,rep)) for mode,rep in m01_set.MEMBERS}
    result.update({case:dict(family=minimum.profile(case)['family'],mode='candidate-minimum',profile=minimum.profile(case)) for case in minimum.CASES})
    result.update({case:dict(family='M04',mode='candidate-minimum',profile=recovery.profile(case)) for case in recovery.CASES})
    return result


def negative_rules(spec):
    plan=spec['profile'];family=spec['family'];node='node-1'
    if family=='M01':cases=m01_evidence.negative_cases(spec['mode'],'initial',node)
    elif family in ('M02','M03'):
        scenario=dict(leader=node,readTarget=node,initialRead='initial',admittedProbe='probe',floorProbes={node:dict(opId='floor')})
        cases=minimum_evidence.negative_cases(plan,scenario)
    else:cases=recovery_evidence.negative_cases(plan,dict(leader=node,initialRead='initial',installed=dict(probe=dict(opId='installed'))))
    return [dict(case=v[0],status='REJECTED',reason=v[4]) for v in cases]


def contract():
    model.load();specs=members();program=model.program()
    return dict(programSha256=model.PLAN_SHA,corpusSha256=digest(model.corpus_bytes()),program=model.PLAN.name,
        callsSha256=digest(encoded(program)),queriesSha256=digest(encoded(model.queries())),members=specs,
        negativeRules={name:negative_rules(spec) for name,spec in specs.items()},
        runtime=dict(voters=3,frameBytes=1<<20,entries=100,inFlight=8,protocolRetries=2,requestTimeoutMillis=1200,
            backoffMillis=25,chunkBytes=65536,retainedBytes=64<<20,stagingBytes=64<<20,heartbeatMillis=1200,
            electionMinimumMillis=3600,electionMaximumMillis=6000,defaultRead=options.parameters(),
            consumerThreads=8,consumerQueue=64,commandsPerProcess=4096,commandBytes=16384,responseBytes=65536),
        evidence=dict(tracePerVoterAcrossGenerations=vars(trace.Limits()),bundle=bundle.LIMITS,authority=budget.LIMITS,
            selectedExpansionBytes=budget.MAX_SELECTION_EXPANSION,selectorCount=budget.MAX_SELECTORS,
            snapshotTransferCount=128,snapshotImageBytes=16<<20,snapshotTransferBytes=64<<20,resourceRowsPerProcess=1024,
            preReopenFiles=4096,preReopenBytes=64<<20,preReopenMemberBytes=8<<20,
            queryRequests=oracle.MAX_REQUESTS,queryInputBytes=oracle.MAX_INPUT_BYTES,queryOutputBytes=oracle.MAX_OUTPUT_BYTES,queryRowBytes=oracle.MAX_ROW_BYTES),
        execution=dict(order=list(specs),concurrentHistories=1,businessRetries=0,workloadRetries=0,stopAfterFailedMember=True,
            minimumFreeBytes=MINIMUM_FREE_BYTES,paidCloud=False,nominalM01Seconds=2700,totalHistories=28,
            acceptance='complete original and relocated physical/public/query/resource replay plus exact negatives; no speedup or latency SLA',
            timing='controller and each JVM clock remain separate; every offered outcome retained',
            failure='preserve complete failed member and prior receipts; no acceptance by selective rerun'))


def shell(*args,cwd=None):return subprocess.check_output(args,cwd=cwd,text=True).strip()


def clean_source(root=ROOT):
    need(not build.git(root,'status','--porcelain').strip(),'machine freeze requires clean tracked/untracked source')
    return build.binding(root,build.git(root,'rev-parse','HEAD').decode().strip())


def environment(storage_root):
    path=Path(storage_root).resolve();need(path.is_dir() and not path.is_symlink(),'machine storage root')
    need(platform.system()=='Linux','machine qualification requires Linux')
    mount=json.loads(shell('findmnt','-J','-T',str(path),'-o','SOURCE,FSTYPE,OPTIONS'))['filesystems']
    need(len(mount)==1 and mount[0]['fstype'] in ('ext4','xfs','btrfs'),'machine requires declared native Linux filesystem')
    def optional(path):
        p=Path(path);return p.read_text().strip() if p.is_file() else None
    model_names=sorted({line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')})
    memory=next(line.split(':',1)[1].strip() for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    java=Path(shutil.which('java')).resolve();javac=Path(shutil.which('javac')).resolve();clock=time.get_clock_info('monotonic')
    return dict(kernel=platform.release(),architecture=platform.machine(),cpuModels=model_names,logicalCpus=os.cpu_count(),
        affinity=sorted(os.sched_getaffinity(0)),memTotal=memory,bootId=optional('/proc/sys/kernel/random/boot_id'),
        python=dict(version=platform.python_version(),executable=str(Path(os.sys.executable).resolve())),
        javaExecutable=dict(path=str(java),sha256=bundle.sha_file(java)),javacExecutable=dict(path=str(javac),sha256=bundle.sha_file(javac)),
        monotonicClock=dict(implementation=clock.implementation,resolution=clock.resolution,monotonic=clock.monotonic,adjustable=clock.adjustable),
        storage=dict(device=path.stat().st_dev,**mount[0]),
        cgroup={k:optional('/sys/fs/cgroup/'+k) for k in ('cpu.max','memory.max','pids.max')})


def validate_plan(value):
    need(type(value) is dict and set(value)=={'schema','status','paidCloud','implementation','contract','environment','storageRoot','compiled','build','createdUnixSeconds'},
         'machine plan fields')
    need(value['schema']==SCHEMA and value['status']=='FROZEN_BEFORE_MEASUREMENTS' and value['paidCloud'] is False,'machine plan status')
    # JSON turns authority limit tuples into arrays; compare canonical bytes.
    need(encoded(value['contract'])==encoded(contract()),'machine execution contract changed')
    need(set(value['compiled'])=={'published','candidate'},'machine compiled family set')
    for family,v in value['compiled'].items():
        need(set(v)=={'artifacts','classes'} and v['artifacts'] and v['classes'],'machine compiled/artifact identity')
        need(all(type(sha) is str and len(sha)==64 and all(c in '0123456789abcdef' for c in sha) for sha in [*v['artifacts'].values(),*v['classes'].values()]),
             'machine artifact/consumer digest shape')
    controls=runtime.evidence.reads.read(model.PLAN.parent/'published-controls.json')
    published={v['artifact']+'-'+v['version']+'.jar':v['sha256'] for v in controls['artifacts']}
    need(value['compiled']['published']['artifacts']==published,'machine published controls changed')
    candidate=value['compiled']['candidate']['artifacts']
    need(set(candidate)=={'general-search-engine-5.2.0-SNAPSHOT.jar','general-search-engine-replication-5.2.0-SNAPSHOT.jar','general-search-engine-4.4.0.jar'} and
         candidate['general-search-engine-4.4.0.jar']==published['general-search-engine-4.4.0.jar'],'machine candidate/control artifact set')
    need(value['build']['binding']==value['implementation'],'machine build/source mismatch')
    need(Path(value['storageRoot']).is_absolute() and type(value['createdUnixSeconds']) is int and value['createdUnixSeconds']>0,'machine storage/time shape')
    return value


def freeze(build_directory,storage_root,output):
    implementation=clean_source();storage_root=Path(storage_root).resolve();output=Path(output).resolve()
    need(output==ROOT/PLAN and not output.exists(),'machine freeze output must be fresh designated document')
    need(not storage_root.exists() and ROOT/'target' in storage_root.parents,'machine fresh target storage root')
    build_directory=Path(build_directory).resolve();manifest=runtime.evidence.reads.read(build_directory/'manifest.json')
    need(manifest['schema']==build.SCHEMA and manifest['binding']==implementation and
         bundle.sha_file(build_directory/'build.tar.gz')==manifest['archiveSha256'],'machine missing exact-source build bundle')
    files={v['path']:v for v in manifest['files']};need(len(files)==len(manifest['files']),'machine duplicate build file')
    for path in build.layout(ROOT)[:2]:need(path in files and bundle.sha_file(ROOT/path)==files[path]['sha256'],'machine current build artifact drift')
    storage_root.mkdir(parents=True);compiled={};env=environment(storage_root)
    need(shutil.disk_usage(storage_root).free>=MINIMUM_FREE_BYTES,'machine insufficient free storage')
    probes=storage_root/'preparation-only';probes.mkdir()
    for family,mode in (('published','published-v51-legacy-strong'),('candidate','candidate-minimum')):
        binding,_,_=runtime.prepare(probes/family,mode,m01_repetition=1)
        need({k:binding[k] for k in implementation}==implementation,'machine source changed during preparation')
        compiled[family]={k:binding[k] for k in ('artifacts','classes')}
    need(clean_source()==implementation,'machine source changed during freeze')
    need(environment(storage_root)==env,'machine environment changed during preparation')
    value=dict(schema=SCHEMA,status='FROZEN_BEFORE_MEASUREMENTS',paidCloud=False,implementation=implementation,contract=contract(),environment=env,
        storageRoot=str(storage_root),compiled=compiled,build=dict(binding=manifest['binding'],manifestSha256=bundle.sha_file(build_directory/'manifest.json'),
        archiveSha256=manifest['archiveSha256']),createdUnixSeconds=int(time.time()))
    validate_plan(value);runtime.save(output,value);runtime.save(storage_root/'frozen-machine.json',value)
    return dict(status='PREPARED',paidCloud=False,plan=str(output),sha256=digest(encoded(value)),
                next='Commit only the designated machine JSON; execution requires its exact parent and clean checkout.')


def admit(root=ROOT):
    value=validate_plan(runtime.evidence.reads.read(root/PLAN));actual=clean_source(root)
    parent=build.git(root,'rev-parse','HEAD^').decode().strip()
    need(parent==value['implementation']['source'],'machine freeze commit must directly follow implementation')
    changed=build.git(root,'diff','--name-only',parent,'HEAD').decode().splitlines()
    need(changed==[PLAN],'machine freeze commit changed implementation')
    need(actual['java']==value['implementation']['java'],'machine JVM changed since build')
    # Reconstruct the exact implementation inventory without the newly added
    # freeze document. Never treat merely being a descendant as source equality.
    names=build.git(root,'ls-files','-z').split(b'\0');inventory=[]
    for raw in sorted(set(names)-{b'',PLAN.encode()}):
        name=os.fsdecode(raw);p=root/name;inventory.append([name,bool(p.stat().st_mode&0o111),digest(p.read_bytes())])
    need(build.digest(build.encoded(inventory))==value['implementation']['checkoutSha256'],'machine implementation checkout differs')
    need(environment(value['storageRoot'])==value['environment'],'machine environment changed since freeze')
    return value,actual


def committed_binding(root,source,java):
    """Reconstruct the recorded checkout digest from immutable Git bytes."""
    process=subprocess.Popen(['git','-C',str(root),'archive','--format=tar',source],stdout=subprocess.PIPE)
    inventory=[];total=0
    try:
        with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
            for item in archive:
                if item.isdir():continue
                need(item.isfile() and len(inventory)<20000 and 0<=item.size<=64<<20,'machine source archive type/bound')
                total+=item.size;need(total<=256<<20,'machine source archive total bound')
                with archive.extractfile(item) as content:data=content.read(item.size+1)
                need(len(data)==item.size,'machine source archive changed')
                inventory.append([item.name,bool(item.mode&0o111),digest(data)])
        need(process.wait(timeout=10)==0,'machine source archive failed')
    finally:
        process.stdout.close()
        if process.poll() is None:process.kill();process.wait(timeout=10)
    return dict(source=source,checkoutSha256=build.digest(build.encoded(sorted(inventory))),java=java)


def verify_launch(value,actual,root=ROOT):
    validate_plan(value);source=actual['source']
    need(build.git(root,'rev-parse',source+'^').decode().strip()==value['implementation']['source'], 'machine replay freeze parent changed')
    need(build.git(root,'diff','--name-only',source+'^',source).decode().splitlines()==[PLAN], 'machine replay implementation changed')
    need(build.git(root,'show',source+':'+PLAN)==encoded(value)+b'\n','machine replay committed plan differs')
    need(actual==committed_binding(root,source,value['implementation']['java']),'machine replay checkout binding differs')
    return actual


def check_binding(value,actual,name,binding):
    validate_plan(value);spec=value['contract']['members'].get(name);need(spec is not None,'machine undeclared member')
    need({k:binding[k] for k in actual}==actual and binding['mode']==spec['mode'] and binding['measurementProfile']==spec['profile'] and
         binding['programSha256']==model.PLAN_SHA,'machine member source/profile mismatch')
    family='published' if spec['mode'].startswith('published') else 'candidate'
    need({k:binding[k] for k in ('artifacts','classes')}==value['compiled'][family],'machine member artifact/consumer drift')
    root=Path(value['storageRoot'])/'histories'/name
    need(binding['origin']==str(root),'machine member origin mismatch')
    return spec


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--storage-root',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/PLAN)
    a=p.parse_args();print(json.dumps(freeze(a.build,a.storage_root,a.output),sort_keys=True))
