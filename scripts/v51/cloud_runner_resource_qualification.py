"""Runner credential/request boundary through creation, IAP and expiry cleanup.

All provider and IAP traffic is synthetic. Private fixture keys live outside
retained evidence; no gcloud process, network, disk formatting or engine runs.
"""
import argparse
from copy import deepcopy
from pathlib import Path
import tempfile
from . import cloud_runner_resources as r, cloud_runner_admission_qualification as q
from . import cloud_experiment_resource_qualification as resources, guest_setup
from . import cloud_native_authority as n, cloud_gcp as g, performance_model as m
from .remote_command import write_once

CASES = ('complete', 'lost-insert-1', 'lost-insert-11', 'lost-insert-13', 'lost-identity-13',
         'lost-ledger', 'lost-context', 'iap-denied', 'guest-id-drift', 'iap-deadline')


class Probe:
    offline = True
    def __init__(self, clock, fault=None): self.clock, self.fault, self.calls = clock, fault, []
    def identity(self, target, deadline):
        self.calls.append(dict(instanceId=target['instanceId'], deadline=deadline))
        # Exercise real key/known-host validation and fixed SSH shape, no process.
        r.iap.transport.ssh_args(target, r.iap.COMMAND)
        if self.fault == 'iap-denied': raise ConnectionError('synthetic IAP denial')
        if self.fault == 'iap-deadline': self.clock.sleep(61)
        return ('999999999' if self.fault == 'guest-id-drift' else target['instanceId']).encode()


def fixture(root, private, fault=None):
    f = q.fixture(root); value = f['value']; old = value['resourcePlan']
    guest = guest_setup.generate(Path(private), old['request']['attempt']); f['key'] = Path(private)/'identity'
    f['value'] = r.admission.plan(f['cfg'],value['artifacts'],guest,value['prices'],old['baseline'],
        sequence=old['request']['sequence'],now=old['request']['createdAt'],maximum_cost=q.COST)
    f['approved'] = r.admission.approval_template(f['value']); f['approved']['confirmed'] = True
    f['env']['RUNNER_EXPERIMENT_CONFIRMATION'] = f['approved']['planSha256']
    http = f['http']
    def hook(method,path,query,body):
        if method != 'GET': return None
        if path.path.endswith('/getGuestAttributes'):
            return http.reply(dict(queryPath='hostkeys/',queryValue=dict(items=[
                dict(namespace='hostkeys',key='ssh-ed25519',value=guest['publicKey'].split()[1])])))
        collection, identity = path.path.rsplit('/',1)
        match = next(((key,value) for key,value in http.resources.items() if key.rsplit('/',1)[0] == collection and
                      (key == path.path or value['id'] == identity)),None)
        if match is None: return None
        key,value = match; value = deepcopy(value)
        if '/instances/' in key:
            value['status'] = 'RUNNING'; value['networkInterfaces'][0]['networkIP'] = '10.0.0.'+value['name'][-1]
        elif '/disks/' in key:
            value['status'] = 'READY'; vm = key.split('/disks/')[0]+'/instances/'+value['name'].rsplit('-',1)[0]
            value['users'] = ['https://compute.googleapis.com'+vm] if vm in http.resources else []
        return http.reply(value)
    http.hook = hook; f['probe'] = Probe(f['clock'],fault)
    return f


def prepare(f, output):
    return r.prepare_offline(f['cfg'],f['env'],q.pq.SOURCE,f['preflight'],f['root'],f['value'],f['approved'],
        f['originals'],f['key'],output,transport=q.auth.Provider(f['http']),issuer=f['issuer'],descriptor=f['descriptor'],
        clock=f['clock'].seconds,wall=f['clock'].wall,sleep=f['clock'].sleep,get=lambda p:deepcopy(f['data'][p]),
        binding=f['binding'],probe=f['probe'],controls=f['controls'])


