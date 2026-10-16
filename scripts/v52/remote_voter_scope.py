"""Service admission for unchanged smoke and the two frozen M04 histories."""
from . import remote_partition_scope as partition
from .evidence import need,encoded

RESTART_CASE=partition.recovery.CASES[0]
RESTART_EXECUTION='loopback-ssh-retained-restart-only'


def profile(value):
    need(type(value) is dict and value.get('case') in partition.recovery.CASES and
         encoded(value)==encoded(partition.recovery.profile(value['case'])),'remote exact M04 profile')
    return value


def history(binding):
    if 'measurementProfile' not in binding:
        need(binding.get('driverExercise') is True and not {'remotePartition','remoteRestart','faultParameters'} & set(binding),
             'remote service whole untimed history only');return None
    value=profile(binding['measurementProfile'])
    need(binding['mode']=='candidate-minimum' and binding['faultParameters']==value['faultParameters'] and
         binding['readParameters']==partition.options.parameters() and binding['programSha256']==partition.model.PLAN_SHA and
         not {'driverExercise','smokeInitialization','readConfigurationOnly'} & set(binding),'remote exact history binding')
    return value


def generation(config):
    value=config.get('generation',1)
    need(type(value) is int and value in (1,2),'voter generation')
    if 'generation' in config:
        bound=config['binding']
        need(bound.get('remoteRestart')==RESTART_EXECUTION and history(bound)['case']==RESTART_CASE,
             'voter undeclared generation')
    return value


def control_name(node,generation=1):return node+'-control'+('' if generation==1 else '-g2')


def fields(config):
    return {'schema','execution','node','root','host','binding','socket','session'} | ({'generation'} if 'generation' in config else set())
