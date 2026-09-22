"""Independent lifecycle/queue evidence, separate from internal mailbox witnesses."""
import copy
import json
import tarfile
from pathlib import Path
from . import storage_inspector as s, runtime_evidence as a
from .storage_harness import need


def classify(call, reason, outcome):
    need(call.get('reasonCode') == reason and call.get('outcome') == outcome, 'incorrect rejection classification')


def mailbox(result):
    need(result['execution']=='internal-runtime-mailbox' and result['publicRuntime'] is False,'internal mailbox relabelled public')
    kind=result['case'];need(kind in ('inputs','completions'),'unknown mailbox')
    limit=32 if kind=='inputs' else 16
    need(result['limit']==limit and result['initialSize']==0 and result['initialRemaining']==limit,'mailbox boundary changed')
    need(result['fullSize']==limit and result['fullRemaining']==0,'mailbox was not full')
    need(result['rejection']==dict(reason='CAPACITY_EXCEEDED',outcome='NOT_SUBMITTED' if kind=='inputs' else 'INDETERMINATE'),'mailbox failure classification')
    need(result['executed']==list(range(limit)) and result['finalSize']==0,'admitted task lost/reordered or refused task executed')
    failed=kind=='completions'
    need(result['closingAtOverflow'] is failed and result['failureAtOverflow'] is failed,'mailbox overflow failure state')
    if failed:need(result['afterOverflow']==dict(reason='CLOSED',outcome='NOT_SUBMITTED'),'completion failure admitted more input')
    else:need(result.get('resumed') is True,'input capacity not reused')


