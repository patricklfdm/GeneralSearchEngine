"""Independent force/receipt/publication oracle for the internal transition kernel."""
import base64
import copy
import json
from pathlib import Path
from . import format_inspector as f, recovery_inspector as recovery, storage_inspector as storage


def raw(value):return base64.b64decode(value,validate=True)
def digest(value):return value[16:48].hex()
def ballot(value):return {k:value[k] for k in ('epoch','proposer','incarnation')}


def validate(root,document=None):
    root=Path(root)
    document=document if document is not None else json.loads((root/'trace.json').read_text())
    f.need(document['schema']=='gse-v51-protocol-case-v1' and document['execution']=='automatic-transition-kernel-only'
           and document['publicRuntime'] is False,'kernel evidence provenance')
    manifest_raw=(root/'node-1/manifest.gsr').read_bytes()
    manifest=dict(f.inspect(manifest_raw,'MANIFEST'),digest=digest(manifest_raw))
    genesis=f.inspect((root/'node-1/genesis.gsr').read_bytes(),'GENESIS')
    nodes={m['node'] for m in manifest['members']}
    f.need(document['scenario'] in ('healthy','entry-chosen','hidden-proof','fenced','retry','restart'),'unknown protocol scenario')
    expected=nodes-{'node-1'} if document['scenario'] in ('entry-chosen','hidden-proof') else nodes
    f.need(len(document['views'])==len(expected) and {v['node'] for v in document['views']}==expected,'incomplete terminal voter evidence')
    reports={node:storage.inspect(root/node) for node in nodes}
    entries={};forced=set();grants={};accepted={};chosen={};requests={};delivered=set();published={};calls={};completed=set();activations=set()
    def frame(value,kind):return f.contextual_frame(raw(value),kind,manifest)
    def image(value):
        snapshot=frame(value,'SNAPSHOT');projection=raw(genesis['application']);sequence=manifest['baseSequence']
        for index,anchor in enumerate(snapshot['anchors'],1):
            key=anchor['entryDigest'];f.need(key in entries,'unobserved publication value')
            entry=entries[key]
            f.need(entry['index']==index and all(entry[k]==anchor[k] for k in ('operation','originEpoch','originIncarnation','payloadDigest')),'publication ancestry')
            f.need(chosen.get(index)==key,'publication value lacks observed entry quorum')
            if entry['operation']<=8:projection+=raw(entry['payload']);sequence+=1
        f.need(raw(snapshot['application'])==projection and snapshot['applicationSequence']==sequence,'independent application projection')
        return snapshot
    def check_message(message):
        f.need(message['sender'] in nodes and message['recipient'] in nodes and message['sender']!=message['recipient'],'message members')
        proposal=frame(message['ballot'],'PROMISE')
        if not message['response']:
            f.need(message['sender']==proposal['proposer'],'request proposer')
            key=(message['sender'],message['ballot'],message['id'])
            f.need(key not in requests or requests[key]==message,'changed exact request retry');requests[key]=message
            return
        key=(message['recipient'],message['ballot'],message['id']);f.need(key in requests,'response without request');request=requests[key]
        f.need(request['recipient']==message['sender'] and request['kind']==message['kind'] and request['ballot']==message['ballot'],'response correlation')
        promised=frame(message['promised'],'PROMISE')
        if not message['accepted']:return
        f.need(ballot(promised)==ballot(proposal),'acknowledgement promise')
        kind=message['kind'];node=message['sender']
        if kind=='PREPARE':
            f.need((node,'PROMISE',storage.sha(raw(message['ballot']))) in forced,'promise reply before force')
            payload=message['payload'];basis,_,_=recovery.basis(raw(payload['basis']),raw(payload['image']),manifest)
            f.need(basis['node']==node and basis['ballot']==ballot(proposal),'frozen basis response')
            image(frame(payload['image'],'IMAGE')['snapshot'])
        elif kind in ('ACCEPT','PROOF'):
            value=frame(request['payload'],kind)
            f.need((node,kind,storage.sha(raw(request['payload']))) in forced,'receipt before force')
            index=frame(value['entry'],'ENTRY')['index'] if kind=='ACCEPT' else value['index']
            bound=value['entryDigest'] if kind=='ACCEPT' else storage.sha(raw(request['payload']))
            expected=f.receipt(kind+'_ACK',manifest['digest'],node,proposal['epoch'],proposal['proposer'],proposal['incarnation'],index,bound)
            f.need(message['payload']==expected,'receipt identity')
    for row in document['trace']:
        event=row['event']
        if event=='FORCE':
            node,kind=row['node'],row['kind'];f.need(node in nodes,'force node');value=frame(row['record'],kind)
            forced.add((node,kind,storage.sha(raw(row['record']))))
            if kind=='PROMISE':
                f.need(node not in grants or value['epoch']>=grants[node]['epoch'],'promise regression');grants[node]=value
            elif kind=='ACCEPT':
                f.need(node in grants and ballot(grants[node])==ballot(value),'accept without current promise')
                entry=frame(value['entry'],'ENTRY');key=digest(raw(value['entry']));entries[key]=entry
                voters=accepted.setdefault((value['epoch'],value['incarnation'],entry['index'],key),set());voters.add(node)
                if len(voters)>=2:
                    f.need(entry['index'] not in chosen or chosen[entry['index']]==key,'conflicting chosen values');chosen[entry['index']]=key
            elif kind=='PROOF':
                f.need(node in grants and ballot(grants[node])==ballot(value),'proof without current promise')
                voters=accepted.get((value['epoch'],value['incarnation'],value['index'],value['entryDigest']),set())
                f.need({r['voter'] for r in value['receipts']}<=voters and len(voters)>=2,'proof before entry quorum')
            else:raise ValueError('unsupported force kind')
        elif event in ('SEND','DELIVER'):
            message=row['message'];check_message(message)
            if event=='DELIVER' and message['response'] and message['accepted'] and message['kind']=='PROOF':
                delivered.add((message['recipient'],message['ballot'],message['id']))
        elif event=='PUBLISH':
            node=row['node'];proposal=frame(row['ballot'],'PROMISE');snapshot=image(row['snapshot'])
            proof=frame(snapshot['terminalProof'],'PROOF');proof_raw=raw(snapshot['terminalProof'])
            f.need(ballot(proof)==ballot(proposal) and node==proposal['proposer'],'publication ballot')
            f.need((node,'PROOF',storage.sha(proof_raw)) in forced,'publication lacks local proof force')
            f.need(any(owner==node and (owner,request_ballot,request_id) in delivered and req['kind']=='PROOF'
                       and raw(req['payload'])==proof_raw for (owner,request_ballot,request_id),req in requests.items()),'publication before proof acknowledgement')
            index=len(snapshot['anchors']);published[node,index]=snapshot
            terminal=entries[snapshot['anchors'][-1]['entryDigest']]
            if terminal['operation']==9 and terminal['originEpoch']==proposal['epoch'] and terminal['originIncarnation']==proposal['incarnation']:
                activations.add((node,proposal['epoch']))
        elif event=='CALL':
            key=row['node'],row['request'];f.need(key not in calls,'duplicate logical request');calls[key]=raw(row['payload'])
        elif event=='COMPLETE':
            key=row['node'],row['request'];f.need(key in calls and key not in completed,'unbound/repeated completion');completed.add(key)
            if row['reason']=='SUCCESS':
                f.need((row['node'],row['index']) in published,'completion before publication')
                snapshot=published[row['node'],row['index']];entry=entries[snapshot['anchors'][-1]['entryDigest']]
                f.need(entry['operation']==1 and raw(entry['payload'])==calls[key],'completed request payload')
            else:f.need(row['outcome'] in ('NOT_SUBMITTED','INDETERMINATE'),'mutation failure outcome')
        else:raise ValueError('unsupported trace event')
    for view in document['views']:
        node=view['node']
        f.need(view['promisedEpoch']==reports[node]['promisedEpoch'] and view['provenIndex']==reports[node]['provenThrough'],'retained authority/status')
        if view['publishedIndex']:f.need((node,view['publishedIndex']) in published,'unobserved published status')
        if view['state']=='LEADER_READY':f.need((node,view['promisedEpoch']) in activations,'ready without fresh activation')
    for index,value in chosen.items():
        f.need(sum(r['provenThrough']>=index and r['acceptedDigests'][index-1]==value for r in reports.values())>=1,'lost chosen value')
    return dict(status='PASS',scenario=document['scenario'],chosen=len(chosen),publications=len(published),calls=len(calls),completed=len(completed))


