"""Authenticate an original prepare attempt before reading its exact plan/package.

This never acquires resources. The native Runner independently re-observes the
build, package, provider state and operator approval before any paid mutation.
"""
import io
from pathlib import Path
import stat
import time
import zipfile
from . import cloud_runner_provenance as origin, cloud_prepared as prepared, cloud_inputs as inputs
from . import cloud_artifacts as artifacts, cloud_authority as a, cloud_credentials as credentials
from . import cloud_preflight_read as reads, cloud_preflight as preflight
from .evidence import need, encoded, digest, strict

SCHEMA = 'gse-v52-preparation-origin-v1'
OBSERVATION = 'gse-v52-prepared-artifact-observation-v1'
LIMITS = {'plan.json': 8 << 20, 'approval.json': 65536, 'preparation.json': 65536, 'inputs.tar.gz': inputs.MAX_BYTES}
MAX_ZIP = 272 << 20


def name(chosen):
    origin.original(chosen); return f"v52-prepared-{chosen['runId']}-{chosen['runAttempt']}"


def validate(files, cfg, source, chosen, *, now):
    need(type(files) is dict and set(files) == set(LIMITS) and all(type(raw) is bytes and 0 < len(raw) <= LIMITS[k] for k, raw in files.items()),
         'V5.2 prepared artifact inventory/size')
    plan = strict(files['plan.json']); sha = prepared.validate(plan, now); context = strict(files['preparation.json'])
    a.validate_request(plan['request'], domain='native')
    need(plan['configuration'] == cfg['provider'] and plan['projectNumber'] == cfg['projectNumber'] and
         plan['request']['layout'] == cfg['layout'] and plan['request']['policy'] == cfg['policy'] and plan['inputs']['source'] == source,
         'V5.2 prepared artifact source/configuration')
    need(strict(files['approval.json']) == prepared.approval_template(plan), 'V5.2 prepared original unconfirmed approval')
    raw = files['inputs.tar.gz']
    need(len(raw) == plan['inputs']['packageBytes'] and digest(raw) == plan['inputs']['packageSha256'], 'V5.2 prepared package bytes')
    a.fields(context, 'schema status configurationSha256 credentialContext planSha256 requestSha256 preparedAt buildSha256 cleanupSha256 '
             'preflightSha256 paidAdmission fullRemoteQualification', 'preparation origin')
    need(context['schema'] == SCHEMA and context['status'] == 'PREPARED_NOT_ADMITTED' and
         context['configurationSha256'] == preflight.configuration(cfg) and context['planSha256'] == sha and
         context['requestSha256'] == a.validate_request(plan['request'], domain='native') and
         context['paidAdmission'] is context['fullRemoteQualification'] is False and context['preparedAt'] == plan['request']['createdAt'],
         'V5.2 prepared original receipt')
    expected = dict(schema=credentials.SCHEMA, **credentials.selection(cfg['provider'], cfg['projectNumber'], 'runner'),
                    source=source['source'], **chosen)
    need(context['credentialContext'] == expected, 'V5.2 prepared original credential invocation')
    for field in ('buildSha256', 'cleanupSha256', 'preflightSha256'): a.hex_value(context[field])
    return dict(schema=OBSERVATION, status='PREPARED_ARTIFACT_VERIFIED_NOT_ADMITTED', planSha256=sha,
        requestSha256=context['requestSha256'], source=source, selected=chosen, preparedAt=context['preparedAt'],
        expiresAt=plan['expiresAt'], paidAdmission=False, fullRemoteQualification=False)


def contents(path, record, sha):
    raw = inputs.regular(path, MAX_ZIP)
    need(len(raw) == record['size_in_bytes'] and digest(raw) == sha, 'V5.2 prepared original ZIP bytes')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist(); names = [r.filename for r in rows]
        need(len(names) == len(set(names)) and set(names) == set(LIMITS), 'V5.2 prepared ZIP inventory')
        for row in rows:
            mode = row.external_attr >> 16
            need(row.orig_filename == row.filename and not row.is_dir() and not row.flag_bits & 1 and
                 stat.S_IFMT(mode) in (0, stat.S_IFREG) and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) and
                 0 < row.file_size <= LIMITS[row.filename], 'V5.2 prepared ZIP member')
        return {row.filename: archive.read(row) for row in rows}


