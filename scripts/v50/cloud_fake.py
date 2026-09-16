"""Deterministic adapter faults for the real Runner; never runtime performance evidence."""
from copy import deepcopy
from .cloud_common import canonical, require, save


class Fake:
    execution = 'fake-owned-runner-only'

    def __init__(self, plan, request, fault=None):
        self.plan, self.request, self.fault = plan, request, fault
        self.objects, self.resources, self.calls = {}, {}, []
        self.counter = 0

    def owns(self, value): return value.get('owner') == self.request['owner']

    def describe(self, row):
        if self.fault == 'forbidden-read' and self.counter >= 6 and row['name'].endswith('n1-data'):
            raise PermissionError('403 is not absence')
        return deepcopy(self.resources.get(row['name']))

    def create(self, row):
        self.calls.append(('create', row['name'])); self.counter += 1
        value = dict(id=str(self.counter), owner=self.request['owner'], users=[])
        if self.fault == 'unresolved-create' and self.counter == 6: raise TimeoutError('insert result unknown')
        self.resources[row['name']] = value
        if self.fault == 'partial-create' and self.counter == 6: raise TimeoutError('created, acknowledgement lost')
        return deepcopy(value)

    def delete(self, row, expected_id):
        self.calls.append(('delete', row['name']))
        value = self.resources.get(row['name'])
        if value is None: return
        require(self.owns(value) and value['id'] == expected_id, 'foreign/reused ID')
        if self.fault == 'delete-failure' and row['kind'] == 'instances' and row['node'] == 2: raise RuntimeError('delete failed')
        require(not value['users'], 'attached disk')
        self.resources.pop(row['name'])
        if row['kind'] == 'instances':
            for key in list(self.resources):
                if row['name'] in self.resources[key]['users']: self.resources.pop(key)

    def attach(self, instance, disk, attach=True):
        self.calls.append(('attach' if attach else 'detach', disk['name']))
        self.resources[disk['name']]['users'] = [instance['name']] if attach else []

    def get_object(self, name): return self.objects.get(name)

    def put_object(self, name, raw, generation='0'):
        self.calls.append(('upload', name))
        require((self.objects.get(name) or ('0',))[0] == generation, 'GCS generation conflict')
        if self.fault == 'upload-failure' and '/final/' in name: raise ConnectionError('upload interrupted')
        version = str(int(generation) + 1); self.objects[name] = (version, raw); return version

    def delete_object(self, name, generation):
        require(self.objects[name][0] == generation, 'GCS generation changed'); del self.objects[name]


class FakeProbe:
    def __init__(self, backend): self.backend = backend; self.started = []; self.stopped = []

    def prepare(self, node): self.backend.calls.append(('prepare', node['node']))
    def bootstrap(self, node): self.backend.calls.append(('bootstrap', node['node']))
    def unmount(self, node, disk): self.backend.calls.append(('unmount', disk['node']))

    def start(self, node):
        self.backend.calls.append(('start', node['node'])); self.started.append(node['node'])
        if self.backend.fault == 'startup-failure' and node['node'] == 2: raise RuntimeError('JVM startup failed')

    def exercise(self):
        self.backend.calls.append(('exercise', 3))
        if self.backend.fault == 'unreachable': raise TimeoutError('member unreachable')
        if self.backend.fault == 'cancel': raise KeyboardInterrupt('cancelled')
        if self.backend.fault in ('foreign-owner', 'reused-id'):
            resource = next(v for k, v in self.backend.resources.items() if k.endswith('n2-data'))
            if self.backend.fault == 'foreign-owner': resource['owner'] = 'unrelated'
            else: resource['id'] = '9999'
            resource['users'] = []  # Replaced resource is not attached to our VM.

    def stop(self, node): self.stopped.append(node['node'])
    def collect(self, node, root): save(root / 'fake.json', dict(execution=self.backend.execution, node=node['node']))
    def validate(self, root):
        require(self.started == [1, 2, 3], 'incomplete fake startup')
        return dict(status='PASS', execution=self.backend.execution, measurementClaim=False)
