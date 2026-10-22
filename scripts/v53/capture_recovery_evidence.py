"""Exact prefix/force replay for current-pinned captures; historical quorums remain fixtures."""
import hashlib
import json
from pathlib import Path
from . import current_generation_evidence as current
from . import basis_sources_evidence as sources
from . import grant_evidence as g
from . import format_fixture as f
from .membership_model import need

AUTHORITY='source.capture.gsr'
INTENT=('CAPTURE_INTENT_CREATED','CAPTURE_INTENT_PREFIX_WRITTEN','CAPTURE_INTENT_WRITTEN','CAPTURE_INTENT_FORCED','CAPTURE_INTENT_PARENT_FORCED')
SOURCE=('SOURCE_BEFORE_CREATE','SOURCE_CREATED','SOURCE_PACKET_CREATED','SOURCE_PACKET_PREFIX_WRITTEN','SOURCE_PACKET_WRITTEN','SOURCE_PACKET_FORCED',
        'SOURCE_IMAGE_CREATED','SOURCE_IMAGE_PREFIX_WRITTEN','SOURCE_IMAGE_WRITTEN','SOURCE_IMAGE_FORCED','SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED')
CLEAR=('CAPTURE_INTENT_DELETED','CAPTURE_INTENT_CLEARED')
CUTS=INTENT+SOURCE+g.CUTS[3:6]+CLEAR+('GRANT_BEFORE_RETURN',)
ORDER=current.OPEN+('CURRENT_BEFORE_CAPTURE',)+g.CUTS[:3]+CUTS


def cases():
    result=[]
    for size in (3,4,5):
        for through in (0,6,7):
            for tail in (False,True):result.append(dict(size=size,through=through,tail=tail,mode='clean',cut='none'))
    for mode in ('halt','kill'):
        for cut in CUTS:result.append(dict(size=3,through=1,tail=True,mode=mode,cut=cut))
    for mode in ('repeat-halt','repeat-kill'):
        result.append(dict(size=5,through=7,tail=True,mode=mode,cut='SOURCE_IMAGE_PREFIX_WRITTEN'))
    for row in result:row['name']=f"{row['size']}-{row['through']}-{str(row['tail']).lower()}-{row['mode']}-{row['cut'].lower()}"
    return result


def digest(data):return hashlib.sha256(data).hexdigest()
def info(data):return dict(bytes=len(data),sha256=digest(data))


def process(root,record,label,code,command):
    need(record['processes'][label]==dict(exitCode=code),'capture process outcome')
    rows=[json.loads(line) for line in g.read(root/(label+'.stdout'),65536).splitlines()]
    need(g.read(root/(label+'.stderr'),65536)==b'','capture unexpected stderr')
    need(all(set(r)=={'event'} or set(r)=={'event','cut'} for r in rows if 'event' in r),'capture event shape')
    if code==0:
        need(rows and rows[-1].get('status')=='PASS' and rows[-1].get('command')==command and not any('status' in r for r in rows[:-1]),'capture terminal result')
    else:need(rows and all('status' not in r for r in rows),'capture return after death')
    return rows


