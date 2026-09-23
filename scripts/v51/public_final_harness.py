"""Final public witnesses: crossed heartbeats and disk-loss/new-group recovery."""
import argparse
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_history, storage_inspector as storage, controls
from .storage_harness import ROOT, need, save
from scripts.v50.offline_harness import REPLICATION

CASES = ('heartbeat-request', 'heartbeat-response', 'one-disk-loss', 'two-disk-loss')
CUTS = {'heartbeat-request': 'WIRE_AFTER_REQUEST_READ_HEARTBEAT',
        'heartbeat-response': 'WIRE_AFTER_RESPONSE_READ_HEARTBEAT'}


class Group:
    def __init__(self, root, cp):
        self.root, self.cp = root, cp
        self.workers, self.history, self.expected, self.starts = {}, [], [], []
    def start(self, node, generation=1):
        began = time.monotonic_ns()
        worker = q.Worker(self.root, node, self.cp, self.history, generation, consumer='lifecycle')
        self.workers[node] = worker
        self.starts.append(dict(node=node, generation=generation, pid=worker.proc.pid,
                                startNanos=began, readyNanos=time.monotonic_ns()))
        return worker
    def read(self, workers=None):
        return protocol.read_after_recovery(self.workers if workers is None else workers, self.expected)
    def write(self, worker, tag):
        docs = [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
        worker.call('addAll', documents=docs); self.expected.extend(docs)
        return self.history[-1]['opId']
    def close(self):
        errors=[]
        for worker in list(self.workers.values()):
            try: worker.stop()
            except Exception as error: errors.append(str(error))
        self.workers.clear()
        need(not errors, 'final coverage worker cleanup: '+str(errors))
    def save(self):
        save(self.root/'history.json', self.history); save(self.root/'worker-starts.json', self.starts)
    def application(self): return [h for h in self.history if h['kind'] in ('read', 'addAll')]


def bootstrap(root, cp, imported=False):
    q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root,
               'setup-import' if imported else 'setup'], root, 'public-bootstrap')


def heartbeat(group, receipt):
    root, workers, case = group.root, group.workers, receipt['case']
    old, active = group.read(); receipt['oldLeader'] = old
    need(old != 'node-3', 'delayed voter campaigned')
    target = 'node-3' if case == 'heartbeat-request' else old
    receipt['target'] = target
    fault.replace(root/(target+'-arm.txt'), CUTS[case]+'\npause\n')
    pause = fault.wait_for(lambda: next((r for r in fault.rows(root, target) if r['event']=='CUT_REACHED'), None), 'heartbeat pause absent')
    receipt['pause'] = pause
    boundary = next(r for r in reversed(fault.rows(root, target)) if r['order'] < pause['order'] and r['event']==CUTS[case])
    epoch = json.loads(storage.raw(boundary['request'])[48:])['epoch']; receipt['oldEpoch'] = epoch
    fault.partition(root, old)
    new, service = group.read({n:w for n,w in workers.items() if n!=old})
    receipt['majorityRead'] = group.history[-1]['opId']; receipt['majorityWrite'] = group.write(service, 50)
    receipt['newLeader'] = new
    fault.partition(root)
    receipt['higherPromise'] = fault.wait_for(lambda: next((r for r in fault.rows(root, target)
        if r['event']=='FORCE' and r['kind']=='PROMISE' and storage.f.inspect(storage.raw(r['record']), 'PROMISE')['epoch']>epoch), None), 'held heartbeat not fenced')
    # The old leader must also process the new fence before refusal is tested.
    fault.wait_for(lambda: workers[old].call('status')['epoch']>epoch, 'old leader not fenced')
    (root/(target+'-release')).touch()
    event = 'REPLY' if case=='heartbeat-request' else 'RECEIVED'
    receipt['delivered'] = fault.wait_for(lambda: next((r for r in fault.rows(root, target)
        if r['event']==event and r.get('request')==boundary['request'] and r['order']>pause['order']), None), 'held heartbeat not delivered')
    receipt['denied'] = []
    for kind, values in [('read', {}), ('addAll', dict(documents=[dict(id=999, value='must-not-appear')]))]:
        result = active.send(kind, **values).result(timeout=35)
        need(result and result['outcome']==('NOT_APPLICABLE' if kind=='read' else 'NOT_SUBMITTED'), 'retired leader served after heartbeat: '+str(result))
        receipt['denied'].append(group.history[-1]['opId'])
    workers.pop(old).stop(); receipt['retained'] = recovery.archive(root, old); group.start(old, 2)
    _, service = group.read(); receipt['laterWrite'] = group.write(service, 70)
    group.read(); receipt['finalRead'] = group.history[-1]['opId']; receipt['expected'] = group.expected


