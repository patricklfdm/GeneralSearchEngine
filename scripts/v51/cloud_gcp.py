"""V5.1 GCS/Compute request adapters; fake HTTP qualification, live reads only.

No paid runner is exposed here. Real adapters have an unqualified execution tag,
so the accepted control runner rejects them independently of HTTP mutation guards.
"""
from copy import deepcopy
import re
import time
import urllib.parse
import uuid
from . import cloud_authority as a, performance_model as m
from .cloud_http import ApiError

CONFIG_FIELDS = {'schema', 'project', 'bucket', 'network', 'subnetwork', 'region', 'zone',
                 'imageProject', 'imageName', 'imageId', 'machineType', 'diskType', 'port'}


def config(value):
    m.need(type(value) is dict and set(value) == CONFIG_FIELDS and value['schema'] == 'gse-v51-provider-config-v1', 'provider configuration fields')
    for key in ('project', 'network', 'subnetwork', 'imageProject', 'imageName'):
        m.need(isinstance(value[key], str) and re.fullmatch('[a-z][a-z0-9-]{0,62}', value[key]), 'provider name '+key)
    m.need(isinstance(value['bucket'], str) and re.fullmatch('[a-z0-9][a-z0-9.-]{1,220}[a-z0-9]', value['bucket']), 'provider bucket')
    env = a.workload.load()['environment']
    m.need(all(value[k] == env[k] for k in ('zone', 'imageProject', 'imageName', 'imageId', 'machineType', 'diskType')) and
           value['region'] == value['zone'].rsplit('-', 1)[0], 'unreviewed provider selection')
    a.integer(value['port'], 1024, 65535)
    return m.sha(m.canonical(value))


def numeric(value):
    m.need(isinstance(value, str) and re.fullmatch('[1-9][0-9]{0,19}', value), 'provider numeric identity')
    return value


def link(value):
    m.need(isinstance(value, str), 'provider resource link')
    return value.replace('https://www.googleapis.com/compute/v1/', 'https://compute.googleapis.com/compute/v1/')


class Store:
    def __init__(self, configuration, api):
        config(configuration)
        self.bucket, self.api = configuration['bucket'], api
        self.execution = a.EXECUTION if api.offline else 'unqualified-v51-gcp-provider'
        self.base = 'https://storage.googleapis.com/storage/v1/b/'+self.bucket+'/o/'

    def url(self, key):
        m.need(isinstance(key, str) and key.startswith(a.PREFIX) and len(key) <= 1024 and
               all(p and p not in ('.', '..') for p in key.split('/')) and '\\' not in key, 'V5.1 object namespace')
        return self.base+urllib.parse.quote(key, safe='')

    def get(self, key):
        deadline = self.api.clock()+30
        try: metadata = self.api.call('GET', self.url(key), deadline=deadline)
        except ApiError as error:
            if error.status == 404: return None
            raise
        generation = numeric(metadata['generation'])
        m.need(metadata['name'] == key and metadata['bucket'] == self.bucket, 'object metadata identity')
        size = int(metadata['size']); m.need(0 <= size <= 8 << 20, 'object byte bound')
        query = urllib.parse.urlencode(dict(alt='media', generation=generation, ifGenerationMatch=generation))
        raw = self.api.call('GET', self.url(key)+'?'+query, raw=True, maximum=8 << 20, deadline=deadline)
        m.need(len(raw) == size, 'object read-back size')
        content_type = metadata['contentType']
        m.need(content_type in ('application/json', 'application/octet-stream'), 'object content type')
        return int(generation), raw if content_type == 'application/octet-stream' else m.strict_json(raw)

    def put(self, key, value, expected):
        self.url(key); a.integer(expected)
        data = value if isinstance(value, bytes) else m.canonical(value)
        m.need(len(data) <= 8 << 20, 'object upload bound')
        url = 'https://storage.googleapis.com/upload/storage/v1/b/'+self.bucket+'/o?'+urllib.parse.urlencode(
            dict(uploadType='media', name=key, ifGenerationMatch=expected))
        # Pass JSON as a JSON object so the API sets the correct content type.
        result = self.api.call('POST', url, value, deadline=self.api.clock()+30)
        m.need(result['name'] == key and result['bucket'] == self.bucket, 'upload identity')
        generation = int(numeric(result['generation']))
        m.need(self.get(key) == (generation, value), 'upload read-back differs')
        return generation

    def delete(self, key, expected):
        a.integer(expected, 1)
        self.api.call('DELETE', self.url(key)+'?'+urllib.parse.urlencode(dict(ifGenerationMatch=expected)),
                      deadline=self.api.clock()+30)
        m.need(self.get(key) is None, 'object deletion absence')