def model(root,case):
    initial,old,generation,data=current.current(root/'initial',case['size'])
    need([k for k,_,_ in old]==['PROMISE'] and old[0][2]['ballot']['counter']==10,'capture initial grant')
    need(generation['cut']['index']==case['through'] and (generation['ownedTail'] is not None)==case['tail'],'capture initial profile')
    final,rows,after,saved=current.current(root/'final',case['size'])
    need(after==generation and saved==data,'capture current generation changed')
    need([k for k,_,_ in rows]==['PROMISE','PROMISE','BASIS'] and rows[0]==old[0] and rows[1][2]['ballot']['counter']==20,'capture final journal')
    basis=rows[-1][2];promise=rows[1][2];source_id=basis['basisId']
    expected=dict(promise,voter='node-1',cut=generation['cut'],capsule=generation['capsule'],inventory=digest(data['indexBytes']),accepted=generation['ownedTail'])
    need(basis==expected,'capture exact original basis')
    selector=g.read(root/'initial/selector.gsr',4096);intent=selector+rows[1][1]+rows[2][1]
    need(len(intent)<=28672,'capture intent bound')
    generation_path=root/'initial/generations'/generation['generation']
    original={'source.gscp':g.read(generation_path/'source.gscp',g.LIMIT)}
    original.update({h+'.image':g.read(generation_path/(h+'.image'),size) for h,size in data['images'].items()})
    need(len(data['images'])==1,'capture qualification image profile')
    def state(cut=None):
        result=dict(initial);index=len(CUTS) if cut is None else CUTS.index(cut)
        result['grants.gsr']=info(b''.join(r[1] for r in rows[:3 if index>=CUTS.index('BASIS_WRITTEN') else 2]))
        if index<CUTS.index('CAPTURE_INTENT_DELETED'):
            length=0 if index==0 else len(intent)//2 if index==1 else len(intent);result[AUTHORITY]=info(intent[:length])
        if index>=CUTS.index('SOURCE_CREATED'):
            prefix='sources/'+source_id+'/';result[prefix[:-1]]=dict(directory=True)
            for name,raw in original.items():
                event='SOURCE_PACKET' if name=='source.gscp' else 'SOURCE_IMAGE';at=CUTS.index(event+'_CREATED')
                if index>=at:result[prefix+name]=info(raw[:0 if index==at else len(raw)//2 if index==at+1 else len(raw)])
        return result
    need(final==state(),'capture exact final snapshot')
    return state,rows,intent,source_id


def recovery_order(snapshot,source_id,complete):
    result=list(current.OPEN)
    if AUTHORITY in snapshot:
        if not complete:
            result+=list(INTENT[1:]);prefix='sources/'+source_id+'/'
            if prefix[:-1] not in snapshot:result+=list(SOURCE[:2])
            for group in ('SOURCE_PACKET','SOURCE_IMAGE'):
                exists=prefix+'source.gscp' in snapshot if group=='SOURCE_PACKET' else any(k.startswith(prefix) and k.endswith('.image') for k in snapshot)
                result+=([group+'_CREATED'] if not exists else [])+[group+'_PREFIX_WRITTEN',group+'_WRITTEN',group+'_FORCED']
            result+=list(SOURCE[-2:])+list(g.CUTS[3:6])
        result+=list(CLEAR)
    return result


def validate_case(directory,case):
    root=Path(directory);record=g.a.load(root/'case.json');need(record['case']==case,'capture case identity')
    if record.get('journalRecovery') is True:
        from . import capture_journal_evidence
        return capture_journal_evidence.validate_case(root,case)
    need(record['execution']=='private-capture-recovery' and record['runtimeEnabled'] is False and record['historicalOwnershipVerified'] is False and record['networkAck'] is False,'capture scope')
    state,rows,intent,source_id=model(root,case);initial=sources.inventory(root/'initial');clean=case['mode']=='clean';repeat=case['mode'].startswith('repeat-')
    names={'init','first','duplicate','inspect'} if clean else {'init','fault','resume','inspect'}|({'recovery-fault'} if repeat else set())
    snapshots={'initial','original','duplicate','final','authority'} if clean else {'initial','crash','resumed','final','authority'}|({'recovery-crash'} if repeat else set())
    need(set(record['processes'])==names,'capture process inventory')
    need({p.name for p in root.iterdir()}=={'case.json',*snapshots}|{n+s for n in names for s in ('.stdout','.stderr')},'capture case inventory')
    need(process(root,record,'init',0,'init')==[dict(command='init',status='PASS')],'capture initialization')
    def returned(output):
        need(output[-1]==dict(status='PASS',command=output[-1]['command'],basis=digest(rows[-1][1]),accepted=rows[-1][2]['accepted'],cut=case['through'],sourceCount=1),'capture returned binding')
    if clean:
        output=process(root,record,'first',0,'prepare');need(g.events(output)==list(ORDER),'capture force order');returned(output)
        duplicate=process(root,record,'duplicate',0,'prepare');need(g.events(duplicate)==list(current.OPEN+('CURRENT_BEFORE_CAPTURE',)),'capture duplicate wrote bytes');returned(duplicate)
        need(sources.inventory(root/'original')==sources.inventory(root/'duplicate')==state(),'capture original/duplicate snapshot')
    else:
        mode=case['mode'].removeprefix('repeat-');point='SOURCE_PACKET_PREFIX_WRITTEN' if repeat else case['cut']
        fault=process(root,record,'fault',73 if repeat or mode=='halt' else -9,'prepare')
        expected=list(ORDER[:ORDER.index(point)+1])+(['AWAITING_KILL'] if not repeat and mode=='kill' else [])
        need(g.events(fault)==expected,'capture crash force order')
        if not repeat and mode=='kill':need(fault[-1]==dict(event='AWAITING_KILL',cut=point),'capture kill handshake')
        crash=sources.inventory(root/'crash');need(crash==state(point),'capture exact crash snapshot')
        if repeat:
            output=process(root,record,'recovery-fault',73 if mode=='halt' else -9,'prepare');order=recovery_order(crash,source_id,False)
            need(g.events(output)==order[:order.index(case['cut'])+1]+(['AWAITING_KILL'] if mode=='kill' else []),'capture repeated recovery force order')
            if mode=='kill':need(output[-1]==dict(event='AWAITING_KILL',cut=case['cut']),'capture repeated kill handshake')
            crash=sources.inventory(root/'recovery-crash');need(crash==state(case['cut']),'capture exact recovery crash snapshot');point=case['cut']
        output=process(root,record,'resume',0,'prepare');need(g.events(output)==recovery_order(crash,source_id,CUTS.index(point)>=CUTS.index('BASIS_WRITTEN'))+['CURRENT_BEFORE_CAPTURE'],'capture recovery force order');returned(output)
        need(sources.inventory(root/'resumed')==state(),'capture resumed snapshot')
    output=process(root,record,'inspect',0,'inspect');need(g.events(output)==list(current.OPEN),'capture inspect wrote authority');returned(output)
    need(sources.inventory(root/'authority')==state(),'capture final source snapshot')
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,historicalOwnershipVerified=False)


def validate(root):
    root=Path(root);need({p.name for p in root.iterdir()}=={c['name'] for c in cases()},'capture complete case inventory')
    return dict(status='PASS',execution='private-capture-recovery',cases=[validate_case(root/c['name'],c) for c in cases()])
