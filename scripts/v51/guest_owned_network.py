"""Owned network fault slice; twelve-cell failure-drill admission stays closed."""
import base64
from contextlib import contextmanager
import threading
from . import guest_owned_faults as faults, performance_model as m, format_inspector as f
from .guest_fault_network import CASES
from .remote_faults import documents

MODE = 'network-faults'
SCOPE = 'owned-network-faults'


class Cell(faults.Cell):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.command_locks = {node: threading.Lock() for node, _, _ in self.clients}
        self.admission = threading.Condition()
        self.reserved = set()
        self.release_error = None

    def execute(self, member, name, payload, deadline):
        # Reserve the single guest executor before the heal deadline. A poll
        # already observing its original command is allowed to finish; later
        # polls cannot slip in ahead of the reserved heal or submit BUSY work.
        lock = self.command_locks[member[0]]
        while True:
            with self.admission:
                while member[0] in self.reserved:
                    remaining = deadline-self.clock()
                    m.need(remaining > 0, 'owned network command admission deadline')
                    self.admission.wait(remaining)
                self.check_release(name)
            remaining = deadline-self.clock()
            m.need(remaining > 0 and lock.acquire(timeout=remaining), 'owned network command admission deadline')
            with self.admission:
                if member[0] not in self.reserved: break
            lock.release()
        try:
            self.check_release(name)
            m.need(self.clock() < deadline, 'owned network command admission deadline')
            return super().execute(member, name, payload, deadline)
        finally: lock.release()

    def check_release(self, name):
        # Failed release ends workload polling promptly, while shutdown and
        # evidence collection still use their original independent deadlines.
        m.need(name != 'fault' or self.release_error is None, 'owned network release failed: '+str(self.release_error))

    @contextmanager
    def reserve_heal(self, members, deadline):
        nodes = {v[0] for v in members}; held = []
        with self.admission:
            m.need(not self.reserved, 'owned network heal already reserved')
            self.reserved = nodes
            self.admission.notify_all()
        try:
            for node in sorted(nodes):
                remaining = deadline-self.clock(); lock = self.command_locks[node]
                m.need(remaining > 0 and lock.acquire(timeout=remaining), 'owned network heal reservation deadline')
                held.append(lock)
            yield
        except BaseException as error:
            with self.admission: self.release_error = str(error)
            raise
        finally:
            # No caller can enter until every original heal observation ends.
            for lock in reversed(held): lock.release()
            with self.admission:
                self.reserved = set(); self.admission.notify_all()

    def heal_at(self, members, when, cancelled):
        self.event('network-heal-reserve')
        with self.reserve_heal(members, min(when, self.end)):
            self.event('network-heal-reserved')
            if cancelled.wait(max(0, when-self.clock())): return
            m.need(self.clock() >= when, 'owned network early heal')
            self.event('network-heal-request')
            def heal(member):
                # These slots are already held. Keep the original exactly-once
                # execute/observe path and deadline without reacquiring a lock.
                result = faults.Cell.execute(self, member, 'fault', dict(action='heal'), self.end)
                m.need(result['state'] == 'SUCCEEDED', 'owned network heal command failed: '+str(result))
            self.parallel(heal, members)
            self.network_healed = True


def scenario(cell, leader, deadline):
    case = cell.case; cell.network_healed = False; errors = []
    def command(member, action, **values):
        return cell.succeeded(member, 'fault', dict(action=action, **values), cell.end)['result']
    members = cell.clients
    if case == 'slow-follower':
        selected = command(cell.member(leader), 'observe-network')['selected']
        m.need(selected is not None, 'owned slow follower selected pair missing')
        basis = f.inspect(base64.b64decode(selected['selected'], validate=True), 'SELECTED')
        target = next(b['node'] for b in basis['bases'] if b['node'] != leader)
        cell.record.update(selected=selected, delayedNode=target)
        members = [cell.member(target)]
    cell.parallel(lambda member:command(member, 'isolate', node=target if case=='slow-follower' else leader), members)
    ready = cell.event('network-ready')['controllerNanos']/1e9
    cancelled = threading.Event()
    def release():
        try: cell.heal_at(members, ready+15, cancelled)
        except BaseException as exc: errors.append(str(exc))
    # Drain control traffic three seconds early, but never remove the injected
    # fault before the original 15-second hold. The guest watchdog stays at 17s.
    timer = threading.Timer(max(0, ready+12-cell.clock()), release); timer.start()
    try:
        if case == 'isolated-old-leader':
            cell.sleep(2)
            cell.record['refusals'] = [cell.call(leader, 'addAll', documents=documents(90)), cell.call(leader, 'read')]
            m.need(all(v['outcome'] != 'SUCCESS' for v in cell.record['refusals']), 'isolated leader served client')
        elif case == 'asymmetric-responses':
            cell.record['directionalCall'] = cell.call(leader, 'addAll', documents=documents(40))
        active = cell.progress(deadline, exclude=() if case=='slow-follower' else (leader,))
        if case == 'slow-follower':
            cell.record['delayed'] = cell.wait(lambda:command(members[0], 'observe-network')['delayed'], deadline, 'no owned delayed force')
            cell.record['lag'] = dict(leader=cell.status(active), follower=cell.status(target))
        timer.join(max(.001, min(17, cell.end-cell.clock())))
        m.need(not timer.is_alive() and not errors and cell.network_healed, 'owned network release failed: '+str(errors))
        through = cell.status(active)['provenIndex']
        for node in cell.running: cell.rejoin(node, through)
    finally:
        cancelled.set(); timer.cancel(); timer.join(timeout=5)
        m.need(not timer.is_alive(), 'owned network release thread remains active')


class Services(faults.Services):
    mode = MODE
    cases = CASES


class Probe(faults.Probe):
    cell_type = Cell
    mode = MODE
    scope = SCOPE
    cases = CASES
