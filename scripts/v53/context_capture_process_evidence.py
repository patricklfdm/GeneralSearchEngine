"""Fresh-process protected-capture/reclamation replay; process death is not power loss."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
from . import context_backing_retirement_evidence as backing
from . import current_generation_evidence as current
from . import capture_journal_evidence as journal
from . import context_completion_process_evidence as completion

capture, source, owner, e, release = backing.capture, backing.source, backing.owner, backing.e, backing.release
POINTS = (*capture.CUTS, 'CONTEXT_SOURCE_MEMBER_FORCED@2', *backing.CUTS, 'SOURCE_RETIREMENT_FILE_DELETED@2')


def trace(path):
    e.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024*1024, 'capture process trace type/capacity')
    raw=path.read_bytes();lines=raw.splitlines();e.need(raw.endswith(b'\n') and 0<len(lines)<=4096,'capture process complete trace')
    rows=[e.parse(line) for line in lines]
    e.need(all(type(row) is dict for row in rows) and b''.join(e.f.canonical(row)+b'\n' for row in rows)==raw,'capture process canonical trace')
    e.need(not any(row.get('event') in owner.ACKS-{'GRANT_BEFORE_RETURN'} or str(row.get('event')).startswith('APPLY_ACK_') for row in rows),
           'capture process unrelated acknowledgement')
    return rows


def events(names):return [dict(event=n) for n in names]
def grant(counter, basis):return dict(event='RETURNED_GRANT',counter=counter,record=e.digest(basis))
def stop(steps,point):return completion.stop([(s[0],None) for s in steps],point)

def source_seal(files):
    segments,_,_=e.decode(files['pending.context']);basis=e.f.decode(segments[3],'records','BASIS')
    count=sum(p.startswith('sources/'+basis['basisId']+'/') for p in files)
    return ['CONTEXT_SOURCE_MEMBER_FORCED']*count+['CONTEXT_SOURCE_DIRECTORY_FORCED','CONTEXT_SOURCE_PARENT_FORCED']


def retain_seal(files):
    return ['CONTEXT_OWNER_VALIDATED']+source_seal(files)+['CONTEXT_ACTIVE_FORCED','CONTEXT_ACTIVE_PARENT_FORCED','CONTEXT_OWNER_BEFORE_RETURN']


def frozen_seed(root):
    source.validate(root/'reference');files,dirs=owner.read_snapshot(root/'reference/reopened');observed,_=owner.read_snapshot(root/'initial')
    promise,_=capture.new_promise(files,observed,22);steps=capture.transaction(files,dirs,promise);files,dirs=steps[-1][1:];capture.match(root/'initial',files,dirs,'process seed')
    return files,dirs


def finish_before_rebind(crash,crash_dirs,initial,steps):
    """Derive second open's source/BASIS repair, stopping before any context write."""
    complete=next(s for s in steps if s[0]=='CONTEXT_SOURCE_PARENT_FORCED');full=steps[-1][1];state=dict(crash)
    prefix=steps[2][1]['grants.gsr'];basis=complete[1]['grants.gsr'][len(prefix):];order=list(current.OPEN)
    if 'source.capture.gsr' in crash:
        if len(crash['grants.gsr'])<len(prefix)+len(basis):
            if len(crash['grants.gsr'])>len(prefix):order+=list(journal.RECOVERY)
            else:
                order+=['CAPTURE_INTENT_PREFIX_WRITTEN','CAPTURE_INTENT_WRITTEN','CAPTURE_INTENT_FORCED','CAPTURE_INTENT_PARENT_FORCED']
                promise=e.f.decode(prefix[len(initial['grants.gsr']):],'records','PROMISE');sp='sources/'+promise['basisId']
                if sp not in crash_dirs:order+=['SOURCE_BEFORE_CREATE','SOURCE_CREATED']
                members=[p for p in full if p.startswith(sp+'/')];members.sort(key=lambda p:(not p.endswith('/source.gscp'),p))
                for p in members:
                    label='SOURCE_PACKET' if p.endswith('/source.gscp') else 'SOURCE_IMAGE'
                    if p not in crash:order.append(label+'_CREATED')
                    order += [label+'_PREFIX_WRITTEN',label+'_WRITTEN',label+'_FORCED']
                order += ['SOURCE_FILES_DIRECTORY_FORCED','SOURCE_DIRECTORY_FORCED','BASIS_BEFORE_WRITE','BASIS_PREFIX_WRITTEN','BASIS_WRITTEN','BASIS_FORCED']
            state['grants.gsr']=complete[1]['grants.gsr']
            state.update({p:b for p,b in complete[1].items() if p.startswith('sources/')})
            state['source.capture.gsr']=complete[1]['source.capture.gsr']
        order+=source_seal(full)
        return state,complete[2],order
    order+=['CONTEXT_OWNER_VALIDATED']+source_seal(full)
    return state,crash_dirs,order


