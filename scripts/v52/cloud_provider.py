"""V5.2 provider mapping for concrete offline or factory-owned native APIs."""
from copy import deepcopy
import math
import re
import time
import urllib.parse as url
import uuid
from scripts.v51.cloud_http import Api, ApiError
from . import cloud_authority as a
from .evidence import need, encoded, digest, strict

COMPUTE = 'https://compute.googleapis.com/compute/v1/projects/'
STORAGE = 'https://storage.googleapis.com/'
MAX_OBJECT = 8 << 20
CONFIG_FIELDS = ('schema project bucket network subnetwork region zone imageProject imageName imageId '
                 'machineType diskType port')
READ_FAILURES = {
    'V52_CONTROL_READ_GENERATION': 'V5.2 wire unobserved media generation',
    'V52_CONTROL_READ_TRUNCATED': 'V5.2 control object bytes truncated',
    'V52_CONTROL_LEASE_ABSENT': 'V5.2 guest lease absent',
    'V52_CONTROL_LEASE_INACTIVE': 'V5.2 guest lease inactive/changed',
}


class ControlReadError(ValueError):
    """Closed diagnostic cause; never retain provider text or control contents."""
    def __init__(self, code):
        need(code in READ_FAILURES, 'V5.2 unknown control read failure')
        self.code = code
        super().__init__(READ_FAILURES[code])


def read_need(value, code):
    if not value: raise ControlReadError(code)


def config(value):
    a.fields(value, CONFIG_FIELDS, 'provider configuration')
    need(value['schema'] == 'gse-v52-provider-config-v1', 'V5.2 provider configuration schema')
    for key in ('project', 'network', 'subnetwork', 'region', 'zone', 'imageProject', 'imageName', 'machineType', 'diskType'):
        need(type(value[key]) is str and re.fullmatch('[a-z][a-z0-9-]{0,62}', value[key]), 'V5.2 provider name')
    need(type(value['bucket']) is str and re.fullmatch('[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', value['bucket']),
         'V5.2 provider bucket')
    need(value['zone'].rsplit('-', 1)[0] == value['region'], 'V5.2 provider region/zone')
    a.numeric(value['imageId']); a.integer(value['port'], 1024, 65535)
    return digest(encoded(value))


def link(value):
    need(type(value) is str, 'V5.2 provider link')
    if value.startswith('https://www.googleapis.com/compute/v1/'):
        return 'https://compute.googleapis.com/compute/v1/'+value.split('/compute/v1/', 1)[1]
    return value


def query(base, **values): return base+'?'+url.urlencode(values)


class OfflineApi(Api):
    def __init__(self, server):
        from .cloud_provider_offline import Server
        need(type(server) is Server, 'V5.2 live HTTP entry not admitted')
        super().__init__(transport=server, tokens=lambda timeout: 'offline-not-a-credential', clock=server.clock)

    def authorize(self, method, endpoint, body):
        from .cloud_provider_offline import Server
        need(type(self.transport) is Server, 'V5.2 live HTTP entry not admitted')


def api_guard(api):
    from .cloud_wire_policy import ScopedOfflineApi
    from .cloud_native_cleanup import NativeCleanupApi
    from .cloud_native_runner import NativeRunnerApi
    if type(api) in (ScopedOfflineApi, NativeCleanupApi, NativeRunnerApi):
        api.validate_adapter(); return
    need(type(api) is OfflineApi, 'V5.2 live HTTP entry not admitted')
    api.authorize('GET', '', None)


def api_domain(api):
    api_guard(api)
    from .cloud_native_cleanup import NativeCleanupApi
    from .cloud_native_runner import NativeRunnerApi
    return 'native' if type(api) in (NativeCleanupApi, NativeRunnerApi) else 'offline'


