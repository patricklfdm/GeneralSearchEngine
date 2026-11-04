"""Exact conditional storage replay across a deferred grant's fresh-process death.

No native network/quorum, power-loss or final-source cohort claim. Original
fixture bytes, forced PROMISE UUIDs and fresh process outcomes are observations;
crash, recovered, duplicate and next-grant files are independently derived.
"""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
import uuid
from . import current_generation_evidence as current
from . import source_release_evidence as release
from . import floor_evidence as floor
from . import floor_release_evidence as floor_release
from .context_evidence import parse
from . import capture_recovery_evidence as capture
from . import grant_evidence as g
from .membership_model import need

f=g.f
CUTS=('PROMISE_FORCED','FLOOR_BEFORE_RETURN','SOURCE_RETIREMENT_JOURNAL_PRUNED',
      'FLOOR_RELEASE_BEFORE_RETURN','CAPTURE_INTENT_FORCED','SOURCE_PACKET_PREFIX_WRITTEN','BASIS_FORCED')
CAPTURED=set(CUTS[4:])
OWNERS={'node-1','node-2','node-5','node-6'}

def info(raw):return dict(bytes=len(raw),sha256=current.sha(raw))
def read(path):return parse(g.read(Path(path),1024*1024))
def inventory(path):return current.s.inventory(path)
def exact(path,expected,label):need(inventory(path)==expected,'deferred process exact '+label)
def cases():return [dict(case=mode+'-'+cut,mode=mode,cut=cut) for mode in ('halt','kill') for cut in CUTS]


def history_inventory(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink(),'deferred process history directory')
    result={};total=0
    for path in root.rglob('*'):
        need(len(result)<4096 and not path.is_symlink() and (path.is_dir() or path.is_file()),'deferred process history bound/type')
        if path.is_file():
            need(path.stat().st_nlink==1,'deferred process history alias')
            total+=path.stat().st_size;need(total<=128*1024*1024,'deferred process history bytes')
            value=info(g.read(path,64*1024*1024))
        else:value=dict(directory=True)
        result[path.relative_to(root).as_posix()]=value
    return result


