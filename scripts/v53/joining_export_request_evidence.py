"""Join successful export handles to their original first framed request.

The native caller first admits physical history, wire causality, resource
accounting and exact response/session ownership. Request identity is separate
from exported content/extent and from constructor rollback qualification.
"""
import base64
from collections import Counter
from . import session_export_evidence as exports
from . import native_source_resources as source

need=exports.need


def bind(traces,closes,initials):
    inventory=exports.inspect(traces,closes)
    account=exports.close.replay(traces,closes,export_ownership=True)
    sessions={(node,name) for node,owner in account['owners'].items() for name in owner['exportAttachments']}
    need(type(initials) is dict and set(initials)==sessions,'joining export complete original initial requests')
    families=Counter();legacy=[]
    for key,initial in initials.items():
        node,session=key;owner=account['owners'][node];attachment=owner['exportAttachments'][session]
        need(type(initial) is dict and set(initial)=={'bytes','received','offered'} and
             type(initial['received']) is int and type(initial['offered']) is int and
             0<=initial['received']<=initial['offered']<len(traces[node]['changes']),
             'joining export original request boundaries')
        kind,request=source.network.t.wire(initial['bytes'])
        need(kind=='CHUNK' and type(request['sequence']) is int and request['sequence']==1 and
             request['payload']['action']=='REQUEST' and type(request['payload']['offset']) is int and
             request['payload']['offset']==0 and request['payload']['bytes']=='',
             'joining export original initial request')
        digest=source.component.physical.e.digest(base64.b64decode(initial['bytes'],validate=True))
        need(request['recipient']['node']==node and session.startswith('source-session-'+source.component.binding(request)+'-'),
             'joining export original request session')
        for name in attachment['children']:
            role=exports.kind(name)
            if role not in exports.REQUEST_BOUND:continue
            suffix=name[len(role)+1:]
            if len(suffix)==36:legacy.append(dict(node=node,owner=name));continue
            need(suffix[:64]==digest,'joining export original request digest')
            life=owner['lifetimes'][name];metadata=owner['lifetimes'][session]
            need(initial['received']<life['start']<metadata['start']<=attachment['resourceSequence']<=initial['offered'],
                 'joining export original construction interval')
            families[role]+=1
    need(not legacy,'joining export legacy request binding')
    need(families,'joining export requests unobserved')
    return dict(status=inventory['status'],scope='original-first-request-to-session-export-handle',
                boundMetadataAllocations=sum(families.values()),families=dict(sorted(families.items())),
                originalInitialRequests=len(initials),joiningExportRequestsQualified=True,
                exportInventory=inventory,metadataExtentsQualified=False,exportContentQualified=False,exportFamilyAuthorityQualified=False,
                failedConstructorExportsQualified=False,allJoiningFamiliesObserved=set(families)==set(exports.REQUEST_BOUND),
                wholeRuntimeResourcesQualified=False,phase3Complete=False)
