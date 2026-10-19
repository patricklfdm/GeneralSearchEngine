"""Original exact-attempt manual cleanup provenance. GET only; no cloud token.

A recent idle PASS is enough to observe the manual entry; it is not a real-delete
or IAM audit. Runner separately owns fresh provider/control and paid admission.
"""
import argparse
from copy import deepcopy
import io
from pathlib import Path
import re
import stat
import time
import zipfile
from . import cloud_ci as ci, cloud_artifacts as artifacts, cloud_authority as a
from . import cloud_credentials as credentials, cloud_preflight as preflight, cloud_preflight_read as reads
from . import cloud_cleanup_bundle as bundle, cloud_cleanup_workflow as workflow
from .evidence import need, encoded, digest

SCHEMA='gse-v52-recent-cleanup-v1'
MAX_ZIP=66<<20
RECENT_SECONDS=7200
OBSERVATION_SECONDS=900


def run_identity(value,source):
    for key in ('id','run_attempt','workflow_id'):a.integer(value[key],1)
    for key in ('repository','head_repository'):
        row=value[key]
        need(type(row['id']) is int and row['id']==credentials.REPOSITORY_ID and row['full_name']==credentials.REPOSITORY and
             type(row['owner']['id']) is int and row['owner']['id']==credentials.OWNER_ID,'V5.2 cleanup repository identity')
    need(value['head_sha']==source and value['head_branch']=='master' and value['path']==workflow.PATH and
         value['event']=='workflow_dispatch' and value['status']=='completed' and value['conclusion']=='success',
         'V5.2 cleanup run not exact-master completed success')
    return value


def latest(rows,source):
    need(type(rows) is list and 0<len(rows)<1000 and
         len({a.integer(r['id'],1) for r in rows})==len(rows),'V5.2 cleanup run inventory')
    need(all(r['head_sha']==source and r['head_branch']=='master' and r['path']==workflow.PATH for r in rows),
         'V5.2 cleanup run outside exact source')
    return max(rows,key=lambda row:row['id'])  # Never skip a newer failed/waiting attempt.


def listing(get,source):
    return ci.pages(get,'actions/workflows/v52-manual-cleanup.yml/runs?branch=master&head_sha='+source,'workflow_runs',limit=999)


def name(run):return f"v52-cleanup-manual-{run['id']}-{run['run_attempt']}"


def job(rows,run,now):
    need(type(rows) is list and len(rows)==1 and rows[0]['name']==workflow.JOB,'V5.2 cleanup job inventory')
    value=rows[0];ci.job_identity(value,run,now=now,required=workflow.REQUIRED)
    times={step['name']:(ci.stamp(step['started_at']),ci.stamp(step['completed_at'])) for step in value['steps'] if step['name'] in workflow.REQUIRED}
    need(all(times[left][1]<=times[right][0] for left,right in zip(workflow.REQUIRED,workflow.REQUIRED[1:])),
         'V5.2 cleanup steps out of order')
    return value,times


def metadata(value,run,times,now):
    a.integer(value['id'],1);a.integer(value['size_in_bytes'],1,MAX_ZIP)
    need(value['name']==name(run) and value['expired'] is False and ci.stamp(value['expires_at'])>now,'V5.2 cleanup artifact name/expiry')
    origin=value['workflow_run']
    for key in ('id','repository_id','head_repository_id'):a.integer(origin[key],1)
    need(origin['id']==run['id'] and origin['repository_id']==origin['head_repository_id']==credentials.REPOSITORY_ID and
         origin['head_sha']==run['head_sha'] and origin['head_branch']=='master','V5.2 cleanup artifact original execution')
    sha=value['digest'];need(type(sha) is str and sha.startswith('sha256:'),'V5.2 cleanup artifact digest missing');a.hex_value(sha[7:])
    need(times[workflow.UPLOAD][0]<=ci.stamp(value['created_at'])<=ci.stamp(value['updated_at'])<=times[workflow.UPLOAD][1],
         'V5.2 cleanup artifact outside exact upload')
    return sha[7:]


