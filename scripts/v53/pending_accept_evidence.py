"""Independent original-byte/force replay of local pending ACCEPT and fresh grant capture."""
import struct
import json
from pathlib import Path
from . import current_generation_evidence as c
from . import generation_install_evidence as install
from . import basis_sources_evidence as s
from . import grant_evidence as g
from . import source_packet as packet
from . import capture_journal_evidence as capture
from .membership_model import need

ACTIVE='pending.accept';NEXT=ACTIVE+'.next'
EMPTY=struct.pack('>4sHHI',b'GSPV',1,3,12)
SEAL=('ACCEPT_ACTIVE_FORCED','ACCEPT_ACTIVE_PARENT_FORCED')
CUTS=('ACCEPT_VALIDATED','ACCEPT_CANDIDATE_CREATED','ACCEPT_PREFIX_WRITTEN','ACCEPT_CANDIDATE_WRITTEN',
      'ACCEPT_CANDIDATE_FORCED','ACCEPT_CANDIDATE_PARENT_FORCED','ACCEPT_RENAMED','ACCEPT_PARENT_FORCED','ACCEPT_BEFORE_RETURN')
RECOVERY=('ACCEPT_RECOVERY_VALIDATED',)+CUTS[2:-1]
OPEN=c.OPEN+SEAL


def cases():
    rows=[dict(size=size,tail=tail,mode='clean',cut='none') for size in (3,4,5) for tail in (False,True)]
    rows += [dict(size=3,tail=True,mode=mode,cut=cut) for mode in ('halt','kill') for cut in CUTS]
    rows += [dict(size=5,tail=False,mode=mode,cut=cut) for mode in ('repeat-halt','repeat-kill') for cut in RECOVERY+SEAL]
    for row in rows:row['name']=f"{row['size']}-{str(row['tail']).lower()}-{row['mode']}-{row['cut'].lower()}"
    return rows


def info(raw):return dict(bytes=len(raw),sha256=c.sha(raw))
def container(frames,payload):
    body=b''.join(frames)+struct.pack('>I',len(payload))+payload
    need(len(payload)<=8*1024*1024,'pending payload bound')
    return struct.pack('>4sHHI',b'GSPV',1,3,12+len(body))+body


