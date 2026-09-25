"""Offline HTTP server double. Exercises adapters through URLs/bytes/status codes."""
from copy import deepcopy
from urllib.parse import urlsplit, parse_qs, unquote
from . import cloud_authority as a, cloud_fake, cloud_gcp, performance_model as m
from .cloud_http import Api


def configuration():
    env = a.workload.load()['environment']
    return dict(schema='gse-v51-provider-config-v1', project='offline-project', bucket='offline-evidence',
                network='offline-network', subnetwork='offline-subnet', region='us-west4', port=19151,
                **{k: env[k] for k in ('zone', 'imageProject', 'imageName', 'imageId', 'machineType', 'diskType')})


class Http:
    offline = True
    def __init__(self, configuration, fault=None):
        self.configuration, self.fault = configuration, fault
        self.objects, self.resources, self.operations, self.requests = {}, {}, {}, []
        self.serial, self.inserts = 1000, 0
        self.hook = None

    def send(self, method, url, headers, body, timeout, maximum):
        p = urlsplit(url); query = {k: v[0] for k, v in parse_qs(p.query).items()}
        self.requests.append(dict(method=method, path=p.path, query=query,
            bodySha256=m.sha(body) if body is not None else None))
        if self.hook:
            response = self.hook(method, p, query, body)
            if response is not None: return response
        if p.hostname == 'storage.googleapis.com':
            return self.storage(method, p.path, query, body, headers['Content-Type'])
        return self.compute(method, p.path, query, body)

    def reply(self, value, status=200): return status, m.canonical(value)

    def metadata(self, key):
        gen, raw, content = self.objects[key]
        return dict(bucket=self.configuration['bucket'], name=key, generation=str(gen), size=str(len(raw)), contentType=content)

    def storage(self, method, path, query, body, content):
        key = query['name'] if method == 'POST' else unquote(path.split('/o/', 1)[1])
        current = self.objects.get(key); generation = current[0] if current else 0
        if 'ifGenerationMatch' in query and int(query['ifGenerationMatch']) != generation: return 412, b''
        if method == 'POST':
            self.serial += 1; self.objects[key] = self.serial, body, content
            return self.reply(self.metadata(key))
        if current is None: return 404, b''
        if method == 'DELETE': del self.objects[key]; return 204, b''
        if query.get('alt') == 'media':
            if int(query['generation']) != generation: return 404, b''
            return 200, current[1]
        return self.reply(self.metadata(key))

    def compute(self, method, path, query, body):
        if '/global/images/' in path:
            p = self.configuration
            return self.reply(dict(name=p['imageName'], id=p['imageId'], status='DEPRECATED' if self.fault == 'image-drift' else 'READY'))
        if '/operations' in path:
            if path.endswith('/operations'):
                request = query['filter'].split('"')[1]
                items = [v for v in self.operations.values() if v['clientOperationId'] == request and v['targetLink'].startswith('https://compute.googleapis.com'+path.rsplit('/', 1)[0]+'/')]
                return self.reply(dict(items=items))
            return self.reply(self.operations[path.rsplit('/', 1)[1]])
        collection, identity = path.rsplit('/', 1)
        if method == 'POST':
            self.inserts += 1
            value = m.strict_json(body)
            # Durable intent must precede every HTTP insert, including a lost reply.
            lease = m.strict_json(self.objects[a.LEASE][1])
            m.need(any(r['attempted'] and r['spec']['name'] == value['name'] for r in lease['resources']), 'HTTP insert before retained intent')
            self.serial += 1; resource_id = str(self.serial)
            value['id'] = resource_id
            if value.get('sourceImage'): value['sourceImageId'] = self.configuration['imageId']
            target = path+'/'+value['name']
            m.need(target not in self.resources, 'HTTP duplicate insert')
            op = dict(name='operation-'+str(self.serial), operationType='insert', clientOperationId=query['requestId'],
                      targetLink='https://compute.googleapis.com'+target, targetId=resource_id, status='DONE')
            if self.fault == 'pending-insert' and self.inserts == 3:
                op.update(status='RUNNING'); op.pop('targetId')
            else: self.resources[target] = value
            self.operations[op['name']] = op
            if self.fault in ('lost-insert', 'pending-insert') and self.inserts == 3:
                raise ConnectionError('injected HTTP insert response lost')
            return self.reply(op)
        match = next(((key, value) for key, value in self.resources.items()
                      if key.rsplit('/', 1)[0] == collection and (key == path or value['id'] == identity)), None)
        if match is None: return 404, b''
        key, value = match
        if method == 'GET': return self.reply(value)
        m.need(identity.isdecimal(), 'name-based HTTP deletion forbidden')
        if self.fault == 'delete-denied': return 403, b''
        del self.resources[key]; self.serial += 1
        op = dict(name='operation-'+str(self.serial), operationType='delete', clientOperationId=query['requestId'],
                  targetLink='https://compute.googleapis.com'+key, targetId=identity, status='DONE')
        self.operations[op['name']] = op
        return self.reply(op)


def fixture(fault=None):
    cfg = configuration(); req, preflight, approval = cloud_fake.fixture()
    req['configurationSha256'] = cloud_gcp.config(cfg)
    preflight['requestSha256'] = a.validate_request(req)
    approval.update(requestSha256=a.validate_request(req), preflightSha256=m.sha(m.canonical(preflight)))
    clock = cloud_fake.Clock(); http = Http(cfg, fault)
    api = Api(transport=http, tokens=lambda timeout: 'offline-token', clock=clock.seconds)
    store = cloud_gcp.Store(cfg, api); provider = cloud_gcp.Compute(cfg, req, api, sleep=clock.sleep)
    return req, preflight, approval, clock, http, store, provider
