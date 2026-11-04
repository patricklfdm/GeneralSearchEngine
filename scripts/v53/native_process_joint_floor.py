"""Capture whole native joint-floor process deaths; no cohort admission.

The focused inspector covers the process boundary and exact interrupted bytes.
Complete two-reopen physical/network/ledger composition remains a separate gate.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile
from . import native_joint_floor_history as base

h,floor,need=base.h,base.floor,base.need
CLASS='io.github.patricklfdm.generalsearch.replication.V53NativeProcessJointFloorTest'
METHOD='originalProcessDeathResumesBeforeFinalAndStableBarrier'
EXECUTION_SCHEMA='gse-v53-native-process-joint-execution-v1'
SCHEMA='gse-v53-joint-floor-process-control-v1'
LABEL='native-process-joint'
MODULE='scripts.v53.native_process_joint_floor'
SCOPE='joint-floor-process'
CASES=tuple(case+','+mode for case in base.CASES for mode in ('halt','kill'))


def selected(case):
    need(type(case) is str and case in CASES,'native process joint exact case')
    ordinal,cut,mode=case.split(',');return int(ordinal),cut,mode


def scope(case,*,scratch_recovery=False):
    ordinal,cut,mode=selected(case)
    row=dict(floor.partial_scope(ordinal,cut),schema='gse-v53-native-process-joint-floor-v1',
                mode=mode,initialFloor='native-tcp',processDeath=True)
    if scratch_recovery:row.update(schema='gse-v53-native-process-joint-floor-v2',scratchRecovery=True)
    return row


def producer_scope(raw,case):
    row=floor.read(Path(raw)/'joint-floor-recovery/receipt.json')
    need(type(row) is dict and row.get('schema') in ('gse-v53-native-process-joint-floor-v1',
         'gse-v53-native-process-joint-floor-v2'),'native process joint known producer version')
    expected=scope(case,scratch_recovery=row['schema'].endswith('-v2'))
    floor.same(row,expected,'native process joint exact producer cut')
    return expected


def command(case):
    selected(case)
    return ['-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+h.MODULE,'-am',
        '-Dsurefire.failIfNoSpecifiedTests=false','-Dtest='+CLASS.rsplit('.',1)[-1]+'#'+METHOD,
        '-Dv53.native.process.joint='+case,'test']


def junit(reports):return base.junit(reports,CLASS,METHOD)


def collect(raw,case):
    raw=Path(raw);selected(case);before=h.inventory(raw)
    side=raw/'joint-floor-recovery'
    producer=producer_scope(raw,case)
    extra={'scratch-recovery'} if producer.get('scratchRecovery') else set()
    need(side.is_dir() and {v.name for v in side.iterdir()}==floor.FILES|{'process'}|extra,'native process joint complete sidecar')
    plan=h.snapshot.s.regular(raw/'original-plan.gsbp',h.snapshot.MIB)
    result=dict(status='PARTIAL',case=case,collectionComplete=True,nativeHistoryQualified=False,
        processDeathQualified=False,phase3Complete=False,inventory=before,
        captureInventory=h.inventory(raw/'source-retirement-captures'),
        processInventory=h.inventory(raw/'joint-floor-recovery/process'),originalPlanSha256=h.digest(plan))
    need(h.inventory(raw)==before,'native process joint collection changed original')
    return result


def messages(path):
    raw=h.snapshot.s.regular(path,64*h.snapshot.MIB)
    need(raw and raw.endswith(b'\n'),'joint process incomplete original stdout')
    result=[]
    for line in raw.splitlines():
        need(len(line)<=16*h.snapshot.MIB,'joint process stdout row capacity')
        value=json.loads(line)
        need(type(value) is dict and set(value)=={'kind','value'} and
            value['kind'] in ('STARTED','OPENED','CUT','EVENT','WIRE','USAGE') and
            type(value['value']) is dict and floor.f.canonical(value)==line,'joint process canonical stdout')
        result.append(value)
        need(len(result)<=h.HISTORY_ROWS,'joint process stdout row count')
    return result


def boundary(raw,case):
    """Original process observations, without claiming complete history replay."""
    raw=Path(raw);side=raw/'joint-floor-recovery';area=side/'process';ordinal,cut,mode=selected(case)
    need({v.name for v in area.iterdir()}=={'spec.json','result.json','controls.json','stdout','stderr','before-open','at-cut','after-death',
                                        'at-cut-scratch','after-death-scratch'},
         'joint process exact original sidecar')
    spec=floor.read(area/'spec.json');result=floor.read(area/'result.json');controls=floor.read(area/'controls.json')
    need(type(result) is dict and type(result.get('pid')) is int and result['pid']>0 and
         type(result.get('parentPid')) is int and result['parentPid']>0 and result['pid']!=result['parentPid'],
         'joint process distinct live PID')
    pid=result['pid']
    floor.same(result,dict(schema=SCHEMA,status='PARTIAL',pid=pid,parentPid=result['parentPid'],mode=mode,ordinal=ordinal,point=cut,
        processDeathQualified=False,phase3Complete=False,liveLockRefused=True,lockReleased=True,exit=73 if mode=='halt' else 137),
        'joint process exact exit and locks')
    need(type(spec) is dict and set(spec)=={'schema','root','identity','paths','ordinal','point','mode','startedNanos','budgetNanos'} and
         type(spec['paths']) is dict and set(spec['paths'])=={'replica','application','scratch'} and
         type(spec['root']) is dict and set(spec['root'])=={'group','history','digest'} and
         all(type(v) is str and Path(v).is_absolute() for v in spec['paths'].values()) and
         len(set(spec['paths'].values()))==3 and type(spec['startedNanos']) is int,'joint process original spec')
    floor.same({k:spec[k] for k in ('schema','ordinal','point','mode','budgetNanos')},
        dict(schema=SCHEMA,ordinal=ordinal,point=cut,mode=mode,budgetNanos=720_000_000_000),'joint process unchanged budget and cut')
    paths=[Path(v) for v in spec['paths'].values()]
    need(all(not a.is_relative_to(b) for a in paths for b in paths if a!=b),'joint process disjoint original roots')
    line=floor.read(side/'lineage.json');timing=floor.read(side/'maintenance.json')
    need(spec['paths']['replica']==line['replica'] and spec['paths']['application']==line['application'] and
         spec['root']['digest']==line['root'] and spec['startedNanos']==timing['startedNanos'] and
         spec['startedNanos']+spec['budgetNanos']==timing['originalDeadlineNanos'], 'joint process unchanged original roots and deadline')
    rows=messages(area/'stdout');events=floor.read(raw/'events.json')
    expected=[dict(kind='STARTED',value=dict(mode=mode,pid=pid)),
              dict(kind='OPENED',value=dict(pid=pid,replica=line['replica'],application=line['application'])),
              dict(kind='CUT',value=dict(mode=mode,pid=pid,ordinal=ordinal,point=cut))]
    observed=[row for row in rows if row['kind'] in ('STARTED','OPENED','CUT')]
    floor.same(observed,expected,'joint process exact control order')
    need(rows[0]==expected[0] and rows[-1]==expected[-1], 'joint process complete worker lifetime')
    need(type(controls) is list and len(controls)==3 and
         all(type(v) is dict and set(v)=={'kind','value','eventCount'} and type(v['eventCount']) is int and
             0<=v['eventCount']<=len(events) for v in controls),'joint process control anchors')
    floor.same([{k:v[k] for k in ('kind','value')} for v in controls],expected,'joint process retained controls')
    start,opened,stop=[v['eventCount'] for v in controls]
    need(start<opened<stop,'joint process control lifetime order')
    child=[(i,row) for i,row in enumerate(events) if row.get('node')=='node-2' and row.get('scope')==SCOPE]
    floor.same([v for _,v in child],[row['value'] for row in rows if row['kind']=='EVENT'],'joint process complete original event projection')
    need(child and all(start<=i<stop for i,_ in child) and child[-1][1]==dict(node='node-2',scope=SCOPE,event=cut),
         'joint process original event bounds')
    first_opened=rows.index(expected[1])
    floor.same([row for i,row in child if i<opened],[v['value'] for v in rows[:first_opened] if v['kind']=='EVENT'],
               'joint process exact open return boundary')
    current=['CURRENT_VALIDATED','CURRENT_FILES_FORCED','CURRENT_GENERATION_FORCED','CURRENT_SELECTOR_FORCED','CURRENT_DIRECTORY_FORCED']
    need([row['event'] for _,row in child if row['event'].startswith('CURRENT_')]==current and
         all(i<opened for i,row in child if row['event'].startswith('CURRENT_')) and
         not any(row['event'].startswith(('PROMISE_','BASIS_','SELECTED_','INSTALL_','PUBLICATION_','RETIREMENT_','SOURCE_RETIREMENT_')) for _,row in child),
         'joint process original cold open before floor')
    need(not any(row['kind']=='WIRE' for row in rows),'joint process unexpected inbound worker traffic')
    usage=[row['value'] for row in rows if row['kind']=='USAGE']
    need(all(set(v)=={'event','usage'} and type(v['event']) is str and type(v['usage']) is dict for v in usage),
         'joint process resource row shape')
    floor.same(usage,floor.read(side/'interrupted-usage.json'),'joint process original resource observations')
    need([v['event'] for v in usage]==[row['event'] for _,row in child if 'request' not in row],
         'joint process storage/resource coverage')
    return spec,child


def original_identity(spec,root_bytes,identity,capsule_root):
    root=floor.f.decode(root_bytes,'records','ROOT')  # Validates the framed checksum before using it.
    need(root_bytes[16:48].hex()==capsule_root and spec['identity']==identity and
         spec['root']==dict(group=root['groupId'],history=root['historyId'],digest=capsule_root),
         'joint process original local identity')


def inspect(raw,case):
    raw=Path(raw);before=collect(raw,case);side=raw/'joint-floor-recovery';spec,child=boundary(raw,case)
    events=floor.read(raw/'events.json');captured=floor.read(side/'floor-events.json')
    need(type(captured) is list and captured and captured==events[:len(captured)] and
         captured[-1]==dict(node='node-2',scope='joint-floor-reopened',event='FLOOR_BEFORE_RETURN'),
         'joint process original recovered floor prefix')
    original={node:floor.c.inventory(side/'originals'/node) for node in floor.NODES};offered={};refs=[];caps=[];ids={};copies={}
    for node,files in original.items():
        prefix,members,packet=floor.c.current(files);manifest=files[prefix+'generation.gsr'];caps.append(packet['capsule'])
        owner=floor.f.decode(files['node.gsr'],'records','NODE');ids[node]=owner['identity']
        need(ids[node]['node']==node,'joint process original copy owner')
        copies[node]=dict(members,**{'generation.gsr':manifest});digest=h.digest(manifest);offered[digest]=copies[node]
        refs.append(dict(voter=node,generation=digest,catalog=packet['capsule']['catalog'],snapshot=packet['capsule']['application']))
    cap=caps[0]
    need(all(v['cut']==cap['cut'] and v['catalog']==cap['catalog'] and v['application']==cap['application'] for v in caps),
         'joint process original common cut')
    need(cap['cut']['view']['old']==['node-'+str(i) for i in range(1,6)] and
         cap['cut']['view']['new']==['node-1','node-2','node-3','node-4','node-6'],'joint process original replacement view')
    floor.catalog.catalog.majority(cap['cut']['view'],list(floor.NODES))
    original_identity(spec,original['node-2']['root.gsr'],ids['node-2'],cap['root'])
    proposal=floor.f.encode('records','FLOOR',dict(root=cap['root'],node='node-2',cut=cap['cut'],sources=refs))
    need(proposal==(side/'proposal.gsr').read_bytes(),'joint process exact original proposal')
    ordinal,cut,_=selected(case);writer=floor.writer_prefix(offered,proposal,floor.partial_scope(ordinal,cut))
    expected=dict(original['node-2'],**writer['interrupted'])
    need(floor.c.inventory(side/'process/before-open')==original['node-2'],'joint process unchanged original handoff')
    for name in ('process/at-cut','process/after-death','interrupted','after-close','after-reopen'):
        need(floor.c.inventory(side/name)==expected,'joint process exact partial original: '+name)
    need([v['event'] for _,v in child if v['event'].startswith('FLOOR_') and v['event']!='FLOOR_COPY_BEFORE_RETURN']==writer['events'],
         'joint process exact partial writer order')
    need(floor.c.inventory(side/'resumed-floor')==dict(original['node-2'],**writer['completed']),
         'joint process exact resumed physical copies')
    need(h.inventory(side/'process/at-cut-scratch')==h.inventory(side/'process/after-death-scratch'),
         'joint process scratch changed across death')
    journal=floor.c.journal(original['node-2']['grants.gsr'],cap['root'],'node-2')
    ballot=next(v['ballot'] for kind,_,v in reversed(journal) if kind=='PROMISE')
    transfers={name:floor.transfer_sessions(raw,captured,copies,ids,cap,ballot,scope=owner)
        for name,owner in (('beforeDeath',SCOPE),('afterDeath','joint-floor-reopened'))}
    need(collect(raw,case)==before,'joint process inspection changed original')
    scratch=None
    if producer_scope(raw,case).get('scratchRecovery'):
        from . import process_joint_scratch as recovery
        scratch=recovery.validate(raw,spec)
    return dict(status='PARTIAL',case=case,processBoundaryChecked=True,interruptedBytesChecked=True,
        originalCopyExchanges=transfers,scratchRetained=True,
        **({'scratchRecovery':scratch} if scratch is not None else {}),
        nativeHistoryQualified=False,processDeathQualified=False,phase3Complete=False,
        outstanding=['complete-two-reopen-physical-network-ledger-replay','resource-overlap-replay','final-source-matrix'])


def capture(output,maven,case,source_from=None):
    return base.capture(output,maven,case,source_from,entry=sys.modules[__name__])


NEGATIVES={
    'exit':'joint process exact exit and locks',
    'live-lock':'joint process exact exit and locks',
    'released-lock':'joint process exact exit and locks',
    'same-pid':'joint process distinct live PID',
    'qualified-claim':'joint process exact exit and locks',
    'ordinal':'joint process unchanged budget and cut',
    'budget':'joint process unchanged budget and cut',
    'deadline-reset':'joint process unchanged original roots and deadline',
    'open-boundary':'joint process exact open return boundary',
    'owner-scope':'joint process complete original event projection',
    'resource-omission':'joint process original resource observations',
    'partial-stdout':'joint process incomplete original stdout',
}


def mutate(raw,name):
    need(name in NEGATIVES,'joint process unknown negative')
    raw=Path(raw);side=raw/'joint-floor-recovery';area=side/'process'
    if name=='partial-stdout':
        path=area/'stdout';value=path.read_bytes();need(value.endswith(b'\n'),'joint process original stdout newline');path.write_bytes(value[:-1]);return
    if name in ('exit','live-lock','released-lock','same-pid','qualified-claim'):
        path=area/'result.json';value=floor.read(path)
        field,replacement={'exit':('exit',0),'live-lock':('liveLockRefused',False),'released-lock':('lockReleased',False),
            'same-pid':('pid',value['parentPid']),'qualified-claim':('processDeathQualified',True)}[name];value[field]=replacement
    elif name in ('ordinal','budget','deadline-reset'):
        path=area/'spec.json';value=floor.read(path)
        if name=='ordinal':value['ordinal']=value['ordinal']%4+1
        else:value['budgetNanos' if name=='budget' else 'startedNanos']+=1
    elif name=='open-boundary':
        path=area/'controls.json';value=floor.read(path);value[1]['eventCount']-=1
    elif name=='owner-scope':
        path=raw/'events.json';value=floor.read(path)
        at=next(i for i,v in enumerate(value) if v.get('node')=='node-2' and v.get('scope')==SCOPE)
        value[at]['scope']='joint-floor-reopened'
    else:
        path=side/'interrupted-usage.json';value=floor.read(path);value.pop()
    h.save(path,value)


def qualify(raw,case):
    raw=Path(raw);before=h.inventory(raw)
    original=inspect(raw,case)  # An unrelated original failure cannot pass negatives.
    results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-joint-process-negative-') as tmp:
            changed=Path(tmp)/'raw';shutil.copytree(raw,changed);mutate(changed,name)
            try:boundary(changed,case)
            except ValueError as error:need(str(error)==reason,'joint process unexpected negative reason: '+name+': '+str(error))
            else:raise ValueError('joint process negative accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    need(h.inventory(raw)==before,'joint process negatives changed original')
    return dict(status='PARTIAL',original=original,negatives=results,processDeathQualified=False,
                nativeHistoryQualified=False,phase3Complete=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True);sub.add_parser('plan')
    for name in ('capture','collect','inspect','qualify'):
        c=sub.add_parser(name);c.add_argument('output');c.add_argument('--case',required=True,choices=CASES)
        if name=='capture':c.add_argument('--maven',default='mvn');c.add_argument('--source-from')
        else:c.add_argument('--raw',required=True)
    a=p.parse_args()
    if a.mode=='plan':
        print(json.dumps(dict(cases=list(CASES),wholeHistories=len(CASES),processDeathQualified=False,phase3Complete=False)));return
    if a.mode=='capture':result=capture(a.output,a.maven,a.case,a.source_from)
    else:
        output=Path(a.output);need(not output.exists(),'native process joint refuses overwrite')
        result={'collect':collect,'inspect':inspect,'qualify':qualify}[a.mode](a.raw,a.case);h.save(output,result)
    print(json.dumps(dict(status=result['status'],processDeathQualified=False,phase3Complete=False),sort_keys=True))


if __name__=='__main__':main()
