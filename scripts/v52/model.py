"""Finite read/publication model; assumes the inherited three-voter consensus safety.

One selected replica is observed, with the two other voters represented as a quorum
availability bit. Voter names are symmetric. This is not a replacement election model.
"""
from dataclasses import asdict, dataclass, replace
from collections import deque
import json
from pathlib import Path

# new, waiting, captured, released, success, rejected, cancelled
NEW, WAIT, ACTIVE, RELEASED, SUCCESS, REJECTED, CANCELLED = range(7)

@dataclass(frozen=True)
class Read:
    policy: str
    identity: int = 0
    minimum: int = 2
    phase: int = NEW
    barrier: int = -1
    epoch: int = 0
    cut: int = -1
    invoked: int = 0
    cancelled: bool = False

@dataclass(frozen=True)
class State:
    accepted: int = 0
    proven: int = 0
    published: int = 0
    sequence: tuple = (0,)
    epoch: int = 1
    role: str = 'leader'
    quorum: bool = True
    closed: bool = False
    expired: bool = False
    reads: tuple = (Read('strong'), Read('minimum'), Read('stale'))


def check(s):
    if not 0<=s.published<=s.proven<=s.accepted<=3:raise ValueError('prefix')
    if len(s.sequence)!=s.proven+1 or not all(0<=v<=2 for v in s.sequence) or tuple(sorted(s.sequence))!=s.sequence:raise ValueError('sequence')
    if sum(r.phase==ACTIVE for r in s.reads)>1:raise ValueError('view ownership')
    if sum(r.phase in (WAIT,ACTIVE,RELEASED) for r in s.reads)>3:raise ValueError('admission bound')
    for r in s.reads:
        if r.invoked not in (0,1):raise ValueError('callback once')
        if r.phase in (ACTIVE,RELEASED,SUCCESS):
            if not 0<=r.cut<=s.published or r.invoked!=1:raise ValueError('committed publication')
            if r.identity!=0:raise ValueError('identity')
            if r.policy=='minimum' and r.cut<r.minimum:raise ValueError('minimum')
            if r.policy=='strong' and (r.barrier<1 or r.cut<r.barrier or r.epoch<1):raise ValueError('strong barrier')
        if r.phase==WAIT and (r.cut!=-1 or r.invoked):raise ValueError('wait owns publication')


def transitions(s):
    active=any(r.phase==ACTIVE for r in s.reads)
    def request(i,r):return replace(s,reads=s.reads[:i]+(r,)+s.reads[i+1:])
    if not s.closed:
        if s.accepted==s.proven and s.accepted<3:
            yield 'accept',replace(s,accepted=s.accepted+1)
        if s.accepted>s.proven and s.quorum:
            for increment in (0,1):
                seq=s.sequence[-1]+increment
                if seq<=2:yield 'proof',replace(s,proven=s.accepted,sequence=s.sequence+(seq,))
        if s.published<s.proven and not active:
            yield 'publish',replace(s,published=s.proven)
        if s.epoch<3:
            yield 'promise',replace(s,epoch=s.epoch+1,role='follower')
        for role in ('leader','follower','recovering'):
            if role!=s.role:yield 'role:'+role,replace(s,role=role)
        yield 'quorum',replace(s,quorum=not s.quorum)
        yield 'close',replace(s,closed=True)
    if not s.expired:yield 'deadline',replace(s,expired=True)
    for i,r in enumerate(s.reads):
        label=str(i)+':'
        if r.phase==NEW:
            yield label+'admit',request(i,replace(r,phase=REJECTED if s.closed or s.expired or s.role=='recovering' or r.identity else WAIT))
        elif r.phase==WAIT:
            yield label+'cancel',request(i,replace(r,phase=CANCELLED))
            if s.closed or s.expired or s.role=='recovering' or r.identity:
                yield label+'reject',request(i,replace(r,phase=REJECTED));continue
            if r.policy=='strong':
                if s.role!='leader' or (r.epoch and r.epoch!=s.epoch):
                    yield label+'fenced',request(i,replace(r,phase=REJECTED));continue
                if r.barrier<0 and s.quorum and s.accepted==s.proven and s.proven<3:
                    future=request(i,replace(r,barrier=s.proven+1,epoch=s.epoch))
                    yield label+'barrier',replace(future,accepted=s.proven+1,proven=s.proven+1,sequence=s.sequence+(s.sequence[-1],))
                if r.barrier<0 or s.published<r.barrier:continue
            if r.policy=='minimum' and s.published<r.minimum:continue
            if not active:
                yield label+'capture',request(i,replace(r,phase=ACTIVE,cut=s.published,invoked=1))
        elif r.phase==ACTIVE:
            # Cancellation after capture retains the actual view until its release.
            yield label+'release',request(i,replace(r,phase=CANCELLED if r.cancelled else RELEASED))
            if not r.cancelled:yield label+'cancel-active',request(i,replace(r,cancelled=True))
        elif r.phase==RELEASED:
            yield label+'complete',request(i,replace(r,phase=SUCCESS))
            yield label+'cancel',request(i,replace(r,phase=CANCELLED))


def explore(depth=12, max_states=2000000):
    # Same/foreign token origins; all enabled schedules from both declared roots.
    roots=[State(),State(reads=(Read('minimum',identity=1),Read('minimum',minimum=0),Read('minimum',minimum=3)))]
    seen=set(roots);frontier=deque((r,0) for r in roots);edges=0;outcomes=set();counts={}
    while frontier:
        state,level=frontier.popleft();check(state)
        outcomes.update(r.phase for r in state.reads)
        if level==depth:continue
        for event,nxt in transitions(state):
            try:check(nxt)
            except ValueError as error:
                raise ValueError(json.dumps(dict(invariant=str(error),depth=level+1,event=event,
                    before=asdict(state),after=asdict(nxt)),sort_keys=True)) from error
            if event.endswith(':capture'):
                captured=nxt.reads[int(event.split(':')[0])]
                if captured.policy=='strong' and (captured.epoch!=state.epoch or state.role!='leader'):raise ValueError('strong capture epoch')
            if any(r.phase==ACTIVE for r in state.reads) and nxt.published!=state.published:raise ValueError('active cut changed')
            edges+=1;counts[event.split(':')[-1]]=counts.get(event.split(':')[-1],0)+1
            for before,after in zip(state.reads,nxt.reads):
                if before.phase in (SUCCESS,REJECTED,CANCELLED) and before!=after:raise ValueError('terminal resurrection')
            if nxt not in seen:
                if len(seen)>=max_states:
                    return dict(status='INCOMPLETE',states=len(seen),transitions=edges,depth=depth,limit=max_states)
                seen.add(nxt);frontier.append((nxt,level+1))
    return dict(status='PASS',execution='abstract-read-foundation-only',states=len(seen),transitions=edges,depth=depth,
                initialStates=len(roots),voters=3,identities=2,positionBound=3,sequenceBound=2,epochBound=3,readBound=3,
                voterSymmetry='selected voter plus two quorum witnesses',outcomes=sorted(outcomes),events=counts)


def run(output):
    try:result=explore()
    except Exception as error:
        Path(output).write_text(json.dumps(dict(status='FAIL',error=str(error)))+'\n');raise
    Path(output).write_text(json.dumps(result,indent=2)+'\n')
    if result['status']!='PASS':raise ValueError('incomplete read model exploration')
    return result
