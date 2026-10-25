"""Protected prepare/run/verify-set operations and bounded public summaries."""
import argparse
from contextlib import contextmanager
import html
import os
from pathlib import Path
import re
import tempfile
import time
from . import cloud_prepare as preparation, cloud_prepared_artifact as downloaded, cloud_prepared as prepared
from . import cloud_execution as execution, cloud_acceptance as acceptance, cloud_access as access
from . import cloud_runner_workflow as workflow, cloud_runner_provenance as origin
from . import cloud_credentials as credentials, cloud_artifacts as artifacts, cloud_preflight_read as reads
from . import cloud_authority as a, cloud_inputs as inputs, cloud_native_runner as native
from . import cloud_member as member, cloud_sdk_runtime as sdk_runtime, cloud_read_retry
from . import cloud_runner_host as execution_host, cloud_provider as provider
from .evidence import need, encoded, digest, strict

OPERATIONS = ('prepare', 'run', 'verify-set')


def environment(env):
    operation = env.get('V52_OPERATION'); raw = env.get('V52_REQUEST')
    need(operation in OPERATIONS and type(raw) is str and 0 < len(raw.encode()) <= 65536, 'V5.2 operation/request required')
    value = strict(raw.encode())
    if operation == 'prepare': preparation.request(value)
    elif operation == 'run':
        a.fields(value, 'preparedRun preparedAttempt confirmation', 'run request')
        a.integer(value['preparedRun'], 1); a.integer(value['preparedAttempt'], 1); a.hex_value(value['confirmation'])
    else: acceptance.selection(value)
    return operation, value


@contextmanager
def private_key():
    """Consume the secret once; children never inherit its raw environment value."""
    raw = os.environ.pop('V52_SSH_KEY', None)
    try:
        need(type(raw) is str and 1 <= len(raw.encode()) <= 4096 and raw.startswith('-----BEGIN OPENSSH PRIVATE KEY-----\n'),
             'V5.2 private SSH secret missing/invalid')
        data = raw.encode(); raw = None
        # gh secret set trims trailing CR/LF from stdin. OpenSSH still needs the
        # final LF in the temporary file. Never strip/rewrite the key body.
        if not data.endswith(b'\n'): data += b'\n'
        need(len(data) <= 4096, 'V5.2 private SSH secret bound')
    except ValueError:
        raise access.PrivateKeyError('SECRET_INVALID') from None
    with tempfile.TemporaryDirectory(prefix='gse-v52-operator-key-') as directory:
        path = Path(directory)/'identity'
        fd = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(data)
        data = None
        public = access.private_public_key(path)
        yield path, public


