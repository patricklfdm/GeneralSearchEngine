"""Closed Phase 6B workload arithmetic; never admits a remote or paid execution."""
import argparse
from pathlib import Path
import struct
from . import performance_model as m, performance_plan as local

PLAN=Path(__file__).resolve().parents[2]/'docs/v5x/v5.1/phase6-cloud-workload-plan.json'
PRE_AMENDMENT_SHA256='bee0b38ae20611a0d36259e554c5d03b1e1ebd87fc71ab648b3848681854754a'
PLAN_SHA256='f0e964ba12fea8702a40082d4a01a85d6d3eb1bf7fe3fecf8778c899af44bea7'


def load(path=PLAN):
    path=Path(path)
    m.need(path.is_file() and not path.is_symlink() and path.stat().st_size<=65536,'cloud contract file')
    value=m.strict_json(path.read_bytes())
    validate(value)
    return value


def payload(operation, keys, documents):
    if operation not in m.OP_IDS:return b''
    result=b'\x00\x01'
    if operation.startswith('INDEX'):
        return result+m.blob(m.canonical(m.INDEXES[1]) if operation=='INDEX_CREATE' else b'category')
    result+=struct.pack('>i',len(keys))
    for i,key in enumerate(keys):
        result+=m.blob(struct.pack('>i',key))
        if documents:result+=m.blob(m.encode_document(documents[i]))
    return result


def call(operation,keys,cycle,**values):
    documents=[m.document(k,1+cycle%9) for k in keys] if operation.startswith(('ADD','UPDATE')) else []
    return dict(operation=operation,keys=keys,documents=documents,cycle=cycle,
                payload=payload(operation,keys,documents),**values)


