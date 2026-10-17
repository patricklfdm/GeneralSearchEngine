"""V5.2 provider facts and diagnostic permissions; never native admission.

The fixed native reader lives in cloud_preflight_read. These pure checks do not
grant an API, qualify conditional permissions or certify an available VM slot.
"""
from copy import deepcopy
import ipaddress
import math
import re
from urllib.parse import urlencode, quote
from scripts.v51 import cloud_image_policy as images
from . import cloud_authority as a, cloud_provider as p, cloud_credentials as credentials
from .evidence import need, encoded, digest

CONFIG_PATH = 'docs/v5x/v5.2/cloud-provider.json'
FRESH_SECONDS = 900
EVIDENCE_PREFIX = 'v5.2-bounded-follower-reads/evidence/'
MIN_RETENTION_DAYS = 30
CLEANUP = (
    'compute.disks.get', 'compute.disks.delete', 'compute.instances.get', 'compute.instances.delete',
    'compute.firewalls.get', 'compute.firewalls.delete', 'compute.networks.updatePolicy',
    'compute.zoneOperations.get', 'compute.zoneOperations.list',
    'compute.globalOperations.get', 'compute.globalOperations.list')
RUNNER = CLEANUP + (
    'compute.projects.get', 'compute.regions.get', 'compute.zones.get', 'compute.machineTypes.get',
    'compute.diskTypes.get', 'compute.disks.create', 'compute.disks.setLabels', 'compute.disks.use',
    'compute.instances.create', 'compute.instances.setLabels', 'compute.instances.setMetadata',
    'compute.instances.setTags', 'compute.instances.getGuestAttributes', 'compute.firewalls.create',
    'compute.networks.get', 'compute.subnetworks.get', 'compute.subnetworks.use')
FORBIDDEN = (
    'resourcemanager.projects.setIamPolicy', 'iam.roles.create', 'iam.roles.update',
    'iam.serviceAccounts.create', 'iam.serviceAccounts.delete', 'iam.serviceAccounts.setIamPolicy',
    'iam.serviceAccounts.actAs', 'iam.serviceAccounts.getAccessToken', 'iam.serviceAccountKeys.create',
    'compute.instances.setServiceAccount', 'compute.subnetworks.useExternalIp',
    'compute.projects.setCommonInstanceMetadata', 'storage.buckets.create')
BUCKET_FORBIDDEN = ('storage.buckets.delete', 'storage.buckets.update', 'storage.buckets.setIamPolicy',
                    'storage.objects.list', 'storage.objects.get', 'storage.objects.create',
                    'storage.objects.delete', 'storage.objects.update')
FLAGS = dict(paidAdmission=False, effectiveIamQualified=False, objectPermissionsQualified=False,
             cleanupReady=False, fullRemoteQualification=False)
LIMITATIONS = (
    'Organization/folder inherited IAM reads are not required; their policies are not audited here.',
    'testIamPermissions is diagnostic, not an authorization decision or exhaustive privilege audit.',
    'Bucket probes cannot prove conditional named-object access; no object testIamPermissions route is used.',
    'Exact image GET proves readability, not useReadOnly or disk creation. No image-list grant is required for a diagnostic probe.',
    'Quota headroom is an observation, not an allocation reservation.',
    'Bucket lifecycle changes can take 24 hours to apply; this observation alone does not qualify retained evidence.')
PENDING = ('fresh manual cleanup; schedule optional', 'conditional control/evidence permissions on actual paths',
           'original source/image/resource creation and exact-ID cleanup', 'owned IAP and guest identity',
           'fresh original CI/input provenance and exact operator approval', 'concrete native owner and whole-member replay')


def configuration(value):
    a.fields(value, 'schema provider projectNumber layout policy', 'preflight configuration')
    need(value['schema'] == 'gse-v52-preflight-config-v1', 'V5.2 preflight configuration schema')
    p.config(value['provider']); a.numeric(value['projectNumber']); a.layout(value['layout']); a.policy(value['policy'])
    return digest(encoded(value))


def context(cfg, source, role):
    sha = configuration(cfg); a.hex_value(source, 40)
    return dict(source=source, preflightConfigurationSha256=sha,
                credentialSelection=credentials.selection(cfg['provider'], cfg['projectNumber'], role))


def query(url, *, method='GET', body=None, maximum=1 << 20, absent=False):
    return dict(method=method, url=url, body=body, maximum=maximum, absent=absent)


