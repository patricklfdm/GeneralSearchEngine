"""Closed storage diagnostics, independent of receipts that grant acceptance."""
from pathlib import Path
from scripts.v51 import guest_transport as transport
from . import cloud_provider as provider, cloud_read_retry, cloud_volume_guest as volume

SCHEMA='gse-v52-storage-diagnostic-v1'
OPERATIONS=frozenset(('source','volume-initialize','python-install','volume-ready','storage-receipt',
    'java-image','java-volume-before','java-install','java-volume-after','java-receipt',
    'placement-source','placement-volume','placement-python','placement-java','placement-parent','placement-binding'))
STAGES=frozenset(('begin','precheck','transport','postcheck','reply'))
ACTIONS=frozenset(('clock','prepare','query','check'))
KINDS=frozenset(('volume','paths'))
NODES=('node-1','node-2','node-3')
ERRORS=frozenset(('V52_STORAGE_EXCHANGE_TIMEOUT','V52_STORAGE_CONNECTION_LOST','V52_STORAGE_VALIDATION_REJECTED',
    'V52_STORAGE_IO_FAILED','V52_STORAGE_UNCLASSIFIED')) | frozenset(transport.FAILURE_DETAILS) | frozenset(provider.READ_FAILURES) | cloud_read_retry.CODES | volume.FAILURE_CODES
MODULES=frozenset(('cloud_storage','cloud_volume_guest','cloud_volume_paths','cloud_iap','cloud_identity',
    'cloud_native_runner','cloud_owner','cloud_credentials','remote_python_ssh','remote_python_receiver',
    'remote_java_ssh','remote_java_receiver','remote_voter_ssh','remote_host','remote_python_package',
    'remote_ssh','evidence','cloud_provider','cloud_wire_policy','cloud_control','cloud_native_cleanup','cloud_read_retry'))
TYPES=frozenset(('TimeoutError','ConnectionError','ValueError','ControlReadError','ReadError','OSError','ProcessError','ProcessRejected','VolumeError','OTHER'))


class VolumeError(ConnectionError):
    """A request-bound receiver rejection; only read deadlines are retryable."""
    def __init__(self,code):
        if code not in volume.FAILURE_CODES:raise ValueError('unknown volume rejection')
        self.code=code;super().__init__(code)

    @property
    def retryable(self):return self.code in volume.READ_TIMEOUT_CODES


def remote_error(error,action,envelope):
    if type(error) is not transport.ProcessError or error.code!='REMOTE_EXIT':return error
    try:
        raw=getattr(error,'partial_output',b'')
        if not 0<len(raw)<=2048:return error
        value=volume.decode(raw)
        if type(value) is not dict or set(value)!={'schema','code','action','envelopeSha256'} or \
           value['schema']!=volume.FAILURE_SCHEMA or value['code'] not in volume.FAILURE_CODES or \
           value['action']!=action or value['envelopeSha256']!=volume.digest(envelope):return error
        return VolumeError(value['code'])
    except (ValueError,TypeError,KeyError):return error


def read_check(value):
    """Closed per-attempt timing, with no raw command, stderr or authority bytes."""
    if type(value) is not dict or set(value)!={'limitSeconds','attempts'} or type(value['limitSeconds']) is not int or value['limitSeconds']!=300:return None
    rows=value['attempts']
    if type(rows) is not list or not 1<=len(rows)<=3:return None
    for index,row in enumerate(rows,1):
        if type(row) is not dict or set(row)!={'attempt','phase','elapsedMillis','remainingMillis','reasonCode'} or \
           type(row['attempt']) is not int or row['attempt']!=index or row['phase'] not in ('clock','check','complete') or \
           any(type(row[k]) is not int or not 0<=row[k]<2**63 for k in ('elapsedMillis','remainingMillis')) or \
           row['reasonCode'] not in ERRORS|{None}:return None
        if (row['phase']=='complete')!=(row['reasonCode'] is None):return None
    return dict(limitSeconds=300,attempts=[dict(row) for row in rows])


def reason(error):
    if type(error) is VolumeError:return error.code
    if type(error) is cloud_read_retry.ReadError:return error.code
    if type(error) in (transport.ProcessError,transport.ProcessRejected):return error.code
    if type(error) is provider.ControlReadError and error.code in provider.READ_FAILURES:return error.code
    if isinstance(error,TimeoutError):return 'V52_STORAGE_EXCHANGE_TIMEOUT'
    if isinstance(error,ConnectionError):return 'V52_STORAGE_CONNECTION_LOST'
    if isinstance(error,ValueError):return 'V52_STORAGE_VALIDATION_REJECTED'
    if isinstance(error,OSError):return 'V52_STORAGE_IO_FAILED'
    return 'V52_STORAGE_UNCLASSIFIED'


def error_type(error):
    name=type(error).__name__
    return name if name in TYPES else 'OTHER'


def origin(error):
    """Only a known repository module and line; never locals or exception text."""
    root=Path(__file__).resolve().parent;trace=error.__traceback__;found=None
    while trace is not None:
        path=Path(trace.tb_frame.f_code.co_filename)
        helper=path.stem=='cloud_provider' and trace.tb_frame.f_code.co_name=='read_need'
        if path.parent==root and path.stem in MODULES and path.stem!='evidence' and not helper and 0<trace.tb_lineno<=10000:
            found=dict(module=path.stem,line=trace.tb_lineno)
        trace=trace.tb_next
    return found


def project(value):
    """Revalidate on export. Extra/private fields never propagate."""
    try:
        if type(value) is not dict or value.get('schema')!=SCHEMA or value.get('status')!='FAIL':return None
        node=value['node'];operation=value['operation'];stage=value['stage']
        kind=value['kind'];action=value['action'];code=value['reasonCode'];typ=value['errorType'];site=value['origin']
        if node not in (None,*NODES) or operation not in OPERATIONS or stage not in STAGES or \
           kind not in (None,*KINDS) or action not in (None,*ACTIONS) or code not in ERRORS or typ not in TYPES:return None
        if (kind is None)!=(action is None):return None
        if site is not None and (type(site) is not dict or set(site)!={'module','line'} or site['module'] not in MODULES or
                                type(site['line']) is not int or not 0<site['line']<=10000):return None
        lists={}
        for key in ('initializedNodes','pythonInstalledNodes','javaInstalledNodes'):
            rows=value[key]
            if type(rows) is not list or len(rows)>3 or any(n not in NODES for n in rows) or len(set(rows))!=len(rows):return None
            lists[key]=list(rows)
        if not set(lists['javaInstalledNodes'])<=set(lists['pythonInstalledNodes'])<=set(lists['initializedNodes']):return None
        timing={}
        if 'readCheck' in value:
            check=read_check(value['readCheck'])
            if check is None:return None
            timing['readCheck']=check
        return dict(schema=SCHEMA,status='FAIL',node=node,operation=operation,stage=stage,kind=kind,action=action,
            reasonCode=code,errorType=typ,origin=site,**lists,**timing)
    except (KeyError,TypeError,ValueError):return None