def program(value,cell,preset='canonical'):
    """Complete planned arrivals; concurrent tape order is a reference interleaving only."""
    m.need(cell in ('healthy','read-heavy','sustained') and preset in ('canonical','experiment'), 'unknown rich schedule')
    if cell=='healthy':
        h=value['healthy'];c=value['corpus'];interval=h['arrivalIntervalMillis']
        warmup=h['warmupCalls'];seconds=h['windowSeconds']
        if preset=='experiment':
            warmup=value['presets']['experiment']['healthyWarmupCalls'];seconds=value['presets']['experiment']['healthyWindowSeconds']
        cycle=0
        for window,count in [('warmup',warmup)]+[(w,seconds*1000//interval) for w in h['windows']]:
            for ordinal in range(count):
                op=h['operations'][ordinal%10];size=c['mutationBulkElements'] if op.endswith('_ALL') else 1
                keys=([1+cycle%c['documents']] if op=='GET' else [] if op.startswith('INDEX') or op=='QUERY' else
                      [1+(cycle+i)%c['documents'] if op.startswith('UPDATE') else 100000+cycle*100+i for i in range(size)])
                yield call(op,keys,cycle,window=window,lane=0,dueMillis=ordinal*interval)
                if ordinal%10==9:cycle+=1
    else:
        p=value['readHeavy' if cell=='read-heavy' else 'sustained']
        for burst in range(p['seconds']*1000//p['burstPeriodMillis']):
            for lane in range(p['lanes']):
                if cell=='read-heavy':
                    ops=p['operationsByLane'][lane];op=ops[burst%len(ops)];cycle=burst
                    keys=[] if op=='QUERY' else [1+burst%value['corpus']['documents']]
                else:
                    ops=p['operationsByLane'];op=ops[burst%len(ops)];cycle=burst//len(ops)
                    keys=[] if op=='QUERY' else [200000+lane*10000+cycle]
                yield call(op,keys,cycle,window=cell,lane=lane,dueMillis=burst*p['burstPeriodMillis'])


def projection(value,cell,preset='canonical'):
    state=m.initial(local.load());peak=len(state.documents);rows=list(program(value,cell,preset))
    for row in rows:
        if row['operation'] in m.OP_IDS:state.apply(m.OP_IDS[row['operation']],row['payload'])
        elif row['operation']=='GET':m.need(row['keys'][0] in state.documents,'planned GET missing')
        peak=max(peak,len(state.documents))
    mutations=sum(r['operation'] in m.OP_IDS for r in rows)
    return dict(calls=len(rows),mutations=mutations,reads=len(rows)-mutations,finalSequence=state.sequence,
                finalDocuments=len(state.documents),peakDocuments=peak,maximumPayloadBytes=max(len(r['payload']) for r in rows),
                maximumDocumentBytes=max((len(m.encode_document(d)) for r in rows for d in r['documents']),default=0),
                scheduleSha256=m.sha(m.canonical([{k:(v.hex() if k=='payload' else v) for k,v in r.items()} for r in rows])))


def audit(value):
    inherited=local.load()
    for key in ('application','replicationBounds','automaticPolicy','publishedControls'):
        m.need(value[key]==inherited[key],'unqualified inherited '+key)
    m.need(value['execution']=='cloud-workload-contract-only' and value['paidAdmission'] is False,'cloud admission forbidden')
    m.need(value['localPlanSha256']==local.PLAN_SHA256 and value['corpus']['corpusSha256']==inherited['localSmoke']['corpusSha256'], 'local corpus binding')
    m.need((value['corpus']['documents'],value['corpus']['seed'],value['corpus']['loadBulkElements'],value['corpus']['mutationBulkElements'])==(64,17,16,4),'calibrated corpus')
    cells=value['cells'];names=[c['name'] for c in cells]
    m.need(len(names)==len(set(names))==15 and names==value['presets']['canonical']['cells'],'canonical cell coverage')
    m.need(value['presets']['failureDrill']['cells']==names[3:] and set(value['presets']['experiment']['cells'])<=set(names),'preset coverage')
    b=value['budgets'];fixed=sum(b[k] for k in ('preparationSeconds','controlOverheadSeconds','validationRetentionSeconds','cleanupSeconds'))
    m.need(all(type(c['seconds']) is int and c['seconds']>0 for c in cells) and sum(c['seconds'] for c in cells)+fixed==b['leaseSeconds']==5400,'whole cloud allocation')
    m.need(b['cleanupSeconds']>=300 and b['operationGraceSeconds']==1080,'cleanup reserve')
    h=value['healthy'];m.need(h['operations']==list(m.OPERATIONS) and h['arrivalIntervalMillis']==1000 and h['concurrency']==1,'healthy schedule')
    m.need(h['warmupCalls']+4*h['windowSeconds']<=h['modeSeconds'] and cells[0]['seconds']==3*h['modeSeconds'],'healthy overhead allowance')
    for key,cell in (('readHeavy','read-heavy'),('sustained','sustained')):
        p=value[key]
        m.need(p['lanes']==4 and p['seconds']*1000%p['burstPeriodMillis']==0 and p['sameBurstDispatchMillis']<=value['scheduler']['maxDispatchLatenessMillis'],'burst schedule')
        m.need(next(c['seconds'] for c in cells if c['name']==cell)>=p['seconds']+60,'cell control/drain allowance')
    m.need(value['sustained']['seconds']*1000//value['sustained']['burstPeriodMillis']%len(value['sustained']['operationsByLane'])==0,'unfinished mutation lane')
    results={cell:projection(value,cell) for cell in names[:3]};results['experiment-healthy']=projection(value,'healthy','experiment')
    m.need([(results[k]['calls'],results[k]['mutations'],results[k]['reads']) for k in results]==[(260,208,52),(120,30,90),(180,108,72),(90,72,18)],'workload counts')
    m.need({c['name']:c['maxEncodedDocumentBytes'] for c in cells if 'maxEncodedDocumentBytes' in c}=={'interrupted-transfer':4100,'minority-capacity':20004},'fault document exceptions')
    f=value['faultProgram'];m.need(max(r['calls'] for r in results.values())+f['auxiliaryBarriersMaximum']+f['campaignSlotsMaximum']<=f['logicalSlotsMaximum']==512,'logical slot budget')
    m.need(all(c['historyCallsMaximum']<=f['historyMaximum']==24 for c in cells[3:]),'bounded fault histories')
    env=value['environment'];m.need(env['voters']==3 and env['voters']*env['vcpusPerVm']==24 and env['voters']*(env['bootDiskGiB']+env['dataDiskGiB'])==450,'cloud topology')
    m.need(env['jvmArguments']==inherited['jvmArguments'],'uncalibrated JVM flags')
    e=value['evidence'];m.need(e['parts']*e['partBytes']==e['compressedBytes'] and e['traceBytes']<e['expandedBytes'] and e['memberBytes']>=e['partBytes'],'evidence arithmetic')
    return dict(status='PASS',execution=value['execution'],paidAdmission=False,workloads=results,
                presetCellCounts={k:len(v['cells']) for k,v in value['presets'].items()},canonicalScheduledCallsMaximum=3*260+120+180+12*24,auxiliaryAutomaticBarriersMaximum=15*8,
                allocatedSeconds=sum(c['seconds'] for c in cells)+fixed,maximumVmHours=5*3*(5400+1080)/3600,
                maximumDiskGiBHours=5*450*(5400+1080)/3600,canonicalHealthySamplesPerOperation=24)


def validate(value):
    m.need(m.sha(m.canonical(value))==PLAN_SHA256,'unreviewed cloud workload contract')
    return dict(audit(value),planSha256=PLAN_SHA256)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,default=PLAN);args=parser.parse_args()
    print(m.canonical(validate(load(args.plan))).decode())
