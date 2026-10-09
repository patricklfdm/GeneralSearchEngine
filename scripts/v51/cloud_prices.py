"""Shared bounded quote arithmetic; callers select their closed lifetime policy."""
import re
from . import cloud_authority as a, cloud_workload_contract as workload, performance_model as m


def estimate(value, now, *, minimum_coverage_seconds):
    fields = {'observedAt', 'expiresAt', 'region', 'machineType', 'diskType', 'vmMicrousdPerHour',
              'diskMicrousdPerGiBHour', 'pricedThroughSeconds', 'retentionDays', 'otherCostsMicrousd', 'sources'}
    m.need(type(value) is dict and set(value) == fields, 'Runner price fields')
    a.integer(value['observedAt'], 1); a.integer(value['expiresAt'], value['observedAt']+1, value['observedAt']+86400)
    env = workload.load()['environment']
    m.need(value['observedAt'] <= now < value['expiresAt'] and
           (value['region'], value['machineType'], value['diskType']) ==
           (env['zone'].rsplit('-', 1)[0], env['machineType'], env['diskType']), 'Runner price freshness/selection')
    a.integer(minimum_coverage_seconds, 1, 86400)
    seconds = a.integer(value['pricedThroughSeconds'], 1, 86400)
    m.need(seconds >= minimum_coverage_seconds, 'Runner price lifetime coverage')
    a.integer(value['retentionDays'], 30, 365)
    vm = a.integer(value['vmMicrousdPerHour'], 1, a.MAXIMUM_BUDGET_MICROUSD)
    disk = a.integer(value['diskMicrousdPerGiBHour'], 1, a.MAXIMUM_BUDGET_MICROUSD)
    extra = value['otherCostsMicrousd']
    m.need(type(extra) is dict and set(extra) == {'requests', 'evidenceRetention', 'network', 'actions', 'failureOverhang'},
           'Runner price coverage')
    for cost in extra.values(): a.integer(cost, 1, a.MAXIMUM_BUDGET_MICROUSD)
    sources = value['sources']
    m.need(type(sources) is dict and set(sources) == {'compute', 'disks', 'storage', 'network', 'actions'}, 'Runner price sources')
    for kind, url in sources.items():
        domain = r'docs\.github\.com' if kind == 'actions' else r'(?:cloud|docs\.cloud)\.google\.com'
        m.need(type(url) is str and len(url) <= 1024 and re.fullmatch(r'https://'+domain+r'/[^\s]+', url), 'Runner price source URL')
    return ((3*vm+450*disk)*seconds+3599)//3600 + sum(extra.values())

