"""Committed membership-operation state machine, not a consensus implementation.

Each force stands for application of an already certified control entry. Later
integration must supply that certificate. Learner receipts have separate force
events. No timeout or client cancellation changes durable cluster state.
"""
from copy import deepcopy
from dataclasses import dataclass

from .transition_model import digest
from .membership_model import need


@dataclass(frozen=True)
class Limits:
    results: int = 2
    identities: int = 8
    changes: int = 4
    revisions: int = 4
    operations: int = 2**63-2  # Long.MAX_VALUE remains the exhausted-next sentinel.

    def __post_init__(self):
        need(all(type(v) is int and v>0 for v in self.__dict__.values()) and self.operations<=2**63-2,'finite positive limits')


def identity(node):
    return dict(voter=node,storage='disk-'+node,endpoint=node+':9000')


def config(root, generation, members):
    return digest(dict(root=root,generation=generation,members=members))


def initial(root, members):
    need(type(root) is str and bool(root),'root')
    validate_members(members)
    return dict(root=root,members=deepcopy(members),generation=0,configuration=config(root,0,members),
                index=0,dataIndex=0,data=digest(dict(root=root,genesis=True)),nextOperation=1,
                retiredThrough=0,active=None,results={},identities=deepcopy(members))


def validate_members(members):
    need(type(members) is list and 3<=len(members)<=5,'stable size')
    need(all(set(row)=={'voter','storage','endpoint'} and all(type(v) is str and 0<len(v)<=128 and v.isascii()
             for v in row.values()) for row in members),'member descriptor')
    need([row['voter'] for row in members]==sorted(row['voter'] for row in members),'member order')
    for key in ('voter','storage','endpoint'):
        need(len({row[key] for row in members})==len(members),'duplicate '+key)


def request(state,target,kind):
    return dict(root=state['root'],number=state['nextOperation'],expected=state['configuration'],kind=kind,target=deepcopy(target))


def joining(state,req):
    old={row['voter']:row for row in state['members']};new={row['voter']:row for row in req['target']}
    return [row for node,row in new.items() if node not in old]


def validate_request(state,req,limits):
    need(set(req)=={'root','number','expected','kind','target'} and req['root']==state['root'],'request root/fields')
    need(type(req['number']) is int and 1<=req['number']<=limits.operations,'operation number')
    validate_members(req['target'])
    old={row['voter']:row for row in state['members']};new={row['voter']:row for row in req['target']}
    shape=(len(new.keys()-old.keys()),len(old.keys()-new.keys()))
    need({'ADD':(1,0),'REMOVE':(0,1),'REPLACE':(1,1)}.get(req['kind'])==shape,'change kind/shape')
    need(all(old[n]==new[n] for n in old.keys()&new.keys()),'existing identity changed')
    need(req['expected']==state['configuration'],'stale configuration')
    for row in joining(state,req):
        for key in row:
            need(row[key] not in {used[key] for used in state['identities']},'reserved/retired identity reuse')


def active(state,number):
    need(state['active']==number,'no matching active operation')
    return state['results'][str(number)]


def receipt_for(state,number):
    row=active(state,number);need(row['phase']=='PREPARING','not preparing')
    peers=joining(state,row['request']);need(len(peers)==1,'no joining learner')
    return dict(root=state['root'],number=number,requestHash=row['requestHash'],revision=row['revision'],
                prepared=deepcopy(row['prepared']),identity=peers[0],
                image=digest(dict(cut=row['prepared'],identity=peers[0])))


def apply(state,command,limits,receipts):
    """Pure reducer of a single certified entry; guards run before any mutation."""
    s=deepcopy(state);kind=command['kind'];index=s['index']+1
    if kind=='RESERVE':
        req=command['request'];validate_request(s,req,limits)
        need(s['active'] is None,'operation busy')
        need(req['number']==s['nextOperation'],'number is not next')
        need(len(s['results'])<limits.results and s['generation']<limits.changes,'operation/change capacity')
        added=joining(s,req);need(len(s['identities'])+len(added)<=limits.identities,'identity capacity')
        row=dict(request=deepcopy(req),requestHash=digest(req),phase='RESERVED',revision=0,
                 prepared=None,receipt=None,binding=None,terminalIndex=None)
        s['results'][str(req['number'])]=row;s['active']=req['number'];s['nextOperation']+=1
        s['identities']+=deepcopy(added)
    elif kind=='DATA':
        if s['active'] is not None:need(active(s,s['active'])['phase'] not in ('SEALED','JOINT'),'transition pauses data')
        need(type(command['value']) is str and len(command['value'])<=128,'data value')
        s['data']=digest(dict(previous=s['data'],value=command['value']));s['dataIndex']=index
    elif kind=='RETIRE':
        through=command['through'];need(type(through) is int and s['retiredThrough']<through<s['nextOperation'],'retirement range')
        for number in range(s['retiredThrough']+1,through+1):
            need(str(number) in s['results'] and s['results'][str(number)]['phase'] in ('COMPLETED','CANCELLED'),
                 'cannot retire active/unknown operation')
        for number in range(s['retiredThrough']+1,through+1):del s['results'][str(number)]
        s['retiredThrough']=through
    else:
        row=active(s,command['number']);phase=row['phase']
        if kind=='PREPARE':
            need(phase in ('RESERVED','PREPARING','READY') and row['revision']<limits.revisions,'preparation unavailable')
            need(command['revision']==row['revision']+1,'revision not next')
            row['revision']=command['revision'];row['phase']='PREPARING';row['receipt']=None
            row['prepared']=dict(revision=row['revision'],index=s['index'],dataIndex=s['dataIndex'],data=s['data'],configuration=s['configuration'])
        elif kind=='READY':
            need(phase=='PREPARING','ready phase');peers=joining(s,row['request'])
            expected=receipt_for(s,command['number']) if peers else None
            need(command['receipt']==expected and (expected is None or digest(expected) in receipts),'unforced/stale learner receipt')
            row['receipt']=deepcopy(expected);row['phase']='READY'
        elif kind=='SEAL':
            need(phase=='READY' and row['prepared']['dataIndex']==s['dataIndex'] and row['prepared']['data']==s['data'],
                 'stale/unready materialization')
            row['binding']=digest(dict(request=row['request'],prepared=row['prepared'],receipt=row['receipt']))
            row['phase']='SEALED'
        elif kind=='INTENT':
            need(phase=='SEALED' and command['binding']==row['binding'],'intent not sealed/exact')
            row['phase']='JOINT'
        elif kind=='FINAL':
            need(phase=='JOINT' and command['binding']==row['binding'],'final not joint/exact')
            s['members']=deepcopy(row['request']['target']);s['generation']+=1
            s['configuration']=config(s['root'],s['generation'],s['members'])
            row['phase']='COMPLETED';row['terminalIndex']=index;s['active']=None
        elif kind=='CANCEL':
            need(phase in ('RESERVED','PREPARING','READY'),'irreversible transition')
            row['phase']='CANCELLED';row['terminalIndex']=index;s['active']=None
        else:raise ValueError('unknown control command')
    s['index']=index
    return s


