"""Complete M01 set and portable member replay; no workload execution CLI.

Expected bindings must come from the separately admitted machine freeze. Member
JSON claiming PASS is never used instead of replaying the actual retained bytes.
"""
import re
from pathlib import Path
from . import measurement_model as model,measurement_m01 as m01,measurement_m01_evidence as evidence
from . import measurement_bundle as bundle
from . import measurement_options as options
from .evidence import need,digest,encoded


def name(mode,repetition):return mode+'-r'+str(repetition)
MEMBERS=tuple((mode,repetition) for mode in model.MODES for repetition in (1,2,3))


def bindings(values):
    model.load();expected={name(mode,repetition) for mode,repetition in MEMBERS}
    need(type(values) is dict and set(values)==expected,'measurement M01 incomplete/extra member set')
    common=None;controls=evidence.reads.read(model.PLAN.parent/'published-controls.json')
    published={v['artifact']+'-'+v['version']+'.jar':v['sha256'] for v in controls['artifacts']}
    compiled={};artifacts={};origins=set()
    for mode,repetition in MEMBERS:
        value=values[name(mode,repetition)];profile=value.get('measurementProfile',{})
        need(value['mode']==mode and profile==m01.profile(mode,repetition) and value['programSha256']==model.PLAN_SHA,
             'measurement M01 member identity/program')
        need(value.get('readParameters')==options.parameters() and 'faultParameters' not in value,'measurement M01 set read parameters changed')
        need(re.fullmatch('[0-9a-f]{40}',value['source']) and re.fullmatch('[0-9a-f]{64}',value['checkoutSha256']) and
             type(value['attempt']) is int and value['attempt']>=1 and isinstance(value['run'],str) and value['run'],
             'measurement M01 source/attempt shape')
        cohort={k:value[k] for k in ('source','checkoutSha256','java','run','attempt')}
        if common is None:common=cohort
        else:need(cohort==common,'measurement M01 mixed source/build/JVM/run/attempt')
        need(isinstance(value['origin'],str) and Path(value['origin']).is_absolute() and value['origin'] not in origins,
             'measurement M01 repeated/nonabsolute member origin');origins.add(value['origin'])
        for artifact,sha in published.items():
            if artifact.endswith('-4.4.0.jar') or mode.startswith('published'):
                need(value['artifacts'].get(artifact)==sha,'measurement M01 changed published control')
        family='published' if mode.startswith('published') else 'candidate'
        if family in artifacts:
            need(value['artifacts']==artifacts[family] and value['classes']==compiled[family],
                 'measurement M01 mixed artifact/compiled consumer set')
        else:artifacts[family]=value['artifacts'];compiled[family]=value['classes']
    return dict(cohort=common,members=len(expected),artifacts=artifacts,classes=compiled)


def portable_member(source,expected,output):
    source=Path(source).resolve();output=Path(output).resolve()
    need(source!=output and source not in output.parents and output not in source.parents,'measurement M01 replay location overlap')
    output.mkdir(parents=True,exist_ok=False)
    receipt=dict(status='FAIL',execution='m01-portable-member',qualifiedMeasurement=False,paidCloud=False)
    try:
        # Pack the stopped history. The archive is immutable while both positive
        # and negative replays independently inspect raw and relocated authority.
        if (source/bundle.INDEX).exists():
            previous=bundle.inventory(source)
            need((source/bundle.INDEX).read_bytes()==encoded(previous)+b'\n','measurement M01 noncanonical existing inventory')
        archive=output/'history.tar.gz';index=bundle.pack(source,archive)
        original=evidence.replay(source,expected,output/'original-validation')
        relocated=bundle.unpack(archive,output/'relocated')
        portable=evidence.replay(relocated,expected,output/'relocated-validation')
        need(original==portable,'measurement M01 relocated result/negative drift')
        initial=evidence.metadata(source,'scenario.json',1<<20)
        required=[dict(case=v[0],status='REJECTED',reason=v[4]) for v in
                  evidence.negative_cases(expected['mode'],initial['initialRead'],initial['leader'])]
        need(original['negatives']==required,'measurement M01 incomplete negative qualification')
        need(bundle.inventory(source)==index==bundle.inventory(relocated),'measurement M01 source changed during replay')
        raw=(source/'node-1/manifest.gsr').read_bytes();manifest=evidence.physical.f.inspect(raw,'MANIFEST')
        receipt.update(status='PASS',binding=expected,domain={k:manifest[k] for k in ('groupId','historyId')},
                       manifestSha256=digest(raw),inventorySha256=digest(encoded(index)),archiveSha256=bundle.sha_file(archive),
                       archiveBytes=archive.stat().st_size,result=original)
        return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:(output/'receipt.json').write_bytes(encoded(receipt)+b'\n')


def validate_results(members,expected):
    """Cross-check independently replayed members, not self-attested input files."""
    admitted=bindings(expected);need(set(members)==set(expected),'measurement M01 replayed member set')
    groups=set();histories=set();manifests=set();outcomes={};total=0
    for mode,repetition in MEMBERS:
        key=name(mode,repetition);member=members[key]
        need(member['status']=='PASS' and member['execution']=='m01-portable-member' and member['binding']==expected[key] and
             member['qualifiedMeasurement'] is False and member['paidCloud'] is False,'measurement M01 unqualified member replay')
        group,history=member['domain']['groupId'],member['domain']['historyId']
        need(group not in groups and history not in histories and member['manifestSha256'] not in manifests,'measurement M01 reused history/domain')
        groups.add(group);histories.add(history);manifests.add(member['manifestSha256'])
        result=member['result'];need(result['status']=='PASS' and result['mode']==mode and result['repetition']==repetition and
            result['execution']=='m01-member-physical-replay' and result['qualifiedMeasurement'] is False and result['paidCloud'] is False and
            result['windows']['completed']==1980 and result['windows']['offered']==1980,'measurement M01 member result identity/count')
        total+=result['windows']['completed'];outcomes[key]=result['ledger']['outcomes']
    return dict(status='PASS',execution='m01-complete-portable-set',qualifiedMeasurement=False,paidCloud=False,
                cohort=admitted['cohort'],histories=len(members),completedOfferedCalls=total,offeredReadCalls=27000,
                offeredUpdateCalls=2700,setupStrongReads=15,nominalOfferedSeconds=2700,outcomes=outcomes,
                boundary='M01 set only; complete machine and M02-M04 admission remain required')


def replay_set(inputs,expected,output):
    """Reject mixed plans before expensive work; stop with prior evidence intact."""
    bindings(expected);need(set(inputs)==set(expected),'measurement M01 input member set')
    paths=[Path(v).resolve() for v in inputs.values()]
    need(len(set(paths))==15 and all(a not in b.parents for a in paths for b in paths if a!=b),'measurement M01 overlapping/repeated input roots')
    output=Path(output).resolve()
    need(all(output!=p and p not in output.parents and output not in p.parents for p in paths),'measurement M01 set output overlap')
    output.mkdir(parents=True,exist_ok=False);members={};receipt=dict(status='FAIL',execution='m01-set-replay',qualifiedMeasurement=False,paidCloud=False)
    try:
        for mode,repetition in MEMBERS:
            key=name(mode,repetition);members[key]=portable_member(inputs[key],expected[key],output/key)
        receipt=validate_results(members,expected)
        return receipt
    except BaseException as error:receipt['failure']=dict(type=type(error).__name__,message=str(error));raise
    finally:
        receipt['completedMembers']=list(members)
        (output/'receipt.json').write_bytes(encoded(receipt)+b'\n')
