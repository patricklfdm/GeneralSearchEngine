"""Local export ownership tied to original native activation/maintenance bytes.

The caller must admit the complete physical and network history first. The
stable derivation below and the required-four adapter share interval matching.
"""
from collections import Counter
from . import native_dispatch_evidence as native
from . import control_close_evidence as close
from . import session_export_evidence as exports

need=close.need


def derive(states,rounds,selection,events,boundaries):
    need(len(states)==1+3*len(rounds) and len(rounds)==2,'direct export stable original states')
    expected=[]
    def points(node,event):
        return [boundaries[i]['sequence'] for i,v in enumerate(events) if v.get('node')==node and v['event']==event]
    for node in native.VOTERS:
        records=native.c.journal(states[0][node]['grants.gsr'],selection['root'],node)
        bases=[(raw,value) for kind,raw,value in records if kind=='BASIS' and value['ballot']==selection['ballot']]
        need(len(bases)==1,'direct export original local BASIS');basis,value=bases[0]
        promises=[raw for kind,raw,promise in records if kind=='PROMISE' and promise['basisId']==value['basisId']]
        need(len(promises)==1,'direct export original local PROMISE')
        grants=points(node,'GRANT_BEFORE_RETURN');installed=points(node,'INSTALL_BEFORE_RETURN')
        need(len(grants)==len(installed)==1,'direct export original activation interval')
        expected.append(dict(node=node,phase='ACTIVATION' if node==selection['ballot']['proposer'] else 'SELECTED',
                             reference=native.e.digest(basis),bytes=len(basis)+len(promises[0]),
                             after=grants[0],through=installed[0]))
        reserved=points(node,'FLOOR_RESERVED');released=points(node,'FLOOR_RELEASE_BEFORE_RETURN')
        need(len(reserved)==len(released)==len(rounds),'direct export original maintenance intervals')
        previous=states[0]
        for index,row in enumerate(rounds):
            prefix,_,_=native.c.current(previous[node]);manifest=previous[node][prefix+'generation.gsr']
            expected.append(dict(node=node,phase='MAINTENANCE',reference=native.e.digest(manifest),bytes=4096,
                                 before=reserved[index],through=released[index]))
            previous=row['published']
    return expected


def replay(traces,closes,expected):
    inventory=exports.replay(traces,closes) # No unattached allocations may disappear.
    account=close.replay(traces,closes,export_ownership=True)
    need(type(expected) is list,'direct export original expectation')
    wanted={};identifiers=set()
    for ordinal,item in enumerate(expected):
        need(type(item) is dict and type(item.get('phase')) is str and item['phase'] in close.DIRECT_ROLES,'direct export original expectation')
        boundary='before' if item['phase']=='MAINTENANCE' else 'after'
        need(set(item)=={'node','phase','reference','bytes',boundary,'through'} and
             type(item['node']) is str and item['node'] in traces and type(item['reference']) is str and
             len(item['reference'])==64 and all(c in '0123456789abcdef' for c in item['reference']) and
             type(item['bytes']) is int and item['bytes']>0 and type(item[boundary]) is int and type(item['through']) is int and
             0<=item[boundary]<item['through']<len(traces[item['node']]['changes']),'direct export original expectation')
        key=item['node'],item['phase'],item['reference']
        identity=tuple(sorted(item.items()))
        need(identity not in identifiers,'direct export duplicate original expectation');identifiers.add(identity)
        wanted.setdefault(key,[]).append((ordinal,item))
    observed=set();kinds=Counter()
    for node,owner in account['owners'].items():
        for name,call in owner['directExports'].items():
            phase=call['phase'];role=close.DIRECT_ROLES[phase];reference=name[len(role)+1:len(role)+65]
            key=node,phase,reference
            need(key in wanted,'direct export original content/cohort')
            life=owner['lifetimes'][name];reserved=traces[node]['changes'][life['start']]['added']
            acquired=call['acquired']['resourceSequence'];begin=call['begin']['resourceSequence']
            def covers(item):
                if phase=='MAINTENANCE':return life['start']<=acquired<=item['before']<item['through']<=begin and item['through']<life['end']
                return item['after']<life['start']<=acquired<item['through']<=begin and item['through']<life['end']
            matches=[(ordinal,item) for ordinal,item in wanted[key] if ordinal not in observed and covers(item)]
            need(matches,'direct export original '+('maintenance' if phase=='MAINTENANCE' else 'activation')+' lifetime')
            need(len(matches)==1,'direct export ambiguous original interval')
            ordinal,item=matches[0];observed.add(ordinal)
            need(len(reserved)==1 and reserved[0]['owner']==name and reserved[0]['bytes']==item['bytes'],
                 'direct export original content extent')
            kinds[phase]+=1
    need(observed==set(range(len(expected))),'direct export missing original local owner')
    return dict(status='PASS',scope='stable-native-direct-export-ownership',directExports=len(observed),
                phases=dict(sorted(kinds.items())),originalContentBindingsQualified=True,
                originalOperationIntervalsQualified=True,exportInventory=inventory,
                allMembershipProfilesQualified=False,wholeRuntimeResourcesQualified=False,phase3Complete=False)