def qualify(output):
    output = Path(output); output.mkdir(parents=True,exist_ok=False); cases=[]
    with tempfile.TemporaryDirectory(prefix='gse-v51-qualifier-keys-') as private:
        for name in CASES:
            root = output/name; root.mkdir()
            f = fixture(root/'inputs',Path(private)/name,name)
            resources.inject(name,f['clock'],f['http'])
            result = prepare(f,root/'prepare')
            m.need(result['status'] == ('PARTIAL' if name == 'complete' else 'FAIL'), 'Runner resource qualification result: '+name)
            if name.startswith('lost-'):
                stage = r.admission.read(root/'prepare/resources/receipt.json')
                phase = 'identity' if name.startswith('lost-identity-') else 'insert' if name.startswith('lost-insert-') else name.removeprefix('lost-')
                m.need(stage['failure'] == dict(phase=phase,type='ConnectionError') and not f['probe'].calls,
                       'Runner unrelated resource failure: '+name)
            elif name != 'complete':
                expected_error = 'ConnectionError' if name == 'iap-denied' else 'ValueError'
                m.need(result['failure'] == dict(phase='iap',type=expected_error) and len(f['probe'].calls) == 1,
                       'Runner unrelated IAP failure: '+name)
            m.need(result['fullRemoteQualification'] is False and result['paidCloud'] is False and
                   result['engineWorkloadExecuted'] is False, 'Runner qualification scope')
            expected = int(name.rsplit('-',1)[1]) if name.startswith(('lost-insert-','lost-identity-')) else 0 if name in ('lost-ledger','lost-context') else 13
            m.need(f['http'].inserts == expected, 'Runner once-only inserts: '+name)
            inserts = [v for v in f['http'].requests if v['method'] == 'POST' and v['path'].startswith('/compute/')]
            m.need(len(inserts) == len({v['query']['requestId'] for v in inserts}) == expected, 'Runner duplicate insert: '+name)
            saved = q.cleanup.snapshot(f['http'])
            req = f['value']['resourcePlan']['request']
            # Use original retained bytes via Store, not the local stage receipt.
            reader = r.h.Api(transport=f['http'],tokens=lambda _: 'offline',clock=f['clock'].seconds)
            store = g.Store(f['cfg']['provider'],reader,authority=n); lease = store.get(n.LEASE)[1]
            if name == 'complete':
                waiting, unchanged, _ = resources.replay(f['cfg']['provider'],q.pq.SOURCE,saved,root/'active',lease['startedAt'])
                m.need(waiting['status'] == 'WAITING' and unchanged == saved, 'Runner active cleanup protection')
            clean,after,calls = resources.replay(f['cfg']['provider'],q.pq.SOURCE,saved,root/'expired',lease['expiresAt']+lease['graceSeconds'])
            _,model,raw,_ = q.cleanup.restore(after); ledger = g.Store(f['cfg']['provider'],raw,authority=n).get(n.LEDGER)[1]
            cost,entries = n.inspect_ledger(ledger)
            m.need(clean['status'] == 'PASS' and not model.resources and n.LEASE not in model.objects and cost == q.COST and
                   entries[n.validate_request(req)]['status'] == 'FAIL', 'Runner cleanup/charged reservation: '+name)
            m.need(all(v['path'].rsplit('/',1)[1] in {value['id'] for value in saved['resources'].values()}
                       for v in calls if v['method'] == 'DELETE' and v['path'].startswith('/compute/')), 'Runner foreign cleanup')
            cases.append(dict(case=name,status='PASS',preparation=result['status'],inserts=expected,
                              iapProbes=len(f['probe'].calls),cleanup=clean['status'],retainedCostMicrousd=cost))
            print(m.canonical(cases[-1]).decode(),flush=True)
    summary=dict(schema='gse-v51-runner-resource-qualification-v1',status='PASS',cases=cases,
                 execution='offline-runner-resources-and-iap',paidCloud=False,fullRemoteQualification=False,engineWorkloadExecuted=False)
    write_once(output/'receipt.json',summary); return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');qualify(parser.parse_args().output)
