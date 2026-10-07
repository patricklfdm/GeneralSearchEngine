"""Closed Runner failure codes; never retain exception text or provider bodies."""
from contextlib import contextmanager
import json
import subprocess
from . import cloud_cleanup_credentials as credentials, cloud_http as h
from . import guest_session_recovery as session_recovery
from . import guest_transport as transport

STAGES = frozenset(('inputs','workflow','identity','approval','precheck','ci','observer',
    'checkout','credentials','artifact-metadata','artifact-bytes','control-read','final-freshness','allocation-recheck'))
GROUPS = {
    'PLAN_CHANGED_OR_EXPIRED': ('Runner plan drift/expiry',),
    'TIMING_CHANGED': ('Runner timing allocation changed',),
    'APPROVAL_MISMATCH': ('Runner exact approval missing/changed',),
    'PRICE_CHANGED_OR_EXPIRED': ('Runner price freshness/selection',),
    'RESERVATION_TOO_SMALL': ('Runner estimate exceeds approved reservation',),
    'BUDGET_CEILING': ('aggregate budget ceiling','ledger budget ceiling'),
    'SSH_KEY_INVALID': ('SSH owned private key','Runner private key inside evidence','Ed25519 public key','Ed25519 key encoding'),
    'SSH_KEY_MISMATCH': ('SSH private/public key mismatch',),
    'SOURCE_CHANGED': ('Runner selected configuration/source','Runner current source configuration changed'),
    'MASTER_CHANGED': ('master moved or source is not master',),
    'EXACT_SOURCE_CI_NOT_GREEN': ('exact-source CI not green','no exact-master CI run','CI skipped/failed/wrong-attempt job'),
    'CI_CHANGED': ('Runner current CI changed','CI changed during observation','Runner CI/master moved during inspection'),
    'CI_INVENTORY_MISMATCH': ('CI missing/duplicate jobs','CI duplicate job ID','CI workflow bytes changed'),
    'GITHUB_READ_FAILED': ('GitHub read failed or oversized',),
    'PRECHECK_EXPIRED': ('same-run observer evidence expired or wrong source','observer observations expired or blocked'),
    'PRECHECK_MISMATCH': ('storage original identity/prerequisites changed','storage requires successful same-run Runner precheck',
        'observer receipt changed, blocked or offline','Runner allocation prerequisite drift'),
    'RETAINED_CONTROL_CHANGED': ('Runner current control state changed','Runner observer ledger changed','Runner allocation control drift'),
    'ARTIFACT_METADATA_CHANGED': ('Runner retained artifact metadata changed','Runner artifact changed during inspection',
        'Runner original build job changed','Runner build job changed during inspection','Runner build producing job changed'),
    'ARTIFACT_EXPIRED': ('Runner artifact expiry',),
    'ARTIFACT_BYTES_MISMATCH': ('Runner original archive size/type','Runner original ZIP digest','Runner prepared package/build changed',
        'Runner original build/source/toolchain mismatch','Runner package receipt','Runner package original manifest mismatch',
        'Runner package payload profile','Runner published controls changed'),
    'ARTIFACT_INVENTORY_INVALID': ('Runner unsafe ZIP member','Runner artifact inventory/failure','Runner artifact required file missing',
        'Runner artifact member bound','Runner artifacts source/inventory'),
    'ADMISSION_DEADLINE': ('Runner admission original deadline','Runner allocation admission expired',
        'Runner first lease admission deadline','provider original deadline','provider late response'),
    'ADMISSION_READ_LIMIT': ('Runner admission read bound',),
    'RUNTIME_RESOURCE_SCOPE': ('owned endpoint','owned runtime compute read scope','owned host key read scope',
        'cleanup compute method/path/operation scope'),
    'RUNTIME_AUTHORITY_CHANGED': ('owned runtime durable authority changed','cleanup bound lease generation changed'),
    'RUNTIME_IDENTITY_CHANGED': ('owned provider/pinned host changed','cleanup numeric lookup identity',
        'guest numeric resource changed','guest instance not running','guest disk attachment/status',
        'guest facts changed/late','provider ownership/intent','instance guest access metadata',
        'resource labels','private interface','attached disk scope/automatic deletion','disk shape','boot image drift'),
    'RUNTIME_DEADLINE': ('owned original stage/lease deadline','owned runtime identity deadline',
        'native session connection budget','native IAP deadline/domain','provider original cleanup/read deadline','guest facts deadline'),
    'RUNTIME_BUDGET_EXCEEDED': ('control/lease budget exceeded',*(
        'budget exceeded: '+stage for stage in ('preparation','healthy','leader-loss','maintenance','no-quorum','validation-retention','cleanup'))),
    'RUNTIME_QUALIFICATION_FAILED': ('owned independent qualification failed',),
}
MESSAGES = {message:code for code,messages in GROUPS.items() for message in messages}
DETAILS = {
    **session_recovery.DETAILS,
    'PREPARATION_DEADLINE':'The original guest preparation deadline expired.',
    'PLAN_CHANGED_OR_EXPIRED':'The exact prepared plan changed or its admission window expired.',
    'TIMING_CHANGED':'The preparation timing allocation does not match the reviewed profile.',
    'APPROVAL_MISMATCH':'The explicit approval does not match the exact prepared request.',
    'PRICE_CHANGED_OR_EXPIRED':'The price observation changed or expired.',
    'RESERVATION_TOO_SMALL':'The estimate exceeds the approved reservation.',
    'BUDGET_CEILING':'The request exceeds the cumulative ledger ceiling.',
    'SSH_KEY_INVALID':'The attempt SSH key or its private location is invalid.',
    'SSH_KEY_MISMATCH':'The private SSH key does not match the approved public key.',
    'SOURCE_CHANGED':'The selected source or configuration changed.',
    'MASTER_CHANGED':'The current master no longer matches the approved source.',
    'EXACT_SOURCE_CI_NOT_GREEN':'Required CI for the exact source is missing or unsuccessful.',
    'CI_CHANGED':'CI or master changed during admission.',
    'CI_INVENTORY_MISMATCH':'The required CI job or workflow inventory does not match.',
    'GITHUB_READ_FAILED':'The bounded GitHub read failed or exceeded its response limit.',
    'PRECHECK_EXPIRED':'The same-run preflight evidence expired or has the wrong source.',
    'PRECHECK_MISMATCH':'The original same-run prerequisite evidence does not match.',
    'RETAINED_CONTROL_CHANGED':'The retained lease or ledger control state changed.',
    'ARTIFACT_METADATA_CHANGED':'The original artifact or producing job metadata changed.',
    'ARTIFACT_EXPIRED':'An original CI artifact has expired.',
    'ARTIFACT_BYTES_MISMATCH':'The original archive, build or package bytes do not match.',
    'ARTIFACT_INVENTORY_INVALID':'The original artifact inventory or a member is invalid.',
    'ADMISSION_DEADLINE':'The original admission deadline expired or a late response arrived.',
    'ADMISSION_READ_LIMIT':'The bounded admission read count was exceeded.',
    'PROVIDER_HTTP':'A provider request returned an unsuccessful HTTP status.',
    'ADMISSION_TIMEOUT':'An admission operation timed out.',
    'ADMISSION_TRANSPORT':'An admission transport operation failed.',
    'ADMISSION_FILE_ACCESS':'A required local admission file could not be accessed.',
    'ADMISSION_SUBPROCESS_FAILED':'An admission helper process failed.',
    'ADMISSION_INPUT_INVALID':'An admission input or response has an invalid structure.',
    'ADMISSION_INTERRUPTED':'Admission was interrupted.',
    'RUNTIME_RESOURCE_SCOPE':'A runtime provider read was outside the exact retained resource scope.',
    'RUNTIME_AUTHORITY_CHANGED':'The original runtime lease or reserved ledger changed or disappeared.',
    'RUNTIME_IDENTITY_CHANGED':'An exact resource, attachment, guest state or pinned host identity changed.',
    'RUNTIME_DEADLINE':'The original runtime command, stage or lease deadline was exhausted.',
    'RUNTIME_BUDGET_EXCEEDED':'Execution exceeded the original stage or lease time budget.',
    'RUNTIME_QUALIFICATION_FAILED':'Independent evidence did not establish every required experiment result.',
    'RUNTIME_TIMEOUT':'A runtime operation timed out; workload mutations are not replayed.',
    'RUNTIME_TRANSPORT':'A runtime transport operation failed; workload mutations are not replayed.',
    'RUNTIME_FILE_ACCESS':'A required runtime or evidence file could not be accessed.',
    'RUNTIME_SUBPROCESS_FAILED':'A runtime helper process failed.',
    'RUNTIME_INPUT_INVALID':'A runtime input or response has an invalid structure.',
    'RUNTIME_INTERRUPTED':'The runtime was interrupted.',
    'UNCLASSIFIED':'No classified failure was retained; raw exception details are withheld.',
}
TYPES = (ValueError,TypeError,KeyError,OSError,FileNotFoundError,PermissionError,TimeoutError,ConnectionError,
         KeyboardInterrupt,subprocess.TimeoutExpired,subprocess.CalledProcessError,json.JSONDecodeError,
         h.ApiError,credentials.CredentialError)