class Store:
    @property
    def execution(self): return a.DOMAINS[api_domain(self.api)]

    def __init__(self, configuration, api):
        config(configuration); api_guard(api)
        self.config, self.api = deepcopy(configuration), api
        self.base = STORAGE+'storage/v1/b/'+self.config['bucket']+'/o/'
        if hasattr(api, 'bind_store'): api.bind_store(self)

    def endpoint(self, key):
        need(type(key) is str and key.startswith(a.PREFIX) and len(key) <= 1024 and
             re.fullmatch('[a-zA-Z0-9./_-]+', key) and all(p not in ('', '.', '..') for p in key.split('/')),
             'V5.2 object namespace')
        return self.base+url.quote(key, safe='')

    def get(self, key):
        api_guard(self.api); endpoint = self.endpoint(key); deadline = self.api.clock()+30
        if type(self.api) is OfflineApi:
            return self._get(key, endpoint, deadline)
        # Metadata and its pinned body share the scoped API's existing RLock.
        # A heartbeat must not replace Policy.metadata between these two calls.
        # Reuse that lock: policy validation performs nested reads while holding
        # it already. This path never acquires the owner's lifecycle lock.
        lock = self.api.lock
        if not lock.acquire(timeout=max(0, deadline-self.api.clock())):
            raise TimeoutError('V5.2 control read lock deadline')
        try:
            if self.api.clock() >= deadline:
                raise TimeoutError('V5.2 control read lock deadline')
            return self._get(key, endpoint, deadline)
        finally:
            lock.release()

    def _get(self, key, endpoint, deadline):
        try: metadata = self.api.call('GET', endpoint, deadline=deadline)
        except ApiError as error:
            if error.status == 404: return None
            raise
        need(type(metadata) is dict and metadata.get('name') == key and metadata.get('bucket') == self.config['bucket'],
             'V5.2 object metadata identity')
        generation = a.numeric(metadata.get('generation'))
        size = metadata.get('size')
        need(type(size) is str and re.fullmatch('0|[1-9][0-9]{0,7}', size) and int(size) <= MAX_OBJECT,
             'V5.2 object size')
        need(metadata.get('contentType') == 'application/json', 'V5.2 control object content type')
        raw = self.api.call('GET', query(endpoint, alt='media', generation=generation, ifGenerationMatch=generation),
                            deadline=deadline, raw=True, maximum=MAX_OBJECT)
        read_need(len(raw) == int(size), 'V52_CONTROL_READ_TRUNCATED')
        value = strict(raw); need(type(value) is dict, 'V5.2 control object shape')
        return int(generation), value

    def put(self, key, value, expected):
        api_guard(self.api); self.endpoint(key); a.integer(expected)
        need(type(value) is dict and len(encoded(value)) <= MAX_OBJECT, 'V5.2 object upload bound/shape')
        endpoint = query(STORAGE+'upload/storage/v1/b/'+self.config['bucket']+'/o',
                         uploadType='media', name=key, ifGenerationMatch=expected)
        result = self.api.call('POST', endpoint, value, deadline=self.api.clock()+30)
        need(type(result) is dict and result.get('name') == key and result.get('bucket') == self.config['bucket'],
             'V5.2 uploaded object identity')
        generation = int(a.numeric(result.get('generation')))
        need(generation > expected, 'V5.2 object generation did not advance')
        return generation  # The shared CAS controller performs exact read-back.

    def delete(self, key, expected):
        api_guard(self.api); a.integer(expected, 1)
        self.api.call('DELETE', query(self.endpoint(key), ifGenerationMatch=expected), deadline=self.api.clock()+30)
        # The controller observes absence without deleting a newer owner.


def context(configuration, req, *, domain='offline'):
    sha = a.validate_request(req, domain=domain)
    need(config(configuration) == req['configurationSha256'], 'V5.2 configuration digest changed')
    return dict(schema='gse-v52-provider-context-v1', requestSha256=sha,
                request=deepcopy(req), configuration=deepcopy(configuration))


def context_key(req):
    return a.PREFIX+'attempts/'+a.validate_request(req, domain=a.domain(req))+'/provider-context.json'


def reconstruct(store, req):
    """Recover from retained public context; never use ambient/current configuration."""
    need(type(store) is Store, 'V5.2 context store type'); api_guard(store.api)
    found = store.get(context_key(req)); need(found is not None, 'V5.2 missing provider context')
    value = found[1]; a.fields(value, 'schema requestSha256 request configuration', 'provider context')
    need(value == context(value['configuration'], req, domain=api_domain(store.api)) and value['configuration'] == store.config,
         'V5.2 provider context changed')
    return Provider(store, req)


