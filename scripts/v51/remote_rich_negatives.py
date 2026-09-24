"""Replay altered physical observations through the concurrent rich oracle."""
import copy
from pathlib import Path
from . import remote_rich_evidence as evidence, performance_physical as physical, performance_model as m
from .remote_rich_physical import Calls


def verify(root):
    root=Path(root);directory=root/'read-heavy-candidate-v5.1-automatic'
    calls=evidence.old.read(directory/'calls.json')
    traces={n:evidence.lines(directory,n+'-trace') for n in ('node-1','node-2','node-3')}
    manifest_bytes=(directory/'node-1/manifest.gsr').read_bytes()
    manifest=dict(physical.f.inspect(manifest_bytes,'MANIFEST'),digest=manifest_bytes[16:48].hex())
    active=calls[0]['node'];read=next(c for c in calls if c['operation']=='GET')
    caller=read['opId'];read_id=next(r['readId'] for r in traces[active] if r['event']=='PUBLIC_READ_INVOKE' and r['opId']==caller)
    cases=('missing-invocation','borrowed-invocation','unknown-read-id','changed-cut','changed-release',
           'missing-release','resealed-answer','missing-leader-proof','missing-proof-ack','failed-original-call')
    results=[]
    for case in cases:
        observed=copy.deepcopy(calls);changed={n:list(rows) for n,rows in traces.items()}
        rows=[]
        for original in changed[active]:
            row=original
            event=row['event'];own=row.get('readId')==read_id
            if case=='missing-invocation' and event=='PUBLIC_READ_INVOKE' and own:continue
            if case=='missing-release' and event=='READ_RELEASED' and own:continue
            if case=='missing-leader-proof' and event=='FORCE' and row['kind']=='PROOF':continue
            if case=='missing-proof-ack' and event=='RECEIVED':
                if physical.f.wire(physical.raw(row['frame']),manifest)['type']=='COMMIT_PROOF_ACK':continue
            if case=='borrowed-invocation' and event=='PUBLIC_READ_INVOKE' and own:
                row=dict(row,opId='not-an-issued-call')
            if case=='unknown-read-id' and event=='READ_CAPTURED' and own:row=dict(row,readId=999999)
            if case=='changed-cut' and event=='READ_CAPTURED' and own:row=dict(row,sequence=row['sequence']+1)
            if case=='changed-release' and event=='READ_RELEASED' and own:row=dict(row,index=row['index']+1)
            if case in ('resealed-answer','failed-original-call') and event=='CLIENT_RESULT' and row.get('opId')==caller:
                row=copy.deepcopy(row)
                if case=='resealed-answer':row['call'].update(answer='wrong captured document',answerSha256=m.sha(m.canonical('wrong captured document')))
                else:row['call']['outcome']='INDETERMINATE'
            rows.append(row)
        changed[active]=rows
        if case in ('resealed-answer','failed-original-call'):
            call=next(c for c in observed if c['opId']==caller)
            if case=='resealed-answer':call.update(answer='wrong captured document',answerSha256=m.sha(m.canonical('wrong captured document')))
            else:call['outcome']='INDETERMINATE'
        try:physical.automatic(directory,observed,changed,cloud_calls=Calls(observed))
        except (ValueError,KeyError) as error:results.append(dict(case=case,status='REJECTED',reason=str(error)))
        else:raise ValueError('accepted invalid concurrent evidence: '+case)
    return results
