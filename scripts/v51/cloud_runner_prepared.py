"""Public-only experiment plans and exact producing-run artifact handoff.

No credentials, resource mutations or execution of downloaded code. The native
entry separately rechecks current CI, original package bytes and live authority.
"""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import stat
import zipfile
from . import cloud_runner_admission as admission, cloud_runner_artifacts as artifacts
from . import cloud_runner_review as workflow, cloud_ci as ci, cloud_authority as a
from . import cloud_recent_cleanup as recent, cloud_cleanup_entry as entry
from . import performance_model as m, remote_command as c

SCHEMA='gse-v51-runner-prepared-v1'
STEP='Prepare exact V5.1 experiment for review (no allocation)'
UPLOAD='Retain public experiment preparation'
FILES=frozenset(('plan.json','approval-template.json','receipt.json','originals/artifacts.json',
                 'originals/build-job.json','originals/build.zip','originals/package.zip'))
MAX_BYTES=600 << 20


def name(run_id):
    a.integer(run_id,1);return f'v51-experiment-prepared-{run_id}-1'


def save(root, value, binding, *, now):
    """Original archive collection has already populated root/originals."""
    root=Path(root);digest=admission.validate_plan(value,now)
    m.need(binding['source']==value['artifacts']['source'] and binding['runAttempt']==1,
           'prepared source/first attempt')
    c.write_once(root/'plan.json',value)
    c.write_once(root/'approval-template.json',admission.approval_template(value))
    receipt=dict(schema=SCHEMA,status='PREPARED',source=binding['source'],runId=binding['runId'],runAttempt=1,
        planSha256=digest,checkedAt=now,expiresAt=value['expiresAt'],paidCloud=False,paidAdmission=False,
        engineWorkloadExecuted=False,fullRemoteQualification=False,
        files={n:m.sha((root/n).read_bytes()) for n in sorted(FILES-{'receipt.json'})})
    c.write_once(root/'receipt.json',receipt);validate(root,binding['source'],digest,now=now)
    return receipt


def validate(root, source, confirmation, *, now):
    root=c.directory(root);found=set();total=0
    for path in root.rglob('*'):
        m.need(not path.is_symlink(),'prepared symlink')
        if path.is_dir():m.need(path.relative_to(root).as_posix()=='originals','prepared directory')
        else:
            key=path.relative_to(root).as_posix();size=path.stat().st_size
            m.need(path.is_file() and key in FILES and size<=
                   (artifacts.MAX_BYTES if key.endswith('.zip') else 4<<20),'prepared file/size')
            found.add(key);total+=size
    m.need(found==FILES and total<=MAX_BYTES,'prepared closed inventory')
    value=c.read(root/'plan.json');receipt=c.read(root/'receipt.json')
    digest=admission.validate_plan(value,now);a.digest(confirmation)
    m.need(digest==confirmation and value['artifacts']['source']==source,'prepared exact plan/source confirmation')
    expected=dict(schema=SCHEMA,status='PREPARED',source=source,runId=receipt['runId'],runAttempt=1,
        planSha256=digest,checkedAt=receipt['checkedAt'],expiresAt=value['expiresAt'],paidCloud=False,paidAdmission=False,
        engineWorkloadExecuted=False,fullRemoteQualification=False,
        files={n:m.sha((root/n).read_bytes()) for n in sorted(FILES-{'receipt.json'})})
    a.integer(receipt['runId'],1);a.integer(receipt['checkedAt'],value['resourcePlan']['request']['createdAt'],now)
    m.need(receipt==expected and c.read(root/'approval-template.json')==admission.approval_template(value),
           'prepared receipt/approval changed')
    return value


def producer(run, jobs, source, run_id, *, now):
    binding=dict(runId=run_id,runAttempt=1,source=source,workflow=a.RUNNER_WORKFLOW,event='workflow_dispatch')
    m.need(run['status']=='completed' and run['conclusion']=='success','prepared producer not successful')
    entry.validate_run(binding,dict(run,status='in_progress',conclusion=None))
    m.need(jobs['total_count']==len(jobs['jobs'])==2 and
           {v['name'] for v in jobs['jobs']}=={'observations',workflow.RUNNER_JOB_NAME},'prepared producing jobs')
    for job in jobs['jobs']:
        m.need(job['run_id']==run_id and job['run_attempt']==1 and job['head_sha']==source and
               job['status']=='completed' and job['conclusion']=='success','prepared job identity/result')
    job=next(v for v in jobs['jobs'] if v['name']==workflow.RUNNER_JOB_NAME)
    start,end=ci.timestamp(job['started_at']),ci.timestamp(job['completed_at'])
    m.need(0<start<=end<=now,'prepared producing time')
    times={}
    for label in (STEP,UPLOAD):
        steps=[v for v in job['steps'] if v['name']==label]
        m.need(len(steps)==1 and steps[0]['status']=='completed' and steps[0]['conclusion']=='success',
               'prepared producing step missing/failed')
        low,high=ci.timestamp(steps[0]['started_at']),ci.timestamp(steps[0]['completed_at'])
        m.need(start<=low<=high<=end,'prepared step time');times[label]=(low,high)
    m.need(times[STEP][1]<=times[UPLOAD][0],'prepared upload before plan')
    return times


