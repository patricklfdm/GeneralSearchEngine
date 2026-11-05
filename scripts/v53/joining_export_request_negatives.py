"""Conditional handler replay and exact request-binding mutations.

These small captures exercise real handlers and budget observations, not a
native joining history. The full native entry has separate physical/network
prerequisites and cannot consume this component receipt as authority.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
from . import joining_export_request_evidence as r

need=r.need
NEGATIVES={
    'foreign-request-digest':'joining export original request digest',
    'foreign-session':'joining export original request session',
    'later-chunk':'joining export original initial request',
    'missing-original':'joining export complete original initial requests',
    'foreign-node':'joining export complete original initial requests',
    'legacy-allocation':'joining export legacy request binding',
    'received-after-allocation':'joining export original construction interval',
    'offer-before-attachment':'joining export original construction interval',
    'boolean-boundary':'joining export original request boundaries',
    'changed-request-body':'joining export original request digest',
}


def mutate(traces,closes,initials,case):
    key,initial=next(iter(initials.items()));node,session=key
    owner=r.exports.close.replay(traces,closes,export_ownership=True)['owners'][node]
    attachment=owner['exportAttachments'][session]
    name=next(n for n in attachment['children'] if r.exports.kind(n) in r.exports.REQUEST_BOUND)
    role=r.exports.kind(name);replacement=None
    if case=='foreign-request-digest':replacement=role+'-'+'e'*64+'-'+name[-36:]
    elif case in ('foreign-session','later-chunk','changed-request-body'):
        _,request=r.source.network.t.wire(initial['bytes']);request=copy.deepcopy(request)
        if case=='foreign-session':request['trace']='00000000-0000-0000-0000-000000000ffe'
        elif case=='later-chunk':request['sequence']=2
        else:request['payload']['digest']='d'*64
        raw=r.source.network.t.f.encode('wire','CHUNK',request);initial['bytes']=base64.b64encode(raw).decode()
        if case=='foreign-session':replacement=role+'-'+r.source.component.physical.e.digest(raw)+'-'+name[-36:]
    elif case=='missing-original':initials.pop(key)
    elif case=='foreign-node':initials['node-99',session]=initials.pop(key)
    elif case=='legacy-allocation':replacement=role+'-'+name[-36:]
    elif case=='received-after-allocation':initial['received']=owner['lifetimes'][name]['start']
    elif case=='offer-before-attachment':initial['offered']=attachment['resourceSequence']-1
    elif case=='boolean-boundary':initial['received']=True
    else:raise ValueError('joining request unknown mutation')
    if replacement:
        for row in traces[node]['changes']:
            for value in row['removed']+row['added']:
                if value['owner']==name:value['owner']=replacement
        for row in closes[node]['rows']:
            if row['owner']==name:row['owner']=replacement
            row['children']=sorted(replacement if child==name else child for child in row['children'])


def replay(traces,closes,initials):
    original=r.bind(traces,closes,initials)
    need(original['exportInventory']['completeExportAllocationInventory'],'joining request original incomplete inventory')
    results=[]
    for case,reason in NEGATIVES.items():
        changed=copy.deepcopy((traces,closes,initials));mutate(*changed,case)
        try:r.bind(*changed)
        except ValueError as error:need(str(error)==reason,'joining request unrelated mutation rejection: '+case+': '+str(error))
        else:raise ValueError('joining request mutation accepted: '+case)
        results.append(dict(case=case,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


def validate_component(directory,*,qualify=False):
    from .native_resource_evidence import collection
    root=Path(directory);before=collection.inventory(root,maximum=16*1024*1024)
    need(not before['directories'] and set(before['files'])=={'scope.json','initial.json','resources.json','closes.json'},
         'joining request exact component inventory')
    load=lambda name:collection.read_json(root,name,16*1024*1024)
    scope=load('scope.json');initial=load('initial.json');node=scope.get('node');role=scope.get('role')
    need(set(scope)=={'schema','role','node','nativeMembershipQualified'} and
         scope['schema']=='gse-v53-joining-export-request-component-v1' and scope['nativeMembershipQualified'] is False and
         node=='node-1' and role in ('joining-retention-export','joining-preparation-export'),
         'joining request conditional component scope')
    need(set(initial)=={'session','bytes','received','offered'},'joining request component initial shape')
    session=initial.pop('session');traces={node:load('resources.json')};closes={node:load('closes.json')}
    result=(replay if qualify else r.bind)(traces,closes,{(node,session):initial})
    original=result['original'] if qualify else result
    need(original['families']=={role:1},'joining request exact component family')
    need(collection.inventory(root)==before,'joining request component original changed')
    return dict(status='PARTIAL',scope='conditional-original-handler-request-binding',component=result,inventory=before,
                nativeMembershipQualified=False,allJoiningFamiliesQualified=False,phase3Complete=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(validate_component(args.root,qualify=args.qualify),sort_keys=True))
