"""Normalize complete original joining observations without losing event positions.

New-format traces require connection identity on every transport observation and
wire row. Legacy traces continue through the existing strict legacy reader.
"""
import argparse
import json
from . import connection_transcript as t
from . import segmented_evidence

need=t.need
SENDS={'NETWORK_SEND',t.SEND};READS={'NETWORK_REQUEST',t.READ};OFFERS={'WIRE_RESPONSE',t.OFFER};DELIVERIES={'NETWORK_RECEIVED',t.DELIVER}
TRANSPORT=SENDS|READS|OFFERS|DELIVERIES|{t.FAIL}


def present(events,wires):
    return any('connection' in row for row in events if row.get('event') in TRANSPORT) or any('connection' in row for row in wires)


def replay(events,wires,identities,root):
    need(type(events) is list and segmented_evidence.rows(wires) and len(events)<=t.native.collection.HISTORY_ROWS and
         len(wires)<=t.native.collection.HISTORY_ROWS,'joining connection bounded observations')
    rows=[];positions=[];starts={};answers={}
    for value in wires:
        need(type(value) is dict and 'connection' in value,'joining connection complete wire metadata')
        need(set(value)=={'connection','request','response','withheld'} and type(value['withheld']) is bool,'connection original response shape')
        identifier,_,_=t.connection(value['connection'])
        need(identifier not in answers,'connection duplicate original response')
        kind,q=t.wire(value['request']);answer,a=t.wire(value['response']);answers[identifier]=(kind,answer)
    for at,value in enumerate(events):
        if value.get('event') not in TRANSPORT:continue
        need('connection' in value,'joining connection complete event metadata')
        identifier,_,_=t.connection(value['connection']);row=dict(value);event=row['event']
        if event=='NETWORK_SEND':
            need(set(row)=={'node','event','request','kind','bytes','connection'},'joining connection old send shape')
            row.update(event=t.SEND,scope='legacy-unscoped')
        elif event=='NETWORK_REQUEST':
            need(set(row)=={'node','event','request','kind','connection'},'joining connection old request shape')
            row.update(event=t.READ,scope='legacy-unscoped')
        elif event=='WIRE_RESPONSE':
            need(set(row)=={'node','event','request','response','connection'} and identifier in answers,'joining connection old response shape')
            kind,answer=answers[identifier];row.update(event=t.OFFER,scope='legacy-unscoped',kind=kind,responseKind=answer)
        elif event=='NETWORK_RECEIVED':
            need(set(row)=={'node','event','kind','response','connection'} and identifier in starts,'joining connection old delivery shape')
            sent=starts[identifier];row.update(event=t.DELIVER,scope='legacy-unscoped',request=sent['request'],kind=sent['kind'],responseKind=value['kind'])
        elif event==t.FAIL and 'scope' not in row:row['scope']='legacy-unscoped'
        if row['event']==t.SEND:starts[identifier]=row
        rows.append(row);positions.append(at)
    # Deliberate transfer loss still needs its existing exact declaration and
    # temporal/export checks. Incidental failed transfer attempts remain gated.
    from . import joining_source_loss as loss
    result=t.replay(rows,wires,identities,root,positions=positions,allow_withheld=loss.declaration(events) is not None)
    for failed in result['failed']:
        if failed['kind'] in ('CHUNK','TRANSFER_COMMIT'):
            responses=[row for row in result['rows'] if row['sent']==failed['sent']]
            need(len(responses)==1 and responses[0].get('withheld',False),'joining connection unqualified transfer attempt')
    loss.requests(events,result['rows'])
    return result


if __name__=='__main__':
    from . import transport_connection_evidence as component
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((component.qualify if args.qualify else component.validate)(args.root,reader=replay),sort_keys=True))