def detail(code):
    return DETAILS.get(code,credentials.DIAGNOSTICS.get(code,DETAILS['UNCLASSIFIED'])) if type(code) is str else DETAILS['UNCLASSIFIED']


def message(error):
    return error.args[0] if type(error) is ValueError and len(error.args)==1 and type(error.args[0]) is str else None


def failure(phase,error):
    if type(error) in (transport.ProcessError,transport.ProcessRejected):
        code=error.code if type(error.code) is str and error.code in transport.FAILURE_DETAILS else 'UNCLASSIFIED'
        return dict(phase=phase,type=type(error).__name__,code=code,detail=detail(code))
    if type(error) is session_recovery.RecoveryError:
        code=error.code if type(error.code) is str and error.code in session_recovery.DETAILS else 'UNCLASSIFIED'
        return dict(phase=phase,type='RecoveryError',code=code,detail=detail(code))
    if type(error) is AdmissionError:
        code=error.code if error.code in DETAILS or error.code in credentials.DIAGNOSTICS else 'UNCLASSIFIED'
        error_type=error.error_type if error.error_type in tuple(t.__name__ for t in TYPES) else 'Exception'
        result=dict(phase=phase,type=error_type,code=code,
                    admissionStage=error.stage if error.stage in STAGES else 'unknown')
        status=error.http_status
    else:
        code=credentials.diagnostic(error).get('reasonCode') or MESSAGES.get(message(error))
        if code is None:
            code=next((c for t,c in ((h.ApiError,'PROVIDER_HTTP'),(TimeoutError,'ADMISSION_TIMEOUT'),
                (subprocess.TimeoutExpired,'ADMISSION_TIMEOUT'),(ConnectionError,'ADMISSION_TRANSPORT'),
                (OSError,'ADMISSION_FILE_ACCESS'),(subprocess.CalledProcessError,'ADMISSION_SUBPROCESS_FAILED'),
                ((KeyError,TypeError,json.JSONDecodeError),'ADMISSION_INPUT_INVALID'),
                (KeyboardInterrupt,'ADMISSION_INTERRUPTED')) if isinstance(error,t)), 'UNCLASSIFIED')
        error_type=type(error).__name__ if type(error) in TYPES else 'Exception'
        result=dict(phase=phase,type=error_type,code=code)
        status=error.status if isinstance(error,h.ApiError) else None
    if type(status) is int and 100<=status<=599:result['httpStatus']=status
    result['detail']=detail(code)
    return result


def runtime_failure(phase,error):
    result=failure(phase,error)
    # Keep closed codes and numeric HTTP status, without mislabelling an owned
    # execution/collection failure as an admission failure.
    code=result['code']
    if code.startswith('ADMISSION_') and 'RUNTIME_'+code[len('ADMISSION_'):] in DETAILS:
        code='RUNTIME_'+code[len('ADMISSION_'):]
        result.update(code=code,detail=detail(code))
    return result


class AdmissionError(ValueError):
    def __init__(self,stage,error):
        if stage not in STAGES:raise ValueError('unknown admission diagnostic stage')
        record=failure('admission',error)
        self.stage,self.code,self.error_type=stage,record['code'],record['type']
        self.http_status=record.get('httpStatus')
        super().__init__(record['detail'])


@contextmanager
def stage(name):
    if name not in STAGES:raise ValueError('unknown admission diagnostic stage')
    try:yield
    except AdmissionError:raise
    except (Exception,KeyboardInterrupt) as error:raise AdmissionError(name,error) from None