def plan(cfg, role):
    configuration(cfg); need(role in credentials.ROLES, 'V5.2 preflight role')
    c = cfg['provider']; base = p.COMPUTE+c['project']; bucket = p.STORAGE+'storage/v1/b/'+c['bucket']
    required = sorted(RUNNER if role == 'runner' else CLEANUP)
    forbidden = sorted(set(FORBIDDEN) | (set(RUNNER)-set(required)))
    result = dict(projectPermissions=query('https://cloudresourcemanager.googleapis.com/v1/projects/'+c['project']+
        ':testIamPermissions', method='POST', body=dict(permissions=sorted(required+forbidden)), maximum=65536),
        bucketPermissions=query(bucket+'/iam/testPermissions?'+urlencode(
            {'permissions':sorted(['storage.buckets.get', *BUCKET_FORBIDDEN])}, doseq=True), maximum=65536),
        bucket=query(bucket+'?'+urlencode(dict(fields='name,projectNumber,location,iamConfiguration,retentionPolicy,'
                                            'defaultEventBasedHold,lifecycle,softDeletePolicy,versioning'))))
    if role == 'runner':
        shapes = dict(project=(base, 'id,name,selfLink,quotas'),
            region=(base+'/regions/'+c['region'], 'id,name,selfLink,status,quotas'),
            zone=(base+'/zones/'+c['zone'], 'id,name,selfLink,status,region'),
            machine=(base+'/zones/'+c['zone']+'/machineTypes/'+c['machineType'], 'id,name,selfLink,guestCpus,memoryMb'),
            diskType=(base+'/zones/'+c['zone']+'/diskTypes/'+c['diskType'], 'id,name,selfLink'),
            network=(base+'/global/networks/'+c['network'], 'id,name,selfLink'),
            subnetwork=(base+'/regions/'+c['region']+'/subnetworks/'+c['subnetwork'],
                        'id,name,selfLink,network,region,privateIpGoogleAccess,ipCidrRange'),
            image=(p.COMPUTE+c['imageProject']+'/global/images/'+c['imageName'],
                   'id,name,selfLink,status,architecture,deprecated,diskSizeGb'))
        result.update({name:query(url+'?'+urlencode(dict(fields=fields))) for name,(url,fields) in shapes.items()})
    return result


def permission_spec(role, name):
    need(role in credentials.ROLES, 'V5.2 permission role')
    if name == 'projectPermissions':
        required = set(RUNNER if role == 'runner' else CLEANUP)
        return required, set(FORBIDDEN) | (set(RUNNER)-required)
    need(name == 'bucketPermissions', 'V5.2 permission probe name')
    return {'storage.buckets.get'}, set(BUCKET_FORBIDDEN)


def permissions(value, role, name):
    need(type(value) is dict and set(value) <= {'kind','permissions'}, 'V5.2 permission response shape')
    if 'kind' in value:
        need(name == 'bucketPermissions' and value['kind'] == 'storage#testIamPermissionsResponse', 'V5.2 permission response kind')
    required, forbidden = permission_spec(role, name); rows = value.get('permissions', [])
    need(type(rows) is list and all(type(v) is str for v in rows) and len(set(rows)) == len(rows) and
         set(rows) <= required | forbidden, 'V5.2 permission response inventory')
    missing, excessive = sorted(required-set(rows)), sorted(forbidden & set(rows))
    return dict(status='BLOCKED' if missing or excessive else 'PASS', missing=missing, forbidden=excessive)


def control_query(cfg, name, generation=None):
    configuration(cfg); need(name in ('ledger','lease'), 'V5.2 control observation name')
    key = a.LEDGER if name == 'ledger' else a.LEASE
    endpoint = p.STORAGE+'storage/v1/b/'+cfg['provider']['bucket']+'/o/'+quote(key, safe='')
    if generation is None:
        return query(endpoint+'?'+urlencode(dict(fields='name,bucket,generation,size,contentType,temporaryHold,eventBasedHold')),
                     maximum=65536, absent=True)
    a.numeric(generation)
    return query(endpoint+'?'+urlencode(dict(alt='media', generation=generation, ifGenerationMatch=generation)), maximum=p.MAX_OBJECT)


def control_metadata(cfg, name, value):
    if value is None: return None
    key = a.LEDGER if name == 'ledger' else a.LEASE
    need(type(value) is dict and value['name'] == key and value['bucket'] == cfg['provider']['bucket'] and
         value['contentType'] == 'application/json' and not value.get('temporaryHold') and not value.get('eventBasedHold'),
         'V5.2 control object identity/type/hold')
    a.numeric(value['generation']); size = value['size']
    need(type(size) is str and re.fullmatch('0|[1-9][0-9]{0,7}', size) and 0 < int(size) <= p.MAX_OBJECT,
         'V5.2 control object size')
    return value['generation'], int(size)


def snapshot(value, name):
    if value is None: return None
    a.fields(value, 'generation value', 'control snapshot'); a.integer(value['generation'], 1)
    if name == 'ledger': a.inspect_ledger(value['value'], domain='native')
    else:
        a.validate_lease(value['value']); need(a.domain(value['value']) == 'native', 'V5.2 native lease required')
    return value


