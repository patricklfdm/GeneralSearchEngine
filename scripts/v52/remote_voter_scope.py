"""Closed service admission for the unchanged smoke and M01–M04 histories."""
from . import remote_partition_scope as partition
from . import measurement_m01 as m01,measurement_minimum as minimum
from .evidence import need,encoded
from . import remote_host_domains as domains

RESTART_CASE=partition.recovery.CASES[0]
RESTART_EXECUTION='loopback-ssh-retained-restart-only'
FORMAL_EXECUTION='loopback-ssh-formal-histories-only'


def profile(value):
    if type(value) is dict and value.get('family')=='M01':
        expected=m01.profile(value.get('mode'),value.get('repetition'))
        need(encoded(value)==encoded(expected),'remote exact M01 profile');return value
    if type(value) is dict and value.get('family') in ('M02','M03'):
        expected=minimum.profile(value.get('case'))
        need(encoded(value)==encoded(expected),'remote exact M02/M03 profile');return value
    need(type(value) is dict and value.get('case') in partition.recovery.CASES and
         encoded(value)==encoded(partition.recovery.profile(value['case'])),'remote exact M04 profile')
    return value


def history(binding):
    if 'measurementProfile' not in binding:
        need(binding.get('driverExercise') is True and not {'remotePartition','remoteRestart','remoteFormal','faultParameters'} & set(binding),
             'remote service whole untimed history only');return None
    value=profile(binding['measurementProfile'])
    parameters=value['parameters'] if value['family'] in ('M02','M03') else partition.options.parameters()
    need(binding['mode']==value['mode'] and binding['readParameters']==parameters and binding['programSha256']==partition.model.PLAN_SHA and
         not {'driverExercise','smokeInitialization','readConfigurationOnly'} & set(binding),'remote exact history binding')
    if value['family']=='M04':need(binding['faultParameters']==value['faultParameters'] and 'remoteFormal' not in binding,'remote exact recovery binding')
    else:need(not {'remotePartition','remoteRestart','faultParameters'} & set(binding),'remote undeclared formal fault')
    return value


def formal(binding):
    if 'remoteFormal' not in binding:return False
    value=history(binding)
    need(domains.matches(binding,'remoteFormal',FORMAL_EXECUTION) and value is not None and value['family'] in ('M01','M02','M03'),
         'remote formal service binding');return True


def generation(config):
    value=config.get('generation',1)
    need(type(value) is int and value in (1,2),'voter generation')
    if 'generation' in config:
        bound=config['binding']
        need(domains.matches(bound,'remoteRestart',RESTART_EXECUTION) and history(bound)['case']==RESTART_CASE,
             'voter undeclared generation')
    return value


def control_name(node,generation=1):return node+'-control'+('' if generation==1 else '-g2')


def fields(config):
    return {'schema','execution','node','root','host','binding','socket','session'} | ({'generation'} if 'generation' in config else set())
