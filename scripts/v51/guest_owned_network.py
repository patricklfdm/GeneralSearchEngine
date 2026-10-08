"""Owned network fault slice; twelve-cell failure-drill admission stays closed."""
import base64
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

    def execute(self, member, name, payload, deadline):
        # The guest has one command executor. Healing may overlap controller
        # polling, but must not race a second submission into that executor.
        # Waiting consumes the original deadline; no BUSY command is replayed.
        lock = self.command_locks[member[0]]
        remaining = deadline-self.clock()
        m.need(remaining > 0 and lock.acquire(timeout=remaining), 'owned network command admission deadline')
        try: return super().execute(member, name, payload, deadline)
        finally: lock.release()


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
    cell.event('network-ready')
    def release():
        cell.event('network-heal-request')
        try:
            cell.parallel(lambda member:command(member, 'heal'), members)
            cell.network_healed = True
        except BaseException as exc: errors.append(str(exc))
    timer = threading.Timer(15, release); timer.start()
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
        timer.cancel(); timer.join(timeout=5)
        m.need(not timer.is_alive(), 'owned network release thread remains active')


class Services(faults.Services):
    mode = MODE
    cases = CASES


class Probe(faults.Probe):
    cell_type = Cell
    mode = MODE
    scope = SCOPE
    cases = CASES