def resource(value, name, endpoint):
    need(type(value) is dict and value['name'] == name and p.link(value['selfLink']) == endpoint,
         'V5.2 provider resource identity')
    return a.numeric(value['id'])


def quota(rows, expected):
    need(type(rows) is list and len(rows) <= 1024 and all(type(v) is dict and type(v.get('metric')) is str for v in rows),
         'V5.2 quota inventory')
    by_name = {v['metric']:v for v in rows}; need(len(by_name) == len(rows), 'V5.2 duplicate quota metric')
    result = {}
    for metric, amount in expected.items():
        row = by_name[metric]; numbers = [row['limit'], row['usage']]
        need(all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in numbers), 'V5.2 quota numbers')
        available = row['limit']-row['usage']; need(available >= amount, 'V5.2 quota headroom: '+metric)
        result[metric] = dict(required=amount, available=available)
    return result


def overlaps(prefix, rows): return any(prefix.startswith(v) or v.startswith(prefix) for v in rows)


def storage(cfg, value):
    need(type(value) is dict and value['name'] == cfg['provider']['bucket'] and value['projectNumber'] == cfg['projectNumber'] and
         value['iamConfiguration']['uniformBucketLevelAccess']['enabled'] is True, 'V5.2 bucket project/access')
    need(not value.get('retentionPolicy') and not value.get('defaultEventBasedHold'), 'V5.2 bucket freezes mutable control')
    rules = value.get('lifecycle', {}).get('rule', [])
    need(type(rules) is list and len(rules) <= 1000, 'V5.2 lifecycle rules')
    for rule in rules:
        action = rule['action']['type']
        need(action in ('Delete','SetStorageClass','AbortIncompleteMultipartUpload'), 'V5.2 lifecycle action')
        if action != 'Delete': continue
        condition = rule['condition']; prefixes = condition.get('matchesPrefix', [''])
        need(type(prefixes) is list and 0 < len(prefixes) <= 1000 and
             all(type(v) is str and len(v) <= 1024 for v in prefixes), 'V5.2 lifecycle prefix shape')
        # Do not rely on age, version state or suffixes to protect the append-only
        # control history: a future row may match them. Keep its namespace intact.
        need(not overlaps(a.PREFIX, prefixes), 'V5.2 lifecycle can delete control history')
        if overlaps(EVIDENCE_PREFIX, prefixes): a.integer(condition.get('age'), MIN_RETENTION_DAYS)
    return dict(projectNumber=value['projectNumber'], minimumEvidenceDays=MIN_RETENTION_DAYS,
                lifecyclePropagationQualified=False, immutableRetentionQualified=False)


