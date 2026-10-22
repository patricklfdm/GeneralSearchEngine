"""Join operation/learner evidence to independently checked actual model votes."""
from copy import deepcopy

from . import activation_oracle as a
from . import operation_oracle as o
from . import transition_model as t
from .membership_model import NODES
from .recovery_oracle import safe


def check(record):
    activation=dict(root=record['root'],old=tuple(record['old']),input=[],
                    events=[e['detail'] for e in record['events'] if e['event']=='activation'])
    protocol=a.check(activation)
    states={n:deepcopy(record['initial']) for n in NODES};prefixes={n:() for n in NODES}
    commands={};images={};receipts=set();admitted=set(record['old']);alive=set(NODES);applications=0;learner_votes=0

    def decode(entry,state):
        if entry.kind=='BARRIER':return dict(kind='BARRIER')
        if entry.kind=='DATA':return dict(kind='DATA',value=entry.payload)
        if entry.kind=='CONTROL':
            safe(entry.payload in commands,'missing control body');command=commands[entry.payload]
            safe(command['kind'] in ('RESERVE','PREPARE','READY','SEAL','CANCEL','RETIRE'),'control entry kind confusion')
            return command
        safe(entry.kind in ('INTENT','FINAL') and state['active'] is not None,'unbound transition command')
        row=state['results'][str(state['active'])]
        safe(tuple(x['voter'] for x in row['request']['target'])==entry.target,'foreign transition target')
        return dict(kind=entry.kind,number=state['active'],binding=entry.operation)

    def eligible(node,context):
        state=states[node];left=[x['voter'] for x in state['members']];right=left;generation=state['generation']
        row=state['results'].get(str(state['active']))
        joint=row is not None and row['phase']=='JOINT'
        if joint:right=[x['voter'] for x in row['request']['target']];generation+=1
        safe(node in alive and state['index']==len(prefixes[node]) and context.index==state['index']+1 and
             context.old==tuple(left) and context.new==tuple(right) and context.generation==generation and
             context.operation==(row['binding'] if joint else '') and node in set(left+right),'unapplied/foreign vote context')
        if node not in admitted:
            safe(joint and node in images and row['receipt']==images[node],'learner vote before forced image/readiness/INTENT')

    for event in record['events']:
        kind=event['event']
        if kind=='command':
            safe(t.digest(event['command'])==event['digest'] and
                 (event['digest'] not in commands or commands[event['digest']]==event['command']),'control descriptor changed')
            commands[event['digest']]=event['command']
        elif kind=='activation':
            row=event['detail']
            if row['event']!='transition':continue
            detail=row['detail']
            if detail['event']=='install-force':prefixes[detail['node']]=detail['chain']
            if detail['event']!='slot':continue
            action=detail['detail'];msg=action.get('message')
            if action['event'] in ('stage','promise-force','accept-force','proof-force'):
                eligible(msg.voter,msg.context)
                if msg.voter not in record['old']:learner_votes+=1
                if msg.kind in ('accept','proof'):
                    command=decode(t.Entry.read(msg.value),states[msg.voter])
                    o.next_state(states[msg.voter],command,record['limits'],receipts)
        elif kind=='apply':
            node=event['node'];state=states[node];index=state['index'];cert=event['certificate']
            safe(node in alive and len(prefixes[node])>index and prefixes[node][index]==cert,'catalog apply before certified prefix force')
            command=decode(t.Entry.read(cert.value),state);safe(command==event['command'],'application command substitution')
            after=o.next_state(state,command,record['limits'],receipts)
            safe(after==event['state'],'catalog application changed')
            states[node]=after;applications+=1
            if command['kind']=='FINAL':admitted.update(x['voter'] for x in after['members'])
        elif kind=='image-force':
            node,source,receipt=event['node'],event['source'],event['receipt'];state=states[source]
            safe(node not in admitted and source in alive and state['active']==receipt['number'] and
                 event['cut']==len(prefixes[source])==state['index'] and o.expected_receipt(state,receipt['number'])==receipt and
                 receipt['identity']['voter']==node and receipt['prepared']['dataIndex']==state['dataIndex'] and
                 receipt['prepared']['data']==state['data'],'unbound/stale learner materialization')
            images[node]=receipt
        elif kind=='receipt-force':
            node,receipt=event['node'],event['receipt']
            safe(node in alive and images.get(node)==receipt and states[node]['index']==len(prefixes[node]) and
                 states[node]['active']==receipt['number'] and o.expected_receipt(states[node],receipt['number'])==receipt,
                 'receipt before verified installed catalog/image')
            receipts.add(t.digest(receipt))
        elif kind=='catalog-crash':safe(event['node'] in alive,'duplicate catalog crash');alive.remove(event['node'])
        elif kind=='catalog-restart':safe(event['node'] not in alive,'catalog restart running');alive.add(event['node'])
        else:safe(False,'unknown integrated event')
    return dict(protocol=protocol,applications=applications,learnerVoteEvents=learner_votes,
                states=states,events=len(record['events']))