def select(rows,run,times,now):
    need(type(rows) is list and len(rows)<=ci.MAX_ROWS and len({a.integer(r['id'],1) for r in rows})==len(rows),
         'V5.2 cleanup artifact inventory')
    matches=[row for row in rows if row['name']==name(run)]
    need(len(matches)==1,'V5.2 cleanup original artifact missing/ambiguous');metadata(matches[0],run,times,now)
    return matches[0]


def contents(path,record,sha):
    raw=artifacts.inputs.regular(path,MAX_ZIP)
    need(len(raw)==record['size_in_bytes'] and digest(raw)==sha,'V5.2 cleanup original ZIP bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows=archive.infolist();names=[v.filename for v in rows]
        need(len(names)==len(set(names)) and bundle.FILES|{'seal.json'}<=set(names)<=bundle.FILES|bundle.OPTIONAL|{'seal.json'},
             'V5.2 cleanup ZIP inventory')
        total=0
        for row in rows:
            mode=row.external_attr>>16;maximum=(1<<20) if row.filename=='seal.json' else bundle.LIMITS[row.filename]
            need(row.orig_filename==row.filename and not row.is_dir() and not row.flag_bits&1 and
                 stat.S_IFMT(mode) in (0,stat.S_IFREG) and row.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and
                 0<row.file_size<=maximum,'V5.2 cleanup ZIP member')
            total+=row.file_size
        need(total<=bundle.MAX_BYTES+(1<<20),'V5.2 cleanup ZIP expanded size')
        return {name:archive.read(name) for name in names}


def validate(value,cfg,source,archive,now):
    a.fields(value,'schema source configurationSha256 startedAt completedAt masterBefore masterAfter runsBefore runsAfter '
             'run runAttempt runAfter jobs jobsAfter artifact artifactAfter artifactsBefore artifactsAfter workflowContent','cleanup observation')
    need(value['schema']==SCHEMA and value['source']==value['masterBefore']==value['masterAfter']==source and
         value['configurationSha256']==preflight.configuration(cfg),'V5.2 cleanup source/configuration')
    a.integer(value['startedAt'],max(1,now-OBSERVATION_SECONDS),now);a.integer(value['completedAt'],value['startedAt'],now)
    run=run_identity(value['run'],source)
    for other in (value['runAttempt'],value['runAfter'],latest(value['runsBefore'],source),latest(value['runsAfter'],source)):
        run_identity(other,source);need(encoded(ci.run_key(other))==encoded(ci.run_key(run)),'V5.2 cleanup run/attempt changed')
    original,times=job(value['jobs'],run,now);after,_=job(value['jobsAfter'],run,now)
    need(encoded(ci.job_key(original))==encoded(ci.job_key(after)),'V5.2 cleanup job changed')
    end=ci.stamp(original['completed_at']);need(now-RECENT_SECONDS<end<=value['startedAt'],'V5.2 cleanup completion stale/future')
    ci.source_content(value['workflowContent'],workflow.PATH,workflow.render())
    record=value['artifact'];sha=metadata(record,run,times,now)
    for other in (value['artifactAfter'],select(value['artifactsBefore'],run,times,now),select(value['artifactsAfter'],run,times,now)):
        need(encoded(record)==encoded(other),'V5.2 cleanup artifact changed')
    files=contents(archive,record,sha);inspection=bundle.verify(files,source,now)
    need(inspection['status']=='PASS' and inspection['runId']==run['id'] and inspection['runAttempt']==run['run_attempt'] and
         inspection['configurationSha256']==preflight.configuration(cfg),'V5.2 cleanup receipt not original native PASS')
    receipt=artifacts.strict(files['receipt.json']);observed=artifacts.strict(files['observations.json'])
    need(times[workflow.RECONCILE][0]<=observed['startedAt']<=observed['completedAt']<=receipt['decisionAt']<=
         receipt['checkedAt']<=times[workflow.RECONCILE][1],'V5.2 cleanup receipt outside original step')
    return dict(schema=SCHEMA,status='RECENT_CLEANUP_VERIFIED_NOT_ADMITTED',source=source,configurationSha256=preflight.configuration(cfg),
        runId=run['id'],runAttempt=run['run_attempt'],artifactId=record['id'],artifactSha256=sha,completedAt=end,
        expiresAt=min(value['startedAt']+OBSERVATION_SECONDS,end+RECENT_SECONDS),
        deletionPathExercised=inspection['deletionPathExercised'],paidAdmission=False,effectiveIamQualified=False,fullRemoteQualification=False)


def collect(directory,cfg,source,client,wall,progress):
    directory=Path(directory);started=int(wall());progress['phase']='cleanup-selection'
    master=client.get('branches/master')['commit']['sha'];need(master==source,'V5.2 cleanup not current master')
    rows=listing(client.get,source);selected=latest(rows,source);run=client.get('actions/runs/'+str(selected['id']))
    run_identity(run,source);need(encoded(ci.run_key(run))==encoded(ci.run_key(selected)),'V5.2 cleanup selection changed')
    attempt=client.get(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}")
    jobs=ci.jobs(client.get,run);_,times=job(jobs,run,int(wall()))
    records=ci.pages(client.get,f"actions/runs/{run['id']}/artifacts",'artifacts');record=select(records,run,times,int(wall()))
    need(encoded(client.get('actions/artifacts/'+str(record['id'])))==encoded(record),'V5.2 cleanup artifact metadata mismatch')
    progress['phase']='cleanup-download';client.download(record['id'],directory/'cleanup.zip',record['size_in_bytes'])
    progress['phase']='cleanup-final-observation'
    value=dict(schema=SCHEMA,source=source,configurationSha256=preflight.configuration(cfg),startedAt=started,
        masterBefore=master,runsBefore=rows,run=run,runAttempt=attempt,jobs=jobs,artifactsBefore=records,artifact=record,
        workflowContent=client.get('contents/'+workflow.PATH+'?ref='+source),
        artifactAfter=client.get('actions/artifacts/'+str(record['id'])),
        artifactsAfter=ci.pages(client.get,f"actions/runs/{run['id']}/artifacts",'artifacts'),
        jobsAfter=ci.jobs(client.get,run),runAfter=client.get('actions/runs/'+str(run['id'])),runsAfter=listing(client.get,source),
        masterAfter=client.get('branches/master')['commit']['sha'],completedAt=int(wall()))
    artifacts.save(directory/'observation.json',value);progress['phase']='cleanup-validation'
    return validate(value,cfg,source,directory/'cleanup.zip',int(wall()))


class Network(artifacts.Network):
    def authorize_path(self,path):
        number=r'[1-9][0-9]{0,19}';page=r'[1-9][0-9]?'
        patterns=(r'branches/master',r'actions/workflows/v52-manual-cleanup\.yml/runs\?branch=master&head_sha=[0-9a-f]{40}&per_page=100&page='+page,
            r'actions/runs/'+number+r'(?:/attempts/'+number+r')?',r'actions/runs/'+number+r'/attempts/'+number+r'/jobs\?per_page=100&page='+page,
            r'actions/runs/'+number+r'/artifacts\?per_page=100&page='+page,r'actions/artifacts/'+number,
            re.escape('contents/'+workflow.PATH)+r'\?ref=[0-9a-f]{40}')
        need(type(path) is str and any(re.fullmatch(pattern,path) for pattern in patterns),'V5.2 cleanup GitHub path outside scope')
    def download(self,identity,output,size):a.integer(size,1,MAX_ZIP);return super().download(identity,output,size)


def collect_native(source,output):
    output=Path(output);need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 cleanup provenance output symlink')
    output.mkdir(parents=True,exist_ok=False);progress=dict(phase='source')
    try:
        cfg=reads.source_configuration(source);workflow.contract()
        result=collect(output,cfg,source,Network(output/'requests'),time.time,progress)
        progress['phase']='final-source'
        need(encoded(reads.source_configuration(source))==encoded(cfg),'V5.2 cleanup provenance source changed');workflow.contract()
        artifacts.save(output/'receipt.json',result);return result
    except BaseException as error:
        artifacts.save(output/'failure.json',dict(status='FAIL',phase=progress['phase'],
            code='V52_RECENT_CLEANUP_'+progress['phase'].upper().replace('-','_')+'_REJECTED',errorType=type(error).__name__,paidAdmission=False))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(encoded(collect_native(args.source,args.output)).decode())
