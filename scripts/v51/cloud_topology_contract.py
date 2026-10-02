"""Closed cleanup-only fixture profile; never a workload or runner admission."""
from . import cloud_authority as a, performance_model as m

COST = 5_000_000
PREPARATION_SECONDS = 600


def manifest(cfg, source, prices_sha):
    from . import cloud_preflight as p
    a.digest(source, 40); a.digest(prices_sha)
    return dict(schema='gse-v51-topology-fixture-manifest-v1', source=source,
        configurationSha256=p.configuration(cfg), providerConfigurationSha256=p.gcp.config(cfg['provider']),
        kind='cleanup-qualification',
        topology=dict(instances=3, machineType='n2-standard-8', bootDisks=3, bootGiB=50,
                      dataDisks=3, dataGiB=100, firewalls=4),
        instanceTerminationAction='STOP', maxRunSeconds=5400,
        leaseSeconds=5400, graceSeconds=1080, preparationSeconds=PREPARATION_SECONDS,
        maximumCostMicrousd=COST, pricesSha256=prices_sha)


def validate(value, req, configuration):
    from . import cloud_native_authority as n, cloud_gcp as g
    n.validate_request(req)
    a.digest(value['configurationSha256']); a.digest(value['pricesSha256'])
    expected = dict(schema='gse-v51-topology-fixture-manifest-v1', source=req['source'],
        configurationSha256=value['configurationSha256'], providerConfigurationSha256=g.config(configuration),
        kind='cleanup-qualification',
        topology=dict(instances=3, machineType='n2-standard-8', bootDisks=3, bootGiB=50,
                      dataDisks=3, dataGiB=100, firewalls=4),
        instanceTerminationAction='STOP', maxRunSeconds=5400,
        leaseSeconds=5400, graceSeconds=1080, preparationSeconds=PREPARATION_SECONDS,
        maximumCostMicrousd=COST, pricesSha256=value['pricesSha256'])
    m.need(value == expected and req['bundleSha256'] == m.sha(m.canonical(value)) and
           req['configurationSha256'] == g.config(configuration) and req['member'] == 'experiment' and
           'guestAccessSha256' in req, 'topology fixture profile/request binding')
    return value