def seed(root):
    root=Path(root);need(root.is_dir() and not root.is_symlink() and (root/'seed').is_dir() and not (root/'seed').is_symlink(),'deferred process original directory')
    need({p.name for p in (root/'seed').iterdir()}==OWNERS,'deferred process exact seed owners')
    initial,rows,generation,packet=current.current(root/'seed/node-1',5)
    need([v[0] for v in rows]==['PROMISE','PROMISE','BASIS','PROMISE','BASIS'] and
         [v[2]['ballot']['counter'] for v in rows]==[10,20,20,21,21] and
         generation['cut']['index']==6 and generation['ownedTail'] is None,'deferred process original seed')
    sources=[rows[i][2]['basisId'] for i in (2,4)]
    need(read(root/'inputs.json')==dict(sources=sources),'deferred process original source IDs')
    base={k:v for k,v in initial.items() if not k.startswith('sources/') and k!='grants.gsr'}
    source={n:g.read(root/'seed/node-1/generations/a'/n,64*1024*1024) for n in ('source.gscp',*[h+'.image' for h in packet['images']])}
    need(len(packet['images'])==1,'deferred process single-image fixture')
    peers={};copies={};refs=[]
    for node in ('node-1','node-2','node-5','node-6'):
        path=root/'seed'/node;members={p.name:g.read(p,64*1024*1024) for p in (path/'generations/a').iterdir()}
        manifest=dict(generation,node=node);raw=f.encode('records','GENERATION',manifest)
        need(members==dict({p.name:g.read(p,64*1024*1024) for p in (root/'seed/node-1/generations/a').iterdir()},**{'generation.gsr':raw}),
             'deferred process original floor generation')
        node_raw=g.read(path/'node.gsr',4096);node_record=f.decode(node_raw,'records','NODE',generation['root'])
        need(node_record['identity']['node']==node,'deferred process original floor identity')
        peer_base=dict(base,**{'node.gsr':info(node_raw),'grants.gsr':info(rows[0][1]),
            'allocator.gsr':info(f.encode('records','ALLOCATOR',dict(root=generation['root'],node=node,counter=0))),
            'selector.gsr':info(f.encode('records','SELECTOR',dict(root=generation['root'],node=node,generation='a',digest=current.sha(raw))))})
        peer_base.update({'generations/a/'+n:info(v) for n,v in members.items()})
        if node=='node-1':peer_base=initial
        exact(path,peer_base,'seed peer '+node)
        peers[node]=peer_base;copies[current.sha(raw)]=members
        refs.append(dict(voter=node,generation=current.sha(raw),catalog=generation['catalog'],snapshot=generation['application']))
    voters={r['voter'] for r in refs};view=generation['cut']['view']
    need(all(len(voters&set(view[side]))>len(view[side])//2 for side in ('old','new')),'deferred process original joint floor')
    raw=f.encode('records','FLOOR',dict(root=generation['root'],node='node-1',cut=generation['cut'],sources=refs))
    floor_events,files,_,directories=floor.transaction(copies,raw)
    floor_files={**{p:dict(directory=True) for p in directories},**{p:info(v) for p,v in files.items()}}
    return dict(initial=initial,rows=rows,generation=generation,packet=packet,sources=sources,source=source,
                base=base,floor=raw,floorFiles=floor_files,peers=peers,floorEvents=[v['event'] for v in floor_events])


def grant(original,raw,counter,seen):
    value=f.decode(raw,'records','PROMISE',original['generation']['root']);old=original['rows'][1][2]
    expected=dict(old,ballot=dict(old['ballot'],counter=counter),basisId=value['basisId'])
    need(value==expected and str(uuid.UUID(value['basisId']))==value['basisId'] and value['basisId'] not in seen,
         'deferred process fresh original promise')
    seen.add(value['basisId']);p=original['packet'];gen=original['generation']
    basis=f.encode('records','BASIS',dict(value,voter='node-1',cut=gen['cut'],capsule=current.sha(p['capsuleBytes']),
          inventory=current.sha(p['indexBytes']),accepted=None))
    return value,basis


def captured(original,promise):
    prefix='sources/'+promise['basisId']
    return {prefix:dict(directory=True),**{prefix+'/'+n:info(v) for n,v in original['source'].items()}}


def states(root,row,original):
    path=Path(root)/row['case'];cut=row['cut'];old=original['rows'];r=original['generation']['root']
    crash_rows=g.journal(g.read(path/'crash/grants.gsr',g.LIMIT),r,'node-1')
    promises=[v for v in crash_rows if v[0]=='PROMISE'];seen={v[2]['basisId'] for v in old if v[0]=='PROMISE'}
    p30=promises[-1][1];value30,b30=grant(original,p30,30,seen)
    base=original['base'];journal=b''.join(v[1] for v in old)+p30
    initial=dict(original['initial'],**{'grants.gsr':info(journal)})
    full=dict(initial,**original['floorFiles']);compact=b''.join(v[1] for v in (old[0],old[3],old[4]))+p30
    identity=old[2][2]['basisId']
    record=f.encode('records','RETIREMENT',dict(root=r,node='node-1',floor=current.sha(original['floor']),
        selector=base['selector.gsr']['sha256'],files=[dict(path='sources/'+identity+'/'+n,size=len(v),sha256=current.sha(v)) for n,v in sorted(original['source'].items())]))
    authority=record+old[1][1]+old[2][1]+original['packet']['capsuleBytes']
    retirement=release.transaction(full,authority,compact,identity)
    pruned=next(v for event,v in retirement if event=='SOURCE_RETIREMENT_JOURNAL_PRUNED')
    released=dict(base,**{'grants.gsr':info(old[0][1]+p30)})
    second_id=old[4][2]['basisId'];second_record=f.encode('records','RETIREMENT',dict(root=r,node='node-1',floor=current.sha(original['floor']),
        selector=base['selector.gsr']['sha256'],files=[dict(path='sources/'+second_id+'/'+n,size=len(v),sha256=current.sha(v)) for n,v in sorted(original['source'].items())]))
    second=release.transaction(retirement[-1][1],second_record+old[3][1]+old[4][1]+original['packet']['capsuleBytes'],old[0][1]+p30,second_id)
    relinquish=floor_release.transaction(second[-1][1],original['floor'])
    # The release record bytes do not supply authority here: only event order is
    # consumed, while both complete floor and final no-floor inventories are derived.
    order=['PROMISE_FORCED',*original['floorEvents'],*[n for n,_ in retirement],*[n for n,_ in second],*[n for n,_ in relinquish],
           *capture.INTENT,*capture.SOURCE,*g.CUTS[3:6]]
    critical={'PROMISE_FORCED','FLOOR_MANIFEST_FORCED','FLOOR_IMAGE_FORCED','FLOOR_AUTHORITY_FORCED','FLOOR_PARENT_FORCED',
              'SOURCE_RETIREMENT_FORCED','JOURNAL_ROTATION_FORCED','JOURNAL_ROTATION_PARENT_FORCED','SOURCE_RETIREMENT_CLEARED',
              'FLOOR_RELEASE_AUTHORITY_FORCED','FLOOR_RELEASE_PARENT_FORCED','CAPTURE_INTENT_FORCED','CAPTURE_INTENT_PARENT_FORCED',
              'SOURCE_PACKET_FORCED','SOURCE_IMAGE_FORCED','BASIS_FORCED'}
    before_cut=order[:order.index(cut)+1]
    fault_rows=[parse(v) for v in g.read(path/'fault.stdout',1024*1024).splitlines()]
    need([v.get('event') for v in fault_rows if v.get('event') in critical]==[v for v in before_cut if v in critical],
         'deferred process original force order')
    complete=dict(released,**captured(original,value30),**{'grants.gsr':info(old[0][1]+p30+b30)})
    intent=g.read(Path(root)/'seed/node-1/selector.gsr',4096)+p30+b30
    if cut=='PROMISE_FORCED':crash=initial;reopened=initial
    elif cut=='FLOOR_BEFORE_RETURN':crash=full;reopened=full
    elif cut=='SOURCE_RETIREMENT_JOURNAL_PRUNED':crash=pruned;reopened=retirement[-1][1]
    elif cut=='FLOOR_RELEASE_BEFORE_RETURN':crash=released;reopened=released
    else:
        crash=dict(released,**{capture.AUTHORITY:info(intent)})
        if cut in ('SOURCE_PACKET_PREFIX_WRITTEN','BASIS_FORCED'):
            prefix='sources/'+value30['basisId'];crash[prefix]=dict(directory=True)
            raw=original['source']['source.gscp'];crash[prefix+'/source.gscp']=info(raw[:len(raw)//2])
        if cut=='BASIS_FORCED':crash=dict(complete,**{capture.AUTHORITY:info(intent)})
        reopened=complete
    exact(path/'crash',crash,'crash '+cut);exact(path/'reopened',reopened,'reopened '+cut)
    maintained=complete if cut in CAPTURED else released
    exact(path/'maintained',maintained,'maintained');exact(path/'same-ballot',maintained,'same ballot')
    final_rows=g.journal(g.read(path/'final/grants.gsr',g.LIMIT),r,'node-1')
    need([v[0] for v in final_rows[-2:]]==['PROMISE','BASIS'],'deferred process fresh next grant')
    p31=final_rows[-2][1];value31,b31=grant(original,p31,31,seen)
    expected=dict(maintained,**captured(original,value31),**{'grants.gsr':info(old[0][1]+p30+(b30 if cut in CAPTURED else b'')+p31+b31)})
    exact(path/'final',expected,'final');exact(path/'cold',expected,'cold');exact(path/'owners/node-1',expected,'live final')
    for node in ('node-2','node-5','node-6'):exact(path/'owners'/node,original['peers'][node],'original peer '+node)
    return dict(promise30=current.sha(p30),basis30=current.sha(b30),basis31=current.sha(b31),captureResumed=cut in CAPTURED)


def processes(path,row,derived):
    need(type(row['processes']) is list and len(row['processes'])==3,'deferred process exact process count')
    pids=set()
    for metadata,action in zip(row['processes'],('fault','resume','inspect')):
        need(type(metadata) is dict and set(metadata)=={'pid','action','exit','lockProbe'} and type(metadata['pid']) is int and
             metadata['pid']>0 and metadata['pid'] not in pids and metadata['action']==action,'deferred process fresh identity');pids.add(metadata['pid'])
        death=action=='fault';expected=73 if row['mode']=='halt' else 137
        need(type(metadata['exit']) is int and metadata['exit']==(expected if death else 0) and
             type(metadata['lockProbe']) is bool and metadata['lockProbe']==(death and row['mode']=='kill'),'deferred process actual outcome')
        need(g.read(path/(action+'.stderr'),1024*1024)==b'','deferred process unexpected stderr')
        rows=[parse(v) for v in g.read(path/(action+'.stdout'),1024*1024).splitlines()]
        need(rows and rows[0]==dict(event='STARTED',action=action,pid=metadata['pid']),'deferred process start binding')
        if death:
            ending=[dict(event='CUT',cut=row['cut'],pid=metadata['pid'])]
            if row['mode']=='kill':ending.append(dict(event='AWAITING_KILL',cut=row['cut']))
            need(rows[-len(ending):]==ending and all('status' not in v for v in rows),'deferred process death handshake')
            events=[v.get('event') for v in rows];need(events.count(row['cut'])==1 and events.index('PROMISE_FORCED')<=events.index(row['cut']),
                'deferred process original promise before cut')
            if row['cut'] not in CAPTURED:need('CAPTURE_INTENT_CREATED' not in events and 'BASIS_FORCED' not in events,'deferred process premature capture')
        else:
            result=rows[-1];need(set(result)=={'status','action','pid','peakSources','peakImages','nativeHistory'} and
                result['status']=='PASS' and result['action']==action and result['pid']==metadata['pid'] and result['nativeHistory'] is False and
                type(result['peakSources']) is int and 0<result['peakSources']<=6 and
                type(result['peakImages']) is int and 0<result['peakImages']<=7 and all('status' not in v for v in rows[:-1]),'deferred process return binding')
            if action=='resume':need([v for v in rows if v.get('event')=='RESUMED']==[dict(event='RESUMED',captured=derived['captureResumed'],basis=derived['basis31'])],
                'deferred process recovered original result')
    return len(pids)


def validate(root):
    root=Path(root);original=seed(root);receipt=read(root/'receipt.json');expected=cases()
    need(type(receipt) is dict and set(receipt)=={'schema','status','cases','expectedCases','historicalAuthority','nativeHistoryQualified','powerLossQualified','phase3Complete'} and
         receipt['schema']=='gse-v53-deferred-grant-process-v1' and receipt['status']=='PASS' and receipt['expectedCases']==14 and
         receipt['historicalAuthority']=='conditional-fixture' and all(receipt[k] is False for k in ('nativeHistoryQualified','powerLossQualified','phase3Complete')) and
         type(receipt['cases']) is list and len(receipt['cases'])==len(expected),'deferred process complete receipt')
    need({p.name for p in root.iterdir()}=={'seed','inputs.json','receipt.json',*[v['case'] for v in expected]},'deferred process root inventory')
    results=[]
    for actual,row in zip(receipt['cases'],expected):
        need(type(actual) is dict and set(actual)=={'case','cut','mode','processes','status'} and all(actual[k]==v for k,v in row.items()) and actual['status']=='PASS',
             'deferred process exact case inventory')
        path=root/row['case'];need((path/'owners').is_dir() and not (path/'owners').is_symlink(),'deferred process owners directory')
        need({p.name for p in (path/'owners').iterdir()}==OWNERS,'deferred process exact live owners')
        need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}==
             {'owners','crash','reopened','maintained','same-ballot','final','cold',*[a+s for a in ('fault','resume','inspect') for s in ('.stdout','.stderr')]},'deferred process case members')
        derived=states(root,row,original);count=processes(path,actual,derived)
        results.append(dict(case=row['case'],status='PASS',freshProcesses=count,**derived))
    return dict(status='PASS',cases=results,scope='conditional-deferred-grant-process',freshProcesses=sum(v['freshProcesses'] for v in results),
                exactPhysicalRecoveryQualified=True,nativeHistoryQualified=False,fullResourceCompositionQualified=False,powerLossQualified=False,phase3Complete=False)


NEGATIVES={
    'lost-promise':'deferred process fresh original promise',
    'missing-floor':'deferred process exact crash FLOOR_BEFORE_RETURN',
    'changed-retiring-source':'deferred process exact crash SOURCE_RETIREMENT_JOURNAL_PRUNED',
    'invented-basis':'deferred process exact same ballot',
    'changed-recovered-source':'deferred process exact reopened SOURCE_PACKET_PREFIX_WRITTEN',
    'cold-extra-file':'deferred process exact cold',
    'missing-force':'deferred process original force order',
    'false-kill-exit':'deferred process actual outcome',
    'reused-process':'deferred process fresh identity',
    'missing-case':'deferred process complete receipt',
}


def mutate(root,variant):
    root=Path(root)
    if variant=='lost-promise':
        path=root/'halt-PROMISE_FORCED/crash/grants.gsr'
        rows=g.journal(g.read(path,g.LIMIT),seed(root)['generation']['root'],'node-1')
        path.write_bytes(b''.join(v[1] for v in rows[:-1]));return
    if variant=='missing-floor':
        next((root/'halt-FLOOR_BEFORE_RETURN/crash/floor-copies').glob('*/generation.gsr')).unlink();return
    if variant=='changed-retiring-source':
        identity=read(root/'inputs.json')['sources'][0]
        (root/'halt-SOURCE_RETIREMENT_JOURNAL_PRUNED/crash/sources'/identity/'source.gscp').write_bytes(b'changed');return
    if variant=='invented-basis':
        path=root/'halt-PROMISE_FORCED';original=seed(root);r=original['generation']['root']
        rows=g.journal(g.read(path/'final/grants.gsr',g.LIMIT),r,'node-1');promise=next(v[1] for v in rows if v[0]=='PROMISE' and v[2]['ballot']['counter']==30)
        _,basis=grant(original,promise,30,{v[2]['basisId'] for v in original['rows'] if v[0]=='PROMISE'})
        file=path/'same-ballot/grants.gsr';file.write_bytes(file.read_bytes()+basis);return
    if variant=='changed-recovered-source':
        next((root/'halt-SOURCE_PACKET_PREFIX_WRITTEN/reopened/sources').glob('*/source.gscp')).write_bytes(b'changed');return
    if variant=='cold-extra-file':(root/'halt-PROMISE_FORCED/cold/extra').write_bytes(b'extra');return
    if variant=='missing-force':
        path=root/'halt-BASIS_FORCED/fault.stdout';rows=[parse(v) for v in path.read_bytes().splitlines()]
        at=next(i for i,v in enumerate(rows) if v.get('event')=='CAPTURE_INTENT_FORCED');rows.pop(at)
        path.write_bytes(b''.join(f.canonical(v)+b'\n' for v in rows));return
    path=root/'receipt.json';value=read(path)
    if variant=='false-kill-exit':next(v for v in value['cases'] if v['mode']=='kill')['processes'][0]['exit']=0
    elif variant=='reused-process':value['cases'][0]['processes'][1]['pid']=value['cases'][0]['processes'][0]['pid']
    elif variant=='missing-case':value['cases'].pop()
    else:raise ValueError('unknown deferred process mutation')
    path.write_bytes(f.canonical(value))


def qualify(root):
    before=history_inventory(root);original=validate(root);results=[]
    for variant,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-deferred-process-negative-') as temp:
            changed=Path(temp)/'raw';shutil.copytree(root,changed);mutate(changed,variant)
            try:validate(changed)
            except ValueError as error:need(str(error)==reason,'deferred process unrelated negative: '+variant+': '+str(error))
            else:raise ValueError('deferred process accepted mutation: '+variant)
        results.append(dict(case=variant,status='REJECTED',reason=reason))
    need(history_inventory(root)==before,'deferred process original changed')
    return dict(original=original,negatives=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps((qualify if args.qualify else validate)(args.root),sort_keys=True))
