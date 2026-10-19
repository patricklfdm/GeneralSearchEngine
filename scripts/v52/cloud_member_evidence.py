"""Replay a complete retained native member without running a workload.

Raw files and separately selected completion/cleanup/ledger are required. These
local checks do not authenticate a cloud download or grant full qualification.
"""
from copy import deepcopy
import math
from pathlib import Path
from . import cloud_authority as a,cloud_evidence_parts as parts,cloud_retention as retention
from . import cloud_member_authority as authority,cloud_inputs as inputs,cloud_artifacts as artifacts
from . import cloud_suite as suite,remote_history as history,measurement_bundle as bundle
from . import measurement_runtime_evidence as smoke,measurement_m01_evidence as m01
from . import measurement_minimum_evidence as minimum,measurement_recovery_evidence as recovery
from .evidence import need,encoded,digest


def names(request):
    selected=request['selection']['member']['histories']
    return {'inputs.tar.gz','authority.json','member.json',
        *['provenance/'+name for name in retention.BUILD_FILES],
        *['recent-cleanup/'+name for name in ('observation.json','cleanup.zip','receipt.json')],
        *['histories/'+name+'/'+file for name in selected for file in ('history.tar.gz','result.json')]}


def inventory(root,request,manifest):
    parts.validate(manifest,request);root=Path(root)
    expected=names(request);need({r['name'] for r in manifest['files']}==expected,'V5.2 member evidence inventory')
    directories={p.as_posix() for name in expected for p in Path(name).parents if p.as_posix()!='.'}
    need(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),'V5.2 member evidence root')
    for path in root.rglob('*'):
        name=path.relative_to(root).as_posix()
        need(not path.is_symlink() and (name in directories and path.is_dir() or name in expected and path.is_file()),
             'V5.2 unexpected member evidence path')
    need(parts.scan({name:root/name for name in expected},request)==manifest,'V5.2 original member file bytes changed')
    return root


def completion(request,manifest,completed,clean,ledger,claim,plan):
    a.validate_completion(completed,request);a.fields(clean,'status checks errors leftovers','original cleanup')
    sha=a.validate_request(request,domain='native')
    need(completed['status']=='PASS' and completed['evidenceSha256']==digest(encoded(manifest)) and
         completed['cleanupSha256']==digest(encoded(clean)),'V5.2 retained successful completion binding')
    lease=authority.resource_claim(request,claim)
    expected={row['spec']['name']:row['id'] for row in lease['resources']}
    need(clean['status']=='PASS' and clean['errors']==[] and clean['leftovers']==[] and type(clean['checks']) is list and
         len(clean['checks'])==len(expected),'V5.2 original cleanup incomplete')
    seen=set()
    for row in clean['checks']:
        a.fields(row,'name expectedId absent observed','original cleanup check')
        need(row['name'] in expected and row['name'] not in seen and row['expectedId']==expected[row['name']] and
             row['absent'] is True and row['observed'] is None,'V5.2 original exact-ID absence changed')
        seen.add(row['name'])
    view=a.inspect_ledger(ledger,domain='native')
    need(view['attempts'].get(sha)==dict(request=request,status='PASS'),'V5.2 original successful ledger attempt')
    baseline=plan['baseline']['ledger'] if plan['baseline'] else a.empty_ledger(domain='native')
    start=len(baseline['entries']);cost=plan['reservation']['costMicrousd']
    need(ledger['entries'][:start]==baseline['entries'] and ledger['entries'][start:start+2]==[
        dict(kind='RESERVED',requestSha256=sha,request=request,reservedCostMicrousd=cost),
        dict(kind='FINISHED',requestSha256=sha,status='PASS',completionSha256=digest(encoded(completed)))],
        'V5.2 original reservation/terminal history changed')
    return dict(reservedCostMicrousd=cost,totalReservedCostMicrousd=view['reservedCostMicrousd'],
                completionSha256=digest(encoded(completed)),cleanupSha256=digest(encoded(clean)))


def replay_history(archive,name,binding,output):
    """Only replay original bytes; this helper also supports historical local tests."""
    spec=history.specification(name);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    family=spec['family']
    need(binding['mode']==spec['mode'] and (family=='UNTIMED' or binding.get('measurementProfile')==spec['profile']),
         'V5.2 retained frozen history profile')
    root=bundle.unpack(archive,output/'raw')
    driver={'UNTIMED':smoke,'M01':m01,'M02':minimum,'M03':minimum,'M04':recovery}[family]
    result=driver.replay(root,binding,output/'validation',**({'package':bundle} if family=='UNTIMED' else {}))
    if family!='UNTIMED':need(result['negatives']==suite.load()['formalNegativeRules'][name],'V5.2 retained exact history negatives')
    reads,updates=history.original_counts(result,spec)
    if family=='UNTIMED':need(reads==spec['reads'] and updates==spec['updates'],'V5.2 retained original call counts')
    manifest=(root/'node-1/manifest.gsr').read_bytes();record=m01.physical.f.inspect(manifest,'MANIFEST')
    return dict(result=result,reads=reads,updates=updates,domain={k:record[k] for k in ('groupId','historyId')},
        manifestSha256=digest(manifest),archiveSha256=bundle.sha_file(archive))


