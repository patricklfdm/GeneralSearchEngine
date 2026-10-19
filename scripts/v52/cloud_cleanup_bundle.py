"""Bounded, source-bound manual cleanup evidence; receipt data is not admission."""
import argparse
import html
from pathlib import Path
from . import cloud_authority as a, cloud_preflight as f, cloud_preflight_read as r, cloud_provider as p
from . import cloud_artifacts as artifacts, cloud_cleanup_workflow as workflow
from .evidence import need, encoded, digest, strict

MAX_BYTES=64<<20
FILES={'configuration.json','observations.json','preflight.json','receipt.json'}
OPTIONAL={'original-context.json','reconciliation.json','exchanges.jsonl'}
LIMITS={**{name:16<<20 for name in FILES|OPTIONAL},'configuration.json':65536,'preflight.json':1<<20}
SCHEMA='gse-v52-cleanup-bundle-v1'


def validate(files,source,*,now):
    need(type(files) is dict and FILES <= set(files) <= FILES|OPTIONAL,'V5.2 cleanup bundle inventory')
    need(all(type(v) is bytes and 0<len(v)<=LIMITS[k] for k,v in files.items()) and sum(map(len,files.values()))<=MAX_BYTES,
         'V5.2 cleanup bundle size/type')
    values={key:strict(raw) for key,raw in files.items() if key.endswith('.json')}
    cfg=values['configuration.json'];f.configuration(cfg);receipt=values['receipt.json'];obs=values['observations.json']
    preflight=values['preflight.json'];a.integer(now,1)
    need(receipt['schema']=='gse-v52-native-cleanup-v1' and receipt['source']==source and receipt['role']=='manual' and
         receipt['trigger']=='workflow_dispatch' and receipt['scope']=='native-v52-cleanup-only' and receipt['paidCloud'] is True and
         receipt['paidAdmission'] is receipt['effectiveIamQualified'] is receipt['fullRemoteQualification'] is False,
         'V5.2 cleanup native receipt scope')
    allowed=set(('schema source role trigger checkedAt decisionAt context credentials originalRequestSha256 observationsSha256 '
                 'controlBefore controlAfter providerWrites resourceDeletesSubmitted deletionPathExercised paidAdmission '
                 'effectiveIamQualified fullRemoteQualification paidCloud scope status activeLease expiresAt graceSeconds '
                 'cleanup leaseReleased').split())
    need(set(receipt)<=allowed,'V5.2 cleanup unknown receipt fields')
    expected_context=f.context(cfg,source,'manual')
    need(encoded(receipt['context'])==encoded(expected_context) and obs['execution']=='native-v52-provider-observations',
         'V5.2 cleanup context/domain')
    a.integer(receipt['checkedAt'],preflight['checkedAt'],now)
    a.integer(receipt['decisionAt'],obs['completedAt'],receipt['checkedAt'])
    need(encoded(preflight)==encoded(f.evaluate(cfg,source,'manual',obs,now=preflight['checkedAt'])) and
         preflight['status']=='PREFLIGHT_OBSERVED_NOT_ADMITTED' and receipt['observationsSha256']==digest(encoded(obs)),
         'V5.2 cleanup original preflight')
    token=f.credential_receipt(receipt['credentials'],expected_context['credentialSelection'],source,obs['execution'])
    need(encoded(token)==encoded(obs['credentials']['context']),'V5.2 cleanup credential attempt changed')
    for key in ('controlBefore','controlAfter'):
        a.fields(receipt[key],'ledger lease','cleanup control snapshot')
        for name,value in receipt[key].items():f.snapshot(value,name)
    need(encoded(receipt['controlBefore'])==encoded(obs['controlAfter']),'V5.2 cleanup original generations changed')
    before,after=receipt['controlBefore'],receipt['controlAfter'];lease=before['lease']
    need(receipt['originalRequestSha256']==(a.validate_request(lease['value']['request'],domain='native') if lease else None),
         'V5.2 cleanup original request')
    a.integer(receipt['providerWrites']);a.integer(receipt['resourceDeletesSubmitted'],0,13)
    need(type(receipt['deletionPathExercised']) is bool and receipt['deletionPathExercised']==
         (receipt['resourceDeletesSubmitted']>0 and receipt['status']=='PASS'),'V5.2 cleanup deletion claim')
    if receipt['status']=='PASS':
        view=a.inspect_ledger(after['ledger']['value'] if after['ledger'] else a.empty_ledger(domain='native'),domain='native')
        need(after['lease'] is None and not any(row['status']=='PENDING' for row in view['attempts'].values()),
             'V5.2 cleanup pending final authority')
        if lease is None:
            need(receipt.get('activeLease') is False and receipt['providerWrites']==receipt['resourceDeletesSubmitted']==0 and
                 encoded(before)==encoded(after) and not (set(files)&OPTIONAL),'V5.2 cleanup empty observation changed')
        else:
            outcome=receipt['cleanup']
            a.fields(outcome,'status checks errors leftovers','cleanup result')
            need(receipt['leaseReleased'] is True and outcome['status']=='PASS' and outcome['errors']==outcome['leftovers']==[],
                 'V5.2 cleanup reconciliation failed')
            attempted=[v for v in lease['value']['resources'] if v['attempted']]
            checks=outcome['checks'];need(type(checks) is list and len(checks)==len(attempted),'V5.2 cleanup absence inventory')
            need(len({v['name'] for v in checks})==len(checks),'V5.2 duplicate cleanup absence')
            for item in attempted:
                rows=[v for v in checks if v['name']==item['spec']['name']]
                need(len(rows)==1 and rows[0]['absent'] is True and rows[0].get('observed') is None,
                     'V5.2 cleanup missing/foreign absence')
                identity=rows[0]['expectedId']
                need(item['id'] is None or item['id']==identity,'V5.2 cleanup original ID changed')
                if identity is not None:a.numeric(identity)
            need(OPTIONAL <= set(files),'V5.2 cleanup reconciliation evidence missing')
            context=values['original-context.json'];a.integer(context['generation'],1)
            original=context['value'];cfg_old=original['configuration'];req=lease['value']['request']
            need(encoded(original)==encoded(p.context(cfg_old,req,domain='native')) and
                 all(cfg_old[k]==cfg['provider'][k] for k in ('project','bucket')),'V5.2 cleanup retained original context')
            inner=values['reconciliation.json']
            need(inner['status']=='PASS' and inner['leaseReleased'] is True and inner['scope']==receipt['scope'] and
                 encoded(inner['cleanup'])==encoded(outcome),'V5.2 cleanup original reconciliation changed')
            previous=before['ledger'];current=after['ledger']
            old=a.inspect_ledger(previous['value'] if previous else a.empty_ledger(domain='native'),domain='native')
            row=old['attempts'].get(receipt['originalRequestSha256'])
            if row is not None and row['status']=='PENDING':
                need(current is not None and current['generation']>previous['generation'] and
                     len(current['value']['entries'])==len(previous['value']['entries'])+1 and
                     encoded(current['value']['entries'][:-1])==encoded(previous['value']['entries']) and
                     view['reservedCostMicrousd']==old['reservedCostMicrousd'] and
                     receipt['originalRequestSha256'] in view['attempts'], 'V5.2 cleanup terminal ledger changed history/cost')
            else:need(encoded(current)==encoded(previous),'V5.2 cleanup rewrote finished/unreserved ledger')
    else:
        need(receipt['status']=='WAITING' and after['lease'] is not None and receipt['providerWrites']==0,
             'V5.2 cleanup unsuccessful observation')
        current=after['lease']['value']
        need(current['phase']!='CLEANING' and receipt['decisionAt']<current['expiresAt']+current['graceSeconds'],
             'V5.2 cleanup waiting beyond original grace')
    if 'exchanges.jsonl' in files:
        journal(files['exchanges.jsonl'],receipt)
    else:need(receipt['providerWrites']==0,'V5.2 cleanup missing journal')
    return dict(schema=SCHEMA,status=receipt['status'],source=source,configurationSha256=f.configuration(cfg),
        runId=token['runId'],runAttempt=token['runAttempt'],checkedAt=receipt['checkedAt'],
        deletionPathExercised=receipt['deletionPathExercised'],paidAdmission=False,fullRemoteQualification=False)


