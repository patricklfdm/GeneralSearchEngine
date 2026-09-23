"""Mutate retained real evidence; summaries/checksums cannot replace raw truth."""
import copy
from pathlib import Path
from unittest.mock import patch
from . import performance_evidence as e, performance_physical as p, performance_model as m, performance_plan
from . import format_encoder, public_qualification_evidence, performance_failover
from .performance_harness import save


def run(root, remaining=lambda:None):
    root=Path(root);admitted=performance_plan.load(root/'plan.json');output=root/'negative-inputs';output.mkdir()
    results=[]
    def reject(name, action, witness):
        remaining()
        save(output/(name+'.json'),witness)
        try:action()
        except (ValueError,KeyError,TypeError) as error:
            results.append(dict(case=name,status='REJECTED',reason=str(error),inputSha256=m.sha(m.canonical(witness))))
        else:raise ValueError('performance negative accepted: '+name)
    mode='candidate-v5.1-automatic';directory=root/mode
    calls=e.read(directory/'calls.json');traces={n:e.lines(directory/(n+'-trace.jsonl')) for n in ('node-1','node-2','node-3')}
    for name in ('missing-call','failed-outcome','changed-query-order','duplicate-op-id','negative-latency'):
        rows=copy.deepcopy(calls)
        if name=='missing-call':rows.pop()
        elif name=='failed-outcome':rows[10]['outcome']='INDETERMINATE'
        elif name=='changed-query-order':
            row=next(r for r in rows if r['operation']=='QUERY');row['answer'].reverse();row['answerSha256']=m.sha(m.canonical(row['answer']))
        elif name=='duplicate-op-id':rows[1]['opId']=rows[0]['opId']
        else:rows[0]['apiEndNanos']=rows[0]['apiStartNanos']-1
        reject(name,lambda:e.calls(rows,admitted),rows)
    manifest_bytes=(directory/'node-1/manifest.gsr').read_bytes()
    manifest=dict(p.f.inspect(manifest_bytes,'MANIFEST'),digest=manifest_bytes[16:48].hex())
    target=next(r for r in calls if r['operation']=='GET')
    for name in ('missing-proof-force','missing-proof-ack','missing-basis-transfer','missing-voter','borrowed-read-barrier','changed-capture-cut','resealed-wrong-publication','leaked-reservation'):
        changed=copy.deepcopy(traces)
        if name=='missing-proof-force':
            changed={n:[r for r in rows if r['event']!='FORCE' or r['kind']!='PROOF'] for n,rows in changed.items()}
        elif name in ('missing-proof-ack','missing-basis-transfer'):
            kind='COMMIT_PROOF_ACK' if name=='missing-proof-ack' else 'BASIS_CHUNK'
            changed={n:[r for r in rows if r['event'] not in ('REPLY','RECEIVED') or
                        p.f.wire(p.raw(r['frame']),manifest)['type']!=kind] for n,rows in changed.items()}
        elif name=='missing-voter':changed.pop('node-1')
        elif name=='borrowed-read-barrier':
            row=next(r for r in changed[target['node']] if r['event']=='CLIENT_INVOKE' and r['opId']==target['opId'])
            capture=next(r for r in changed[target['node']] if r['event']=='READ_CAPTURED')
            row['order']=capture['order']
        elif name=='changed-capture-cut':
            row=next(r for rows in changed.values() for r in rows if r['event']=='READ_CAPTURED');row['sequence']+=1
        elif name=='resealed-wrong-publication':
            row=next(r for rows in changed.values() for r in rows if r['event']=='PUBLISHED')
            value=p.f.inspect(p.raw(row['snapshot']),'SNAPSHOT');value['applicationSequence']+=1
            import base64
            row['snapshot']=base64.b64encode(format_encoder.encode('SNAPSHOT',value)).decode()
        else:
            rows=changed[target['node']];rows.remove(next(r for r in rows if r['event']=='TRANSPORT' and r['transition'].endswith('_RELEASED')))
        reject(name,lambda:p.automatic(directory,calls,changed),changed)
    execution=e.read(root/'execution.json')
    record_path=directory/(target['node']+'-process.json');original=e.read(record_path)
    for name in ('wrong-artifact','changed-toolchain','serial-process','cross-clock-api'):
        record=copy.deepcopy(original)
        if name=='wrong-artifact':record['ready']['identity']['coreSha256']='0'*64
        elif name=='changed-toolchain':record['ready']['identity']['jvmArguments']=[]
        elif name=='serial-process':record['endNanos']=record['startNanos']-1
        else:
            next(v for v in record['exchanges'] if v['request']['command']=='call')['response']['call']['apiStartNanos']=-1
        real_read=e.read
        def altered(path):
            return record if Path(path)==record_path else real_read(path)
        def action():
            with patch.object(e,'read',altered):e.process(directory,mode,target['node'],execution['adapters'][mode],admitted)
        reject(name,action,record)
    samples_path=directory/(target['node']+'-samples.jsonl');original_samples=e.lines(samples_path)
    for name in ('missing-periodic-samples','missing-window-sample','leaked-close-permit'):
        changed=copy.deepcopy(original_samples)
        if name=='missing-periodic-samples':changed=[r for r in changed if r['boundary']!='periodic']
        elif name=='missing-window-sample':changed=[r for r in changed if r['boundary']!='window-start']
        else:changed[-1]['queues']['admissionAvailable']=3
        for i,row in enumerate(changed,1):row['order']=i
        actual_lines=e.lines
        def altered_samples(path):return changed if Path(path)==samples_path else actual_lines(path)
        def action():
            with patch.object(e,'lines',altered_samples):e.process(directory,mode,target['node'],execution['adapters'][mode],admitted)
        reject(name,action,changed)
    configured_root=root/'published-v5.0-configured'
    configured_calls=e.read(configured_root/'calls.json')
    configured_traces={n:e.lines(configured_root/(n+'-trace.jsonl')) for n in ('node-1','node-2','node-3')}
    for name,event in (('configured-missing-publication','AFTER_APPLICATION_PUBLICATION'),('configured-missing-actual-peer','REPLY')):
        changed={n:[r for r in rows if r['event']!=event] for n,rows in configured_traces.items()}
        reject(name,lambda:e.configured_physical(configured_root,configured_calls,changed),changed)
    fault_root=root/'failover';fault=e.read(fault_root/'receipt.json');history=e.read(fault_root/'history.json')
    for name in ('forged-killed-process','changed-pre-reopen-archive','forged-rejoin-cut'):
        receipt=copy.deepcopy(fault)
        if name=='forged-killed-process':receipt['fault']['pid']+=1
        elif name=='changed-pre-reopen-archive':receipt['fault']['retained']['sha256']='0'*64
        else:receipt['rejoin']['through']=193
        reject(name,lambda:performance_failover.validate(fault_root,receipt,history,admitted),receipt)
    for result in public_qualification_evidence.negatives(fault_root,history):
        results.append(dict(case='small-'+result['case'],status='REJECTED',checks=result['rejected']))
    save(root/'negatives.json',results)
    return results