def published_control(root):
    controls.resolve(ROOT/'target/v51-controls')
    jar = ROOT/'target/v51-controls/general-search-engine-4.4.0.jar'
    classes = root/'control-classes'; classes.mkdir()
    source = ROOT/'general-search-engine-replication/src/test/java/io/github/patricklfdm/generalsearch/admission/AdmissionJson.java'
    cp = os.pathsep.join(map(str, (jar, REPLICATION, classes)))
    q.command(['javac', '-cp', cp, '-d', classes, source, ROOT/'scripts/v51/java/PublicRuntimeConsumer.java'], root, 'control-compile')
    result = q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'control'], root, 'published-v44')
    need('controlSource='+str(jar) in result.stderr.splitlines(), 'wrong published restore control')
    return dict(json.loads(result.stdout), jarSha256=storage.sha(jar.read_bytes()))


def disks(group, receipt):
    root, cp, workers = group.root, group.cp, group.workers
    # Both histories include a real retained restart before retiring disks.
    workers.pop('node-1').stop(); group.start('node-1', 2)
    _, active = group.read()
    through = active.call('status')['provenIndex']
    fault.wait_for(lambda: all(w.call('status')['provenIndex']>=through for w in workers.values()), 'pre-loss prefix not retained')
    backup = active.call('backup', target=str(root/'backup'))
    receipt['backupOperation'] = group.history[-1]['opId']; receipt['backup'] = backup
    receipt['backupInventory'] = storage.inventory(root/'backup'); receipt['backupDocuments'] = list(group.expected)
    victims = ['node-3'] if receipt['case']=='one-disk-loss' else ['node-2', 'node-3']
    (root/'lost').mkdir(); receipt['losses'] = []; receipt['retiredVoters'] = {}; receipt['probes'] = {}
    for node in victims:
        victim = workers.pop(node); victim.stop(kill=True)
        before = storage.inventory(root/node); storage.inspect(root/node)
        (root/node).rename(root/'lost'/node)
        receipt['retiredVoters'][node] = before
        receipt['losses'].append(dict(node=node, pid=victim.proc.pid, exitCode=victim.proc.returncode, atNanos=time.monotonic_ns()))
        receipt['probes'][node] = []
        for attempt in (1, 2):
            result = q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicLifecycleConsumer', root, node[-1], 'probe'], root, f'absent-{node}-{attempt}')
            receipt['probes'][node].append(json.loads(result.stdout))
            need(not (root/node).exists(), 'missing voter silently re-enrolled')
        need(storage.inventory(root/'lost'/node)==before, 'retired disk changed')
    if len(victims)==1:
        _, active = group.read(); receipt['survivorWrite'] = group.write(active, 50)
        group.read(); receipt['survivorRead'] = group.history[-1]['opId']
        # The new group deliberately restores the earlier verified backup cut;
        # this later successful write must not be fabricated into that backup.
    else:
        receipt['denied'] = []
        for kind, values in [('read', {}), ('addAll', dict(documents=[dict(id=999, value='must-not-appear')]))]:
            result = workers['node-1'].send(kind, **values).result(timeout=35)
            need(result and result['outcome']==('NOT_APPLICABLE' if kind=='read' else 'NOT_SUBMITTED'), 'minority admitted public operation: '+str(result))
            receipt['denied'].append(group.history[-1]['opId'])
    group.close(); group.save()
    receipt['control'] = published_control(root)
    newroot = root/'new-group'; newroot.mkdir()
    (newroot/'group-id.txt').write_text('22222222-2222-2222-2222-222222222222\n')
    shutil.copytree(root/'backup', newroot/'import-backup'); bootstrap(newroot, cp, True)
    new = Group(newroot, cp); new.expected = list(receipt['backupDocuments'])
    try:
        for node in protocol.NODES: new.start(node)
        _, active = new.read(); receipt['newInitialRead'] = new.history[-1]['opId']
        for tag in (110, 120, 130): new.write(active, tag)
        new.workers.pop('node-1').stop(); new.start('node-1', 2)
        new.read(); receipt['newFinalRead'] = new.history[-1]['opId']; receipt['newExpected'] = new.expected
    finally:
        try: new.close()
        finally: new.save()
    initial = receipt['backupDocuments']; application = new.application()
    receipt['newHistory'] = public_history.check(application, initial_documents=initial)
    receipt['newPhysical'] = physical.physical(newroot, application)
    receipt['newNegatives'] = physical.negatives(newroot, application, initial_documents=initial)
    need(storage.inventory(root/'backup')==receipt['backupInventory'], 'restore modified source backup')