class Plan:
    """Pure request-bound wire shapes. Native intent is data, not admission."""
    def __init__(self, configuration, req):
        a.validate_request(req, domain=a.domain(req))
        need(config(configuration)==req['configurationSha256'], 'V5.2 configuration digest changed')
        self.config,self.request=deepcopy(configuration),deepcopy(req)
        self.specs={s['name']:s for s in a.resources(req)}
        self.base=COMPUTE+self.config['project']

    def spec(self, spec):
        need(type(spec) is dict and self.specs.get(spec.get('name'))==spec, 'V5.2 foreign resource intent')

    def scope(self, spec):
        self.spec(spec)
        return self.base+('/global' if spec['kind'] == 'firewall' else '/zones/'+self.config['zone'])

    def endpoint(self, spec, identity=None):
        if identity is not None: a.numeric(identity)
        return self.scope(spec)+'/'+spec['kind']+'s/'+(identity or spec['name'])

    def operation_id(self, spec, action='insert', identity=None):
        self.spec(spec); need(action in ('insert', 'delete'), 'V5.2 operation action')
        if action == 'delete': a.numeric(identity)
        raw = spec['operationId'] if action == 'insert' else digest(encoded([spec, action, identity]))
        return str(uuid.UUID(hex=raw[:32]))

    def body(self, spec):
        self.spec(spec); c = self.config
        body = dict(name=spec['name'], description=encoded(dict(suite='v5.2', requestSha256=spec['requestSha256'],
                                                              specSha256=digest(encoded(spec)))).decode())
        if spec['kind'] == 'firewall':
            deny = spec['purpose'].startswith('deny-'); ssh = spec['purpose'] in ('iap', 'deny-ssh')
            body.update(network=self.base+'/global/networks/'+c['network'], direction='INGRESS', disabled=False,
                        priority=950 if deny else 900, targetTags=[spec['owner']])
            body['denied' if deny else 'allowed'] = [dict(IPProtocol='tcp', ports=['22' if ssh else str(c['port'])])]
            body.update(sourceTags=[spec['owner']]) if spec['purpose'] == 'peer' else body.update(
                sourceRanges=['35.235.240.0/20' if spec['purpose'] == 'iap' else '0.0.0.0/0'])
        else:
            body['labels'] = dict(owner=spec['owner'], suite='v52', source=self.request['selection']['binding']['source'])
            if spec['kind'] == 'disk':
                body.update(sizeGb=str(spec['sizeGiB']), type=self.scope(spec)+'/diskTypes/'+c['diskType'])
                if spec['purpose'] == 'boot': body['sourceImage'] = COMPUTE+c['imageProject']+'/global/images/'+c['imageName']
            else:
                body.update(machineType=self.scope(spec)+'/machineTypes/'+c['machineType'], tags=dict(items=[spec['owner']]),
                    networkInterfaces=[dict(network=self.base+'/global/networks/'+c['network'],
                        subnetwork=self.base+'/regions/'+c['region']+'/subnetworks/'+c['subnetwork'], accessConfigs=[])],
                    serviceAccounts=[], disks=[], metadata=dict(items=[dict(key=k,value=v) for k,v in (
                        ('block-project-ssh-keys','TRUE'), ('enable-oslogin','FALSE'), ('enable-guest-attributes','TRUE'))]),
                    scheduling=dict(provisioningModel='STANDARD', automaticRestart=False))
                if 'guestAccess' in self.request:
                    from .cloud_access import metadata
                    body['metadata']['items'] = metadata(self.request['guestAccess'])
                for purpose in ('boot','data'):
                    disk = next(s for s in self.specs.values() if s['kind']=='disk' and s['node']==spec['node'] and s['purpose']==purpose)
                    body['disks'].append(dict(source=self.endpoint(disk), boot=purpose=='boot', autoDelete=False,
                        mode='READ_WRITE', type='PERSISTENT', deviceName='gse-'+purpose+'-'+str(spec['node'])))
        return body

    def inspect(self, spec, value):
        expected = self.body(spec)
        need(type(value) is dict and value.get('name') == spec['name'] and value.get('description') == expected['description'],
             'V5.2 resource ownership')
        identity = a.numeric(value.get('id'))
        if spec['kind'] == 'firewall':
            for key in ('network','direction','disabled','priority','targetTags','allowed','denied','sourceTags','sourceRanges'):
                actual = value.get(key, [] if key not in expected else None)
                if key == 'network': actual = link(actual)
                need(actual == expected.get(key, []), 'V5.2 firewall policy changed')
            need(not any(value.get(k) for k in ('sourceServiceAccounts','targetServiceAccounts','destinationRanges')), 'V5.2 firewall scope')
        else:
            need(value.get('labels') == expected['labels'], 'V5.2 resource labels')
            if spec['kind'] == 'disk':
                need(value.get('sizeGb') == expected['sizeGb'] and link(value.get('type')) == expected['type'], 'V5.2 disk layout')
                need(value.get('sourceImageId') == (self.config['imageId'] if spec['purpose']=='boot' else None), 'V5.2 disk image ID')
                need(not any(value.get(k) for k in ('sourceSnapshot','sourceDisk','sourceStorageObject','resourcePolicies')), 'V5.2 disk source/policy')
            else:
                need(link(value.get('machineType')) == expected['machineType'] and not value.get('serviceAccounts') and
                     value.get('tags',{}).get('items') == expected['tags']['items'], 'V5.2 instance identity')
                nics = value.get('networkInterfaces'); need(type(nics) is list and len(nics)==1, 'V5.2 private interface')
                nic = nics[0]; want = expected['networkInterfaces'][0]
                need(link(nic.get('network')) == want['network'] and link(nic.get('subnetwork')) == want['subnetwork'] and
                     not nic.get('accessConfigs') and not nic.get('ipv6AccessConfigs') and not nic.get('externalIpv6'), 'V5.2 external interface')
                disks = value.get('disks'); need(type(disks) is list and len(disks)==2, 'V5.2 disk attachments')
                for got, want in zip(disks,expected['disks']):
                    need(all((link(got.get(k)) if k=='source' else got.get(k)) == v for k,v in want.items()), 'V5.2 disk attachment changed')
                items = value.get('metadata',{}).get('items')
                need(type(items) is list and sorted(items,key=lambda x:x['key']) == sorted(expected['metadata']['items'],key=lambda x:x['key']),
                     'V5.2 instance metadata')
                scheduling = value.get('scheduling',{})
                need(all(scheduling.get(k)==v for k,v in expected['scheduling'].items()) and
                     not any(scheduling.get(k) for k in ('maxRunDuration','terminationTime','instanceTerminationAction')),
                     'V5.2 instance hard lifetime changed')
        return dict(spec=deepcopy(spec), id=identity)

    def decode(self, spec, op, action='insert', identity=None):
        need(type(op) is dict and op.get('clientOperationId') == self.operation_id(spec,action,identity) and
             op.get('operationType') == action, 'V5.2 operation request binding')
        targets = {self.endpoint(spec)}
        if identity is not None: targets.add(self.endpoint(spec,identity))
        need(link(op.get('targetLink')) in targets and type(op.get('name')) is str and
             re.fullmatch('[A-Za-z0-9_-]{1,200}',op['name']), 'V5.2 operation target binding')
        status = op.get('status'); need(status in ('PENDING','RUNNING','DONE'), 'V5.2 operation status')
        target = op.get('targetId')
        if target is not None: a.numeric(target)
        need(identity is None or target is None or target == identity, 'V5.2 delete target changed')
        if status != 'DONE': return dict(spec=deepcopy(spec),state='PENDING',id=None)
        if op.get('error'): need(action=='insert' and target is None, 'V5.2 unresolved operation failure')
        else: a.numeric(target)
        return dict(spec=deepcopy(spec),state='DONE',id=target)

