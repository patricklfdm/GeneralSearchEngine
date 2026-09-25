"""Local fault adapters for the V5.1 controller, not a cloud/workload simulator."""
from copy import deepcopy
from pathlib import Path
from . import cloud_authority as a, performance_model as m, remote_command as command, remote_collection as collection


class Clock:
    def __init__(self): self.now = 10**9
    def nanos(self): return self.now
    def wall(self): return 10000 + self.now//10**9
    def seconds(self): return self.now/10**9
    def sleep(self, seconds): self.now += int(seconds*10**9)


class Store:
    execution = a.EXECUTION
    def __init__(self, fault=None):
        self.objects, self.serial, self.events, self.fault = {}, 0, [], fault

    def get(self, key):
        if self.fault == 'readback-failure' and key.endswith('/evidence.json') and key in self.objects:
            raise ConnectionError('injected evidence read-back failure')
        return deepcopy(self.objects.get(key))

    def put(self, key, value, expected):
        current = self.objects.get(key)
        m.need(expected == (current[0] if current else 0), 'object generation conflict')
        if self.fault == 'upload-failure' and '/parts/' in key:
            raise ConnectionError('injected immutable upload failure')
        if self.fault == 'completion-failure' and key.endswith('/completion.json'):
            raise ConnectionError('injected completion upload failure')
        self.serial += 1
        self.objects[key] = (self.serial, deepcopy(value))
        self.events.append(dict(action='put', key=key, generation=self.serial))
        return self.serial

    def delete(self, key, expected):
        m.need(key in self.objects and self.objects[key][0] == expected, 'object generation conflict')
        del self.objects[key]
        self.events.append(dict(action='delete', key=key, generation=expected))


class Provider:
    execution = a.EXECUTION
    def __init__(self, store, fault=None):
        self.store, self.fault = store, fault
        self.objects, self.operations, self.events = {}, {}, []

    def describe(self, spec):
        return deepcopy(self.objects.get(spec['name']))

    def create(self, spec, deadline):
        # Assert the ordering at the adapter boundary, rather than merely testing
        # that the controller eventually writes a matching intent.
        lease = self.store.get(a.LEASE)[1]
        m.need(any(r['spec'] == spec and r['attempted'] for r in lease['resources']), 'create without retained intent')
        m.need(spec['operationId'] not in self.operations and spec['name'] not in self.objects, 'duplicate create')
        self.events.append(dict(action='create', spec=deepcopy(spec)))
        if self.fault == 'unresolved-create' and len(self.events) == 3:
            self.operations[spec['operationId']] = dict(spec=spec, state='PENDING', id=None)
            raise TimeoutError('injected unresolved insertion')
        value = dict(spec=deepcopy(spec), id=str(1000+len(self.operations)))
        self.operations[spec['operationId']] = dict(spec=deepcopy(spec), state='DONE', id=value['id'])
        self.objects[spec['name']] = value
        if self.fault == 'partial-create' and len(self.events) == 3:
            raise ConnectionError('injected lost create response')
        return deepcopy(value)

    def operation(self, spec):
        result = deepcopy(self.operations.get(spec['operationId'], dict(spec=spec, state='UNKNOWN', id=None)))
        if spec['kind'] == 'instance' and spec['node'] == 1:
            if self.fault == 'operation-read-failure': raise PermissionError('injected operation read denied')
            if self.fault == 'foreign-owner' and spec['name'] in self.objects:
                self.objects[spec['name']]['spec']['owner'] = 'unrelated-owner'
            if self.fault == 'reused-id' and spec['name'] in self.objects:
                self.objects[spec['name']]['id'] = '999999'
        return result

    def delete(self, spec, expected_id):
        current = self.objects.get(spec['name'])
        m.need(current == dict(spec=spec, id=expected_id), 'conditional delete identity')
        self.events.append(dict(action='delete', spec=deepcopy(spec), id=expected_id))
        if self.fault in ('delete-failure', 'false-delete') and spec['kind'] == 'instance' and spec['node'] == 1:
            if self.fault == 'delete-failure': raise ConnectionError('injected delete failure')
            return
        del self.objects[spec['name']]