class Store:
    def __init__(self,members,*,root='v53-operations',limits=Limits()):
        self.limits=limits;self.state=initial(root,members);self.start=deepcopy(self.state)
        need(limits.results>0 and limits.identities>=len(members) and limits.changes>0 and limits.revisions>0
             and limits.operations>0,'limits')
        self.pending=None;self.alive=True;self.receipts=set();self.events=[]

    def stage(self,command):
        need(self.alive and self.pending is None,'writer busy/offline')
        state=apply(self.state,command,self.limits,self.receipts)
        self.pending=(deepcopy(command),state);self.events.append(dict(event='stage',command=deepcopy(command)))

    def force(self):
        need(self.alive and self.pending is not None,'missing pending command')
        command,self.state=self.pending;self.pending=None
        self.events.append(dict(event='force',command=command,state=deepcopy(self.state)))

    def commit(self,kind,**values):self.stage(dict(kind=kind,**values));self.force()

    def learner_force(self,number):
        need(self.alive,'offline');receipt=receipt_for(self.state,number)
        self.receipts.add(digest(receipt));self.events.append(dict(event='learner-force',receipt=deepcopy(receipt)))
        return receipt

    def submit(self,req):
        need(req.get('root')==self.state['root'] and type(req.get('number')) is int and req['number']>0,'operation identity')
        number=req['number']
        if number<=self.state['retiredThrough']:return dict(status='RETIRED',through=self.state['retiredThrough'])
        retained=self.state['results'].get(str(number))
        if retained is not None:
            need(retained['request']==req,'operation ID conflict');return deepcopy(retained)
        self.commit('RESERVE',request=req);return deepcopy(self.state['results'][str(number)])

    def query(self,root,number):
        need(root==self.state['root'] and type(number) is int and number>0,'query identity')
        if number<=self.state['retiredThrough']:return dict(status='RETIRED',through=self.state['retiredThrough'])
        row=self.state['results'].get(str(number))
        return dict(status='UNKNOWN') if row is None else deepcopy(row)

    def crash(self):
        need(self.alive,'already stopped');self.pending=None;self.alive=False;self.events.append(dict(event='crash'))

    def restart(self):
        need(not self.alive,'already running');self.alive=True;self.events.append(dict(event='restart'))

    def detach_waiter(self):
        self.events.append(dict(event='client-detach'))  # timeout/cancel future is NOT cluster cancellation

    def evidence(self):
        return dict(initial=deepcopy(self.start),limits=self.limits.__dict__,events=deepcopy(self.events))


def read_allowed(policy,*,readable,role,known_removed,draining,minimum=None,cut=0,barrier=False):
    if not readable or known_removed or draining or role not in ('LEADER_READY','FOLLOWER','UNAVAILABLE'):return False
    if policy=='LEADER_STRONG':return role=='LEADER_READY' and barrier
    if policy=='STALE_ALLOWED':return True
    if policy=='AT_LEAST_INDEX':return minimum is not None and cut>=minimum
    raise ValueError('read policy')


def maintenance(state,target,responses,nonce):
    """Fresh barrier response set already authenticated; no process-stop or deletion authority."""
    need(state['active'] is None,'membership operation pending')
    need(type(nonce) is str and 0<len(nonce)<=128,'maintenance challenge')
    voters={m['voter'] for m in state['members']};need(target in voters,'maintenance target')
    names=[r['voter'] for r in responses]
    need(len(set(names))==len(names) and set(names)<=voters-{target},'maintenance voter set')
    need(len(names)>len(voters)//2 and all(r['configuration']==state['configuration'] and
         r['index']==state['index'] and r['nonce']==nonce and r['ready'] for r in responses),
         'maintenance fresh surviving majority')
    return dict(configuration=state['configuration'],index=state['index'],target=target,nonce=nonce)