def journal(raw,receipt):
    lines=raw.splitlines();need(0<len(lines)<=65536 and all(0<len(v)<=16384 for v in lines),'V5.2 cleanup journal bound')
    pending={};writes=deletes=0
    for raw in lines:
        row=strict(raw);a.integer(row['exchange'],1)
        common={'exchange','method','url','operation','phase'}
        need(set(row)==common|({'status','bytes'} if row['phase']=='response' else {'errorType'} if row['phase']=='uncertain' else set()),
             'V5.2 cleanup journal fields')
        if row['phase']=='send':
            need(row['exchange']==len(pending)+1,'V5.2 cleanup journal sequence')
            pending[row['exchange']]=dict(row,terminal=False)
            need(row['method'] in ('GET','POST','DELETE'),'V5.2 cleanup journal method')
            if row['method']!='GET':writes+=1
            if row['operation']=='delete':
                need(row['method']=='DELETE','V5.2 cleanup delete journal');deletes+=1
        else:
            need(row['phase'] in ('response','uncertain') and row['exchange'] in pending,'V5.2 cleanup journal phase')
            original=pending[row['exchange']]
            need(not original['terminal'] and all(row[k]==original[k] for k in common-{'phase'}),'V5.2 cleanup journal pairing')
            original['terminal']=True
            if row['phase']=='response':a.integer(row['status'],100,599);a.integer(row['bytes'],0,16<<20)
            else:need(type(row['errorType']) is str and row['errorType'].isidentifier(),'V5.2 cleanup journal error')
    need(all(v['terminal'] for v in pending.values()) and writes==receipt['providerWrites'] and deletes==receipt['resourceDeletesSubmitted'],
         'V5.2 cleanup journal incomplete/counts')