def negatives(root):
    root=Path(root);original=json.loads((root/'trace.json').read_text());validate(root,original)
    mutations={
        'missing-force':lambda v:v.update(trace=[r for r in v['trace'] if r['event']!='FORCE' or r['kind']!='PROOF']),
        'lost-ack-is-not-quorum':lambda v:v.update(trace=[r for r in v['trace'] if r['event']!='DELIVER' or r['message']['kind']!='PROOF' or not r['message']['response']]),
        'invented-completion':lambda v:next(r for r in v['trace'] if r['event']=='COMPLETE').update(index=999),
        'wrong-receipt':lambda v:next(r['message'] for r in v['trace'] if r['event']=='SEND' and r['message']['response'] and r['message']['kind']=='ACCEPT').update(payload='0'*64),
        'ready-without-publication':lambda v:next(row for row in v['views'] if row['node']=='node-3').update(state='LEADER_READY'),
        'removed-terminal-evidence':lambda v:v.update(trace=[],views=[]),
    }
    def forge_application(v):
        from .format_encoder import encode
        row=next(r for r in v['trace'] if r['event']=='PUBLISH');snapshot=f.inspect(raw(row['snapshot']),'SNAPSHOT')
        snapshot['application']=base64.b64encode(b'forged').decode();row['snapshot']=base64.b64encode(encode('SNAPSHOT',snapshot)).decode()
    mutations['rechecksummed-application']=forge_application
    results=[]
    for name,mutate in mutations.items():
        changed=copy.deepcopy(original);mutate(changed)
        try:validate(root,changed)
        except ValueError as error:results.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('negative accepted: '+name)
    return results
