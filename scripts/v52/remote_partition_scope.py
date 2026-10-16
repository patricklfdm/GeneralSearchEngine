"""Closed admission for one unchanged M04 history; no other formal service yet."""
from . import measurement_recovery as recovery,measurement_options as options,measurement_model as model
from .evidence import need,encoded

CASE=recovery.CASES[1]
EXECUTION='loopback-ssh-partition-history-only'


def profile(value):
    need(encoded(value)==encoded(recovery.profile(CASE)),'remote partition exact M04 profile')
    return value


def history(binding):
    if 'measurementProfile' not in binding:
        need(binding.get('driverExercise') is True and not {'remotePartition','faultParameters'} & set(binding),
             'remote service whole untimed history only')
        return None
    value=profile(binding['measurementProfile'])
    need(binding['mode']=='candidate-minimum' and binding['faultParameters']==value['faultParameters'] and
         binding['readParameters']==options.parameters() and binding['programSha256']==model.PLAN_SHA and
         not {'driverExercise','smokeInitialization','readConfigurationOnly'} & set(binding),
         'remote partition exact history binding')
    return value