class Compute:
    def __init__(self, configuration, req, api, *, sleep=time.sleep):
        m.need(config(configuration) == req['configurationSha256'], 'provider request configuration digest')
        a.validate_request(req)
        self.config, self.req, self.api, self.sleep = deepcopy(configuration), deepcopy(req), api, sleep
        self.execution = a.EXECUTION if api.offline else 'unqualified-v51-gcp-provider'
        self.base = 'https://compute.googleapis.com/compute/v1/projects/'+configuration['project']
        self.inventory = a.resources(req)

    def scope(self, spec):
        m.need(spec in self.inventory, 'provider closed resource inventory')
        return self.base+('/global' if spec['kind'] == 'firewall' else '/zones/'+self.config['zone'])

    def url(self, spec, identity=None):
        kind = {'firewall': 'firewalls', 'disk': 'disks', 'instance': 'instances'}[spec['kind']]
        return self.scope(spec)+'/'+kind+'/'+(numeric(identity) if identity is not None else spec['name'])

    def operation_id(self, spec, action='insert', identity=None):
        self.scope(spec)
        digest = spec['operationId'] if action == 'insert' else m.sha(m.canonical([spec, action, identity]))
        return str(uuid.UUID(hex=digest[:32]))

    def description(self, spec):
        return m.canonical(dict(suite=a.SUITE, requestSha256=a.validate_request(self.req), specSha256=m.sha(m.canonical(spec)))).decode()

    def body(self, spec):
        p = self.config; self.scope(spec)
        value = dict(name=spec['name'], description=self.description(spec))
        if spec['kind'] == 'firewall':
            purpose = spec['purpose']; allowed = purpose in ('peer', 'iap')
            value.update(network=self.base+'/global/networks/'+p['network'], direction='INGRESS', disabled=False,
                         targetTags=[spec['owner']], priority=900 if allowed else 950)
            value['allowed' if allowed else 'denied'] = [dict(IPProtocol='tcp', ports=[str(p['port']) if purpose in ('peer', 'deny-replication') else '22'])]
            if purpose == 'peer': value['sourceTags'] = [spec['owner']]
            else: value['sourceRanges'] = ['35.235.240.0/20' if purpose == 'iap' else '0.0.0.0/0']
        else:
            value['labels'] = {'gse-owner': spec['owner'], 'gse-suite': 'v51-automatic', 'gse-source': self.req['source']}
            if spec['kind'] == 'disk':
                value.update(sizeGb=str(spec['sizeGiB']), type=self.scope(spec)+'/diskTypes/'+p['diskType'])
                if spec['purpose'] == 'boot':
                    value['sourceImage'] = 'https://compute.googleapis.com/compute/v1/projects/'+p['imageProject']+'/global/images/'+p['imageName']
            else:
                disks = [r for r in self.inventory if r['kind'] == 'disk' and r['node'] == spec['node']]
                value.update(machineType=self.scope(spec)+'/machineTypes/'+p['machineType'], tags=dict(items=[spec['owner']]),
                    networkInterfaces=[dict(subnetwork=self.base+'/regions/'+p['region']+'/subnetworks/'+p['subnetwork'], accessConfigs=[])],
                    serviceAccounts=[], disks=[dict(source=self.url(r), boot=r['purpose'] == 'boot', autoDelete=False,
                        mode='READ_WRITE', type='PERSISTENT', deviceName='gse-'+r['purpose']+'-'+str(r['node'])) for r in disks],
                    scheduling=dict(provisioningModel='STANDARD', automaticRestart=False,
                        maxRunDuration=dict(seconds='5400'), instanceTerminationAction='DELETE'),
                    metadata=dict(items=[dict(key='block-project-ssh-keys', value='TRUE'), dict(key='enable-oslogin', value='FALSE')]))
        return value

    def inspect(self, spec, value):
        numeric(value['id'])
        m.need(value['name'] == spec['name'] and value['description'] == self.description(spec), 'provider ownership/intent')
        expected = self.body(spec)
        if spec['kind'] == 'firewall':
            for key in ('direction', 'disabled', 'targetTags', 'priority', 'allowed', 'denied', 'sourceTags', 'sourceRanges'):
                m.need(value.get(key, []) == expected.get(key, []), 'firewall shape '+key)
            m.need(link(value['network']) == expected['network'], 'firewall network')
        elif spec['kind'] == 'disk':
            m.need(int(value['sizeGb']) == spec['sizeGiB'] and link(value['type']) == self.body(spec)['type'], 'disk shape')
            if spec['purpose'] == 'boot': m.need(value['sourceImageId'] == self.config['imageId'], 'boot image drift')
        elif spec['kind'] == 'instance':
            m.need(link(value['machineType']) == self.body(spec)['machineType'] and not value.get('serviceAccounts'), 'instance shape')
            m.need(len(value['networkInterfaces']) == 1 and not value['networkInterfaces'][0].get('accessConfigs') and
                   link(value['networkInterfaces'][0]['subnetwork']) == self.body(spec)['networkInterfaces'][0]['subnetwork'], 'private interface')
            wanted = {d['source']: d for d in self.body(spec)['disks']}
            m.need(len(value['disks']) == 2 and {link(d['source']) for d in value['disks']} == set(wanted) and
                   all(all(d[k] == wanted[link(d['source'])][k] for k in ('autoDelete', 'boot', 'mode', 'type', 'deviceName'))
                       for d in value['disks']), 'attached disk scope/automatic deletion')
            m.need(value['tags']['items'] == [spec['owner']] and
                   all(value['scheduling'].get(k) == v for k, v in expected['scheduling'].items()), 'instance tags/lifetime')
        if spec['kind'] != 'firewall':
            m.need(all(value['labels'].get(k) == v for k, v in expected['labels'].items()), 'resource labels')
        return dict(spec=deepcopy(spec), id=value['id'])

    def describe(self, spec, *, identity=None, deadline=None):
        try: value = self.api.call('GET', self.url(spec, identity), deadline=deadline or self.api.clock()+30)
        except ApiError as error:
            if error.status == 404: return None
            raise
        result = self.inspect(spec, value)
        if identity is not None: m.need(result['id'] == identity, 'numeric resource lookup changed')
        return result

    def decode_operation(self, spec, op, action='insert', identity=None):
        m.need(op['clientOperationId'] == self.operation_id(spec, action, identity) and op['operationType'] == action and
               link(op['targetLink']) == self.url(spec), 'operation request/target binding')
        m.need(isinstance(op['name'], str) and re.fullmatch('[a-zA-Z0-9_-]{1,200}', op['name']), 'operation name')
        m.need(op['status'] in ('PENDING', 'RUNNING', 'DONE'), 'operation status')
        if op['status'] != 'DONE': return dict(spec=deepcopy(spec), state='PENDING', id=None)
        target = op.get('targetId')
        if op.get('error'):
            m.need(action == 'insert' and target is None, 'operation failure with unresolved target')
        else:
            numeric(target)
            if identity is not None: m.need(target == identity, 'delete operation target ID changed')
        return dict(spec=deepcopy(spec), state='DONE', id=target)

    def operation(self, spec):
        query = urllib.parse.urlencode(dict(filter='clientOperationId = "'+self.operation_id(spec)+'"'))
        value = self.api.call('GET', self.scope(spec)+'/operations?'+query, deadline=self.api.clock()+30)
        m.need(not value.get('nextPageToken') and len(value.get('items', [])) <= 1, 'ambiguous operation lookup')
        return self.decode_operation(spec, value['items'][0]) if value.get('items') else dict(spec=deepcopy(spec), state='UNKNOWN', id=None)

    def wait(self, spec, op, deadline, action='insert', identity=None):
        while True:
            result = self.decode_operation(spec, op, action, identity)
            if result['state'] == 'DONE': return result
            m.need(self.api.clock() < deadline, 'provider operation deadline')
            self.sleep(min(.25, max(0, deadline-self.api.clock())))
            op = self.api.call('GET', self.scope(spec)+'/operations/'+op['name'], deadline=deadline)

    def create(self, spec, deadline):
        deadline /= 10**9  # Controller uses nanoseconds on the same monotonic clock.
        body = self.body(spec)
        if spec['kind'] == 'disk' and spec['purpose'] == 'boot':
            image = self.api.call('GET', body['sourceImage'], deadline=deadline)
            m.need(image['id'] == self.config['imageId'] and image['status'] == 'READY' and
                   image['name'] == self.config['imageName'], 'image identity/status')
        url = self.url(spec).rsplit('/', 1)[0]+'?'+urllib.parse.urlencode(dict(requestId=self.operation_id(spec)))
        op = self.api.call('POST', url, body, deadline=deadline)
        result = self.wait(spec, op, deadline)
        m.need(result['id'] is not None, 'insert rejected')
        observed = self.describe(spec, identity=result['id'], deadline=deadline)
        m.need(observed is not None, 'created resource absent')
        return observed

    def delete(self, spec, expected_id):
        numeric(expected_id); deadline = self.api.clock()+30
        if self.describe(spec, identity=expected_id, deadline=deadline) is None: return
        # Discovery accepts numeric resource identifiers. Never fall back to a
        # name-based delete; a reused name must not identify another generation.
        url = self.url(spec, expected_id)+'?'+urllib.parse.urlencode(dict(requestId=self.operation_id(spec, 'delete', expected_id)))
        try: op = self.api.call('DELETE', url, deadline=deadline)
        except ApiError as error:
            if error.status == 404: return
            raise
        self.wait(spec, op, deadline, 'delete', expected_id)
        m.need(self.describe(spec, identity=expected_id, deadline=deadline) is None, 'numeric deletion absence')