class Provider(Plan):
    @property
    def execution(self): return self.store.execution

    def __init__(self, store, req, *, wall=time.time, sleep=time.sleep):
        need(type(store) is Store, 'V5.2 provider store type'); api_guard(store.api)
        a.validate_request(req, domain=api_domain(store.api))
        self.context = context(store.config, req, domain=api_domain(store.api))
        super().__init__(store.config, req)
        self.store, self.api = store, store.api
        self.wall, self.sleep = wall, sleep; self.cleaning = False
        if hasattr(self.api, 'bind_provider'): self.api.bind_provider(self)

    def spec(self, spec):
        super().spec(spec); api_guard(self.api)
        need(self.config == self.store.config == self.context['configuration'] and self.request == self.context['request'],
             'V5.2 provider configuration changed')

    def describe(self, spec, *, identity=None, deadline=None):
        try: value = self.api.call('GET', self.endpoint(spec,identity), deadline=deadline or self.api.clock()+30)
        except ApiError as error:
            if error.status == 404: return None
            raise
        result = self.inspect(spec,value)
        need(identity is None or result['id'] == identity, 'V5.2 exact resource ID changed')
        return result

    def prepare_context(self, req):
        from .cloud_control import retain
        need(req == self.request, 'V5.2 provider request changed')
        retain(self.store, context_key(req), self.context)

    def begin_cleanup(self): self.cleaning = True

    def receipt_key(self, spec):
        return a.PREFIX+'attempts/'+spec['requestSha256']+'/operations/'+spec['operationId']+'.json'

    def remember(self, spec, op):
        from .cloud_control import retain
        self.decode(spec,op)
        value = {k:op[k] for k in ('name','clientOperationId','operationType','targetLink','status','targetId') if k in op}
        if op.get('error'): value['error'] = True  # Never retain provider messages/URLs/credentials.
        retain(self.store,self.receipt_key(spec),dict(schema='gse-v52-provider-operation-v1',spec=spec,operation=value))

    def not_submitted(self, spec):
        # A CLEANING lease fences the last active-owner check before POST. An
        # absent marker observed after that fence proves this intent was never
        # submitted. A later marker writer still cannot pass its owner check.
        from .cloud_control import retain
        key = self.receipt_key(spec).replace('.json','-unsubmitted.json')
        value = dict(schema='gse-v52-provider-not-submitted-v1',spec=spec)
        current = self.store.get(a.LEASE)
        if current is None: return False
        lease = a.validate_lease(current[1])
        if lease['request'] != self.request or lease['phase'] != 'CLEANING': return False
        saved = self.store.get(key)
        if saved is not None:
            need(saved[1] == value,'V5.2 unsubmitted proof changed'); return True
        submission = self.store.get(self.receipt_key(spec).replace('.json','-submitted.json'))
        if submission is not None and not (hasattr(self.api,'can_prove_unsubmitted') and
                                          self.api.can_prove_unsubmitted(spec,submission[1])): return False
        retained = self.store.get(context_key(self.request))
        need(retained is not None and retained[1] == self.context,'V5.2 unsubmitted context missing/changed')
        retain(self.store,key,value)
        return True

    def operation(self, spec):
        self.spec(spec); saved = self.store.get(self.receipt_key(spec))
        if saved is not None:
            value = saved[1]; a.fields(value,'schema spec operation','operation receipt')
            need(value['schema']=='gse-v52-provider-operation-v1' and value['spec']==spec, 'V5.2 operation receipt changed')
            result = self.decode(spec,value['operation']); need(result['state']=='DONE','V5.2 incomplete retained operation')
            return result
        deadline = self.api.clock()+30; found = []; pages = set(); token = None
        for _ in range(32):
            parameters = dict(filter='clientOperationId = "'+self.operation_id(spec)+'"',maxResults=100)
            if token is not None: parameters['pageToken'] = token
            page = self.api.call('GET',query(self.scope(spec)+'/operations',**parameters),deadline=deadline)
            need(type(page) is dict and type(page.get('items',[])) is list, 'V5.2 operation page')
            found.extend(page.get('items',[])); need(len(found)<=1,'V5.2 ambiguous original operation')
            token = page.get('nextPageToken')
            if token is None or token == '': break
            need(type(token) is str and 0<len(token)<=2048 and token not in pages, 'V5.2 operation page token')
            pages.add(token)
        else: raise ValueError('V5.2 operation page bound')
        if not found:
            return dict(spec=deepcopy(spec),state='DONE' if self.not_submitted(spec) else 'UNKNOWN',id=None)
        result = self.decode(spec,found[0])
        if result['state']=='DONE': self.remember(spec,found[0])
        return result

    def wait(self, spec, op, deadline, action='insert', identity=None):
        original_name = op.get('name') if type(op) is dict else None
        while True:
            result = self.decode(spec,op,action,identity)
            need(op['name']==original_name, 'V5.2 original operation name changed')
            if result['state']=='DONE':
                if action=='insert': self.remember(spec,op)
                return result
            need(self.api.clock()<deadline, 'V5.2 original operation deadline')
            self.sleep(min(.25,deadline-self.api.clock()))
            op = self.api.call('GET',self.scope(spec)+'/operations/'+original_name,deadline=deadline)

    def owned_insert(self, spec):
        current = self.store.get(a.LEASE); ledger = self.store.get(a.LEDGER)
        need(current is not None and ledger is not None,'V5.2 missing original ownership')
        lease = a.validate_lease(current[1]); row = next(r for r in lease['resources'] if r['spec']==spec)
        charged = a.inspect_ledger(ledger[1],domain=api_domain(self.api))['attempts'].get(spec['requestSha256'])
        need(lease['request']==self.request and lease['phase']=='ACTIVE' and lease['renewedAt']<=self.wall()<lease['expiresAt'] and
             row['attempted'] and row['id'] is None and charged is not None and charged['status']=='PENDING', 'V5.2 insert not owned/charged')

    def create(self, spec, deadline):
        need(not self.cleaning, 'V5.2 cleanup fenced insert'); self.spec(spec)
        remaining = deadline-self.wall()
        need(type(remaining) in (int,float) and math.isfinite(remaining) and 0<remaining<=300, 'V5.2 create exchange deadline')
        until = self.api.clock()+remaining; body = self.body(spec)
        self.prepare_context(self.request)
        self.owned_insert(spec)
        if 'sourceImage' in body:
            image = self.api.call('GET',body['sourceImage'],deadline=until)
            need(image.get('id')==self.config['imageId'] and image.get('name')==self.config['imageName'] and image.get('status')=='READY',
                 'V5.2 image identity/status')
            need(image.get('deprecated',{}).get('state') in (None,'DEPRECATED'), 'V5.2 unusable pinned image')
        from .cloud_control import put
        self.owned_insert(spec)
        submission = self.receipt_key(spec).replace('.json','-submitted.json')
        need(self.store.get(submission) is None,'V5.2 original insert already submitted')
        marker = (self.api.submission_value(spec) if hasattr(self.api,'submission_value') else
                  dict(schema='gse-v52-provider-submission-v1',spec=spec))
        put(self.store,submission,marker,0)
        self.owned_insert(spec)
        endpoint = query(self.endpoint(spec).rsplit('/',1)[0],requestId=self.operation_id(spec))
        # Each mutation is sent once. An uncertain response leaves the retained
        # intent for the shared reconciler; it never creates another resource.
        op = self.api.call('POST',endpoint,body,deadline=until)
        result = self.wait(spec,op,until); need(result['id'] is not None,'V5.2 original insertion rejected')
        observed = self.describe(spec,identity=result['id'],deadline=until)
        need(observed is not None,'V5.2 inserted resource absent'); return observed

    def delete(self, spec, expected_id):
        need(self.cleaning,'V5.2 deletion requires cleanup'); a.numeric(expected_id)
        self.spec(spec); current = self.store.get(a.LEASE)
        need(current is not None,'V5.2 cleanup ownership missing')
        lease = a.validate_lease(current[1])
        need(lease['phase']=='CLEANING' and lease['request']==self.request and
             any(r['spec']==spec and r['attempted'] and r['id']==expected_id for r in lease['resources']),
             'V5.2 cleanup ownership changed')
        deadline = self.api.clock()+300
        if self.describe(spec,identity=expected_id,deadline=deadline) is None: return
        endpoint = query(self.endpoint(spec,expected_id),requestId=self.operation_id(spec,'delete',expected_id))
        try: op = self.api.call('DELETE',endpoint,deadline=deadline)
        except ApiError as error:
            if error.status != 404: raise
        else: self.wait(spec,op,deadline,'delete',expected_id)
        need(self.describe(spec,identity=expected_id,deadline=deadline) is None,'V5.2 deleted resource still present')


def qualified(store, provider):
    if type(store) is not Store or type(provider) is not Provider or provider.store is not store: return False
    api_guard(store.api)
    return (provider.api is store.api and provider.config == store.config and
            a.domain(provider.request) == api_domain(store.api))