def seal(files,source,now):
    result=validate(files,source,now=now)
    return dict(schema=SCHEMA,inspection=result,files={k:dict(bytes=len(v),sha256=digest(v)) for k,v in sorted(files.items())})


def verify(files,source,now):
    need('seal.json' in files,'V5.2 cleanup seal missing')
    value=strict(files['seal.json']);body={k:v for k,v in files.items() if k!='seal.json'}
    need(encoded(value)==encoded(seal(body,source,now)),'V5.2 cleanup seal/inventory changed')
    return value['inspection']


def seal_native(source,root,output):
    root=Path(root);output=Path(output);cfg=r.source_configuration(source);workflow.contract()
    need(not (root/'failure.json').exists(),'V5.2 cleanup original factory failed')
    files={'configuration.json':encoded(cfg)}
    for name in (FILES-{'configuration.json'})|OPTIONAL:
        if name in FILES or (root/name).exists():files[name]=artifacts.inputs.regular(root/name,LIMITS[name])
    value=seal(files,source,int(r.time.time()))
    need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 cleanup bundle output symlink')
    output.mkdir(parents=True,exist_ok=False)
    for name,raw in files.items():
        with (output/name).open('xb') as stream:stream.write(raw)
    need(encoded(r.source_configuration(source))==encoded(cfg),'V5.2 cleanup bundle source changed')
    workflow.contract()
    artifacts.save(output/'seal.json',value)
    return value


def summary(root):
    root=Path(root)
    print('## V5.2 manual cleanup\n')
    if not (root/'receipt.json').exists() or (root/'failure.json').exists():
        print('Cleanup did not produce an accepted receipt. Inspect retained diagnostics.');return
    value=artifacts.read(root/'receipt.json')
    print('| Item | Result |\n| --- | --- |')
    for label,key in (('Status','status'),('Source','source'),('Original request','originalRequestSha256'),
        ('Control/resource writes submitted','providerWrites'),('Resource deletes submitted','resourceDeletesSubmitted'),
        ('Successful deletion path exercised','deletionPathExercised')):
        print('| '+label+' | '+html.escape(str(value.get(key,'—'))).replace('|','&#124;').replace('\n',' ')+' |')
    print('\nWAITING preserves an active lease. Empty PASS observes an idle control area; it does not prove deletion permissions.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',nargs='?',choices=('seal','summary'),default='seal')
    parser.add_argument('--source');parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.action=='summary':summary(args.root)
    else:
        if not args.source or not args.output:parser.error('seal requires source/output')
        value=seal_native(args.source,args.root,args.output);print(encoded(value['inspection']).decode())
