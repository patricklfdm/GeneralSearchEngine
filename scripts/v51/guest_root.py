"""Controller root admission and delivery; native cloud execution remains closed."""
import base64
from copy import deepcopy
from pathlib import Path
from . import guest_delivery as delivery, guest_delivery_receiver as receiver
from . import guest_root_admission as admission, guest_root_policy, guest_root_receiver
from . import guest_transport, performance_model as m, remote_command as c


def trusted_source():
    # All executable receiver bytes are from this controller's checkout. This
    # bootstrap never imports the helper until its closed payload was verified.
    modules = {module.__name__.rsplit('.', 1)[1]: Path(module.__file__).read_text()
               for module in (receiver, guest_root_policy, guest_root_receiver)}
    return ("import sys,types\n"
            "p=types.ModuleType('trusted');p.__path__=[];sys.modules['trusted']=p\n"
            "for name,source in "+repr(modules)+".items():\n"
            " q=types.ModuleType('trusted.'+name);q.__package__='trusted';sys.modules[q.__name__]=q\n"
            " exec(compile(source,'<trusted-controller-'+name+'>','exec'),q.__dict__)\n"
            "sys.modules['trusted.guest_root_receiver'].main()\n")


class Endpoint(delivery.Endpoint):
    def __init__(self, target, plan):
        admission.validate_plan(plan)
        m.need(target['instanceId'] == plan['delivery']['instanceId'] and target['user'] == plan['access']['user'],
               'root SSH target identity')
        super().__init__(target, admission.PARENT, 0)
        self.plan, self.observations, self.failures = deepcopy(plan), [], []

    def remote(self, action, token):
        return ['sudo', '-n', '-u', 'root', '-g', 'root', '--', 'python3', '-I', '-c', trusted_source(),
                action, base64.b64encode(m.canonical(self.plan)).decode(), token]

    def _call(self, action, value, data, deadline, token):
        m.need(value == self.plan['delivery'], 'root delivery plan changed')
        try:
            raw = guest_transport.process(self.argv(self.remote(action, token)), data, deadline,
                                          maximum=4096, request_maximum=receiver.MAX_BYTES)
        except Exception as error:
            if len(self.failures) < 8: self.failures.append(dict(action=action, type=type(error).__name__, message=str(error)[:2000]))
            raise
        result = m.strict_json(raw)
        m.need(type(result) is dict and set(result) == {'schema', 'planSha256', 'rootUid', 'answer'} and
               result['schema'] == 'gse-v51-root-transport-v1' and result['planSha256'] == m.sha(m.canonical(self.plan)) and
               type(result['rootUid']) is int and result['rootUid'] == 0, 'root transport identity')
        if len(self.observations) < 32: self.observations.append(dict(action=action, **result))
        return result['answer']


class Transport:
    """Verify root helper before the supplied offline volume adapter is entered."""
    offline = True

    def __init__(self, provider, lease, volume, endpoint_factory=Endpoint):
        m.need(provider.api.offline is True and volume.offline is True, 'native root startup disabled')
        self.provider, self.lease, self.volume, self.endpoint_factory = provider, lease, volume, endpoint_factory
        self.helper = delivery.pack(Path(__file__).resolve().parents[2], provider.req['source'])

    def prepare(self, facts, target, output, deadline, *, recheck):
        recheck()
        plan = admission.plan(self.provider.req, self.lease(), facts, self.provider.guest_access, self.helper)
        endpoint = self.endpoint_factory(target, plan)
        record = dict(schema='gse-v51-root-startup-v1', plan=plan, status='FAIL', paidCloud=False,
                      nativeWritesEnabled=False, fullRemoteQualification=False)
        try:
            answer = delivery.deliver(endpoint, plan['delivery'], self.helper, deadline)
            m.need(answer['state'] == 'SUCCEEDED', 'root helper installation failed')
            checked = endpoint.exchange('check', plan['delivery'], b'', deadline)
            m.need(checked == answer, 'root self-check receipt changed')
            recheck(); record.update(status='PASS', receipt=answer)
        except Exception as error:
            record['failure'] = dict(type=type(error).__name__, message=str(error)[:2000]); raise
        finally:
            record.update(deadline=endpoint.budget, observations=endpoint.observations, transportFailures=endpoint.failures)
            c.write_once(Path(output).with_name('root-'+Path(output).name+'.json'), record, maximum=262144)
        return self.volume.prepare(facts, target, output, deadline, recheck=recheck)
