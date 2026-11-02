"""Bind an unselected node's post-grant retirement to original wire/forces.

Inputs are pre/post states derived by the current physical reader. Packet-only
fallback proves no application copy; the subsequent complete copy must arrive
before the governing floor and retirement. This component supplies no client or
process-success claim.
"""
from . import node_inflight_evidence as p
from . import floor_evidence as floor
from . import floor_release_evidence as release
from . import remove_retirement_evidence as retirement
from .joining_same_view_physical import covering_floor

n,c,e,f,need=p.n,p.c,p.e,p.f,p.need
PREFIXES=('FLOOR_','RETIREMENT_','SOURCE_RETIREMENT_','JOURNAL_ROTATION_','RETENTION_','SELECTED_RETENTION_')


def transaction(before,after,node,voters):
    """Derive all floor, source and release callbacks, including file counts."""
    files=before[node];prefix,members,packet=c.current(files)
    need(len(voters)==2 and voters[0]==node and len(set(voters))==2,
         'node grant maintenance exact floor cohort')
    need(all(not k.startswith('generations/') or k==prefix[:-1] or k.startswith(prefix) for k in files)
         and files[n.s.FILE]==after[n.s.FILE], 'node grant maintenance source-only scope')
    copies={v:before[v] for v in voters}
    held=covering_floor(files,copies,node)
    originals={}
    for value in copies.values():
        path,contents,_=c.current(value);manifest=value[path+'generation.gsr']
        originals[e.digest(manifest)]=dict(contents,**{'generation.gsr':manifest})
    events,_,_,_=floor.transaction(originals,held['floor-copies/floor.gsr'],handoff=True)
    available=retirement.r.peer.t.confirmation.endpoints(packet,members.get('ancestry.gsr',b''))
    retired,decisions=retirement.source_plans(held,node,available)
    need(decisions,'node grant maintenance original retired source')
    record=f.encode('records','RETIREMENT',dict(root=packet['capsule']['root'],node=node,
        floor=e.digest(retired['floor-copies/floor.gsr']),selector=e.digest(retired['selector.gsr']),
        files=[dict(path=k,size=len(v),sha256=e.digest(v)) for k,v in sorted(retired.items())
               if k.startswith('floor-copies/') and v is not None]))
    released=release.transaction(retirement.physical(retired),record)
    need(released and released[-1][1]==retirement.physical(after),
         'node grant maintenance exact released state')
    return (['FLOOR_COPY_BEFORE_RETURN']*len(voters)+[v['event'] for v in events]+
            [point for decision in decisions for point,_ in decision['steps']]+[point for point,_ in released]),len(decisions)


def transfers(phase,before,node,voters,ballot,lower,upper):
    peer=next(v for v in voters if v!=node)
    prefix,members,packet=c.current(before[peer]);local=c.current(before[node])[1]
    force=phase.at(node,'FLOOR_PARENT_FORCED')
    need(lower<force<upper,'node grant maintenance floor before advertised grant')
    delivered=phase.probe(node,peer,ballot,packet['capsule']['cut'],lower,force)
    missing=any(local.get(h+'.image')!=members[h+'.image'] for h in packet['images'])
    if missing:
        # The first completed packet proves which original images are missing.
        # It cannot stand in for the second, complete prefix acquisition.
        probe=[(n.current_reference(packet['capsule'],'retained-current-packet'),members['source.gscp'],'CAPSULE')]
        value=phase.transfer(node,peer,[probe],ballot,delivered,force)
        delivered=max(v[0] for v in value['arrivals'])
    value=phase.transfer(node,peer,n.maintenance_prefixes(members,packet,local),ballot,delivered,force)
    delivered=max(v[0] for v in value['arrivals'])
    phase.transfer(node,peer,n.maintenance_generations(before[peer][prefix+'generation.gsr'],members,packet),ballot,delivered,force)
    return int(missing)


class Replay:
    def __init__(self,derived):
        self.derived=derived;self.used=set();self.results=[]

    def __call__(self,phase,selected):
        ballot=selected['ballot'];voters={v['voter'] for v in selected['sources']}
        for key,value in self.derived.items():
            counter,node=key
            if counter!=ballot['counter']:continue
            need(key not in self.used and node not in voters,'node grant maintenance unselected original owner')
            before,after,cohort=value['before'],value['after'],value['voters']
            fresh=p.net.a.frozen(before[node],ballot)
            rows=[v for v in phase.entries if v['kind']=='PREPARE' and v['request']['recipient']['node']==node]
            need(rows and all(v['answer']=='PROMISE' and v['response']['payload']==dict(basis=e.digest(fresh[1]))
                 and v['request']['ballot']==ballot for v in rows), 'node grant maintenance original advertised grant')
            lower=phase.at(node,'GRANT_BEFORE_RETURN');upper=min(v['offered'] for v in rows)
            need(lower<upper,'node grant maintenance grant interval')
            expected,sources=transaction(before,after,node,cohort)
            observed=[v for v in phase.events[lower+1:upper] if v['node']==node and v['event'].startswith(PREFIXES)]
            need(observed==[dict(node=node,event=event) for event in expected],
                 'node grant maintenance complete original callbacks')
            fallback=transfers(phase,before,node,cohort,ballot,lower,upper)
            self.used.add(key)
            self.results.append(dict(node=node,ballot=counter,sources=sources,callbacks=len(expected),packetOnlyFallbacks=fallback))

    def complete(self):
        need(self.used==set(self.derived),'node grant maintenance unbound derived transition')
        return self.results
