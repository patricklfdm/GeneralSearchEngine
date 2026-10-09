"""Closed native full-preset identities and ceilings, also shipped to trusted guests.

No caller-selected duration. v1/v2 requests retain their original semantics.
The same timing plan identity binds every member of a new v3 sequence.
"""
from copy import deepcopy
import hashlib
import json
import re

REQUEST_SCHEMA = 'gse-v51-native-request-v3'
PLAN_SHA256 = 'f201a52a96b6451f068090f0f8b6999f15c774fa9ae41ec60182f2329c214670'
MEMBERS = ('experiment', 'failure-drill', 'canonical-1', 'canonical-2', 'canonical-3')
ORDERS = ('any-order', 'experiment-first', 'canonical-first')
PROFILES = {'failure-drill': {'profile': 'owned-failure-drill-v1',
                   'cells': ['leader-loss',
                             'isolated-old-leader',
                             'asymmetric-requests',
                             'asymmetric-responses',
                             'slow-follower',
                             'interrupted-transfer',
                             'entry-chosen',
                             'proof-quorum',
                             'group-restart',
                             'maintenance',
                             'no-quorum',
                             'minority-capacity'],
                   'limitsSeconds': {'preparation': 3600,
                                     'leader-loss': 600,
                                     'isolated-old-leader': 600,
                                     'asymmetric-requests': 600,
                                     'asymmetric-responses': 600,
                                     'slow-follower': 600,
                                     'interrupted-transfer': 600,
                                     'entry-chosen': 600,
                                     'proof-quorum': 600,
                                     'group-restart': 600,
                                     'maintenance': 900,
                                     'no-quorum': 300,
                                     'minority-capacity': 600,
                                     'validation-retention': 2400,
                                     'cleanup': 900,
                                     'control': 900},
                   'leaseSeconds': 16200,
                   'operationGraceSeconds': 1800,
                   'retentionReserveSeconds': 300,
                   'commandGuardSeconds': 16500,
                   'terminationGraceSeconds': 60,
                   'jobMinutes': 330,
                   'jobOverheadReserveSeconds': 3240,
                   'healthyModeSeconds': None},
 'canonical': {'profile': 'owned-canonical-v1',
               'cells': ['healthy',
                         'read-heavy',
                         'sustained',
                         'leader-loss',
                         'isolated-old-leader',
                         'asymmetric-requests',
                         'asymmetric-responses',
                         'slow-follower',
                         'interrupted-transfer',
                         'entry-chosen',
                         'proof-quorum',
                         'group-restart',
                         'maintenance',
                         'no-quorum',
                         'minority-capacity'],
               'limitsSeconds': {'preparation': 5400,
                                 'healthy': 1800,
                                 'read-heavy': 600,
                                 'sustained': 600,
                                 'leader-loss': 600,
                                 'isolated-old-leader': 600,
                                 'asymmetric-requests': 600,
                                 'asymmetric-responses': 600,
                                 'slow-follower': 600,
                                 'interrupted-transfer': 600,
                                 'entry-chosen': 600,
                                 'proof-quorum': 600,
                                 'group-restart': 600,
                                 'maintenance': 900,
                                 'no-quorum': 300,
                                 'minority-capacity': 600,
                                 'validation-retention': 2400,
                                 'cleanup': 900,
                                 'control': 900},
               'leaseSeconds': 19800,
               'operationGraceSeconds': 1800,
               'retentionReserveSeconds': 300,
               'commandGuardSeconds': 20100,
               'terminationGraceSeconds': 60,
               'jobMinutes': 360,
               'jobOverheadReserveSeconds': 1440,
               'healthyModeSeconds': 600}}


def need(ok, message):
    if not ok: raise ValueError(message)


def selection(member):
    need(type(member) is str and member in MEMBERS, 'native preset member')
    repetition = int(member[-1]) if member.startswith('canonical-') else None
    return ('canonical' if repetition else member), repetition


