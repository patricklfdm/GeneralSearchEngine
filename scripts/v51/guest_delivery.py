"""Bounded helper distribution: one install, then receipt queries under one deadline."""
import base64
from pathlib import Path
import time
from . import guest_delivery_receiver as receiver, performance_model as m, remote_command as c
from .guest_transport import process, ssh_args


def pack(root, source):
    root = Path(root)
    files = {name:base64.b64encode((root/name).read_bytes()).decode() for name in receiver.INPUTS}
    files['scripts/__init__.py'] = ''
    files['helper.py'] = base64.b64encode((root/'scripts/v51/guest_helper.py').read_bytes()).decode()
    raw = m.canonical(dict(schema='gse-v51-helper-payload-v1', source=source, files=files))
    m.need(len(raw) <= receiver.MAX_BYTES, 'helper package bound'); return raw


def describe(raw, binding, provider, access):
    from .guest_setup import access as validate_access
    c.validate_binding(binding); validate_access(access)
    m.need(binding['attempt'] == access['attempt'] == provider['attempt'] and
           binding['node'] == 'node-'+str(provider['node']), 'helper request owner')
    value = receiver.descriptor(dict(schema='gse-v51-helper-delivery-v1', binding=binding,
        instanceId=provider['instanceId'], diskId=provider['diskId'], guestAccessSha256=m.sha(m.canonical(access)),
        payloadSha256=m.sha(raw), payloadBytes=len(raw)))
    receiver.payload(raw, value); return value


class Endpoint:
    """Cloud routing is closed; qualification uses loopback and one monotonic clock.

    A different host's monotonic epoch cannot be used here. Remote-host budget
    translation and privileged admission must be qualified before opening IAP.
    """
    offline = False
    def __init__(self, target, parent, uid): self.target, self.parent, self.uid = target, str(parent), uid
    def argv(self, remote): return ssh_args(self.target, remote)
    def exchange(self, action, value, data, deadline):
        m.need(self.offline is True, 'live helper delivery disabled pending paid admission')
        m.need(value['instanceId'] == self.target['instanceId'], 'helper pinned instance mismatch')
        remaining = deadline-time.monotonic(); m.need(0 < remaining <= 600, 'helper original deadline')
        encoded = base64.b64encode(m.canonical(value)).decode()
        remote = ['python3', '-I', '-c', Path(receiver.__file__).read_text(), action, self.parent, encoded, str(self.uid), str(deadline)]
        raw = process(self.argv(remote), data, deadline, maximum=4096, request_maximum=receiver.MAX_BYTES)
        return m.strict_json(raw)


def deliver(endpoint, value, raw, deadline, *, clock=time.monotonic, sleep=time.sleep):
    receiver.descriptor(value); files = receiver.payload(raw, value)
    m.need(endpoint.offline is True and clock() < deadline, 'helper delivery scope/deadline')
    answer = None
    try: answer = endpoint.exchange('install', value, raw, deadline)
    except (ConnectionError, TimeoutError): pass
    while True:
        if answer is not None:
            expected = receiver.envelope(value, answer.get('state'))
            m.need(all(answer.get(k) == v for k, v in expected.items()) and
                   all(answer.get(k) is False for k in ('paidCloud', 'realBlockDeviceWritten', 'fullRemoteQualification')),
                   'helper response identity')
            m.need(answer['state'] in ('SUCCEEDED', 'FAILED', 'UNCERTAIN', 'NOT_FOUND'), 'helper response state')
            if answer['state'] in ('SUCCEEDED', 'FAILED'):
                if answer['state'] == 'SUCCEEDED':
                    m.need(answer.get('inventory') == dict(files=len(files), decodedBytes=sum(map(len, files.values()))),
                           'helper response inventory')
                m.need(clock() < deadline, 'helper late receipt'); return answer
        left = deadline-clock(); m.need(left > 0, 'helper unresolved; never reinstall')
        sleep(min(.05, left)); m.need(clock() < deadline, 'helper unresolved; never reinstall')
        try: answer = endpoint.exchange('query', value, b'', deadline)
        except (ConnectionError, TimeoutError): answer = None