def bound_history(value,name,source,admitted):
    a.fields(value,'status history family mode binding result archiveSha256 originalReads originalUpdates '
             'qualifiedMeasurement fullRemoteQualification paidCloud','retained history result')
    spec=history.specification(name);binding=value['binding'];placement=admitted['placements'][name]
    need(value['status']=='PASS' and value['history']==name and value['family']==spec['family'] and value['mode']==spec['mode'] and
         all(value[k] is False for k in ('qualifiedMeasurement','fullRemoteQualification','paidCloud')),
         'V5.2 retained history result scope')
    need(all(binding.get(k)==v for k,v in placement.items()) and binding['mode']==spec['mode'],
         'V5.2 retained history original placement')
    own=admitted['preflight']['credentialContext']
    need(binding['run']==str(own['runId']) and type(binding['attempt']) is int and binding['attempt']==own['runAttempt'],
         'V5.2 retained history original invocation')
    version='5.1.0' if spec['mode'].startswith('published') else inputs.VERSION
    names={f'general-search-engine-{version}.jar',f'general-search-engine-replication-{version}.jar','general-search-engine-4.4.0.jar'}
    need(binding['artifacts']=={name:digest(admitted['files']['artifacts/'+name]) for name in names},
         'V5.2 retained history original artifacts')
    storage=admitted['storage'];a.fields(binding['remoteReceivers'],'node-1 node-2 node-3','retained receivers')
    need(all(binding['remoteReceivers'][n]['originalRoot']==root for n,root in admitted['roots'][name].items()),
         'V5.2 retained history original roots')
    need(binding['remotePython']['nodes']==storage['python'] and binding['remoteJava']['nodes']==storage['java'] and
         binding['remoteJava']['descriptorSha256']==digest(encoded(storage['javaDescriptor'])),
         'V5.2 retained history original installations')
    return binding


def replay(root,request,manifest,completed,clean,ledger,source,cfg,output,*,progress=lambda stage,**kw:None):
    """Internal local replay; caller must authenticate selected original objects."""
    root=inventory(root,request,manifest);output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)) and root.resolve() not in output.resolve().parents and
         output.resolve() not in root.resolve().parents and output.resolve()!=root.resolve(),'V5.2 replay output overlap')
    output.mkdir(parents=True,exist_ok=False);result=dict(status='FAIL',fullRemoteQualification=False,paidCloud=False)
    try:
        progress('authority');value=artifacts.read(root/'authority.json');admitted=authority.replay(root,value,request,source,cfg)
        accounting=completion(request,manifest,completed,clean,ledger,value['claim'],value['plan'])
        selected=request['selection'];receipt=artifacts.read(root/'member.json')
        a.fields(receipt,'schema status selection source resourceClaimSha256 histories fullRemoteQualification paidCloud elapsedSeconds',
                 'original member execution')
        need(receipt['schema']=='gse-v52-native-member-execution-v1' and receipt['status']=='MEMBER_EXECUTED_NOT_QUALIFIED' and
             receipt['selection']==selected and receipt['source']==source and
             receipt['resourceClaimSha256']==digest(encoded(value['claim'])) and
             receipt['fullRemoteQualification'] is False and receipt['paidCloud'] is True and
             type(receipt['elapsedSeconds']) in (int,float) and math.isfinite(receipt['elapsedSeconds']) and receipt['elapsedSeconds']>=0,
             'V5.2 original member execution identity')
        rows=[];replayed={};bindings={};groups=set();histories=set();manifests=set()
        for name in selected['member']['histories']:
            progress('history-replay',name=name,completed=len(rows));directory=root/'histories'/name
            original=artifacts.read(directory/'result.json');binding=bound_history(original,name,source,admitted)
            actual=replay_history(directory/'history.tar.gz',name,binding,output/name)
            need(actual['result']==original['result'] and actual['archiveSha256']==original['archiveSha256'] and
                 (actual['reads'],actual['updates'])==(original['originalReads'],original['originalUpdates']),
                 'V5.2 original history replay differs from retained result')
            group,history_id=(actual['domain'][k] for k in ('groupId','historyId'))
            need(group not in groups and history_id not in histories and actual['manifestSha256'] not in manifests,
                 'V5.2 repeated original history')
            groups.add(group);histories.add(history_id);manifests.add(actual['manifestSha256']);replayed[name]=actual;bindings[name]=binding
            rows.append(dict(history=name,archive=name+('/history.tar.gz' if original['family']=='UNTIMED' else '/portable/history.tar.gz'),
                archiveSha256=actual['archiveSha256'],bindingSha256=digest(encoded(binding)),reads=actual['reads'],updates=actual['updates']))
        need(receipt['histories']==rows and sum(r['reads'] for r in rows)==selected['member']['reads'] and
             sum(r['updates'] for r in rows)==selected['member']['updates'],'V5.2 original complete member history rows')
        inventory(root,request,manifest)
        result.update(status='MEMBER_REPLAYED_NOT_QUALIFIED',selection=deepcopy(selected),source=deepcopy(source),
            requestSha256=a.validate_request(request,domain='native'),manifestSha256=digest(encoded(manifest)),
            accounting=accounting,histories=replayed,bindings=bindings,claim=value['claim'],configurationSha256=authority.preflight.configuration(cfg),
            invocation={k:admitted['preflight']['credentialContext'][v] for k,v in (('run','runId'),('attempt','runAttempt'))})
        result['invocation']['run']=str(result['invocation']['run'])
        return result
    except BaseException as error:
        result['failure']=dict(type=type(error).__name__);raise
    finally:
        # Per-history validation retains detailed data. Keep the member receipt
        # bounded without copying all query/oracle inputs into a second JSON.
        saved={k:v for k,v in result.items() if k not in ('histories','bindings')}
        if result['status']=='MEMBER_REPLAYED_NOT_QUALIFIED':
            saved['histories']={name:{k:v for k,v in row.items() if k!='result'} for name,row in result['histories'].items()}
            saved['bindingHashes']={name:digest(encoded(v)) for name,v in result['bindings'].items()}
        artifacts.save(output/'receipt.json',saved)