def internal(root):
    root=Path(root);result=json.loads((root/'result.json').read_text());mailbox(result)
    def inventory(name):return {v['path']:dict(size=v['size'],sha256=v['sha256']) for v in json.loads((root/name).read_text())}
    before=inventory('before.json');need(before==inventory('after.json')==s.inventory(root/'node-1'),'mailbox fixture changed authority')
    with tarfile.open(root/'before-reopen.tar.gz') as tar:
        saved={m.name.removeprefix('node-1/'):dict(size=m.size,sha256=s.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
    need(saved==before,'mailbox archive changed')
    report=s.inspect(root/'node-1');reopened=json.loads((root/'reopened.json').read_text())
    need(reopened['pid']!=result['pid'],'mailbox reopen reused JVM')
    for key in ('promisedEpoch','acceptedThrough','provenThrough','applicationSequence'):need(report[key]==reopened['status'][key],'mailbox reopened authority differs')
    need(report['acceptedThrough']==report['provenThrough']==report['applicationSequence']==0,'mailbox fixture manufactured application progress')
    variants=[]
    for name,change in [('changed-limit',lambda r:r.update(limit=1)),('missing-task',lambda r:r['executed'].pop()),
                         ('refused-task-executed',lambda r:r['executed'].append(r['limit'])),
                         ('wrong-outcome',lambda r:r['rejection'].update(outcome='SUCCESS')),
                         ('public-label',lambda r:r.update(publicRuntime=True)),
                         ('wrong-failure-state',lambda r:r.update(failureAtOverflow=not r['failureAtOverflow']))]:
        value=copy.deepcopy(result);change(value)
        try:mailbox(value)
        except ValueError as error:variants.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('mailbox oracle admitted '+name)
    return dict(status='PASS',execution='internal-runtime-mailbox',publicRuntime=False,inspection=report,negatives=variants)


def public(root,traces,history,receipt):
    root=Path(root);case=receipt['case'];leader=receipt['leader'];rows=traces[leader]
    need(case in ('queued-deadline','query-reentrancy','completion-chain','completion-capacity'),'unknown backpressure case')
    encoded=(root/'node-1/manifest.gsr').read_bytes()
    seal=s.f.inspect((root/'node-1/bootstrap-seal.gsr').read_bytes(),'SEAL')
    plan=s.f.inspect(s.raw(s.f.inspect(s.raw(seal['receipt']),'RECEIPT')['plan']),'PLAN')
    need(s.raw(plan['manifest'])==encoded,'backpressure bootstrap binding')
    need(all(t['bounds']['maxPendingClientOperations']==4 and t['policy']['operationTimeoutMillis']==9600 for t in plan['targets']),'unsealed public bound/deadline')
    calls={v['opId']:v for v in history};need(len(calls)==len(history),'duplicate backpressure call')
    for call in history:
        own=[r for r in traces[call['node']] if r['pid']==call['pid'] and r.get('opId')==call['opId']]
        invokes=[r for r in own if r['event']=='CLIENT_INVOKE']
        ends=[r for r in own if r['event'] in ('CLIENT_SUCCESS','CLIENT_FAILURE')]
        need(len(invokes)==len(ends)==1 and invokes[0]['order']<ends[0]['order'],'missing actual client interval')
        need(ends[0]['outcome']==call['outcome'] and ends[0].get('reasonCode')==call.get('reasonCode'),'client rejection differs from worker')
    def one(event,opid):
        found=[r for r in rows if r['event']==event and r.get('opId')==opid]
        need(len(found)==1,'missing/duplicate '+event);row=found[0]
        need(opid in calls and row['pid']==calls[opid]['pid'] and row['generation']==calls[opid]['generation'],'callback process identity')
        return row
    def order(event,opid):return one(event,opid)['order']
    for key,kind in (('resumedWrite','addAll'),('resumedRead','read'),('afterRestartRead','read')):
        call=calls[receipt[key]];need(call['kind']==kind and call['outcome']=='SUCCESS','missing later public service')
    starts=[r for r in rows if r['event']=='STARTED']
    need(len(starts)==2 and len({r['pid'] for r in starts})==2 and {r['generation'] for r in starts}=={1,2},'missing retained public restart')
    archive=root/'before-reopen.tar.gz';saved=receipt['retained']
    need(saved['node']==leader and s.sha(archive.read_bytes())==saved['sha256'],'backpressure archive identity')
    with tarfile.open(archive) as tar:
        inventory={m.name.removeprefix(leader+'/'):dict(size=m.size,sha256=s.sha(tar.extractfile(m).read())) for m in tar.getmembers() if m.isfile()}
    need(inventory==saved['inventory'],'backpressure retained bytes changed')
    need(calls[receipt['afterRestartRead']]['startNanos']>receipt['restartNanos']>calls[receipt['resumedRead']]['endNanos'],'restart read precedes recovery')
    rejected=[];last=0
    if case=='queued-deadline':
        held=receipt['heldRead'];begin=one('QUERY_HELD',held);end=one('QUERY_HELD_RELEASED',held)
        need(calls[held]['kind']=='read' and calls[held]['outcome']=='SUCCESS','active cooperative query did not finish')
        need(len(receipt['queued'])==3 and len(set(receipt['queued']))==3,'missing queued operations')
        for opid in receipt['queued']:
            call=calls[opid];classify(call,'DEADLINE_EXCEEDED','NOT_SUBMITTED');rejected.append(opid)
            invoke=one('CLIENT_INVOKE',opid);returned=one('CLIENT_FAILURE',opid)
            need(begin['order']<invoke['order']<returned['order']<end['order'],'queued failure outside held query')
            need(returned['localNanos']-invoke['localNanos']>=9600*1_000_000,'queued failure before sealed deadline')
            need(order('CLIENT_ENQUEUED',opid)<returned['order'],'missing queued submission')
        overflow=receipt['overflow'];classify(calls[overflow],'CAPACITY_EXCEEDED','NOT_SUBMITTED');rejected.append(overflow)
        need(max(order('CLIENT_ENQUEUED',i) for i in receipt['queued'])<order('CLIENT_FAILURE',overflow)<min(order('CLIENT_FAILURE',i) for i in receipt['queued']),'overflow was not while queued calls owned capacity')
        need(end['localNanos']-begin['localNanos']>9600*1_000_000,'cooperative callback did not span deadline')
        need(not any(r['event']=='ARGUMENT_TOUCHED' for r in rows),'rejected queued argument evaluated');last=end['order']
    elif case=='query-reentrancy':
        opid=receipt['callbackRead'];need(calls[opid]['outcome']=='SUCCESS','outer query failed')
        invoked=one('READ_CALLBACK',opid);finished=one('CLIENT_SUCCESS',opid)
        nested=[r for r in rows if r['event']=='REENTRY' and r.get('opId')==opid]
        methods={'add','read','start','checkpoint','backup','close'}
        need(len(nested)==6 and {r['method'] for r in nested}==methods,'missing nested reentry check')
        for row in nested:
            classify(row,'REENTRANT_CALL','NOT_SUBMITTED' if row['method']=='add' else 'NOT_APPLICABLE')
            need(row['pid']==invoked['pid'] and invoked['order']<row['order']<finished['order'],'reentry outside query callback')
        diagnostic=one('CALLBACK_DIAGNOSTICS',opid);need(diagnostic['schema'] is True and diagnostic['durability']=='OPEN','callback diagnostics unavailable')
        releases=[r for r in rows if r['event']=='READ_RELEASED' and r['pid']==invoked['pid'] and invoked['order']<r['order']<finished['order']]
        need(len(releases)==1 and max(r['order'] for r in nested)<releases[0]['order'],'reentry after query release')
        need(not any(r['event']=='FORCE' and r['kind']=='ACCEPT' and r['pid']==invoked['pid'] and invoked['order']<r['order']<releases[0]['order'] for r in rows),'reentry appended authority');last=finished['order']
    elif case=='completion-chain':
        need(len(receipt['chain'])==3 and len(set(receipt['chain']))==3,'missing completion chain')
        first,second,read=receipt['chain'];enter=one('COMPLETION_CHAIN_ENTER',first);leave=one('COMPLETION_CHAIN_EXIT',first)
        need([calls[i]['kind'] for i in (first,second,read)]==['addAll','addAll','read'] and all(calls[i]['outcome']=='SUCCESS' for i in (first,second,read)),'nested callback operation failed')
        need(order('CLIENT_SUCCESS',first)<enter['order']<order('CLIENT_INVOKE',second)<order('CLIENT_SUCCESS',second)<order('CLIENT_INVOKE',read)<order('CLIENT_SUCCESS',read)<leave['order'],'nested calls not inside completion callback')
        need(enter['thread'].startswith('gse-automatic-public-completion-'),'completion handler ran on submitting thread');last=leave['order']
    else:
        held=receipt['heldCompletions'];need(len(held)==4 and len(set(held))==4,'completion capacity not full')
        starts=[];ends=[]
        for opid in held:
            need(calls[opid]['kind']=='addAll' and calls[opid]['outcome']=='SUCCESS','held completion was not successful write')
            begin=one('COMPLETION_HELD',opid);end=one('COMPLETION_HELD_RELEASED',opid)
            need(order('CLIENT_SUCCESS',opid)<begin['order']<end['order'],'completion hold order')
            need(begin['thread'].startswith('gse-automatic-public-completion-'),'held callback on submitting thread')
            starts.append(begin['order']);ends.append(end['order'])
        need(len(receipt['rejected'])==2,'missing completion-capacity calls')
        for opid,kind in zip(receipt['rejected'],('addAll','read')):
            need(calls[opid]['kind']==kind,'wrong overflow call');classify(calls[opid],'CAPACITY_EXCEEDED','NOT_SUBMITTED' if kind=='addAll' else 'NOT_APPLICABLE')
            need(max(starts)<order('CLIENT_INVOKE',opid)<order('CLIENT_FAILURE',opid)<min(ends),'capacity failure outside held completions')
            if kind=='addAll':rejected.append(opid)
        last=max(ends)
    need(last<order('CLIENT_INVOKE',receipt['resumedWrite']),'later write precedes released pressure')
    # Check every local ACCEPT, not just quorum-chosen writes, for rejected payloads.
    denied=[calls[i]['documents'] for i in rejected]
    for own in traces.values():
        for row in own:
            if row['event']=='FORCE' and row['kind']=='ACCEPT':
                vote=s.f.inspect(s.raw(row['record']),'ACCEPT');entry=s.f.inspect(s.raw(vote['entry']),'ENTRY')
                if entry['operation']==4:need([dict(id=k,value=v) for k,v in a.documents_command(s.raw(entry['payload']))] not in denied,'rejected operation has local ACCEPT')
    return dict(status='PASS',case=case,publicRuntime=True,rejectedWithoutAccept=len(rejected))


def public_negatives(root,traces,history,receipt):
    variants=[];leader=receipt['leader'];case=receipt['case']
    def remove(name):
        changed={n:[r for r in rows if r['event']!=name] for n,rows in traces.items()};variants.append(('missing-'+name,changed,history,receipt))
    remove('STARTED')
    for key in ('resumedWrite','resumedRead','afterRestartRead'):
        changed=copy.deepcopy(history);next(v for v in changed if v['opId']==receipt[key])['outcome']='NOT_APPLICABLE';variants.append(('missing-'+key,traces,changed,receipt))
    claim=copy.deepcopy(receipt);claim['retained']['sha256']='0'*64;variants.append(('changed-archive',traces,history,claim))
    events={'queued-deadline':['QUERY_HELD','QUERY_HELD_RELEASED','CLIENT_ENQUEUED'],
            'query-reentrancy':['REENTRY','CALLBACK_DIAGNOSTICS'],
            'completion-chain':['COMPLETION_CHAIN_ENTER','COMPLETION_CHAIN_EXIT'],
            'completion-capacity':['COMPLETION_HELD','COMPLETION_HELD_RELEASED']}[case]
    for event in events:remove(event)
    changed=copy.deepcopy(traces)
    if case=='queued-deadline':
        next(r for r in changed[leader] if r['event']=='CLIENT_FAILURE' and r.get('opId')==receipt['queued'][0])['localNanos']=0
    elif case=='query-reentrancy':next(r for r in changed[leader] if r['event']=='REENTRY')['reasonCode']='NOT_READY'
    elif case=='completion-chain':next(r for r in changed[leader] if r['event']=='COMPLETION_CHAIN_ENTER')['thread']='main'
    else:next(r for r in changed[leader] if r['event']=='COMPLETION_HELD')['thread']='main'
    variants.append(('invalid-boundary',changed,history,receipt))
    if case=='queued-deadline':
        changed=copy.deepcopy(traces);row=copy.deepcopy(next(r for r in changed[leader] if r['event']=='CLIENT_ENQUEUED' and r.get('opId')==receipt['queued'][0]));row['event']='ARGUMENT_TOUCHED';changed[leader].append(row)
        variants.append(('evaluated-expired-argument',changed,history,receipt))
        changed=copy.deepcopy(history);next(v for v in changed if v['opId']==receipt['queued'][0])['outcome']='INDETERMINATE'
        variants.append(('unsafe-queued-outcome',traces,changed,receipt))
    if case=='query-reentrancy':
        changed=copy.deepcopy(traces);next(r for r in changed[leader] if r['event']=='REENTRY')['outcome']='SUCCESS'
        variants.append(('nested-call-succeeded',changed,history,receipt))
    if case=='completion-capacity':
        changed=copy.deepcopy(traces);row=next(r for r in changed[leader] if r['event']=='COMPLETION_HELD_RELEASED');row['order']=1
        variants.append(('early-permit-release',changed,history,receipt))
    claim=copy.deepcopy(receipt);claim['restartNanos']=max(v['endNanos'] for v in history)+1
    variants.append(('read-before-restart',traces,history,claim))
    result=[]
    for name,t,h,r in variants:
        try:public(root,t,h,r)
        except ValueError as error:result.append(dict(case=name,status='REJECTED',reason=str(error)))
        else:raise ValueError('backpressure oracle admitted '+name)
    return result
