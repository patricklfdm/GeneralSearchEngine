"""Independent backup bytes, public restore and original receipt binding."""
from pathlib import Path
from . import performance_model as m, performance_semantics as semantics, remote_command as c
from . import cloud_package as package, cloud_workload_contract as contract, guest_bootstrap as bootstrap
from . import guest_authority as authority


def validate(root, config, base, manifest, rows, exchanges, state, stopped):
    backups=[(q,r) for q,r in rows if q['command']=='backup']
    restores=[(q,r) for q,r in rows if q['command']=='restore-backup']
    m.need(len(backups)==len(restores)==1, 'guest backup/restore coverage')
    (bq,br),(rq,rr)=backups[0],restores[0]
    windows=[r for q,r in rows if q['command']=='window']
    m.need(bq['payload']==rq['payload']=={} and windows and
           windows[-1]['endedNanos']<=br['startedNanos']<=br['endedNanos']<=stopped['startedNanos'] and
           stopped['endedNanos']<=rr['startedNanos']<=rr['endedNanos']<=rows[-1][1]['startedNanos'], 'guest backup/restore order')
    folder=root/'backup';backed=c.read(folder/'backup-result.json');restored=c.read(folder/'restore-result.json')
    m.need(backed==br['result'] and restored==rr['result'] and
           c.read(folder/'backup-claim.json')==dict(config=config) and
           c.read(folder/'restore-claim.json')==dict(config=config,backupSha256=m.sha(m.canonical(backed))), 'guest backup/restore receipt binding')
    files=authority.inventory(folder/'export')
    m.need(set(files)==set(bootstrap.SOURCE) and files==backed['files']==restored['files'], 'guest backup original inventory')
    response=backed['response'];op=response['opId']
    matches=[v for v in exchanges if v['request'].get('opId')==op]
    m.need(len(matches)==1, 'guest backup JVM coverage');exchange=matches[0]
    m.need(exchange['request']==dict(command='backup',opId=op) and exchange['response']==response and
           br['startedNanos']<=exchange['startNanos']<=exchange['endNanos']<=br['endedNanos'] and
           response['sequence']==state.sequence, 'guest backup JVM binding/cut')
    original=c.read(root/(config['binding']['node']+'-jvm.json'))
    process=restored['process']
    result=restore_process(root,config,base,manifest,process,rr,original,state)
    return op,files,result


def restore_process(root, config, base, manifest, process, receipt, original, state):
    base=Path(base);spec=manifest['modes'][package.MODES[0]]
    m.need(spec['main']==package.MAINS[package.MODES[0]] and spec['classes']=='classes-'+package.MODES[0] and
           len(spec['jars'])==1, 'guest public restore classpath')
    cp=':'.join(str(base/n) for n in [*spec['jars'],spec['classes']])
    agent=Path(config['root'])/'agents'/config['binding']['node']
    args=[str(base/'runtime/bin/java'),*contract.load()['environment']['jvmArguments'],'-cp',cp,
          package.PACKAGE+package.MAINS[package.MODES[0]],str(agent/'restored-check'),'restore',
          str(base/'source-inputs/docs/v5x/v5.1/phase6-plan.json'),str(Path(config['root'])/'export')]
    m.need(set(process)=={'args','pid','exitCode','startedNanos','endedNanos'} and process['args']==args and
           type(process['pid']) is int and process['pid']>0 and process['pid'] not in (original['pid'],receipt['process']['pid']) and
           type(process['exitCode']) is int and process['exitCode']==0 and
           receipt['startedNanos']<=process['startedNanos']<process['endedNanos']<=receipt['endedNanos'], 'guest independent restore process')
    decoded=semantics.source_backup(root/'backup/export',state)
    semantics.state_observation(c.read(root/'backup/restore.stdout',maximum=1<<20),state)
    return dict(status='PASS',sequence=state.sequence,backup=decoded,restorePid=process['pid'])


def trace_binding(traces, node, response):
    rows=[(owner,row) for owner,values in traces.items() for row in values
          if row['event'] in ('CLIENT_INVOKE','CLIENT_RESULT') and row.get('command')=='backup']
    m.need(len(rows)==2 and all(owner==node for owner,_ in rows), 'guest backup trace coverage/owner')
    invoke,result=[row for _,row in rows]
    m.need(invoke['event']=='CLIENT_INVOKE' and result['event']=='CLIENT_RESULT' and
           invoke['opId']==response['opId'] and invoke['pid']==response['pid'] and
           all(result.get(k)==v for k,v in response.items()) and invoke['order']<result['order'],
           'guest backup trace original response')