def metadata(record, source, run_id, times):
    a.integer(record['id'],1);a.integer(record['size_in_bytes'],1,MAX_BYTES)
    run=record['workflow_run']
    m.need(record['name']==name(run_id) and record['expired'] is False and
           run['id']==run_id and run['head_sha']==source and run['head_branch']=='master' and
           run['repository_id']==run['head_repository_id']==ci.REPOSITORY_ID,'prepared artifact identity')
    low,high=times[UPLOAD]
    m.need(low<=ci.timestamp(record['created_at'])<=ci.timestamp(record['updated_at'])<=high,
           'prepared artifact producing time')
    sha=record['digest'];m.need(type(sha) is str and sha.startswith('sha256:'),'prepared artifact digest')
    return a.digest(sha[7:])


def unpack(path, record, digest, output):
    path=Path(path);m.need(path.stat().st_size==record['size_in_bytes']<=MAX_BYTES and
                         m.sha(path.read_bytes())==digest,'prepared original ZIP size/digest')
    with zipfile.ZipFile(path) as archive:
        rows=archive.infolist();names=[v.filename for v in rows]
        m.need(len(rows)<=len(FILES)+1 and len(set(names))==len(names) and
               sum(v.file_size for v in rows)<=MAX_BYTES,'prepared ZIP inventory/bound')
        for row in rows:
            raw=row.filename[:-1] if row.is_dir() else row.filename;name_path=PurePosixPath(raw);mode=row.external_attr>>16
            m.need(row.orig_filename==row.filename and raw==name_path.as_posix() and
                   not name_path.is_absolute() and '..' not in name_path.parts and '\\' not in raw and
                   not row.flag_bits&1 and stat.S_IFMT(mode) in (0,stat.S_IFREG,stat.S_IFDIR) and
                   (raw=='originals' if row.is_dir() else raw in FILES),'prepared unsafe ZIP member')
            m.need(row.file_size<=(artifacts.MAX_BYTES if raw.endswith('.zip') else 4<<20),'prepared ZIP member bound')
        m.need({r.filename for r in rows if not r.is_dir()}==FILES,'prepared ZIP missing files')
        root=Path(output);root.mkdir(mode=0o700,parents=True,exist_ok=False);(root/'originals').mkdir(mode=0o700)
        for key in sorted(FILES):
            with (root/key).open('xb') as stream:stream.write(archive.read(key))
    return root


def collect(root, source, run_id, confirmation, *, now, get=ci.github, fetch=recent.download):
    """Read one explicitly selected first-attempt plan; no green-history search."""
    root=Path(root);root.mkdir(parents=True,exist_ok=False);a.integer(run_id,1)
    path=f'actions/runs/{run_id}';run=get(path)
    attempt=get(path+'/attempts/1')
    jobs=get(path+'/attempts/1/jobs?per_page=100');times=producer(run,jobs,source,run_id,now=now)
    m.need(producer(attempt,jobs,source,run_id,now=now)==times,'prepared run changed/retried')
    listing=get(path+'/artifacts?per_page=100')
    m.need(listing['total_count']==len(listing['artifacts'])<=100,'prepared artifact inventory incomplete')
    selected=[v for v in listing['artifacts'] if v['name']==name(run_id)]
    m.need(len(selected)==1,'prepared artifact missing/duplicate');record=selected[0]
    digest=metadata(record,source,run_id,times);fetch(record['id'],root/'prepared.zip')
    public=unpack(root/'prepared.zip',record,digest,root/'prepared')
    value=validate(public,source,confirmation,now=now);receipt=c.read(public/'receipt.json')
    m.need(receipt['runId']==run_id and times[STEP][0]<=receipt['checkedAt']<=times[STEP][1],
           'prepared receipt outside producing step')
    m.need(get(f"actions/artifacts/{record['id']}")==record and get(path)==run and
           get(path+'/attempts/1/jobs?per_page=100')==jobs,'prepared artifact/producer changed during download')
    c.write_once(root/'provenance.json',dict(run=run,jobs=jobs,artifact=record))
    approved=deepcopy(c.read(public/'approval-template.json'));approved['confirmed']=True
    admission.approval(value,approved,confirmation,now)
    return public,value,approved
