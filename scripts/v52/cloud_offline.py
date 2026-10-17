"""In-memory fault adapters; no SDK, credentials, subprocess or network I/O."""
from copy import deepcopy
import threading
from . import cloud_authority as a
from .evidence import need


class Store:
    execution = a.DOMAINS['offline']
    def __init__(self):
        self.objects = {}; self.serial = 0; self.events = []; self.fault = lambda *args: None
        self.lock = threading.RLock()

    def get(self, key):
        self.fault('get', key, None)
        with self.lock: return deepcopy(self.objects.get(key))

    def put(self, key, value, expected):
        self.fault('before-put', key, value)
        with self.lock:
            current = self.objects.get(key)
            need(expected == (current[0] if current else 0), 'V5.2 object generation conflict')
            self.serial += 1; generation = self.serial
            self.objects[key] = (generation, deepcopy(value))
            self.events.append(dict(action='put', key=key, generation=generation, value=deepcopy(value)))
        self.fault('after-put', key, value)
        return generation

    def delete(self, key, expected):
        self.fault('before-delete', key, None)
        with self.lock:
            need(key in self.objects and self.objects[key][0] == expected, 'V5.2 object generation conflict')
            del self.objects[key]; self.events.append(dict(action='delete', key=key, generation=expected))
        self.fault('after-delete', key, None)


class Provider:
    execution = a.DOMAINS['offline']
    def __init__(self, store):
        self.store = store; self.objects = {}; self.operations = {}; self.events = []
        self.fault = lambda *args: None

    def prepare_context(self, req): a.validate_request(req, domain='offline')

    def begin_cleanup(self): pass

    def describe(self, spec):
        self.fault('describe', spec)
        return deepcopy(self.objects.get(spec['name']))

    def operation(self, spec):
        self.fault('operation', spec)
        return deepcopy(self.operations.get(spec['operationId'], dict(spec=spec, state='UNKNOWN', id=None)))

    def create(self, spec, deadline):
        lease = self.store.get(a.LEASE)[1]; a.validate_lease(lease)
        need(lease['phase'] == 'ACTIVE' and any(r['spec'] == spec and r['attempted'] for r in lease['resources']),
             'V5.2 create without active retained intent')
        ledger = self.store.get(a.LEDGER)[1]
        need(a.inspect_ledger(ledger, domain='offline')['attempts'][spec['requestSha256']]['status'] == 'PENDING',
             'V5.2 create without charge')
        need(spec['operationId'] not in self.operations and spec['name'] not in self.objects, 'V5.2 repeated insert')
        self.events.append(dict(action='create', spec=deepcopy(spec), deadline=deadline))
        self.fault('before-create', spec)
        value = dict(spec=deepcopy(spec), id=str(1000+len(self.operations)))
        self.operations[spec['operationId']] = dict(spec=deepcopy(spec), state='DONE', id=value['id'])
        self.objects[spec['name']] = value
        self.fault('after-create', spec)
        return deepcopy(value)

    def delete(self, spec, identity):
        need(self.objects.get(spec['name']) == dict(spec=spec, id=identity), 'V5.2 delete identity changed')
        self.fault('before-delete', spec)
        del self.objects[spec['name']]; self.events.append(dict(action='delete', spec=deepcopy(spec), id=identity))
        self.fault('after-delete', spec)
