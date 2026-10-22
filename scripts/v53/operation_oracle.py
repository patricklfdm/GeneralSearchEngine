"""Independent committed-operation replay. Does not import operation_model."""
from copy import deepcopy

from .transition_model import digest
from .recovery_oracle import safe


TERMINAL={'CANCELLED','COMPLETED'}


def membership(rows):
    safe(type(rows) is list and 3<=len(rows)<=5,'member count')
    safe(all(set(r)=={'voter','storage','endpoint'} and all(type(v) is str and 0<len(v)<=128 and v.isascii()
             for v in r.values()) for r in rows),'descriptor fields')
    safe([r['voter'] for r in rows]==sorted(r['voter'] for r in rows),'descriptor order')
    for k in ('voter','storage','endpoint'):safe(len({r[k] for r in rows})==len(rows),'duplicate identity')


def expected_receipt(s,number):
    row=s['results'][str(number)];old={r['voter'] for r in s['members']}
    new=[r for r in row['request']['target'] if r['voter'] not in old]
    if not new:return None
    safe(len(new)==1 and row['phase']=='PREPARING','learner receipt phase')
    return dict(root=s['root'],number=number,requestHash=row['requestHash'],revision=row['revision'],
                prepared=row['prepared'],identity=new[0],image=digest(dict(cut=row['prepared'],identity=new[0])))


def next_state(before,cmd,limits,receipts):
    s=deepcopy(before);kind=cmd['kind'];position=s['index']+1
    if kind=='RESERVE':
        r=cmd['request'];membership(r['target']);number=r['number']
        safe(set(r)=={'root','number','expected','kind','target'} and r['root']==s['root'] and
             type(number) is int and number==s['nextOperation'] and 1<=number<=limits['operations'] and
             s['active'] is None and len(s['results'])<limits['results'] and s['generation']<limits['changes'], 'reservation allocation')
        safe(r['expected']==s['configuration'],'reservation configuration')
        old={x['voter']:x for x in s['members']};target={x['voter']:x for x in r['target']}
        delta=(len(target.keys()-old.keys()),len(old.keys()-target.keys()))
        safe(delta=={'ADD':(1,0),'REMOVE':(0,1),'REPLACE':(1,1)}.get(r['kind']) and
             all(target[n]==old[n] for n in target.keys()&old.keys()),'reservation target')
        added=[x for x in r['target'] if x['voter'] not in old]
        safe(len(s['identities'])+len(added)<=limits['identities'],'identity capacity')
        for row in added:
            safe(all(row[k] not in {x[k] for x in s['identities']} for k in row),'identity reused')
        s['identities']+=added;s['active']=number;s['nextOperation']+=1
        s['results'][str(number)]=dict(request=r,requestHash=digest(r),phase='RESERVED',revision=0,
             prepared=None,receipt=None,binding=None,terminalIndex=None)
    elif kind=='DATA':
        safe(s['active'] is None or s['results'][str(s['active'])]['phase'] not in ('SEALED','JOINT'),'data after seal')
        safe(type(cmd['value']) is str and len(cmd['value'])<=128,'data value')
        s['data']=digest(dict(previous=s['data'],value=cmd['value']));s['dataIndex']=position
    elif kind=='RETIRE':
        end=cmd['through'];safe(type(end) is int and s['retiredThrough']<end<s['nextOperation'],'retire range')
        for n in range(s['retiredThrough']+1,end+1):
            safe(str(n) in s['results'] and s['results'][str(n)]['phase'] in TERMINAL,'active result retired')
            del s['results'][str(n)]
        s['retiredThrough']=end
    else:
        n=cmd['number'];safe(s['active']==n,'foreign operation');row=s['results'][str(n)];phase=row['phase']
        if kind=='PREPARE':
            safe(phase in ('RESERVED','PREPARING','READY') and cmd['revision']==row['revision']+1
                 and row['revision']<limits['revisions'],'preparation revision')
            row.update(phase='PREPARING',revision=cmd['revision'],receipt=None)
            row['prepared']=dict(revision=cmd['revision'],index=s['index'],dataIndex=s['dataIndex'],data=s['data'],configuration=s['configuration'])
        elif kind=='READY':
            safe(phase=='PREPARING','ready before prepare');expected=expected_receipt(s,n)
            safe(cmd['receipt']==expected and (expected is None or digest(expected) in receipts),'ready without original forced receipt')
            row.update(phase='READY',receipt=expected)
        elif kind=='SEAL':
            safe(phase=='READY' and row['prepared']['dataIndex']==s['dataIndex'] and row['prepared']['data']==s['data'],'stale seal')
            row['binding']=digest(dict(request=row['request'],prepared=row['prepared'],receipt=row['receipt']));row['phase']='SEALED'
        elif kind=='INTENT':
            safe(phase=='SEALED' and cmd['binding']==row['binding'],'unsealed intent');row['phase']='JOINT'
        elif kind=='FINAL':
            safe(phase=='JOINT' and cmd['binding']==row['binding'],'foreign final')
            s['members']=deepcopy(row['request']['target']);s['generation']+=1
            s['configuration']=digest(dict(root=s['root'],generation=s['generation'],members=s['members']))
            row.update(phase='COMPLETED',terminalIndex=position);s['active']=None
        elif kind=='CANCEL':
            safe(phase in ('RESERVED','PREPARING','READY'),'cancel after irreversible seal')
            row.update(phase='CANCELLED',terminalIndex=position);s['active']=None
        else:safe(False,'unknown command')
    s['index']=position
    return s


def check(record):
    s=deepcopy(record['initial']);limits=record['limits'];members=s['members'];membership(members)
    safe(s==dict(root=s['root'],members=members,generation=0,configuration=digest(dict(root=s['root'],generation=0,members=members)),
         index=0,dataIndex=0,data=digest(dict(root=s['root'],genesis=True)),nextOperation=1,retiredThrough=0,
         active=None,results={},identities=members),'initial metadata')
    pending=None;receipts=set();alive=True;commits=0
    for event in record['events']:
        kind=event['event']
        if kind=='stage':
            safe(alive and pending is None,'overlapping command')
            pending=(deepcopy(event['command']),next_state(s,event['command'],limits,receipts))
        elif kind=='force':
            safe(alive and pending is not None and pending[0]==event['command'] and pending[1]==event['state'],
                 'missing force predecessor or changed state')
            s=pending[1];pending=None;commits+=1
        elif kind=='learner-force':
            value=event['receipt'];safe(alive and s['active']==value['number'] and expected_receipt(s,value['number'])==value,
                                       'foreign learner force')
            receipts.add(digest(value))
        elif kind=='crash':safe(alive,'duplicate crash');alive=False;pending=None
        elif kind=='restart':safe(not alive,'restart running');alive=True
        elif kind!='client-detach':safe(False,'unknown operation event')
    return dict(commits=commits,events=len(record['events']),state=s)