class Probe:
    execution = a.EXECUTION
    def __init__(self, root, clock, fault=None):
        self.root, self.clock, self.fault = Path(root), clock, fault
        self.root.mkdir(parents=True, exist_ok=False)
        self.raw = self.root/'raw'; self.raw.mkdir()
        self.cells, self.submits, self.handlers, self.queries = [], 0, 0, 0
        self.stopped = False

    def prepare(self, req, deadline):
        self.req = req
        self.owner = command.binding(req['source'], req['bundleSha256'], req['attempt'], 'node-1')
        self.store = command.CommandStore(self.raw/'commands', self.owner, create=True)
        if self.fault == 'startup-failure': raise ValueError('injected startup failure')
        if self.fault == 'preparation-overrun': self.clock.sleep(601)

    def cell(self, cell, deadline):
        value = command.request(self.owner, m.sha(cell.encode())[:32], 'window', dict(cell=cell))
        probe = self
        class Transport:
            def submit(self, request, original_deadline):
                probe.submits += 1
                if probe.fault == 'unreachable': raise ConnectionError('injected missing connection')
                def handler(name, payload, checkpoint):
                    probe.handlers += 1
                    if probe.fault == 'cancel':
                        probe.store.cancel(request); checkpoint()
                    command.write_once(probe.raw/(cell+'.json'), dict(cell=cell, diagnosticOnly=True))
                    return dict(diagnosticOnly=True)
                result = probe.store.execute(request, handler)
                if probe.fault in ('lost-submit', 'query-reconnect'): raise ConnectionError('injected lost terminal reply')
                return result
            def query(self, request, original_deadline):
                probe.queries += 1
                if probe.fault == 'query-reconnect' and probe.queries % 2 == 1:
                    raise ConnectionError('injected expired query connection')
                return probe.store.query(request)
        result = command.submit_and_observe(Transport(), value,
            min(deadline/10**9, self.clock.seconds()+9.6), clock=self.clock.seconds, sleep=self.clock.sleep)
        m.need(result['state'] == 'SUCCEEDED', 'diagnostic command failed: '+result['state'])
        self.cells.append(cell)
        if self.fault == 'cell-overrun': self.clock.sleep(901)

    def stop(self): self.stopped = True

    def retention_files(self):
        for path in sorted((self.root/'parts').iterdir()):
            yield path.name, path.read_bytes()

    def collect_validate(self, output, deadline):
        if self.fault == 'collection-failure': raise ConnectionError('injected truncated collection')
        command.write_once(self.raw/'diagnostic.json', dict(cells=self.cells, handlers=self.handlers,
                           submits=self.submits, queries=self.queries, stopped=self.stopped))
        binding = m.sha(m.canonical(getattr(self, 'owner', dict(unprepared=True))))
        parts = collection.pack(self.raw, self.root/'parts', binding)
        receipt = collection.unpack(self.root/'parts', self.root/'replay', binding)
        return dict(execution=a.EXECUTION, engineWorkloadExecuted=False, cells=self.cells[:],
                    submits=self.submits, handlers=self.handlers, queries=self.queries,
                    collection=receipt, partsSha256=m.sha(m.canonical(parts)))


def fixture(*, source='a'*40, attempt='b'*32, sequence='c'*32, member='experiment', order='experiment-first',
            now=10001, previous=0, cost=1_000_000, cleanup_event='schedule'):
    req = a.request(source, 'd'*64, 'e'*64, sequence, attempt, member, now=now, order=order)
    preflight = dict(schema='gse-v51-control-preflight-v1', execution=a.EXECUTION,
        requestSha256=a.validate_request(req), checkedAt=now, expiresAt=now+900,
        checks={k: True for k in a.CHECKS}, workflow=a.RUNNER_WORKFLOW, ref='refs/heads/master', environment=a.ENVIRONMENT,
        cleanup=dict(source=source, event=cleanup_event, workflow=a.CLEANUP_WORKFLOWS[cleanup_event],
                     ref='refs/heads/master', completedAt=now-1, runId=1, executed=True, conclusion='success', reconciliation='PASS'))
    approval = dict(schema='gse-v51-control-approval-v1', execution=a.EXECUTION,
        requestSha256=a.validate_request(req), preflightSha256=m.sha(m.canonical(preflight)), confirmed=True,
        maximumCostMicrousd=cost, previousCostMicrousd=previous)
    return req, preflight, approval
