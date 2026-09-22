"""Bounded real transport saturation and delayed force through public JVMs."""
import argparse
import base64
import json
import socket
import time
import uuid
from . import public_qualification_harness as q, public_qualification_evidence as physical
from . import public_fault_harness as fault, public_protocol_harness as protocol
from . import public_promise_harness as matrix, public_recovery_harness as recovery
from . import public_bounds_harness as wire, public_history, public_pressure_evidence as evidence
from .storage_harness import need, save

CASES = ('outbound-saturation', 'inbound-saturation', 'slow-follower-accept', 'slow-follower-proof', 'slow-leader-accept')


def scenario(root, cp, case):
    root.mkdir(); workers = {}; history = []; expected = []; sockets = []
    receipt = dict(status='FAIL', case=case, publicRuntime=True)
    (root/'pressure-evidence').touch(); (root/'promise-evidence').touch(); (root/'chunk-bytes.txt').write_text('4096\n')
    if case == 'slow-leader-accept': (root/'bounds-profile.txt').write_text('pressure\n')
    def start(node, generation=1):
        workers[node] = q.Worker(root, node, cp, history, generation); return workers[node]
    def docs(tag): return [dict(id=tag+i, value=f'tag-{tag+i}-'+'x'*512) for i in (0, 1)]
    def write(active, tag): active.call('addAll', documents=docs(tag)); expected.extend(docs(tag)); return history[-1]['opId']
    def rows(node, event): return [r for r in fault.rows(root, node) if r['event'] == event]
    def release():
        fault.replace(root/'pressure-rules.txt', ''); (root/'pressure-release').touch()
        for node in workers: (root/(node+'-release')).touch()
    try:
        q.command(['java', '-cp', cp, q.PACKAGE+'admission.PublicRuntimeConsumer', root, 'setup'], root, 'public-bootstrap')
        if case.endswith('saturation'):
            protocol.network(root, [f'{n} node-3 BEFORE_REQUEST_WRITE PREPARE' for n in ('node-1','node-2')])
        for node in protocol.NODES: start(node)
        leader, active = fault.leader(workers); need(leader != 'node-3', 'delayed voter campaigned')
        protocol.network(root, [])
        receipt.update(leader=leader, target=leader if case == 'slow-leader-accept' else 'node-3')
        for tag in (10, 20, 30): write(active, tag)
        protocol.read_after_recovery(workers, expected)
        index = active.call('status')['provenIndex']
        fault.wait_for(lambda: all(w.call('status')['provenIndex'] >= index for w in workers.values()), 'pressure seed prefix not retained')
        proof = next(r['record'] for r in reversed(rows(leader, 'FORCE')) if r['kind']=='PROOF')
        peer = next(r['voter'] for r in evidence.a.f.inspect(evidence.a.raw(proof),'PROOF')['receipts'] if r['voter']!=leader)
        receipt['seedProof']=proof; receipt['quorumPeer']=peer
        if case.startswith('slow-follower'): receipt['target']=peer
        if case.endswith('saturation'): need(peer!='node-3','pressure peer is in active write quorum')
        target = receipt['target']; receipt['pressureStartNanos'] = time.monotonic_ns()
        if case == 'outbound-saturation':
            fault.replace(root/'pressure-rules.txt', f'{leader} {target} BEFORE_REQUEST_WRITE *\n')
            fault.wait_for(lambda: len(rows(leader, 'PRESSURE_HELD')) == 2, 'two outbound lanes not occupied')
            full = max(r['order'] for r in rows(leader, 'PRESSURE_HELD'))
            receipt['duringWrite'] = write(active, 40)
            fault.wait_for(lambda: any(r['transition'] == 'OUTBOUND_REJECTED' and r['order'] > full
                                      for r in rows(leader, 'TRANSPORT')), 'no actual outbound capacity rejection while held')
            protocol.read_after_recovery(workers, expected); receipt['duringRead'] = history[-1]['opId']
        elif case == 'inbound-saturation':
            source = 'node-2' if leader == 'node-1' else 'node-1'
            fault.replace(root/'pressure-rules.txt', f'{source} {target} BEFORE_RESPONSE_WRITE HANDSHAKE\n')
            manifest = json.loads((root/target/'manifest.gsr').read_bytes()[48:]); mdigest=(root/target/'manifest.gsr').read_bytes()[16:48].hex()
            port = int((root/'ports.txt').read_text().splitlines()[2]); probes=[]
            def frame(sequence):
                return wire.encode_wire(dict(protocol='gse-replication/1.2', groupId=manifest['groupId'], configurationId=manifest['configurationId'],
                    manifestDigest=mdigest, epoch=1, proposer=None, incarnationId='00000000-0000-0000-0000-000000000000', sender=source,
                    recipient=target, type='HANDSHAKE', traceId=str(uuid.uuid4()), eventSequence=sequence, payload=dict(mode='AUTOMATIC')))
            for i in range(32):
                if len(rows(target, 'PRESSURE_HELD')) == 8: break
                data=frame(i+1); connection=socket.create_connection(('127.0.0.1',port),timeout=3); sockets.append(connection)
                try: connection.sendall(data)
                except (BrokenPipeError,ConnectionResetError): pass
                probes.append(base64.b64encode(data).decode()); save(root/'pressure-probes.json', probes)
                # A normal runtime exchange may briefly occupy a slot; allow its
                # bounded completion, then try another probe without discarding evidence.
                began=time.monotonic(); count=len(rows(target,'PRESSURE_HELD'))
                while time.monotonic()-began < .15 and len(rows(target,'PRESSURE_HELD')) <= count: time.sleep(.01)
            need(len(rows(target,'PRESSURE_HELD')) == 8, 'eight inbound reservations not occupied')
            data=frame(100)
            try: reply,terminal=wire.exchange(port,data)
            except (BrokenPipeError,ConnectionResetError): reply,terminal=b'','RESET'
            receipt['rejectedProbe']=dict(request=base64.b64encode(data).decode(),response=base64.b64encode(reply).decode(),terminal=terminal)
            need(not reply and terminal in ('EOF','RESET'), 'saturated inbound endpoint did not close probe')
            receipt['duringWrite']=write(active,40); protocol.read_after_recovery(workers,expected);receipt['duringRead']=history[-1]['opId']
        else:
            kind='PROOF' if case.endswith('proof') else 'ACCEPT'; cut=kind+'_AFTER_WRITE'
            fault.replace(root/(target+'-arm.txt'), cut+'\npause\n')
            pending=active.send('addAll',documents=docs(40));receipt['heldOperation']=history[-1]['opId']
            reached=fault.wait_for(lambda: next(iter(rows(target,'CUT_REACHED')),None), 'slow force cut not reached')
            need(reached['cut']==cut and reached['pid']==workers[target].proc.pid,'wrong slow force process')
            receipt['cut']=reached; receipt['cutObservedNanos']=time.monotonic_ns(); paused=time.monotonic()
            if case == 'slow-leader-accept':
                rejected=[]
                for kind,values in [('addAll',dict(documents=docs(90))),('read',{})]:
                    result=active.send(kind,**values).result(timeout=5);rejected.append(history[-1]['opId'])
                    need(result is not None and result.get('reasonCode')=='CAPACITY_EXCEEDED' and result['outcome']==('NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE'),'slow-force admission classification')
                receipt['rejectedOperations']=rejected
            else:
                result=pending.result(timeout=20)
                need(result is not None and result['outcome']=='INDETERMINATE' and result.get('reasonCode') in protocol.READ_REJECTIONS,
                     'slow quorum force must preserve indeterminate outcome')
            while time.monotonic()-paused < 1.4: time.sleep(.02)
        receipt['releaseNanos']=time.monotonic_ns(); release()
        if case.startswith('slow-'):
            result=pending.result(timeout=20)
            need(result is not None and (result['outcome']=='SUCCESS' or result['outcome']=='INDETERMINATE' and
                 result.get('reasonCode') in protocol.READ_REJECTIONS),'unexpected released force outcome')
            # Resolve one uncertain atomic bulk with a fresh public read. Never
            # replay the write or infer its application from a role/status hint.
            for _ in range(4):
                leader,active=fault.leader(workers); observed=active.send('read').result(timeout=35)
                need(observed is not None,'force recovery read disconnected')
                if observed['outcome']=='SUCCESS':
                    allowed=[expected+docs(40)] if result['outcome']=='SUCCESS' else [expected,expected+docs(40)]
                    need(observed['documents'] in allowed,'uncertain bulk recovered a partial/unexpected projection')
                    expected=list(observed['documents']);receipt['resolvedRead']=history[-1]['opId'];break
                need(observed['outcome']=='NOT_APPLICABLE' and observed.get('reasonCode') in protocol.READ_REJECTIONS,'unexpected force recovery read failure')
            else:raise ValueError('force recovery read did not stabilize')
        for connection in sockets: connection.close()
        sockets.clear()
        leader,active=protocol.read_after_recovery(workers,expected)
        receipt['resumedWrite']=write(active,50);protocol.read_after_recovery(workers,expected)
        index=active.call('status')['provenIndex']
        fault.wait_for(lambda: workers[target].call('status')['provenIndex'] >= index,'released pressure voter did not recover')
        active.stop();del workers[leader];receipt['retained']=recovery.archive(root,leader)
        start(leader,2);protocol.read_after_recovery(workers,expected)
        receipt['expected']=expected
    except BaseException as error:receipt['failure']=str(error);raise
    finally:
        release()
        for connection in sockets:connection.close()
        errors=[]
        for worker in workers.values():
            try:worker.stop()
            except Exception as error:errors.append(str(error))
        if errors:receipt['cleanupErrors']=errors
        save(root/'history.json',history);save(root/'receipt.json',receipt)
        need(not errors,'pressure cleanup: '+str(errors))
    try:
        traces=physical.traces_at(root)
        receipt['history']=public_history.check(history);receipt['physical']=physical.physical(root,history,traces)
        receipt['pressure']=evidence.validate(root,traces,history,receipt)
        receipt['negatives']=physical.negatives(root,history)+evidence.negatives(root,traces,history,receipt)
        receipt['status']='PASS'
    except BaseException as error:receipt['failure']=str(error);raise
    finally:save(root/'receipt.json',receipt)
    return receipt


def run(output,only=None):
    return matrix.run_matrix(output,only,cases=CASES,scenario_runner=scenario,execution='public-transport-pressure')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only');a=p.parse_args();run(a.output,a.only)
