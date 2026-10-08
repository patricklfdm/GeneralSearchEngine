"""Fixed partition/delay controls for offline owned fault qualification."""
import threading
import time
from . import performance_model as m, public_trace, remote_command as c

CASES = ('isolated-old-leader', 'asymmetric-requests', 'asymmetric-responses', 'slow-follower')
NODES = ('node-1', 'node-2', 'node-3')


def rules(case, leader):
    m.need(case in CASES[:3] and leader in NODES, 'network fault selection')
    barrier = 'AFTER_RESPONSE_READ' if case == 'asymmetric-responses' else 'BEFORE_REQUEST_WRITE'
    return [f'{a} {b} {barrier} *' for a in NODES for b in NODES if a != b and
            (leader in (a, b) if case == 'isolated-old-leader' else a == leader)]


class Controls:
    def __init__(self, handler): self.h = handler

    def release(self, watchdog=False):
        h = self.h
        with h.lock:
            if not h.isolated or h.healed: return
            if h.case == 'slow-follower': (h.s.cell/(h.s.node+'-slow-force')).unlink()
            else: h.rules([])
            h.healed = True
            h.isolation.update(healedNanos=time.monotonic_ns(), watchdog=watchdog)
            c.write_once(h.s.cell/'isolation.json', h.isolation)
            if h.timer is not None: h.timer.cancel()

    def handle(self, payload):
        h = self.h; action = payload.get('action')
        m.need(h.s.config['execution'] == 'local-guest-service-only', 'network faults not admitted natively')
        if action == 'observe-network':
            m.need(payload == {'action':action} and h.case == 'slow-follower', 'network observation scope')
            rows = public_trace.live_rows(h.s.cell, h.s.node)
            selected = next((v for v in reversed(rows) if v['event'] == 'PROMISE_QUORUM'), None)
            delayed = next((v for v in rows if v['event'] == 'SLOW_FORCE_BEGIN'), None)
            return dict(selected=selected, delayed=delayed)
        if action == 'isolate':
            m.need(set(payload) == {'action', 'node'} and payload['node'] in NODES and not h.isolated and
                   (h.case != 'slow-follower' or payload['node'] == h.s.node), 'network injection consumed/scope')
            with h.lock:
                # The original durable claim also prevents a new command ID
                # from repeating an injection after an uncertain handler result.
                c.write_once(h.s.cell/'network-injection-claim.json', payload)
                h.isolated = True
                if h.case == 'slow-follower':
                    (h.s.cell/(h.s.node+'-slow-force')).touch(exist_ok=False)
                    data = dict(node=h.s.node, delayMillis=1500)
                else:
                    value = rules(h.case, payload['node']); h.rules(value); data = dict(rules=value, node=payload['node'])
                h.isolation = dict(appliedNanos=time.monotonic_ns(), **data)
                h.timer = threading.Timer(17, lambda:self.release(True))
                h.timer.daemon = True; h.timer.start()
                return dict(h.isolation)
        if action == 'heal':
            m.need(payload == {'action':action} and h.isolated, 'network heal scope')
            self.release(); return c.read(h.s.cell/'isolation.json')
        raise ValueError('unsupported network fault action')
