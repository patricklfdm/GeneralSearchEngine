"""Additional physical-history admission for exact remote fault ACK barriers."""
from pathlib import Path
from . import remote_partition as controller,remote_partition_scope as scope,remote_voter as v
from .evidence import need,digest,encoded

FILE='partition-control.json'


def validate(root,binding):
    root=Path(root)
    need(v.scope.domains.matches(binding,'remotePartition',scope.EXECUTION) and scope.history(binding) is not None,
         'partition retained scope')
    v.h.bundle.inventory(root)
    scenario=v.c.read(root/'scenario.json',1<<20);record=v.c.read(root/FILE,v.c.REQUEST_BYTES)
    need(type(record) is dict and set(record)=={'schema','case','transitions','cleanup'} and
         record['schema']=='gse-v52-partition-controller-v1' and record['case']==scope.CASE and record['cleanup']==[],
         'partition incomplete controller evidence')
    rows=record['transitions'];target=scenario['target']
    need(type(rows) is list and len(rows)==2 and target in v.h.topology.NODES,'partition complete cut/heal')
    history=v.c.read(root/'history.json',16<<20)
    selected=[c for c in history if c['opId']==scenario['selectedStatus']]
    need(len(selected)==1,'partition selected-pair observation')
    for op,row in zip(('cut','heal'),rows):
        command=dict(operation=op,target=target)
        need(type(row) is dict and set(row)=={'request','startNanos','endNanos','nodes'} and row['request']==command and
             type(row['startNanos']) is int and type(row['endNanos']) is int and 0<row['startNanos']<row['endNanos'] and
             type(row['nodes']) is list and [r['node'] for r in row['nodes']]==list(v.h.topology.NODES),
             'partition controller barrier fields')
        for answer in row['nodes']:
            need(set(answer)=={'node','request','startNanos','endNanos','replyLost','answer'} and answer['request']==command and
                 type(answer['replyLost']) is bool and type(answer['startNanos']) is int and type(answer['endNanos']) is int and
                 row['startNanos']<=answer['startNanos']<answer['endNanos']<=row['endNanos'],'partition controller ACK order')
            node=answer['node'];control=root/(node+'-control');config=v.c.read(control/'config.json',v.c.REQUEST_BYTES)
            need(config['binding']==binding and config['node']==node,'partition selected service binding')
            controller.observed(answer['answer'],config,command)
            store=control/'partition';sha=digest(encoded(config))
            need(v.c.read(store/(op+'-request.json'))==dict(configSha256=sha,request=command) and
                 v.c.read(store/(op+'-result.json'))==answer['answer']['result'],'partition original receipt changed')
    need(selected[0]['endNanos']<rows[0]['startNanos']<rows[0]['endNanos']<=scenario['partitionNanos']<
         scenario['healIssuedNanos']<=rows[1]['startNanos']<rows[1]['endNanos']<=scenario['healCompletedNanos'],
         'partition whole-history barrier order')
    for node in v.h.topology.NODES:
        control=root/(node+'-control');store=control/'partition';config=v.c.read(control/'config.json',v.c.REQUEST_BYTES)
        need({p.name for p in store.iterdir()}=={'lock','cut-request.json','cut-result.json','heal-request.json','heal-result.json','final.json'},
             'partition unknown/partial/cleanup records')
        cut=v.c.read(store/'cut-result.json');heal=v.c.read(store/'heal-result.json')
        need(cut['beforeSha256'] is None and heal['beforeSha256']==cut['afterSha256'] and cut['endNanos']<heal['startNanos'],
             'partition original guest state order')
        need(v.c.read(store/'final.json')==dict(configSha256=digest(encoded(config)),currentSha256=digest(b'')),
             'partition collected state not healed')
    return dict(status='PASS',case=scope.CASE,transitions=2,receiverAcknowledgements=6)