def scenario(root, cp, case):
    root.mkdir(); group = Group(root, cp); receipt = dict(case=case, status='FAIL', publicRuntime=True)
    (root/'promise-evidence').touch(); (root/'final-coverage-evidence').touch(); (root/'chunk-bytes.txt').write_text('4096\n')
    try:
        bootstrap(root, cp)
        for node in protocol.NODES: group.start(node)
        _, active = fault.leader(group.workers)
        for tag in (10, 20, 30): group.write(active, tag)
        group.read()
        if case in CUTS: heartbeat(group, receipt)
        else: disks(group, receipt)
    except BaseException as error: receipt['failure'] = str(error); raise
    finally:
        fault.partition(root)
        for node in protocol.NODES: (root/(node+'-release')).touch()
        try: group.close()
        finally: group.save(); save(root/'receipt.json', receipt)
    try:
        from . import public_final_evidence as evidence
        application = group.application(); traces = physical.traces_at(root)
        receipt['history'] = public_history.check(application)
        receipt['physical'] = physical.physical(root, application, traces, retired_voters=receipt.get('retiredVoters'))
        receipt['scenario'] = evidence.validate(root, traces, group.history, receipt)
        receipt['negatives'] = physical.negatives(root, application, retired_voters=receipt.get('retiredVoters'))+evidence.negatives(root, traces, group.history, receipt)
        receipt['status'] = 'PASS'
    except BaseException as error: receipt['failure'] = str(error); raise
    finally: save(root/'receipt.json', receipt)
    return receipt


def run(output, only=None):
    module=ROOT/'general-search-engine-replication'; prerequisites={}
    for name,count in [('V51VersionBoundaryTest',3),('V51AutomaticTransportTest',6)]:
        report=module/f'target/surefire-reports/TEST-io.github.patricklfdm.generalsearch.replication.{name}.xml'
        source=module/f'src/test/java/io/github/patricklfdm/generalsearch/replication/{name}.java'
        suite=ET.parse(report).getroot()
        need(int(suite.attrib['tests'])>=count and all(int(suite.attrib.get(k,0))==0 for k in ('failures','errors','skipped')),
             'final coverage Java prerequisite: '+name)
        need(report.stat().st_mtime_ns>=source.stat().st_mtime_ns, 'stale final Java prerequisite: '+name)
        prerequisites[name]=dict(tests=int(suite.attrib['tests']),sha256=storage.sha(report.read_bytes()))
    receipt=matrix.run_matrix(output, only, cases=CASES, scenario_runner=scenario, execution='public-final-coverage', consumer_sources=('PublicLifecycleConsumer.java',))
    receipt['javaTests']=prerequisites; save(Path(output)/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('output'); p.add_argument('--only'); a=p.parse_args(); run(a.output, a.only)
