"""Complete successful-session export charges from admitted original contents.

The native caller first admits the whole physical/network/control history.
No extent is learned from observed allocation sizes or export owner labels.
Direct calls, constructor rollback and physical peaks remain separate scopes.
"""
import base64
from collections import Counter
from . import joining_metadata_extents as metadata

control=metadata.control;e=control.e;f=metadata.f;sha=metadata.sha
exports=metadata.exports;need=exports.need


def charge(role,binding,size):return dict(role=role,binding=binding,bytes=size)


def derive(reader):
    pending=e.pending_ack(reader.model);plans={}
    for values in reader.groups:
        first=values[0];q=first['offer']['request'];node=q['recipient']['node'];raw=first['raw']
        initial=f.encode('wire','CHUNK',q);binding=sha(initial)
        need(q['sequence']==1 and q['payload']['action']=='REQUEST' and q['payload']['offset']==0 and q['payload']['bytes']=='' and
             binding==first['offer']['requestHash'] and binding not in plans,'session extents unique original initial request')
        kind=e.record_kind(raw);identified=metadata.classify(raw,pending);charges=[]
        if identified is not None:
            need(len(values)==1 and first['kind']=='RECORD','session extents singleton metadata export')
            role,size=identified;charges.append(charge(role,binding,size))
            if role in ('joining-retention-export','joining-intent'):
                own=e.current(reader.windows,node,first['offer']['received'],first['commit']['offered'])
                charges.append(charge('prefix-export',sha(own['manifest']),4096))
        elif kind=='ROOT':
            own=e.current(reader.windows,node,first['offer']['received'],values[-1]['commit']['offered'])
            reader.root_export(values,own)
            charges=[charge('learner-root-export',sha(reader.model.root_bytes),2*len(reader.model.root_bytes)+4096),
                     charge('prefix-export',sha(own['manifest']),4096)]
        elif kind=='GENERATION' or first['kind']=='CAPSULE':
            e.authorize_generation(values,reader.windows)
            own=e.current(reader.windows,node,first['offer']['received'],values[-1]['commit']['offered'])
            charges=[charge('prefix-export',sha(own['manifest']),4096)]
        elif kind=='BASIS':
            source=e.authorize_source(values,reader.windows,reader.sources)
            charges=[charge('source-export',sha(source['basis']),len(source['basis'])+len(source['promise']))]
        else:
            scope=e.authorize_record(values,reader.windows,reader.records)
            role='vote-export' if scope in ('pending-payload','native-vote-receipt') else 'record-export'
            need(role=='vote-export' or e.record_kind(raw) in ('PROMISE','SELECTED','ENTRY','ACCEPT','PROOF','CERTIFICATE','CHECKPOINT','CHECKPOINT_ACK'),
                 'session extents original forced record kind')
            charges=[charge(role,q['payload']['digest'] if role=='vote-export' else sha(raw),len(raw))]
        plans[binding]=dict(node=node,request=base64.b64encode(initial).decode(),charges=sorted(charges,key=lambda v:v['role']))
    need(plans,'session extents unobserved original content')
    return plans


def bind(traces,closes,initials,expected):
    inventory=exports.inspect(traces,closes)
    account=exports.close.replay(traces,closes,export_ownership=True)
    sessions={(node,name) for node,owner in account['owners'].items() for name in owner['exportAttachments']}
    need(type(initials) is dict and set(initials)==sessions and type(expected) is dict and expected,
         'session extents complete original sessions')
    used=set();families=Counter();allocated=0
    for (node,session),initial in initials.items():
        owner=account['owners'][node];attachment=owner['exportAttachments'][session]
        need(type(initial) is dict and set(initial)=={'bytes','received','offered'} and
             type(initial['received']) is int and type(initial['offered']) is int and
             0<=initial['received']<=initial['offered']<len(traces[node]['changes']),
             'session extents original request boundaries')
        kind,q=metadata.requests.source.network.t.wire(initial['bytes']);binding=sha(metadata.decoded(initial['bytes']))
        need(kind=='CHUNK' and q['sequence']==1 and q['payload']['action']=='REQUEST' and q['payload']['offset']==0 and q['payload']['bytes']=='' and
             q['recipient']['node']==node and session.startswith('source-session-'+metadata.requests.source.component.binding(q)+'-'),
             'session extents original request session')
        need(binding in expected and binding not in used,'session extents complete original content');used.add(binding);plan=expected[binding]
        need(type(plan) is dict and set(plan)=={'node','request','charges'} and plan['node']==node and plan['request']==initial['bytes'] and
             type(plan['charges']) is list and len(plan['charges']) in (1,2),'session extents original expectation')
        charges=plan['charges']
        for item in charges:
            need(type(item) is dict and set(item)=={'role','binding','bytes'} and type(item['role']) is str and item['role'] in exports.ROLES and
                 type(item['binding']) is str and len(item['binding'])==64 and all(c in '0123456789abcdef' for c in item['binding']) and
                 type(item['bytes']) is int and 0<item['bytes']<=384*1024*1024,'session extents original charge expectation')
        roles=[v['role'] for v in charges]
        need(roles==sorted(set(roles)) and frozenset(roles) in exports.SHAPES,'session extents original charge group')
        names=sorted(attachment['children'],key=exports.kind)
        need([exports.kind(name) for name in names]==roles,'session extents exact original export group')
        for name,item in zip(names,charges):
            need(name.startswith(item['role']+'-'+item['binding']+'-'),'session extents original content binding')
            life=owner['lifetimes'][name];session_life=owner['lifetimes'][session]
            need(initial['received']<life['start']<session_life['start']<=attachment['resourceSequence']<=initial['offered'],
                 'session extents original construction interval')
            values=[v for v in traces[node]['changes'][life['start']]['added'] if v['owner']==name]
            need(len(values)==1 and values[0]['unit']=='CONTROL' and not values[0]['claimSource'] and values[0]['bytes']==item['bytes'],
                 'session extents original reservation extent')
            allocated+=1
        families[exports.SHAPES[frozenset(roles)]]+=1
    need(used==set(expected),'session extents complete original content')
    return dict(status=inventory['status'],scope='original-content-to-all-successful-session-export-charges',
                sessions=len(sessions),ownedAllocations=allocated,families=dict(sorted(families.items())),
                allObservedSessionContentExtentsQualified=True,exportInventory=inventory,
                allExportFamiliesQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