def collect(output, cfg, source, chosen, workflow, client, wall):
    origin.original(chosen); started = int(wall()); output = Path(output)
    master = client.get('branches/master')['commit']['sha']; need(master == source['source'], 'V5.2 prepared current master moved')
    path = f"actions/runs/{chosen['runId']}/attempts/{chosen['runAttempt']}"
    run = origin.run_identity(client.get(path), source['source'], chosen)
    jobs = origin.ci.jobs(client.get, run); job, times = origin.job(jobs, run, int(wall()))
    listing = f"actions/runs/{chosen['runId']}/artifacts"; rows = origin.ci.pages(client.get, listing, 'artifacts')
    kwargs = dict(artifact_name=name(chosen), maximum=MAX_ZIP)
    record = origin.select(rows, run, chosen, times, int(wall()), **kwargs); artifact_path = 'actions/artifacts/'+str(record['id'])
    need(client.get(artifact_path) == record, 'V5.2 prepared original metadata mismatch')
    client.download(record['id'], output/'prepared.zip', record['size_in_bytes'])
    observed = dict(schema=OBSERVATION, startedAt=started, selected=chosen, masterBefore=master, run=run, jobs=jobs,
        artifactsBefore=rows, artifact=record, workflowContent=client.get('contents/'+origin.PATH+'?ref='+source['source']),
        artifactAfter=client.get(artifact_path), artifactsAfter=origin.ci.pages(client.get, listing, 'artifacts'),
        jobsAfter=origin.ci.jobs(client.get, run), runAfter=client.get(path), masterAfter=client.get('branches/master')['commit']['sha'],
        completedAt=int(wall()))
    artifacts.save(output/'observation.json', observed)
    origin.run_identity(observed['runAfter'], source['source'], chosen)
    after, _ = origin.job(observed['jobsAfter'], run, int(wall()))
    need(origin.ci.run_key(run) == origin.ci.run_key(observed['runAfter']) and origin.ci.job_key(job) == origin.ci.job_key(after),
         'V5.2 prepared original attempt/job changed')
    need(observed['masterAfter'] == master and started <= observed['completedAt'] <= int(wall()) <= started+900,
         'V5.2 prepared source/observation changed')
    origin.ci.source_content(observed['workflowContent'], origin.PATH, workflow)
    need(record == observed['artifactAfter'] == origin.select(observed['artifactsAfter'], run, chosen, times, int(wall()), **kwargs),
         'V5.2 prepared artifact changed')
    files = contents(output/'prepared.zip', record, origin.metadata(record, run, chosen, times, int(wall()), **kwargs))
    receipt = validate(files, cfg, source, chosen, now=int(wall()))
    need(times[origin.EXECUTE][0] <= receipt['preparedAt'] <= times[origin.EXECUTE][1] and
         origin.ci.stamp(job['completed_at']) <= started, 'V5.2 preparation outside original execution')
    return files, dict(receipt, artifactId=record['id'], artifactSha256=record['digest'][7:])


class Network(origin.Network):
    def download(self, identity, output, size):
        a.integer(size, 1, MAX_ZIP); return artifacts.Network.download(self, identity, output, size)


def collect_native(source, chosen, output):
    output = Path(output)
    need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 prepared output link')
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        cfg = reads.source_configuration(source); bound = inputs.checkout(origin.ci.ROOT, source); workflow = origin.contract()
        files, receipt = collect(output, cfg, bound, chosen, workflow, Network(output/'requests'), time.time)
        need(reads.source_configuration(source) == cfg and inputs.checkout(origin.ci.ROOT, source) == bound and origin.contract() == workflow,
             'V5.2 prepared source changed')
        (output/'files').mkdir()
        for name, raw in files.items():
            with (output/'files'/name).open('xb') as stream: stream.write(raw)
        artifacts.save(output/'receipt.json', receipt); return receipt
    except BaseException as error:
        artifacts.save(output/'failure.json', dict(status='FAIL', code='V52_PREPARED_ARTIFACT_REJECTED', errorType=type(error).__name__, paidAdmission=False))
        raise
