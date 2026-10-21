"""Closed pre-tunnel diagnostics; no credentials, URLs or exception messages."""
import time
from . import cloud_storage_diagnostics as storage, cloud_credentials as credentials
from . import cloud_provider as provider, cloud_read_retry
from scripts.v51 import guest_transport as transport

PHASES=frozenset(('directory','owner-lock','api-lock','identity-before','credentials','identity-after','credential-file'))
TYPES=storage.TYPES|frozenset(('ContextError','CredentialError','ApiError'))
CODES=frozenset(transport.FAILURE_DETAILS)|frozenset(provider.READ_FAILURES)|frozenset(credentials.exchange.DIAGNOSTICS)|frozenset(
    'V52_CREDENTIAL_'+code for code in credentials.CODES)|frozenset((
    'IAP_ORIGINAL_CONNECT_TIMEOUT','IAP_IDENTITY_OR_AUTHORITY_REJECTED'))|frozenset(
    'IAP_PROVIDER_HTTP_'+str(status) for status in range(100,600))|cloud_read_retry.CODES


def attempt(number,phase,began,durations,error=None,code=None):
    typ=None if error is None else type(error).__name__
    return dict(attempt=number,status='PASS' if error is None else 'FAIL',phase=phase,
        elapsedMillis=max(0,round((time.monotonic()-began)*1000)),phaseMillis=dict(durations),
        reasonCode=code if code in CODES else (None if error is None else 'IAP_IDENTITY_OR_AUTHORITY_REJECTED'),
        errorType=typ if typ in TYPES or typ is None else 'OTHER',origin=None if error is None else storage.origin(error))


def project(rows):
    """Revalidate the bounded diagnostic before exporting it from the Runner."""
    if type(rows) is not list or not 1<=len(rows)<=2:return None
    result=[]
    for index,row in enumerate(rows,1):
        if type(row) is not dict or set(row)!={'attempt','status','phase','elapsedMillis','phaseMillis','reasonCode','errorType','origin'}:
            return None
        if type(row['attempt']) is not int or row['attempt']!=index or row['status'] not in ('PASS','FAIL') or row['phase'] not in PHASES:
            return None
        durations=row['phaseMillis']
        if type(durations) is not dict or not set(durations)<=PHASES or any(
            type(n) is not int or not 0<=n<2**63 for n in (row['elapsedMillis'],*durations.values())):return None
        if row['status']=='PASS':
            if any(row[k] is not None for k in ('reasonCode','errorType','origin')):return None
            if index!=len(rows):return None
        elif row['reasonCode'] not in CODES or row['errorType'] not in TYPES:return None
        site=row['origin']
        if site is not None and (type(site) is not dict or set(site)!={'module','line'} or
            site['module'] not in storage.MODULES or type(site['line']) is not int or not 0<site['line']<=10000):return None
        result.append(dict(row,phaseMillis=dict(durations),origin=None if site is None else dict(site)))
    return result