def resume_prefix(second,full,retire_steps):
    order=list(current.OPEN)
    if 'source.capture.gsr' in second:
        order+=source_seal(full)
        if second['pending.context']==full['pending.context'] and 'pending.context.next' not in second:
            order+=['CONTEXT_ACTIVE_FORCED','CONTEXT_ACTIVE_PARENT_FORCED']
        else:
            if 'pending.context.next' not in second:order.append('CONTEXT_CANDIDATE_CREATED')
            order+=['CONTEXT_PREFIX_WRITTEN','CONTEXT_CANDIDATE_WRITTEN','CONTEXT_CANDIDATE_FORCED','CONTEXT_CANDIDATE_PARENT_FORCED','CONTEXT_RENAMED','CONTEXT_PARENT_FORCED']
        order+=['CAPTURE_INTENT_DELETED','CAPTURE_INTENT_CLEARED']
    order+=retain_seal(full)+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED']
    # Complete retained decisions resume during open; an empty created file still
    # requires an explicit exact deletion request after open.
    during_open=bool(second.get(release.AUTHORITY,b''))
    if during_open:order += [n for n,_ in retire_steps]
    return order,during_open


def validate_case(root,initial,initial_dirs,mode,point):
    name=mode+'-'+point;case=root/name
    e.need(case.is_dir() and not case.is_symlink() and {p.name for p in case.iterdir()} ==
           {'store','crash','recovery-crash','recovered','final'}|{n+s for n in ('fault','recovery','resume') for s in ('.stdout','.stderr')},'capture process member inventory')
    for label in ('fault','recovery','resume'):
        path=case/(label+'.stderr');e.need(path.is_file() and not path.is_symlink() and path.stat().st_size==0,'capture process stderr')
    fault,recovery,resume=[trace(case/(label+'.stdout')) for label in ('fault','recovery','resume')]
    observed,_=owner.read_snapshot(case/'crash')
    deleting=point.startswith(('SOURCE_RETIREMENT_','JOURNAL_ROTATION_'))
    if deleting:
        # Rotation may already have removed backing 22's journal frames. The
        # complete context still retains exact grant 23; compare it to the
        # predeclared next ballot, then derive the pre-rotation capture afresh.
        promise=e.decode(observed['pending.context'])[0][2];value=e.f.decode(promise,'records','PROMISE')
        prior=e.f.decode(e.decode(initial['pending.context'])[0][2],'records','PROMISE')
        e.need(value==dict(prior,ballot=dict(prior['ballot'],counter=23),basisId=value['basisId'])
               and 'sources/'+value['basisId'] not in initial_dirs,'capture process original grant identity')
    else:promise,_=capture.new_promise(initial,observed,23)
    steps=capture.transaction(initial,initial_dirs,promise);full,full_dirs=steps[-1][1:]
    segments,_,_=e.decode(full['pending.context']);basis=segments[3];old=e.f.decode(e.decode(initial['pending.context'])[0][3],'records','BASIS')['basisId']
    authority,compact,deletion=backing.retirement(full,full_dirs,old);recovered=deletion[-1][1]
    first=deletion if deleting else steps;at=stop(first,point)
    first_state=first[at][1] if deleting else backing.inventory(first[at][1],first[at][2])
    e.need(source.state(case/'crash')==first_state,'capture process exact first prefix')
    before=events(list(current.OPEN)+retain_seal(initial)+['CERTIFICATE_ACTIVE_FORCED','CERTIFICATE_ACTIVE_PARENT_FORCED','OPEN_RETURNED'])
    if deleting:before+=events([s[0] for s in steps])+[grant(23,basis)]
    expected=before+events([s[0] for s in first[:at+1]])
    if mode=='kill':expected.append(dict(event='AWAITING_KILL',cut=point))
    e.need(fault==expected,'capture process first force/death order')
    crash,crash_dirs=owner.read_snapshot(case/'crash')
    if deleting:
        second,second_dirs=crash,crash_dirs;second_order=list(current.OPEN)+['CONTEXT_OWNER_VALIDATED']+source_seal(full)
    else:second,second_dirs,second_order=finish_before_rebind(crash,crash_dirs,initial,steps)
    capture.match(case/'recovery-crash',second,second_dirs,'process second interruption')
    e.need(recovery==events(second_order),'capture process second force/death order')
    e.need(source.state(case/'recovered')==recovered,'capture process exact recovered authority')
    after_capture=dict(second)
    if 'source.capture.gsr' in second:after_capture=full
    during_deletion=release.transaction(backing.inventory(after_capture,full_dirs if 'source.capture.gsr' in second else second_dirs),authority,compact,old)
    open_order,automatic=resume_prefix(second,full,during_deletion)
    early=release.AUTHORITY in second and not automatic
    expected=events(open_order+['OPEN_RETURNED'])
    if early:expected+=events([n for n,_ in during_deletion])
    expected+=events(['GRANT_BEFORE_RETURN'])+[grant(23,basis)]
    if not automatic and not early:expected+=events([n for n,_ in during_deletion])
    expected+=events(retain_seal(full)+['RECOVERED'])
    clean,clean_dirs=owner.read_snapshot(case/'recovered');end,_=owner.read_snapshot(case/'final')
    next_promise=e.decode(end['pending.context'])[0][2];next_value=e.f.decode(next_promise,'records','PROMISE')
    expected_value=dict(e.f.decode(promise,'records','PROMISE'),ballot=dict(e.f.decode(promise,'records','PROMISE')['ballot'],counter=24),basisId=next_value['basisId'])
    e.need(next_value==expected_value and next_value['basisId'] not in {old,e.f.decode(basis,'records','BASIS')['basisId']},'capture process subsequent grant identity')
    fresh=capture.transaction(clean,clean_dirs,next_promise);fresh_files,fresh_dirs=fresh[-1][1:];fresh_basis=e.decode(fresh_files['pending.context'])[0][3]
    _,_,last=backing.retirement(fresh_files,fresh_dirs,e.f.decode(basis,'records','BASIS')['basisId'])
    e.need(source.state(case/'store')==source.state(case/'final')==last[-1][1],'capture process exact continuing authority')
    expected+=events([s[0] for s in fresh])+[grant(24,fresh_basis)]+events([n for n,_ in last]+retain_seal(fresh_files))
    expected.append(dict(status='PASS',peakImages=7,steadyImages=6,runtimeEnabled=False))
    e.need(resume==expected,'capture process resume force/ack order')
    return dict(case=name,mode=mode,cut=point,status='PASS',exitCodes=[73 if mode=='halt' else 137,73,0])