def execute_native(source, output):
    output = execution.output_path(output)
    output.mkdir(parents=True, mode=0o700, exist_ok=False); (output/'diagnostics').mkdir()
    phase = 'input'; result = dict(status='FAIL', fullRemoteQualification=False); operation = None
    progress = member.Progress('operator'); progress.thread.start()
    try:
        operation, request = environment(dict(os.environ)); phase = 'identity'
        cfg = reads.source_configuration(source); workflow.contract()
        bound = credentials.identity(cfg['provider'], cfg['projectNumber'], dict(os.environ), role='runner', source=source, checkout=source)
        chosen = {key:bound[key] for key in ('runId', 'runAttempt')}
        if operation == 'prepare':
            phase = 'prepare-key'; progress.update(phase)
            with private_key() as (_, public):
                phase = 'prepare'; progress.update(phase)
                result = preparation.prepare_native(source, request, public, output/'prepare')
            public_root = output/'prepare/public'; artifact_name = downloaded.name(chosen)
        elif operation == 'run':
            phase = 'prepared-download'; progress.update(phase)
            downloaded.collect_native(source, dict(runId=request['preparedRun'], runAttempt=request['preparedAttempt']), output/'prepared')
            files = output/'prepared/files'; plan = artifacts.read(files/'plan.json'); phase = 'approval'
            sha = prepared.validate(plan, int(time.time()))
            need(sha == request['confirmation'], 'V5.2 selected prepared plan confirmation changed')
            phase='host-selection'
            execution_host.require_member(plan['request']['selection']['member']['name'],dict(os.environ))
            approval = prepared.approval_template(plan); approval['confirmed'] = True
            artifacts.save(output/'approval.json', approval)
            phase = 'run-key'; progress.update(phase)
            with private_key() as (key, public):
                if public != plan['request']['guestAccess']['publicKey']: raise access.PrivateKeyError('KEY_MISMATCH')
                access.check_private_key(key, plan['request']['guestAccess'])
                phase = 'run'; progress.update(phase)
                result = execution.run_native(source, files/'plan.json', output/'approval.json', sha, files/'inputs.tar.gz', key, output/'run')
            public_root = output/'run/public'; artifact_name = origin.name(chosen)
        else:
            phase = 'verify-set'; progress.update(phase); os.environ.pop('V52_SSH_KEY', None)
            result = acceptance.verify_native(source, request, output/'verify-set')
            public_root = output/'set-public'; public_root.mkdir()
            artifacts.save(public_root/'cloud-set.json', result); artifact_name = f"v52-cloud-set-{chosen['runId']}-{chosen['runAttempt']}"
        phase = 'final-source'; progress.update(phase)
        need(reads.source_configuration(source) == cfg, 'V5.2 operator source changed'); workflow.contract()
        # Move only the explicitly constructed public directory. No glob can
        # include private workspaces, key files, auth descriptors or raw logs.
        public_root.rename(output/'result')
        phase = 'actions-output'; workflow.outputs(dict(artifactName=artifact_name), dict(os.environ))
        report = report_data(operation, source, result, output)
        artifacts.save(output/'diagnostics/report.json', report)
        return report
    except BaseException as error:
        failure = dict(status='FAIL', operation=operation, phase=phase, source=source,
            code='V52_OPERATOR_'+phase.upper().replace('-', '_')+'_REJECTED', errorType=type(error).__name__,
            fullCiRequired=native.ci.REQUIRE_FULL_CI, fullRemoteQualification=False)
        if isinstance(error, access.PrivateKeyError): failure['causeCode'] = error.code
        failure.update(credentials.failure(error))
        failure.update(sdk_runtime.failure(error))
        failure.update(cloud_read_retry.failure(error))
        failure.update(provider.operation_failure(error))
        for relative in ('prepare/failure.json', 'prepared/failure.json', 'run/failure.json', 'run/native/failure.json',
                         'run/member/failure.json'):
            path = output/relative
            if path.is_file():
                try:
                    inner = artifacts.read(path)
                    failure.update(credentials.public_failure(inner))
                    failure.update(sdk_runtime.public_failure(inner))
                    failure.update(cloud_read_retry.public_failure(inner))
                    failure.update(provider.public_operation_failure(inner))
                    code = inner.get('code')
                    if type(code) is str and re.fullmatch('V52_[A-Z0-9_]{1,128}', code): failure['causeCode'] = code
                    status = inner.get('httpStatus')
                    if type(status) is int and 100 <= status <= 599: failure['httpStatus'] = status
                    if relative=='run/member/failure.json' and inner.get('phase') in member.FAILURE_PHASES:
                        failure['memberPhase']=inner['phase']
                except Exception: pass  # A broken diagnostic cannot mask the original operation failure.
        if phase == 'prepare':
            try:
                build = artifacts.public_failure(artifacts.read(output/'prepare/build/failure.json'))
                if build is not None: failure['buildProvenance'] = build
            except Exception: pass
        cleanup=cleanup_report(output/'run/native')
        if cleanup is not None:failure['cleanup']=cleanup
        iap=iap_report(output/'run/member/guests')
        if iap is not None:failure['iap']=iap
        storage=storage_report(output/'run/member/storage')
        if storage is not None:failure['storage']=storage
        native.diagnostic(output/'diagnostics/failure.json', failure)
        # Do not publish a result when a final source/output/summary check fails.
        # GitHub also requires the original entire job to complete successfully.
        raise
    finally:
        os.environ.pop('V52_SSH_KEY', None)
        progress.close()


def storage_report(root):
    from . import cloud_storage_diagnostics as diagnostic
    try:return diagnostic.project(strict(inputs.regular(root/'diagnostic.json',16384)))
    except Exception:return None


def cleanup_report(root):
    """Project closed cleanup fields only; this is a diagnostic, not acceptance."""
    try:
        if (root/'cleanup-failure.json').is_file():return dict(status='FAIL')
        path=root/'cleanup.json'
        if not path.is_file():return None
        value=strict(inputs.regular(path,65536));status=value.get('status');count=value.get('resourceDeletesSubmitted')
        if status not in ('PASS','FAIL','NOT_ACQUIRED') or type(count) is not int or not 0<=count<=10000:return None
        result=value.get('result')
        if status=='NOT_ACQUIRED':
            if result is not None:return None
            return dict(status=status,resourceDeletesSubmitted=count)
        if type(result) is not dict or result.get('status')!=status or type(result.get('leaseReleased')) is not bool:return None
        if status=='PASS':
            cleanup=result.get('cleanup')
            if not result['leaseReleased'] or type(cleanup) is not dict or cleanup.get('status')!='PASS' or \
               cleanup.get('leftovers')!=[] or cleanup.get('errors')!=[]:return None
        return dict(status=status,leaseReleased=result['leaseReleased'],resourceDeletesSubmitted=count)
    except Exception:return None