def allocation(member):
    preset, repetition = selection(member)
    if preset == 'experiment':
        from . import native_experiment_timing as old
        limits = dict(old.STAGES)
        value = dict(profile=old.PROFILE, limitsSeconds=limits, leaseSeconds=old.LEASE_SECONDS,
            operationGraceSeconds=old.GRACE_SECONDS, cells=['healthy','leader-loss','maintenance','no-quorum'],
            retentionReserveSeconds=None, healthyModeSeconds=old.CONTROLS['mode'], commandGuardSeconds=15000,
            terminationGraceSeconds=60, jobMinutes=270, jobOverheadReserveSeconds=1140)
    else: value = deepcopy(PROFILES[preset])
    value.update(approvalSeconds=900, allocatedSeconds=sum(value['limitsSeconds'].values()), preset=preset,
                 repetition=repetition, controlNode=None if preset == 'failure-drill' else 'node-'+str(repetition or 1))
    value['unallocatedSeconds'] = value['leaseSeconds']-value['allocatedSeconds']
    value['priceCoverageSeconds'] = value['limitsSeconds']['preparation']+value['leaseSeconds']+value['operationGraceSeconds']
    return value


def by_profile(profile):
    for member in ('experiment','failure-drill','canonical-1'):
        value=allocation(member)
        if value['profile']==profile:return value
    raise ValueError('unreviewed budget profile')


def selected(req):
    return req.get('schema') == REQUEST_SCHEMA


def validate(req):
    fields={'schema','suite','execution','paidCloud','source','bundleSha256','configurationSha256','workloadSha256',
            'sequence','attempt','order','member','createdAt','guestAccessSha256','timingProfile','timingPlanSha256'}
    need(type(req) is dict and set(req)==fields and req['schema']==REQUEST_SCHEMA, 'native preset request fields')
    value=allocation(req['member'])
    need(req['suite']=='v5.1-automatic-leadership-suite-v1' and req['execution']=='gcp-v51-owned-control' and
         req['paidCloud'] is True and req['order'] in ORDERS and req['timingProfile']==value['profile'] and
         req['timingPlanSha256']==PLAN_SHA256 and
         req['workloadSha256']=='f0e964ba12fea8702a40082d4a01a85d6d3eb1bf7fe3fecf8778c899af44bea7', 'native preset request identity')
    for key,size in (('source',40),('sequence',32),('attempt',32),('bundleSha256',64),('configurationSha256',64),
                     ('workloadSha256',64),('guestAccessSha256',64)):
        need(type(req[key]) is str and re.fullmatch('[0-9a-f]{%d}'%size,req[key]), 'native preset request digest')
    need(type(req['createdAt']) is int and 1<=req['createdAt']<(1<<63)-value['leaseSeconds']-value['operationGraceSeconds'],
         'native preset request timestamp')
    return value


def request_sha(req):
    validate(req)
    return hashlib.sha256(json.dumps(req,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def volume_request(value):
    """Verify the full admitted request inside a new-format volume descriptor."""
    need(value.get('schema')=='gse-v51-native-volume-request-v2', 'native preset volume schema')
    req=value['nativeRequest']; validate(req)
    need(value['requestSha256']==request_sha(req) and
         all(value['binding'][k]==req[k] for k in ('source','bundleSha256','workloadSha256','attempt')) and
         hashlib.sha256(json.dumps(value['access'],sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()==req['guestAccessSha256'],
         'native preset volume request binding')
    return req


def package_request(value):
    volume=value['nativeVolume']['request']
    if volume.get('schema')=='gse-v51-native-volume-request-v1':
        need('nativeRequest' not in volume, 'legacy native volume fields');return None
    req=volume_request(volume)
    need(value['binding']==volume['binding'], 'native preset package binding')
    return req


def package_profile(value):
    req=package_request(value)
    return validate(req)['profile'] if req is not None else 'owned-experiment-v2'


def fault_configuration(config, cases):
    """Called only after the native service authenticates its installed session."""
    if config.get('execution')=='local-guest-service-only':return False
    need(config.get('execution')=='native-v51-guest-service', 'native fault execution')
    need('nativeRequest' in config, 'native fault request missing')
    selected=validate(config['nativeRequest'])
    need(config.get('faultCell') in cases and config['faultCell'] in selected['cells'], 'native fault selection')
    return True
