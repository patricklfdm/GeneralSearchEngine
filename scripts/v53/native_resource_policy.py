"""Caller-bound native fixture staging; never infer admission from a receipt."""
from .membership_model import need
from . import bootstrap_replay_contract as source

SMALL = 'SMALL_FIXTURE'
DEFAULT = 'DEFAULT_SNAPSHOT_STAGING'
LIMITS = {SMALL: 512*1024**2, DEFAULT: 16*1024**3}


def check(profile):
    need(type(profile) is str and profile in LIMITS, 'native resource explicit profile')
    return LIMITS[profile]


def scope(profile, bootstrap_source, wire_layout):
    check(profile)
    source.check_layout(bootstrap_source, wire_layout)
    need(profile == SMALL or (bootstrap_source, wire_layout) == (source.BACKUP, source.SEGMENTED),
         'default staging requires explicit segmented backup')


def options(profile):
    check(profile)
    return {} if profile == SMALL else dict(resource_profile=profile)


def receipt(value, profile):
    limit = check(profile)
    return value if profile == SMALL else dict(value, resourceProfile=profile, stagingLimit=limit)


def check_receipt(value, profile):
    limit = check(profile)
    need(type(value) is dict, 'native resource receipt')
    if profile == SMALL:
        need('resourceProfile' not in value and 'stagingLimit' not in value, 'native resource receipt profile')
    else:
        need(value.get('resourceProfile') == profile and type(value.get('stagingLimit')) is int and
             value['stagingLimit'] == limit, 'native resource receipt profile')