def validate(root):
    root=Path(root);names={mode+'-'+point for mode in ('halt','kill') for point in POINTS}
    e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}==names|{'reference','initial','inputs.json','receipt.json'},'capture process case inventory')
    initial,dirs=frozen_seed(root);inputs=source.load(root/'inputs.json');e.exact(inputs,'observations')
    e.need(type(inputs['observations']) is list and len(inputs['observations'])<=512,'capture process observations')
    for row in inputs['observations']:
        e.exact(row,'voter storage record parent')
        for key,kind in (('voter','node'),('storage','uuid'),('record','hash'),('parent','hash')):e.f.check_type(row[key],kind,{})
    rows=[validate_case(root,initial,dirs,mode,point) for mode in ('halt','kill') for point in POINTS]
    expected=dict(schema='gse-v53-context-capture-process-v1',status='PASS',cases=rows,expectedCases=100,freshProcesses=300,lockProbes=50,
                  inputsSha256=e.digest((root/'inputs.json').read_bytes()),historicalBootstrap='conditional-fixture',powerLoss=False,runtimeEnabled=False)
    e.need(source.load(root/'receipt.json')==expected,'capture process receipt scope')
    return dict(status='PASS',cases=100,freshProcesses=300,lockProbes=50,originalFirst=True,subsequentGrant=24,originalVote=20,installedSelection=21,
                peakReservedImages=7,steadyReservedImages=6,runtimeEnabled=False,powerLoss=False,historicalBootstrap='conditional-fixture')


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'reference':'context checksum','missing':'capture process case inventory','seed':'context capture exact process seed',
              'first':'capture process exact first prefix','second':'context capture exact process second interruption','recovered':'capture process exact recovered authority',
              'final':'capture process exact continuing authority','source':'capture process exact continuing authority',
              'first-force':'capture process first force/death order','second-force':'capture process second force/death order',
              'resume-force':'capture process resume force/ack order','early-grant':'capture process second force/death order',
              'wrong-grant':'capture process resume force/ack order','ack':'capture process unrelated acknowledgement',
              'scope':'capture process receipt scope','inputs':'capture process receipt scope','capacity':'capture process resume force/ack order',
              'truncated':'capture process complete trace','stderr':'capture process stderr','link':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-capture-process-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);case=moved/'halt-CAPTURE_INTENT_CREATED'
            if name=='reference':
                path=moved/'reference/original-retirement/initial/pending.context';raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif name=='missing':shutil.rmtree(case)
            elif name in ('seed','first','second','recovered','final'):
                place=moved/'initial' if name=='seed' else case/{'first':'crash','second':'recovery-crash','recovered':'recovered','final':'final'}[name]
                (place/'pending.accept').write_bytes(b'changed')
            elif name=='source':next((case/'final/sources').rglob('source.gscp')).unlink()
            elif name in ('first-force','second-force','resume-force','early-grant','wrong-grant','ack'):
                label='fault' if name=='first-force' else 'recovery' if name in ('second-force','early-grant') else 'resume';path=case/(label+'.stdout');rows=trace(path)
                if name=='first-force':rows.remove(dict(event='PROMISE_FORCED'))
                elif name=='second-force':rows.remove(dict(event='BASIS_FORCED'))
                elif name=='resume-force':rows.remove(dict(event='CONTEXT_PARENT_FORCED'))
                elif name=='early-grant':rows.append(dict(event='RETURNED_GRANT',counter=23,record='0'*64))
                elif name=='wrong-grant':next(row for row in rows if row.get('event')=='RETURNED_GRANT')['record']='0'*64
                else:rows.append(dict(event='ACCEPT_BEFORE_RETURN'))
                path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            elif name in ('scope','inputs'):
                path=moved/('receipt.json' if name=='scope' else 'inputs.json');value=source.load(path)
                if name=='scope':value['powerLoss']=True
                else:value['observations'].reverse()
                path.write_bytes(e.f.canonical(value))
            elif name=='capacity':
                path=case/'resume.stdout';rows=trace(path);rows[-1]['peakImages']=8;path.write_bytes(b''.join(e.f.canonical(row)+b'\n' for row in rows))
            elif name=='truncated':
                path=case/'fault.stdout';path.write_bytes(path.read_bytes()+b'{')
            elif name=='stderr':(case/'fault.stderr').write_bytes(b'error')
            else:
                path=case/'final/pending.context';path.unlink();path.symlink_to((root/'initial/pending.context').resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong capture process negative: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted capture process mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-capture-process-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'capture process portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
