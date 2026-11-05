"""Exact in-process export handles owned by successful source sessions.

This augments admitted physical/network evidence; it cannot independently prove
the bytes served or qualify failed constructors and every export family.
"""
from collections import Counter
import re
from uuid import UUID
from . import control_close_evidence as close

need=close.need
BOUND=('source-export','record-export','vote-export','prefix-export','learner-root-export')
UNBOUND=('joining-retention-export','joining-intent','joining-preparation-export',
         'joining-completion-export','joining-checkpoint-export')
ROLES=BOUND+UNBOUND
SHAPES={frozenset((role,)):role for role in ROLES if role not in
        ('learner-root-export','joining-retention-export','joining-intent')}
SHAPES.update({frozenset((role,'prefix-export')):role for role in
               ('learner-root-export','joining-retention-export','joining-intent')})


def kind(name):
    role=next((v for v in ROLES if name.startswith(v+'-')),None)
    if role is None:return None
    suffix=name[len(role)+1:]
    if role in BOUND:
        need(re.fullmatch(r'[0-9a-f]{64}-[0-9a-f-]{36}',suffix) is not None,
             'session export original content binding')
        suffix=suffix[65:]
    try:nonce=UUID(suffix);valid=nonce.int!=0 and str(nonce)==suffix
    except ValueError:valid=False
    need(valid,'session export original allocation identity')
    return role


def inspect(traces,closes):
    account=close.replay(traces,closes,export_ownership=True)
    allocations=0;sessions=0;families=Counter();revoked=0;unattached=[]
    for node,owner in account['owners'].items():
        life=owner['lifetimes'];claimed={};exports={}
        for name in life:
            role=kind(name)
            if role is not None:exports[name]=role
        for session,attachment in owner['exportAttachments'].items():
            children=attachment['children'];roles=[kind(name) for name in children]
            need(None not in roles and len(set(roles))==len(roles) and frozenset(roles) in SHAPES,
                 'session export exact owned group')
            pair=owner['pairs'][session]
            for name in children:
                need(name not in claimed,'session export multiply owned handle')
                need(life[name]['end']<=pair['returned']['resourceSequence'],'session export release before normal return')
                claimed[name]=session
                revoked+=life[name]['end']<=attachment['resourceSequence']
            families[SHAPES[frozenset(roles)]]+=1;sessions+=1
        for name in sorted(set(exports)-set(claimed)):
            unattached.append(dict(node=node,owner=name,role=exports[name],**life[name]))
        # Each handle is an immutable export reservation. Size is checked by
        # the physical export reader, not inferred from this ownership marker.
        mutations={name:[] for name in claimed}
        for row in traces[node]['changes']:
            for value in row['added']+row['removed']:
                if value['unit']=='CONTROL' and value['owner'] in mutations:
                    mutations[value['owner']].append((row['event'],value))
        for changes in mutations.values():
            need(len(changes)==2 and [v[0] for v in changes]==['RESERVE','RELEASE'] and
                 changes[0][1]==changes[1][1],'session export immutable allocation')
        allocations+=len(claimed)
    need(sessions>0,'session export unobserved ownership')
    return dict(status='PARTIAL' if unattached else 'PASS',scope='observed-source-session-export-handles',sessions=sessions,
                ownedAllocations=allocations,revokedBeforeAttachment=revoked,families=dict(sorted(families.items())),
                declaredSessionExportReleaseQualified=True,unattachedExports=unattached,
                completeExportAllocationInventory=not unattached,exportContentExtentsQualified=False,
                allExportFamiliesQualified=False,failedConstructorExportsQualified=False,
                wholeRuntimeResourcesQualified=False,phase3Complete=False)


def replay(traces,closes):
    result=inspect(traces,closes)
    need(result['completeExportAllocationInventory'],'session export unclaimed allocation')
    return result