def iap_report(root):
    """Keep bounded counters and closed codes, never raw channel diagnostics."""
    from . import cloud_iap as iap
    codes=set(iap.transport.FAILURE_DETAILS)|{'IAP_ORIGINAL_CONNECT_TIMEOUT','IAP_IDENTITY_OR_AUTHORITY_REJECTED',
        'IAP_LISTENER_CLOSED','IAP_CLOSE_INCOMPLETE','IAP_OWNER_OR_PIN_CHANGED'}
    codes.update('V52_CREDENTIAL_'+code for code in credentials.CODES)
    codes.update(iap.diagnostics.CODES)
    def code(value):
        if value is None:return None
        if type(value) is str and (value in codes or re.fullmatch(r'IAP_PROVIDER_HTTP_[1-5][0-9]{2}',value)):return value
        return 'IAP_UNCLASSIFIED'
    try:
        value=strict(inputs.regular(root/'connections.json',131072))
        if value.get('schema')!='gse-v52-iap-connections-v2' or value.get('status') not in ('CLOSED','FAIL') or \
           value.get('fullRemoteQualification') is not False:return None
        nodes=value.get('nodes')
        if type(nodes) is not dict or not set(nodes)<=set(iap.topology.NODES):return None
        rows={}
        for node,row in nodes.items():
            counts={key:row[key] for key in ('accepted','completed','failed','active','peakActive','capacityRejections',
                                           'sentBytes','receivedBytes','historyDropped')}
            if any(type(v) is not int or not 0<=v<2**63 for v in counts.values()):return None
            if counts['completed']+counts['active']!=counts['accepted'] or counts['failed']>counts['completed'] or \
               not counts['active']<=counts['peakActive']<=min(iap.MAX_ACTIVE,counts['accepted']) or \
               counts['historyDropped']!=max(0,counts['completed']-iap.MAX_RECENT):return None
            rows[node]=dict(counts,lastFailureCode=code(row.get('lastFailureCode')))
            # Optional fields keep historical receipts readable. Project only
            # closed phases/codes/origins; never export the connection ring.
            if 'admissionRetries' in row or 'admissionMillis' in row or 'lastAdmission' in row:
                retries=row.get('admissionRetries');millis=row.get('admissionMillis')
                if type(retries) is not int or not 0<=retries<=counts['completed'] or \
                   type(millis) is not int or not 0<=millis<2**63:return None
                attempts=None if row.get('lastAdmission') is None else iap.diagnostics.project(row['lastAdmission'])
                if row.get('lastAdmission') is not None and attempts is None:return None
                rows[node].update(admissionRetries=retries,admissionMillis=millis,lastAdmission=attempts)
        return dict(status=value['status'],failureCode=code(value.get('failureCode')),
                    closeFailed=value.get('closeFailure') is not None,nodes=rows)
    except Exception:return None


def report_data(operation, source, result, output):
    row = dict(status=result['status'], operation=operation, source=source, fullCiRequired=native.ci.REQUIRE_FULL_CI,
               fullRemoteQualification=result.get('fullRemoteQualification', False))
    if operation == 'prepare':
        plan = artifacts.read(output/'result/plan.json'); approval = prepared.approval_template(plan)
        row.update(member=plan['request']['selection']['member']['name'], sequence=plan['request']['selection']['binding']['sequence'],
            requestSha256=approval['requestSha256'], planSha256=approval['planSha256'], expiresAt=plan['expiresAt'],
            preparedRun=result['credentialContext']['runId'], preparedAttempt=result['credentialContext']['runAttempt'],
            **plan['reservation'], warnings=plan['warnings'],
            runRequest=dict(preparedRun=result['credentialContext']['runId'], preparedAttempt=result['credentialContext']['runAttempt'],
                            confirmation=approval['planSha256']))
    elif operation == 'run':
        row.update(member=result['selection']['member']['name'], sequence=result['selection']['binding']['sequence'],
            requestSha256=result['requestSha256'], runId=result['credentialContext']['runId'], runAttempt=result['credentialContext']['runAttempt'],
            startedAt=result['startedAt'], completedAt=result['completedAt'], reservedCostMicrousd=result['reservedCostMicrousd'],
            manifestSha256=result['manifestSha256'], completionSha256=result['completionSha256'], cleanupSha256=result['cleanupSha256'])
    else:
        row.update(totals=result['totals'], selected=result['selected'], selectedReservedCostMicrousd=result['selectedReservedCostMicrousd'],
                   ledgerReservedCostMicrousd=result['ledgerReservedCostMicrousd'])
    if 'member' in row:
        chosen=preparation.suite.member(row['member'])
        row.update(logicalMember=preparation.suite.logical_member(row['member']),
            histories=chosen['histories'],historyCount=len(chosen['histories']),
            recommendedRunHost='github-hosted' if row['member'] in preparation.suite.HOSTED_MEMBERS else 'self-hosted')
    return row


