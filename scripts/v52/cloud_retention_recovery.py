"""One named operator waiver for a completed workload whose retention timed out.

No original status, ledger entry, source or seal is rewritten. Only this exact
failed invocation may replace a successful retention seal with pinned original
diagnostics, complete original bytes, exact cleanup and independent replay.
"""
from copy import deepcopy
from pathlib import Path
import io
import time
import zipfile
from . import cloud_quota_continuation as quota, cloud_authority as a
from . import cloud_inputs as inputs, cloud_ci as ci, cloud_preflight as preflight
from . import cloud_artifacts as artifacts, cloud_runner_provenance as runners
from .evidence import need, encoded, digest, strict

POLICY = 'docs/v5x/v5.2/experiment-retention-recovery.json'
POLICY_SHA256 = '7769464fd60dfeae4a06a881c51541c8dc83edefb208078e243f36513e973108'


def load(root=ci.ROOT):
    value = strict(inputs.regular(Path(root)/POLICY, 65536))
    need(digest(encoded(value)) == POLICY_SHA256, 'V5.2 recovered experiment policy changed')
    return value


def request(value):
    from .cloud_acceptance import selection
    a.fields(value, 'recovery selected', 'experiment retention recovery request')
    policy = load(); chosen = selection(value['selected'])
    need(value['recovery'] == policy['id'] and chosen == {
        name: {k:pin[k] for k in ('requestSha256', 'runId', 'runAttempt')}
        for name, pin in policy['originals'].items()}, 'V5.2 recovery requires all fifteen pinned originals')
    return chosen


def applies(scope, req):
    if type(scope) is not Scope: return False
    return scope.validate_request(req) == scope.policy['failure']['member']


def terminal_status(scope, req):
    return 'FAIL' if applies(scope, req) else 'PASS'


