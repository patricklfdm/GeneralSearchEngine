"""Closed storage diagnostics, independent of receipts that grant acceptance."""
from pathlib import Path
from scripts.v51 import guest_transport as transport

SCHEMA='gse-v52-storage-diagnostic-v1'
OPERATIONS=frozenset(('source','volume-initialize','python-install','volume-ready','storage-receipt',
    'java-image','java-volume-before','java-install','java-volume-after','java-receipt',
    'placement-source','placement-volume','placement-python','placement-java','placement-parent','placement-binding'))
STAGES=frozenset(('begin','precheck','transport','postcheck','reply'))
ACTIONS=frozenset(('clock','prepare','query','check'))
KINDS=frozenset(('volume','paths'))
NODES=('node-1','node-2','node-3')
ERRORS=frozenset(('V52_STORAGE_EXCHANGE_TIMEOUT','V52_STORAGE_CONNECTION_LOST','V52_STORAGE_VALIDATION_REJECTED',
    'V52_STORAGE_IO_FAILED','V52_STORAGE_UNCLASSIFIED')) | frozenset(transport.FAILURE_DETAILS)
MODULES=frozenset(('cloud_storage','cloud_volume_guest','cloud_volume_paths','cloud_iap','cloud_identity',
    'cloud_native_runner','cloud_owner','cloud_credentials','remote_python_ssh','remote_python_receiver',
    'remote_java_ssh','remote_java_receiver','remote_voter_ssh','remote_host','remote_python_package',
    'remote_ssh','evidence'))
TYPES=frozenset(('TimeoutError','ConnectionError','ValueError','OSError','ProcessError','ProcessRejected','OTHER'))


def reason(error):
    if type(error) in (transport.ProcessError,transport.ProcessRejected):return error.code
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
        if path.parent==root and path.stem in MODULES and path.stem!='evidence' and 0<trace.tb_lineno<=10000:
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
        return dict(schema=SCHEMA,status='FAIL',node=node,operation=operation,stage=stage,kind=kind,action=action,
            reasonCode=code,errorType=typ,origin=site,**lists)
    except (KeyError,TypeError,ValueError):return None
