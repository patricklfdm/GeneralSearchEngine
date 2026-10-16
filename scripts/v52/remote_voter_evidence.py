"""Correlate persistent channels by exact messages, never by clock subtraction.

This is additional local lifecycle evidence, not a replacement for physical,
query, offered-window or cross-host replication causality validation.
"""
from pathlib import Path
from . import remote_voter as voter, remote_command as c, remote_host as host
from . import measurement_history as ledger, remote_topology as topology
from .evidence import need, encoded, digest


def edges(events,calls,node):
    need(type(events) is list and 1<=len(events)<=2*voter.MAX_CALLS+1,'voter event count')
    need(type(calls) is list and len(calls)<=voter.MAX_CALLS,'voter call count')
    owned={call['opId']:call for call in calls}
    need(len(owned)==len(calls),'voter duplicate controller operation')
    sent={};received=set();previous=0
    for seq,row in enumerate(events,1):
        need(type(row) is dict and type(row.get('seq')) is int and row['seq']==seq,'voter event sequence')
        now=row['localNanos'];need(type(now) is int and now>0 and now>=previous,'voter guest clock order');previous=now
        base={'seq','kind','localNanos'};kind=row['kind']
        if kind=='SUBMIT':
            need(set(row)==base|{'request'},'voter submit event fields')
            request=row['request'];op=request['opId']
            need(op==f'{node}-g1-{len(sent)+1}' and op in owned and op not in sent,'voter duplicate/foreign submit')
            need(request==ledger.request(owned[op]),'voter original request changed');sent[op]=row
        elif kind=='RESULT':
            need(set(row)==base|{'response'},'voter result event fields')
            response=row['response'];op=response['opId']
            need(op in sent and op not in received,'voter unsubmitted/duplicate response')
            call=owned[op];need(call['node']==node and call['generation']==1 and call['response']==response and
                              call['outcome']==response['outcome'],'voter original response changed')
            need(type(call['startNanos']) is int and type(call['endNanos']) is int and
                 0<call['startNanos']<call['endNanos'],'voter controller clock order')
            # JVM API times are yet another domain. Full trace replay validates
            # these against JVM observations; no Python/Java epoch is inferred.
            need(all(type(response[k]) is int for k in ('receivedNanos','apiStartNanos','apiEndNanos')) and
                 response['receivedNanos']<=response['apiStartNanos']<=response['apiEndNanos'],'voter JVM clock order')
            received.add(op)
        else:
            need(kind=='STOPPED' and seq==len(events) and set(row)==base|{'exitCode','failure'} and
                 type(row['exitCode']) is int and row['exitCode']==0 and row['failure'] is None,'voter incomplete stop')
    need(events[-1]['kind']=='STOPPED' and set(sent)==received==set(owned),'voter incomplete message edges')
    return dict(operations=len(owned),messageEdges=2*len(owned))


def validate(root,binding):
    root=Path(root);need(binding['remoteTopology']['placement']=='local-no-gcp','voter cross-host qualification unavailable')
    need(binding.get('remoteVoterControl')=='local-persistent-voters-v1','voter control binding')
    voter.h.bundle.inventory(root)
    need(c.read(root/'binding.json',4<<20)==binding,'voter evidence binding changed')
    history=c.read(root/'history.json',16<<20);processes=c.read(root/'processes.json',64<<10)
    controller=c.read(root/'controller-domain.json',4096)
    need(set(controller)=={'clock','process','session'} and controller['clock']=='python-monotonic-ns','voter controller domain')
    c.hex_value(controller['session'],32,'controller session');c.validate_process(controller['process'],controller['process'])
    results={};services=set();jvms=set()
    for node in topology.NODES:
        control=root/(node+'-control');config=c.read(control/'config.json',c.REQUEST_BYTES);sha=digest(encoded(config))
        need(set(config)=={'schema','execution','node','root','host','binding','socket','session'} and
             config['schema']==voter.SCHEMA and config['execution']=='local-persistent-voters-only' and
             config['binding']==binding and config['node']==node and config['root']==binding['remoteReceivers'][node]['originalRoot'],
             'voter retained config binding')
        host.validate_pin(config['host']);c.hex_value(config['session'],32,'voter session')
        need(c.read(control/'launch.json')==dict(configSha256=sha),'voter retained launch')
        identity=c.read(control/'identity.json');started=c.read(control/'started.json');stopped=c.read(control/'stopped.json')
        need(set(identity)=={'service','jvm','consumer','host','session'} and identity['host']==config['host'] and
             identity['session']==config['session'],'voter retained identity')
        for kind,seen in (('service',services),('jvm',jvms)):
            value=identity[kind];c.validate_process(value,config['host'])
            need(value['bootId']==controller['process']['bootId'],'voter local-only boot binding')
            key=tuple(value[k] for k in ('bootId','pid','startTicks'));need(key not in seen,'voter duplicate process identity');seen.add(key)
        need(started==dict(configSha256=sha,service=identity['service']),'voter retained start')
        records=[p for p in processes if p['node']==node]
        need(len(records)==1 and records[0]==dict(node=node,generation=1,pid=identity['jvm']['pid'],exitCode=0,identity=identity['consumer']),
             'voter JVM physical binding')
        path=control/'events.jsonl';need(path.is_file() and not path.is_symlink() and path.stat().st_size<=voter.MAX_BYTES,'voter journal file bound')
        events=[]
        with path.open('rb') as stream:
            while True:
                value=voter.receive(stream)
                if value is None:break
                events.append(value);need(len(events)<=2*voter.MAX_CALLS+1,'voter journal count bound')
        need(stopped==dict(schema=voter.SCHEMA,configSha256=sha,identity=identity,lastSequence=len(events),
             journalSha256=voter.h.bundle.sha_file(path),exitCode=0,failure=None),'voter retained terminal binding')
        if 'remoteVoterLifecycle' in binding or (control/'lifecycle.json').exists():
            from . import remote_voter_lifecycle_evidence
            remote_voter_lifecycle_evidence.validate(root,binding,config,sha)
        own=[call for call in history if call['node']==node]
        need(all(call['pid']==identity['jvm']['pid'] for call in own),'voter controller process binding')
        results[node]=edges(events,own,node)
        if 'remoteVoterTransport' in binding or (control/'ssh-streams.json').exists():
            from . import remote_voter_ssh_evidence
            remote_voter_ssh_evidence.validate(control,binding,config,sha,events)
    need(not services & jvms and all(v[1]!=controller['process']['pid'] for v in services|jvms),'voter independent process owners')
    need(sum(v['operations'] for v in results.values())==len(history),'voter foreign controller call')
    return dict(status='PASS',execution='local-persistent-voter-message-edges-only',nodes=results,
                qualifiedMeasurement=False,fullRemoteQualification=False,paidCloud=False)