class Scope:
    def __init__(self, cfg, source, chosen):
        self.policy = load(); quota.source_compatible(source['source'], quota.load())
        inputs.identity(source)
        self.source = deepcopy(source); self.cfg = deepcopy(cfg)
        self.chosen = request(dict(recovery=self.policy['id'], selected=chosen))
        need(preflight.configuration(cfg) == self.policy['configurationSha256'] and all(
            pin['source']['java'] == source['java'] for pin in self.policy['originals'].values()),
            'V5.2 recovery configuration/toolchain changed')
        self.frozen = digest(encoded([self.policy, self.source, self.cfg, self.chosen]))

    def guard(self, source=None, cfg=None):
        need(type(self) is Scope and digest(encoded([self.policy, self.source, self.cfg, self.chosen])) == self.frozen and
             (source is None or source == self.source) and (cfg is None or cfg == self.cfg), 'V5.2 recovery scope changed')

    def member_source(self, name):
        self.guard(); need(name in self.chosen, 'V5.2 recovery unknown member')
        return deepcopy(self.policy['originals'][name]['source'])

    def validate_request(self, req):
        self.guard(); sha = a.validate_request(req, domain='native')
        name = req['selection']['member']['name']; pin = self.policy['originals'].get(name)
        need(pin is not None and sha == pin['requestSha256'] and req['selection']['binding'] == pin['binding'] and
             req['configurationSha256'] == preflight.p.config(self.cfg['provider']) and req['layout'] == self.cfg['layout'] and
             req['policy'] == self.cfg['policy'], 'V5.2 recovery original request changed')
        return name

    def selections(self, requests):
        from . import cloud_suite as suite
        need(len(requests) == len(suite.MEMBERS), 'V5.2 recovery incomplete original set')
        names = [self.validate_request(req) for req in requests]
        need(set(names) == set(suite.MEMBERS) and len(set(req['selection']['attempt'] for req in requests)) == len(names),
             'V5.2 recovery duplicate original member/attempt')
        for req in requests: suite.validate_selection(req['selection'])
        bindings = {name:deepcopy(self.policy['originals'][name]['binding']) for name in names}
        return dict(binding=bindings['experiment'], originalBindings=bindings)

    def objects(self, req, manifest, completed, clean):
        need(applies(self, req), 'V5.2 recovery not the waived invocation')
        pin = self.policy['originals']['experiment']
        need(completed['status'] == 'FAIL' and completed['evidenceSha256'] is None and all(
            digest(encoded(value)) == pin[key] for key, value in
            (('manifestSha256', manifest), ('completionSha256', completed), ('cleanupSha256', clean))),
            'V5.2 recovery original immutable objects changed')

    def generation(self, label, observed):
        need(label in ('manifest', 'completion', 'cleanup') and
             observed['generation'] == self.policy['failure'][label+'Generation'], 'V5.2 recovery original generation changed')

    def original(self, name, record):
        self.guard(); pin = self.policy['originals'][name]
        need(name != 'experiment' and record['status'] == 'ORIGINAL_RUNNER_VERIFIED_NOT_QUALIFIED' and
             record['source'] == self.member_source(name) and
             record['selected'] == {k:pin[k] for k in ('runId', 'runAttempt')} and
             all(record[k] == pin[k] for k in ('artifactId', 'artifactSha256')) and
             all(record['seal'][k] == pin[k] for k in ('requestSha256', 'completionSha256', 'manifestSha256', 'cleanupSha256')),
             'V5.2 recovery successful original changed')

    def report(self):
        self.guard()
        return dict(id=self.policy['id'], policySha256=POLICY_SHA256, scope=self.policy['scope'],
            waivedOriginal=self.chosen['experiment'], originalCompletionStatus='FAIL', originalJobConclusion='failure',
            originalLedgerRewritten=False, recoveredParts=self.policy['failure']['recoveredParts'],
            requirements='complete manifest hashes, original authority, exact-ID cleanup, every history/negative replay')

    def failed_runner(self, run, jobs, artifact, raw):
        """Pins cover repository, workflow, source, attempt, step outcomes/times and bytes."""
        self.guard(); pin = self.policy['originals']['experiment']; failure = self.policy['failure']
        need(digest(encoded(ci.run_key(run))) == failure['runKeySha256'] and run['status'] == 'completed' and
             run['conclusion'] == 'failure' and run['id'] == pin['runId'] and run['run_attempt'] == pin['runAttempt'] and
             run['head_sha'] == pin['source']['source'], 'V5.2 recovery original failed run changed')
        need(type(jobs) is list and len(jobs) == 1 and digest(encoded(ci.job_key(jobs[0]))) == failure['jobKeySha256'],
             'V5.2 recovery original failed job changed')
        need(artifact['id'] == pin['artifactId'] and artifact['name'] == f"v52-runner-diagnostics-{pin['runId']}-{pin['runAttempt']}" and
             artifact['expired'] is False and artifact['digest'] == 'sha256:'+pin['artifactSha256'] and
             len(raw) == artifact['size_in_bytes'] <= runners.MAX_ZIP and digest(raw) == pin['artifactSha256'] and
             artifact['workflow_run']['id'] == pin['runId'] and artifact['workflow_run']['head_sha'] == pin['source']['source'],
             'V5.2 recovery original diagnostic artifact changed')
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            need(len(archive.infolist()) == 1 and archive.namelist() == ['failure.json'] and
                 archive.infolist()[0].file_size <= 65536, 'V5.2 recovery diagnostic inventory')
            diagnostic = strict(archive.read('failure.json'))
        need(diagnostic == failure['diagnostic'] and diagnostic['causeCode'] == 'V52_ORIGINAL_MEMBER_RETENTION_REJECTED' and
             diagnostic['readRetry'] == dict(attempts=1, code='V52_READ_DEADLINE', reason='timeout', scope='provider-read', stop='deadline') and
             diagnostic['cleanup'] == dict(leaseReleased=True, resourceDeletesSubmitted=13, status='PASS'),
             'V5.2 recovery not the approved retention timeout')
        return dict(status='ORIGINAL_FAILED_RETENTION_VERIFIED_NOT_QUALIFIED', source=deepcopy(pin['source']),
            selected=deepcopy(self.chosen['experiment']), artifactId=pin['artifactId'], artifactSha256=pin['artifactSha256'],
            waiver=self.report(), fullRemoteQualification=False, paidCloud=False)

    def collect(self, req, output, client):
        need(applies(self, req), 'V5.2 recovery wrong original runner')
        output = Path(output); output.mkdir(parents=True, exist_ok=False)
        pin = self.policy['originals']['experiment']; path = f"actions/runs/{pin['runId']}/attempts/{pin['runAttempt']}"
        artifact_path = 'actions/artifacts/'+str(pin['artifactId'])
        master = client.get('branches/master'); need(master['commit']['sha'] == self.source['source'], 'V5.2 recovery master moved')
        run = client.get(path); jobs = ci.jobs(client.get, run); artifact = client.get(artifact_path)
        need(artifact['id'] == pin['artifactId'] and 0 < artifact['size_in_bytes'] <= runners.MAX_ZIP, 'V5.2 recovery diagnostic bound')
        client.download(pin['artifactId'], output/'diagnostics.zip', artifact['size_in_bytes'])
        result = self.failed_runner(run, jobs, artifact, inputs.regular(output/'diagnostics.zip', runners.MAX_ZIP))
        need(ci.stamp(artifact['expires_at']) > int(time.time()), 'V5.2 recovery diagnostic expired')
        workflow = client.get('contents/'+runners.PATH+'?ref='+pin['source']['source'])
        ci.source_content(workflow, runners.PATH, runners.contract())
        after = client.get(path); after_jobs = ci.jobs(client.get, after); after_artifact = client.get(artifact_path)
        self.failed_runner(after, after_jobs, after_artifact, inputs.regular(output/'diagnostics.zip', runners.MAX_ZIP))
        need(artifact == after_artifact and client.get('branches/master')['commit']['sha'] == self.source['source'],
             'V5.2 recovery collection identity changed')
        artifacts.save(output/'observation.json', dict(run=run, runAfter=after, jobs=jobs, jobsAfter=after_jobs,
            artifact=artifact, artifactAfter=after_artifact, masterBefore=master, workflowContent=workflow))
        artifacts.save(output/'receipt.json', result); return result