def model(root,case):
    original,rows,generation,_=c.current(root/'provisioned',case['size'])
    need([kind for kind,_,_ in rows]==['PROMISE','PROMISE','BASIS','SELECTED'],'pending installed original journal')
    files,selector,manifest,data=install.plan(root,rows,generation,case,install.selected_originals.recorded_mode(root))
    initial=dict(original);initial['generations/b']=dict(directory=True)
    initial.update({'generations/b/'+name:info(raw) for name,raw in files.items()});initial['selector.gsr']=info(selector);initial[ACTIVE]=info(EMPTY)
    need(s.inventory(root/'initial')==initial,'pending initial installation')
    selected=g.f.decode(files['selected.gsr'],'records','SELECTED');promise=g.f.decode(files['promise.gsr'],'records','PROMISE')
    if selected['nextEntry'] is None:
        payload=b'pending-original-payload';cut=selected['cut']
        entry=g.f.encode('records','ENTRY',dict(root=selected['root'],authority=selected['view'],index=cut['index']+1,previous=cut['entry'],
                      origin=selected['ballot'],kind='DATA',payload=c.sha(payload)))
    else:
        entry=data['objects'][selected['nextEntry']];value=g.f.decode(entry,'records','ENTRY');payload=data['objects'][value['payload']]
    entry_value=g.f.decode(entry,'records','ENTRY')
    accept=g.f.encode('records','ACCEPT',dict(root=selected['root'],authority=selected['view'],ballot=selected['ballot'],entry=c.sha(entry),index=entry_value['index']))
    vote=container([selector,files['promise.gsr'],files['selected.gsr'],entry,accept],payload)
    def state(point=None):
        expected=dict(initial);position=len(CUTS) if point is None else CUTS.index(point)
        if position>=CUTS.index('ACCEPT_RENAMED'):expected[ACTIVE]=info(vote)
        elif position>=1:expected[NEXT]=info(vote[:0 if position==1 else len(vote)//2 if position==2 else len(vote)])
        return expected
    objects=dict(data['objects']);objects.update({c.sha(entry):entry,c.sha(accept):accept,c.sha(payload):payload})
    composed=install.packet_bytes(data['capsule'],objects,data['images']);decoded=packet.decode(composed)
    final,history=s.state(root/'final',case['size'],extra_names={'selector.gsr','generations',ACTIVE})
    need(history[:len(rows)]==rows and [k for k,_,_ in history[len(rows):]]==['PROMISE','BASIS'],'pending captured journal')
    p,b=history[-2:];need(p[2]['ballot']==dict(promise['ballot'],counter=21),'pending next ballot')
    expected=dict(p[2],voter='node-1',cut=selected['cut'],capsule=c.sha(decoded['capsuleBytes']),inventory=c.sha(decoded['indexBytes']),accepted=c.sha(accept))
    need(b[2]==expected,'pending capture original vote binding');packet.bind(decoded,b[1]);identity=b[2]['basisId']
    expected=state();expected['grants.gsr']=info(b''.join(r[1] for r in history));expected['sources/'+identity]=dict(directory=True)
    expected['sources/'+identity+'/source.gscp']=info(composed)
    for h,count in data['images'].items():expected['sources/'+identity+'/'+h+'.image']=info(files[h+'.image'])
    need(final==expected,'pending exact final capture');need(s.inventory(root/'authority')==final,'pending final authority')
    need(sum(final.get(n,{}).get('bytes',0) for n in ('grants.gsr',ACTIVE,NEXT))<=g.LIMIT,'pending shared journal bound')
    need(sum(n.endswith('.image') for n in final)<=7,'pending shared image bound')
    return state,history,vote,dict(accepted=c.sha(accept),entry=c.sha(entry)),expected


def output(root,record,name,command,code=0):
    need(record['processes'][name]==dict(exitCode=code),'pending process outcome')
    rows=[json.loads(line) for line in g.read(root/(name+'.stdout'),65536).splitlines()]
    need(g.read(root/(name+'.stderr'),65536)==b'','pending unexpected stderr')
    if code==0:need(rows and rows[-1].get('status')=='PASS' and rows[-1].get('command')==command and all('status' not in v for v in rows[:-1]),'pending process return')
    else:need(rows and all('status' not in v for v in rows),'pending return after death')
    need(all(set(v)=={'event'} or set(v)=={'event','cut'} for v in rows if 'event' in v),'pending event shape')
    return rows


def validate_case(directory,case):
    root=Path(directory);record=g.a.load(root/'case.json');need(record['case']==case,'pending case identity')
    need(record['execution']=='private-pending-accept' and record['runtimeEnabled'] is False and record['remoteOwnershipVerified'] is False and record['networkAck'] is False,'pending evidence scope')
    state,history,vote,returned,final=model(root,case)
    clean=case['mode']=='clean';repeat=case['mode'].startswith('repeat-');mode=case['mode'].removeprefix('repeat-')
    names={'init','install','capture','inspect'}|({'first','duplicate'} if clean else {'fault','resume'})|({'recovery-fault'} if repeat else set())
    snapshots={'inputs','provisioned','initial','final','authority'}|({'original','duplicate'} if clean else {'crash','resumed'})|({'recovery-crash'} if repeat else set())
    need(set(record['processes'])==names and {p.name for p in root.iterdir()}=={'case.json',*snapshots}|{n+x for n in names for x in ('.stdout','.stderr')},'pending case inventory')
    for name in ('init','install'):need(output(root,record,name,name)==[dict(command=name,status='PASS')],'pending fixture initialization')
    def success(rows,advanced=False):
        basis=history[-1] if advanced else history[2]
        need(rows[-1]==dict(status='PASS',command=rows[-1]['command'],**returned,basis=c.sha(basis[1]),captured=basis[2]['accepted']),'pending returned original binding')
    if clean:
        rows=output(root,record,'first','accept');need(g.events(rows)==list(OPEN+CUTS),'pending acceptance force order');success(rows)
        rows=output(root,record,'duplicate','accept');need(g.events(rows)==list(OPEN+('ACCEPT_BEFORE_RETURN',)),'pending duplicate force order');success(rows)
        need(s.inventory(root/'original')==s.inventory(root/'duplicate')==state(),'pending duplicate original bytes')
    else:
        point='ACCEPT_CANDIDATE_WRITTEN' if repeat else case['cut'];rows=output(root,record,'fault','accept',73 if repeat or mode=='halt' else -9)
        order=OPEN+CUTS;need(g.events(rows)==list(order[:order.index(point)+1])+(['AWAITING_KILL'] if not repeat and mode=='kill' else []),'pending crash force order')
        if not repeat and mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=point),'pending kill handshake')
        need(s.inventory(root/'crash')==state(point),'pending exact crash snapshot');position=CUTS.index(point)
        if repeat:
            rows=output(root,record,'recovery-fault','accept',73 if mode=='halt' else -9);order=c.OPEN+RECOVERY+SEAL+('ACCEPT_BEFORE_RETURN',)
            need(g.events(rows)==list(order[:order.index(case['cut'])+1])+(['AWAITING_KILL'] if mode=='kill' else []),'pending repeated recovery force order')
            if mode=='kill':need(rows[-1]==dict(event='AWAITING_KILL',cut=case['cut']),'pending repeated kill handshake')
            position=CUTS.index('ACCEPT_CANDIDATE_WRITTEN') if case['cut'] in RECOVERY[:4] else CUTS.index(case['cut']) if case['cut'] in CUTS else len(CUTS)
            # A complete original remains complete even at another prefix-write cut during recovery.
            need(s.inventory(root/'recovery-crash')==state(None if position>=len(CUTS) else CUTS[position]),'pending exact recovery snapshot')
        rows=output(root,record,'resume','accept')
        if position>=CUTS.index('ACCEPT_RENAMED'):order=OPEN+('ACCEPT_BEFORE_RETURN',)
        elif position>=CUTS.index('ACCEPT_CANDIDATE_WRITTEN'):order=c.OPEN+RECOVERY+SEAL+('ACCEPT_BEFORE_RETURN',)
        elif position>=1:order=OPEN+('ACCEPT_VALIDATED',)+CUTS[2:]
        else:order=OPEN+CUTS
        need(g.events(rows)==list(order),'pending resume force order');success(rows);need(s.inventory(root/'resumed')==state(),'pending resumed snapshot')
    rows=output(root,record,'capture','capture');need(g.events(rows)==list(OPEN+capture.ORDER[len(c.OPEN):]),'pending capture force order');success(rows,True)
    rows=output(root,record,'inspect','inspect');need(g.events(rows)==list(OPEN),'pending inspect force order');success(rows,True)
    return dict(case=case['name'],status='PASS',runtimeEnabled=False,networkAck=False)


def validate(root):
    root=Path(root);need({p.name for p in root.iterdir()}=={v['name'] for v in cases()},'pending complete case set')
    return dict(status='PASS',execution='private-pending-accept',cases=[validate_case(root/case['name'],case) for case in cases()])
