"""Original-source replay of receiving scratch death and interrupted deletion.

The source/bootstrap history is independently reconstructed before examining any
scratch. This does not establish election, voting or whole-runtime crash recovery.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
from . import source_export_evidence as x

e=x.e
c=x.c
load=x.load
RECEIVE=('CREATED','PARTIAL_PACKET','PACKET_VERIFIED','PARTIAL_IMAGE','COMPLETE')
CLEANUP=('RECOVERY_VALIDATED','FILE_REMOVED','FILE_REMOVAL_FORCED','DIRECTORY_REMOVED','DIRECTORY_REMOVAL_FORCED')
UUID=r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def histories():
    for role in ('OUTGOING','INCOMING'):
        for mode in ('halt','kill'):
            for receive,cleanup in zip(RECEIVE,CLEANUP):
                name=f'{role.lower()}-{mode}-{receive.lower()}'
                yield dict(case=name,role=role,mode=mode,receiveCut=receive,cleanupCut=cleanup,
                           receiveExit=91 if mode=='halt' else 137,cleanupExit=91 if mode=='halt' else 137,freshJvms=3,status='PASS')


def history(path,row,grant,original):
    expected={'case.json','receive.ready','cleanup.ready','recover.json','crashed','interrupted','after'}
    expected|={f'{stage}.{suffix}' for stage in ('receive','cleanup','recover') for suffix in ('stdout','stderr')}
    e.need(path.is_dir() and not path.is_symlink() and {p.name for p in path.iterdir()}==expected,'scratch case inventory')
    e.need(load(path/'case.json')==row,'scratch case binding')
    for stage,cut in (('receive',row['receiveCut']),('cleanup',row['cleanupCut'])):
        e.need(load(path/(stage+'.ready'))==dict(cut=cut,mode=row['mode']),'scratch exact observed process cut')
    for name in expected:
        if name.endswith(('.stdout','.stderr')):e.need((path/name).read_bytes()==b'','scratch worker output')
    crashed=c.inventory(path/'crashed');e.need(crashed.get('scope.lock')==b'' and 'owner.json' in crashed,'scratch owner inventory')
    marker=json.loads(crashed['owner.json']);e.need(set(marker)=={'schema','root','identity','role','parent','directoryKey'},'scratch owner shape')
    e.need(marker['schema']=='gse-v53-derived-scratch-v1' and marker['root']==grant['root'] and marker['identity']==grant['local'] and marker['role']==row['role'],'scratch owner binding')
    parent=marker['parent']
    e.need(set(parent)=={'path','parentRealPath','fileStoreName','fileStoreType','parentFileKey'} and all(isinstance(v,str) and v for v in parent.values()) and
           Path(parent['path']).is_absolute() and str(Path(parent['path']).parent)==parent['parentRealPath'] and isinstance(marker['directoryKey'],str) and marker['directoryKey'],'scratch original path binding')
    dirs=sorted(name for name,value in crashed.items() if value is None)
    if row['role']=='OUTGOING':
        e.need(len(dirs)==1 and re.fullmatch('source-'+UUID,dirs[0]),'scratch outgoing directory shape');source=dirs[0]
    else:
        e.need(len(dirs)==2 and re.fullmatch('selected-'+UUID,dirs[0]) and dirs[1]==dirs[0]+'/source-1','scratch incoming directory shape');source=dirs[1]
    before={'owner.json':crashed['owner.json'],'scope.lock':b'',**{name:None for name in dirs}}
    packet=original['source.gscp'];cut=row['receiveCut']
    before[source+'/source.gscp']=b'' if cut=='CREATED' else packet[:17] if cut=='PARTIAL_PACKET' else packet
    if cut in ('PACKET_VERIFIED','PARTIAL_IMAGE','COMPLETE'):
        images=sorted(name for name in original if name.endswith('.image'))
        for n,name in enumerate(images):before[source+'/'+name]=original[name] if cut=='COMPLETE' else original[name][:17] if cut=='PARTIAL_IMAGE' and n==0 else b''
    e.need(crashed==before,'scratch original receiving state')
    interrupted=dict(before);files=sorted(name for name in before if name.startswith(source+'/') and before[name] is not None)
    if row['cleanupCut'] in ('FILE_REMOVED','FILE_REMOVAL_FORCED'):interrupted.pop(files[0])
    elif row['cleanupCut'] in ('DIRECTORY_REMOVED','DIRECTORY_REMOVAL_FORCED'):
        for name in files:interrupted.pop(name)
        interrupted.pop(source)
    e.need(c.inventory(path/'interrupted')==interrupted,'scratch exact interrupted deletion')
    remaining=[dict(path=name,directory=False,bytes=len(value)) for name,value in sorted(interrupted.items()) if '/' in name and value is not None]
    remaining += [dict(path=name,directory=True,bytes=0) for name in sorted((name for name,value in interrupted.items() if value is None),reverse=True)]
    e.need(load(path/'recover.json')==dict(status='PASS',discarded=remaining,remainingLeases=0),'scratch exact recovery receipt')
    e.need(c.inventory(path/'after')=={k:before[k] for k in ('owner.json','scope.lock')},'scratch final state')
    return row


def validate(directory):
    root=Path(directory);e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()}=={'receipt.json','stable-3'},'scratch evidence inventory')
    raw=root/'stable-3';x.case(raw,3,additional=('grant.json','crashes'))
    files=c.inventory(raw/'captured/node-1');_,members,packet=c.current(files);r=packet['capsule']['root'];records=c.journal(files['grants.gsr'],r,'node-1')
    grant=dict(root=r,source=e.f.decode(files['node.gsr'],'records','NODE')['identity'],
               local=e.f.decode(c.inventory(raw/'captured/node-2')['node.gsr'],'records','NODE')['identity'],
               promise=e.digest(records[-2][1]),basis=e.digest(records[-1][1]),capsule=e.digest(members['source.gscp']))
    e.need(load(raw/'grant.json')==grant,'scratch original grant')
    original={'source.gscp':members['source.gscp'],**{h+'.image':members[h+'.image'] for h in packet['images']}}
    rows=list(histories());e.need({p.name for p in (raw/'crashes').iterdir()}=={v['case'] for v in rows},'scratch complete process inventory')
    cases=[history(raw/'crashes'/row['case'],row,grant,original) for row in rows]
    expected=dict(schema='gse-v53-scratch-process-v1',status='PASS',cases=cases,freshJvms=60,publicRuntime=False,network=False,scope='receiving-scratch-restart-only')
    e.need(load(root/'receipt.json')==expected,'scratch scope/receipt');return expected


def qualify(directory):
    result=validate(directory);negative=[]
    mutations=[('scope','scratch scope/receipt'),('missing-case','scratch complete process inventory'),('grant','scratch original grant'),
               ('receiving-bytes','scratch original receiving state'),('owner','scratch owner binding'),('interrupted','scratch exact interrupted deletion'),
               ('recovery-receipt','scratch exact recovery receipt'),('final-extra','scratch final state'),('exit','scratch case binding'),('cut','scratch exact observed process cut')]
    for name,reason in mutations:
        with tempfile.TemporaryDirectory(prefix='v53-scratch-negative-') as temp:
            target=Path(temp)/'raw';shutil.copytree(directory,target);raw=target/'stable-3';member=raw/'crashes/outgoing-halt-created'
            if name=='scope':p=target/'receipt.json';v=load(p);v['publicRuntime']=True;p.write_text(json.dumps(v))
            elif name=='missing-case':shutil.rmtree(member)
            elif name=='grant':p=raw/'grant.json';v=load(p);v['local']=v['source'];p.write_text(json.dumps(v))
            elif name=='receiving-bytes':next((member/'crashed').glob('*/source.gscp')).write_bytes(b'changed')
            elif name=='owner':p=member/'crashed/owner.json';v=load(p);v['root']='f'*64;p.write_text(json.dumps(v))
            elif name=='interrupted':next((member/'interrupted').glob('*/source.gscp')).unlink()
            elif name=='recovery-receipt':p=member/'recover.json';v=load(p);v['discarded'][0]['path']='foreign';p.write_text(json.dumps(v))
            elif name=='final-extra':(member/'after/unlisted').write_bytes(b'keep')
            elif name=='exit':p=member/'case.json';v=load(p);v['receiveExit']=0;p.write_text(json.dumps(v))
            elif name=='cut':p=member/'receive.ready';v=load(p);v['cut']='COMPLETE';p.write_text(json.dumps(v))
            try:validate(target)
            except ValueError as error:e.need(reason in str(error),'scratch unrelated negative: '+name+': '+str(error))
            else:raise ValueError('scratch accepted negative: '+name)
            negative.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=result,negatives=negative)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--qualify',action='store_true');a=p.parse_args()
    print(json.dumps(qualify(a.directory) if a.qualify else validate(a.directory),sort_keys=True))