def facts(cfg, rows):
    c=cfg['provider']; base=p.COMPUTE+c['project']; paths=plan(cfg,'runner')
    names=dict(project=c['project'], region=c['region'], zone=c['zone'], machine=c['machineType'], diskType=c['diskType'],
               network=c['network'], subnetwork=c['subnetwork'], image=c['imageName'])
    identities={name:resource(rows[name], resource_name, paths[name]['url'].split('?',1)[0]) for name,resource_name in names.items()}
    need(rows['zone']['status'] == rows['region']['status'] == 'UP' and
         p.link(rows['zone']['region']) == base+'/regions/'+c['region'], 'V5.2 region/zone unavailable')
    subnet=rows['subnetwork']
    need(p.link(subnet['network']) == base+'/global/networks/'+c['network'] and
         p.link(subnet['region']) == base+'/regions/'+c['region'] and subnet['privateIpGoogleAccess'] is True,
         'V5.2 private subnet identity/access')
    address=ipaddress.ip_network(subnet['ipCidrRange'], strict=True)
    private_ranges = [ipaddress.ip_network(v) for v in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')]
    need(address.version == 4 and address.num_addresses >= 8 and any(address.subnet_of(v) for v in private_ranges),
         'V5.2 private subnet IPv4 range')
    image=images.observe(rows['image'], dict(name=c['imageName'],id=c['imageId'],status='READY',architecture='X86_64'))
    size=rows['image']['diskSizeGb']; a.numeric(size)
    need(int(size) <= cfg['layout']['bootDiskGiB'], 'V5.2 boot disk smaller than frozen image')
    cpus=a.integer(rows['machine']['guestCpus'],1,4096); memory=a.integer(rows['machine']['memoryMb'],1,1<<30)
    family=c['machineType'].split('-',1)[0]; metrics={'e2':'CPUS','n2':'N2_CPUS'}
    need(family in metrics and c['diskType']=='pd-ssd', 'V5.2 unreviewed machine/disk quota policy')
    disk_gib=3*sum(cfg['layout'].values())
    regional=quota(rows['region']['quotas'], {metrics[family]:3*cpus,'SSD_TOTAL_GB':disk_gib,'INSTANCES':3})
    global_=quota(rows['project']['quotas'], {'CPUS_ALL_REGIONS':3*cpus,'FIREWALLS':4})
    return dict(resources=identities, machine=dict(voters=3,cpusPerVoter=cpus,memoryMiBPerVoter=memory,diskGiB=disk_gib),
                regionalQuota=regional,globalQuota=global_,allocationGuaranteed=False,warnings=images.warnings(image))


def credential_receipt(token, selected, source, execution):
    a.fields(token,'schema execution context status attempts completedExchanges reasonCode runObservation paidAdmission '
             'fullRemoteQualification','preflight credential receipt')
    need(token['schema']=='gse-v52-credential-exchange-v1' and token['status']=='PASS' and token['reasonCode'] is None and
         token['paidAdmission'] is False and token['fullRemoteQualification'] is False, 'V5.2 preflight credential result')
    a.integer(token['attempts'],1);a.integer(token['completedExchanges'],1,token['attempts'])
    bound=token['context']
    a.fields(bound,'schema source runId runAttempt '+' '.join(selected),'preflight credential context')
    need(bound['schema']==credentials.SCHEMA and bound['source']==source and
         all(bound[k]==v for k,v in selected.items()), 'V5.2 preflight credential context')
    a.integer(bound['runId'],1);a.integer(bound['runAttempt'],1)
    observation=token['runObservation']
    a.fields(observation,'schema runId runAttempt source workflow observationSha256','preflight credential run')
    need(observation['schema']=='gse-v52-credential-run-observation-v1' and
         encoded({k:observation[k] for k in ('runId','runAttempt','source','workflow')})==
         encoded({k:bound[k] for k in ('runId','runAttempt','source','workflow')}), 'V5.2 preflight exact credential run')
    a.hex_value(observation['observationSha256'])
    need(token['execution']==execution.replace('provider-observations','credential-exchange'), 'V5.2 preflight credential domain')
    return deepcopy(bound)


def evaluate(cfg, source, role, value, *, now):
    expected=context(cfg, source, role); a.integer(now,1)
    a.fields(value,'schema context execution startedAt completedAt planSha256 observations controlBefore controlAfter credentials',
             'preflight observation')
    need(value['schema']=='gse-v52-provider-observations-v1' and encoded(value['context'])==encoded(expected) and
         value['execution'] in ('offline-v52-provider-observations','native-v52-provider-observations'), 'V5.2 preflight context')
    a.integer(value['startedAt'],max(1,now-FRESH_SECONDS)); a.integer(value['completedAt'],value['startedAt'],now)
    queries=plan(cfg,role)
    need(value['planSha256']==digest(encoded(queries)) and set(value['observations'])==set(queries), 'V5.2 preflight query inventory')
    bound=credential_receipt(value['credentials'],expected['credentialSelection'],source,value['execution'])
    for side in ('controlBefore','controlAfter'):
        a.fields(value[side],'ledger lease','preflight control pair')
        for name,entry in value[side].items():snapshot(entry,name)
    need(encoded(value['controlBefore'])==encoded(value['controlAfter']), 'V5.2 control generation changed during preflight')
    rows=value['observations']; checks={name:permissions(rows[name],role,name) for name in ('projectPermissions','bucketPermissions')}
    def check(name, action):
        try:checks[name]=dict(status='PASS',detail=action())
        except (ValueError,KeyError,TypeError):checks[name]=dict(status='BLOCKED',code='V52_PREFLIGHT_'+name.upper()+'_REJECTED')
    check('storage',lambda:storage(cfg,rows['bucket']))
    if role=='runner':check('provider',lambda:facts(cfg,rows))
    control=value['controlAfter']; ledger=control['ledger']
    view=a.inspect_ledger(ledger['value'] if ledger else a.empty_ledger(domain='native'),domain='native')
    pending=sum(row['status']=='PENDING' for row in view['attempts'].values())
    checks['control']=dict(status='BLOCKED' if role=='runner' and (control['lease'] is not None or pending) else 'PASS',
        leasePresent=control['lease'] is not None,pendingAttempts=pending,previousCostMicrousd=view['reservedCostMicrousd'],
        budgetMode='soft',softBudgetMicrousd=cfg['policy']['budgetMicrousd'],
        budgetExceeded=view['reservedCostMicrousd']>cfg['policy']['budgetMicrousd'])
    return dict(schema='gse-v52-provider-preflight-v1',context=expected,credentialContext=bound,
        status='PREFLIGHT_OBSERVED_NOT_ADMITTED' if all(v['status']=='PASS' for v in checks.values()) else 'BLOCKED',
        checkedAt=now,observationsSha256=digest(encoded(value)),checks=checks,limitations=list(LIMITATIONS),pending=list(PENDING),**FLAGS)