def summary(output):
    root = Path(output)/'diagnostics'; print('## V5.2 Replication Runner\n')
    path = root/'failure.json' if (root/'failure.json').exists() else root/'report.json'
    if not path.exists(): print('No completed operation report. Inspect the failed step; no acceptance is established.'); return
    value = artifacts.read(path)
    def cell(v): return html.escape(str(v)).replace('|', '&#124;').replace('\n', ' ')
    print('| Item | Result |\n| --- | --- |')
    for key, item in value.items():
        if key not in ('runRequest', 'selected', 'totals'): print('| '+cell(key)+' | '+cell(item)+' |')
    if 'totals' in value:
        print('\n### Complete original set\n\n| Metric | Value |\n| --- | --- |')
        for key, item in value['totals'].items(): print('| '+cell(key)+' | '+cell(item)+' |')
    if 'runRequest' in value:
        print('\n### Exact run request\n\nReview the member, source and reservation before choosing **run**.\n')
        print('Set **execution_host** to `'+cell(value.get('recommendedRunHost','self-hosted'))+'`.\n')
        print('```json\n'+encoded(value['runRequest']).decode()+'\n```')
    if 'selected' in value:
        print('\n### Original invocations\n\n| Member | Run / attempt | Request |\n| --- | --- | --- |')
        for name, item in value['selected'].items():
            print('| '+cell(name)+' | '+cell(str(item['runId'])+' / '+str(item['runAttempt']))+' | '+cell(item['requestSha256'])+' |')
    print('\nTime and cumulative cost limits are soft warnings. Request limits, approval expiry and lease/grace checks remain enforced.')


def prepare_request(source, selected_member, sequence, cost, coverage, valid_seconds, output):
    """Render an explicitly priced operator draft, without provider or CI I/O."""
    cfg = reads.source_configuration(source); preparation.suite.member(selected_member); a.hex_value(sequence, 32)
    a.integer(cost, 1); a.integer(coverage, 1); a.integer(valid_seconds, 1, 86400)
    now = int(time.time())
    estimate = dict(schema='gse-v52-operator-estimate-v1', currency='USD', configurationSha256=prepared.provider.config(cfg['provider']),
        layoutSha256=digest(encoded(cfg['layout'])), createdAt=now, expiresAt=now+valid_seconds, coverageSeconds=coverage,
        costMicrousd=cost, includes=list(prepared.INCLUDES), priceSources=[
            'https://cloud.google.com/compute/all-pricing', 'https://cloud.google.com/compute/disks-image-pricing',
            'https://cloud.google.com/storage/pricing', 'https://cloud.google.com/vpc/network-pricing',
            'https://docs.github.com/en/billing/concepts/product-billing/github-actions'])
    value = dict(member=selected_member, sequence=sequence, estimate=estimate)
    output = Path(output); need(not any(p.is_symlink() for p in (output, *output.parents)), 'V5.2 request draft output link')
    output.mkdir(parents=True, exist_ok=False); artifacts.save(output/'request.json', value)
    artifacts.save(output/'receipt.json', dict(status='OPERATOR_ESTIMATE_DRAFT', source=source, livePricesVerified=False,
        costMicrousd=cost, coverageSeconds=coverage, paidAdmission=False))
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('action', choices=('execute', 'summary', 'prepare-request'))
    parser.add_argument('--source'); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--member', choices=preparation.suite.MEMBERS); parser.add_argument('--sequence')
    parser.add_argument('--cost-microusd', type=int); parser.add_argument('--coverage-seconds', type=int)
    parser.add_argument('--valid-seconds', type=int, default=14400); args = parser.parse_args()
    if args.action == 'summary': summary(args.output)
    elif args.action == 'prepare-request':
        if not args.source or not args.member or not args.sequence or args.cost_microusd is None or args.coverage_seconds is None:
            parser.error('prepare-request requires source/member/sequence/cost-microusd/coverage-seconds')
        print(encoded(prepare_request(args.source, args.member, args.sequence, args.cost_microusd,
            args.coverage_seconds, args.valid_seconds, args.output)).decode())
    else:
        if not args.source: parser.error('execute requires source')
        try: print(encoded(execute_native(args.source, args.output)).decode())
        except Exception:
            print('v52Operator=FAIL; inspect the safe operation summary', flush=True); raise SystemExit(2) from None
