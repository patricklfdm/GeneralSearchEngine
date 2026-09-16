"""Exercise the production lifecycle with virtual cells and fake disk generations."""
import time
from pathlib import Path
from .cloud_common import canonical, plan, require, save
from .cloud_fake import Fake, FakeProbe
from .cloud_presets import EXECUTION, ORDER, preset, workload_request
from .cloud_runner import BUDGET, LEASE, Runner


def cells(profile, action, clock=time.monotonic, sleep=time.sleep):
    """One fixed elapsed window per ordered cell; early completion cannot shorten it."""
    result = []
    for cell in preset(profile)['cells']:
        started = clock(); deadline = started + cell['seconds']
        action(cell['name'], deadline)
        require(clock() <= deadline, 'preset cell deadline: ' + cell['name'])
        while clock() < deadline: sleep(min(.25, deadline - clock()))
        result.append(dict(name=cell['name'], startedSeconds=started, finishedSeconds=clock(),
                           reservedSeconds=cell['seconds'], status='PASS'))
    return result


class PresetFake(Fake):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.peak_disk_gib = 0; self.resource_inventory = []; self.injected = False

    def create(self, row):
        replacement = row.get('generation') == 2
        if replacement and self.fault == 'replacement-unresolved':
            self.calls.append(('create', row['name'])); raise TimeoutError('replacement insert unresolved')
        value = super().create(row)
        self.resources[row['name']].update(sizeGiB=row.get('sizeGiB', 0), requestId=row['requestId'])
        self.peak_disk_gib = max(self.peak_disk_gib, sum(v.get('sizeGiB', 0) for v in self.resources.values()))
        if replacement and self.fault == 'replacement-lost-ack': raise TimeoutError('replacement created; response lost')
        return value

    def insert_finished(self, row):
        return not (row.get('generation') == 2 and row.get('attempted') and
                    not row.get('id') and self.fault == 'replacement-unresolved')

    def delete(self, row, expected_id):
        old = row['name'].endswith('n3-data')
        if old and self.fault == 'old-delete-failure': raise RuntimeError('old disk deletion failed')
        if old and self.fault == 'old-delete-lies': return
        if old and not self.injected and self.fault in ('old-foreign', 'old-reused-id'):
            self.injected = True
            self.resources[row['name']]['owner' if self.fault == 'old-foreign' else 'id'] = 'unrelated'
        super().delete(row, expected_id)


class PresetProbe(FakeProbe):
    def __init__(self, backend):
        super().__init__(backend); self.runner = None; self.virtual_seconds = 0; self.windows = []

    def quiesce(self): self.backend.calls.append(('quiesce', (1, 2, 3)))
    def preserve_disk(self, node, disk):
        self.backend.calls.append(('preserve', disk['name']))
        return dict(execution=EXECUTION, diskId=disk['id'], diagnosticOnly=True)

    def initialize_replacement(self, source, disk):
        self.backend.calls.append(('replacement-admission', source['node'], disk['node']))
        if self.backend.fault == 'replacement-bootstrap': raise RuntimeError('replacement bootstrap failed')
        return dict(execution=EXECUTION, source=source['node'], target=disk['node'], diskId=disk['id'])

    def mount_replacement(self, node, disk):
        self.backend.calls.append(('replacement-mount', disk['name']))
        return dict(execution=EXECUTION, diskId=disk['id'])

    def resume_replacement(self, node):
        if self.backend.fault == 'replacement-cancel': raise KeyboardInterrupt('cancelled after replacement mount')
        self.backend.calls.append(('resume', node))

    def exercise(self):
        def action(name, deadline):
            self.backend.calls.append(('cell', name))
            if name == 'follower-replacement': self.runner.replace_data_disk(3, 1)
            elif name == 'leader-replacement': self.runner.replace_data_disk(1, 2)
            elif self.backend.fault == 'cell-overrun': self.virtual_seconds = deadline + 1
        def advance(seconds): self.virtual_seconds += seconds
        self.windows = cells(self.backend.request['profile'], action, lambda: self.virtual_seconds, advance)

    def validate(self, root):
        super().validate(root)
        profile = preset(self.backend.request['profile'])
        require([v['name'] for v in self.windows] == [v['name'] for v in profile['cells']], 'incomplete preset cells')
        require(self.backend.peak_disk_gib == 450, 'replacement peak disk budget')
        result = dict(status='PASS', execution=EXECUTION, measurementClaim=False, windows=self.windows,
                      peakDiskGiB=self.backend.peak_disk_gib, virtualMeasurementSeconds=self.virtual_seconds)
        save(root / 'preset-qualification.json', result)
        return result


def run_one(root, profile, repetition, sequence, run_id, *, objects=None, fault=None, source='a'*40):
    import json
    req = workload_request(source, run_id, 1, 'b' * 64, profile, sequence, repetition)
    backend = PresetFake(plan(), req, fault)
    if objects is not None: backend.objects = objects
    budget = backend.get_object(BUDGET)
    previous = sum(v['maximumCostMicrousd'] for v in json.loads(budget[1])['reservations']) if budget else 0
    probe = PresetProbe(backend)
    runner = Runner(backend, probe, root, approval=dict(maximumCostMicrousd=1_000_000, previousAttemptsCostMicrousd=previous))
    probe.runner = runner
    return backend, runner.run()


def matrix(root, profile=None):
    root = Path(root); results = []; objects = {}
    # Qualify the complete prerequisite chain even when inspecting one preset.
    sequence = 'c' * 32
    selected = ORDER if profile is None or profile == 'canonical' else ORDER[:1 if profile == 'experiment' else 2]
    for index, (name, repetition) in enumerate(selected, 1):
        backend, state = run_one(root / f'{index}-{name}', name, repetition, sequence, index, objects=objects)
        require(state['status'] == 'PASS' and state['leaseReleased'] and not backend.resources, 'serial preset qualification failed')
        results.append(dict(profile=name, repetition=repetition, status='PASS', peakDiskGiB=backend.peak_disk_gib))
    for index, fault in enumerate(('old-delete-failure', 'old-delete-lies', 'old-foreign', 'old-reused-id',
            'replacement-lost-ack', 'replacement-unresolved', 'replacement-bootstrap', 'replacement-cancel', 'cell-overrun', 'upload-failure'), 100):
        isolated = {}; attempt_set = f'{index:032x}'
        _, first = run_one(root / (fault + '-prerequisite'), 'experiment', 1, attempt_set, index, objects=isolated)
        require(first['status'] == 'PASS', 'fault prerequisite')
        backend, failed = run_one(root / fault, 'failure-drill', 1, attempt_set, index + 100, objects=isolated, fault=fault)
        require(failed['status'] == 'FAIL', 'failure not detected: ' + fault)
        results.append(dict(case=fault, status='PASS', expectedFailure=True, cleanup=failed.get('cleanup'), leaseRetained=LEASE in isolated))
    result = dict(schema='gse-v50-preset-qualification-v1', status='PASS', execution=EXECUTION,
                  paidResourcesCreated=False, measurementClaim=False, cases=results)
    save(root / 'matrix.json', result); return result
