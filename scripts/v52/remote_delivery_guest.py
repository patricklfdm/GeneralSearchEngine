"""Fixed guest upload and detached bootstrap; no voter or arbitrary command entry."""
import argparse
from . import remote_python_context as python_context
import base64
import os
from pathlib import Path
import subprocess
import sys
from . import remote_delivery_package as p,remote_voter as v
from .evidence import need,encoded,digest,strict

c,host,h=p.c,p.host,p.h
ACTIONS={'probe','begin','part','query','install'}
LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_delivery_guest import main;main()"
ERROR_SCHEMA='gse-v52-delivery-error-v1'
ERRORS={'HOST_CHANGED','SOURCE_CHANGED','REQUEST_REJECTED','GUEST_IO_FAILURE'}


def store_for(value):return Path(value['parent'])/(value['node']+'-delivery')


def begin(parent,value):
    need(p.check(value)==parent,'delivery parent mismatch');store=store_for(value)
    if not store.exists() and not store.is_symlink():
        destination=parent/value['node'];need(not destination.exists() and not destination.is_symlink(),'delivery destination consumed')
        store.mkdir(mode=0o700);c.sync_directory(parent)
        c.write_once(store/'descriptor.json',value,c.REQUEST_BYTES);(store/'parts').mkdir(mode=0o700);c.sync_directory(store)
    need(load(store,digest(encoded(value)))==value,'delivery changed original descriptor')
    return query(store,value)


def load(store,sha):
    c.hex_value(sha,64,'delivery descriptor hash');host.observe(store)
    value=c.read(store/'descriptor.json',c.REQUEST_BYTES)
    need(digest(encoded(value))==sha,'delivery descriptor changed');p.check(value,source=False)
    need(store_for(value)==store,'delivery store path');c.directory(store/'parts');return value


def parts(store,value):
    rows=value['package']['parts'];files=list((store/'parts').iterdir())
    allowed={f'{i:04d}.json'+suffix for i in range(len(rows)) for suffix in ('','.writing')}
    need(len(files)<=len(rows)*2 and all(f.name in allowed for f in files),
         'delivery unknown part files')
    count=0;partial=False
    for index,row in enumerate(rows):
        path=store/'parts'/f'{index:04d}.json'
        if not path.exists():
            partial=(path.with_name(path.name+'.writing')).exists()
            need(not any((store/'parts'/f'{later:04d}.json').exists() for later in range(index+1,len(rows))),'delivery part gap')
            break
        raw=read_part(path,row,index);count+=1
    return count,partial


def read_part(path,row,index):
    value=c.read(path,c.REQUEST_BYTES)
    need(type(value) is dict and set(value)=={'index','data'} and type(value['index']) is int and value['index']==index and
         type(value['data']) is str and len(value['data'])<=4*((p.PART+2)//3),'delivery part fields')
    raw=base64.b64decode(value['data'],validate=True)
    need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'delivery part bytes changed');return raw


def query(store,value):
    count,partial=parts(store,value);sha=digest(encoded(value))
    answer=dict(descriptorSha256=sha,state='UNCERTAIN' if partial else 'UPLOADING',completedParts=count,started=None,terminal=None,alive=False)
    if count==len(value['package']['parts']):answer['state']='READY'
    launch=store/'launch.json';started=store/'started.json';terminal=store/'terminal.json'
    if launch.exists():
        need(c.read(launch)==dict(descriptorSha256=sha),'delivery launch changed');answer['state']='STARTING'
        if started.exists():
            own=c.read(started);need(set(own)=={'descriptorSha256','process'} and own['descriptorSha256']==sha,'delivery worker binding')
            c.validate_process(own['process'],value['host']);answer['started']=own;answer['alive']=c.process_alive(own['process'])
            answer['state']='RUNNING' if answer['alive'] else 'UNCERTAIN'
        if terminal.exists():
            outcome=c.read(terminal,c.REQUEST_BYTES)
            need(answer['started'] and outcome['descriptorSha256']==sha and outcome['process']==answer['started']['process'] and
                 outcome['state'] in ('SUCCEEDED','FAILED'),'delivery terminal binding')
            answer['terminal']=outcome;answer['state']='EXITING' if answer['alive'] else outcome['state']
    elif (store/'launch.json.writing').exists():answer['state']='UNCERTAIN'
    else:need(not started.exists() and not terminal.exists(),'delivery orphaned launch')
    return answer


def part(store,value,payload):
    need(type(payload) is dict and set(payload)=={'index','data'} and type(payload['index']) is int and
         0<=payload['index']<len(value['package']['parts']) and type(payload['data']) is str and
         len(payload['data'])<=4*((p.PART+2)//3),'delivery upload fields')
    index=payload['index'];row=value['package']['parts'][index];raw=base64.b64decode(payload['data'],validate=True)
    need(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'delivery upload hash')
    before=query(store,value);need(before['state'] in ('UPLOADING','READY') and index<=before['completedParts'],'delivery upload order/consumed')
    path=store/'parts'/f'{index:04d}.json'
    if index==before['completedParts']:
        try:c.write_once(path,payload,c.REQUEST_BYTES)
        except FileExistsError:pass
    need(read_part(path,row,index)==raw,'delivery duplicate bytes changed')
    return query(store,value)


def install(store,value):
    p.check(value);before=query(store,value)
    if before['state']!='READY':return before
    destination=Path(value['parent'])/value['node'];need(not destination.exists() and not destination.is_symlink(),'delivery destination consumed')
    try:c.write_once(store/'launch.json',dict(descriptorSha256=digest(encoded(value))))
    except FileExistsError:return query(store,value)
    with (store/'worker.log').open('xb') as log:
        subprocess.Popen(python_context.child('delivery',LAUNCH,['worker',str(store)]),cwd=h.ROOT,
                         stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    return query(store,value)


def worker(store):
    value=c.read(store/'descriptor.json',c.REQUEST_BYTES);p.check(value);sha=digest(encoded(value));identity=v.process(os.getpid())
    need(store_for(value)==store and c.read(store/'launch.json')==dict(descriptorSha256=sha),'delivery worker claim')
    c.write_once(store/'started.json',dict(descriptorSha256=sha,process=identity))
    result=dict(descriptorSha256=sha,process=identity,state='FAILED',error='INSTALL_FAILED')
    try:
        meta=value['package'];archive=store/p.CAPSULE
        with archive.open('xb') as out:
            for i,row in enumerate(meta['parts']):out.write(read_part(store/'parts'/f'{i:04d}.json',row,i))
            out.flush();os.fsync(out.fileno())
        p.verify_archive(archive,meta);destination=Path(value['parent'])/value['node']
        h.bundle.unpack(archive,destination);destination.chmod(0o700);p.installed(destination,meta)
        command=[python_context.java(),'-cp',h.Receivers.paths(destination,meta),h.PACKAGE+'V52RemoteBootstrap',str(destination),value['node']]
        observed=subprocess.run(command,cwd=h.ROOT,capture_output=True,text=True,timeout=120,env=python_context.environment())
        (store/'bootstrap.stdout').write_text(observed.stdout);(store/'bootstrap.stderr').write_text(observed.stderr)
        need(observed.returncode==0,'bootstrap: '+observed.stderr[-6000:]);answer=strict(observed.stdout)
        p.bootstrap_answer(answer,value);p.installed(destination,meta);p.check(value)
        receipt=dict(schema='gse-v52-receiver-bootstrap-v1',execution=p.execution(value['package']),descriptor=value,descriptorSha256=sha,
                     process=identity,receiverHost=host.observe(destination),answer=answer)
        python_context.record(destination/(value['node']+'-python-bootstrap.json'))
        c.write_once(destination/(value['node']+'-delivery.json'),receipt,c.REQUEST_BYTES)
        result=dict(descriptorSha256=sha,process=identity,state='SUCCEEDED',receipt=receipt)
    finally:c.write_once(store/'terminal.json',result,c.REQUEST_BYTES)


def exchange(action,root,value):
    need(action in ACTIONS,'delivery action')
    if action=='probe':need(value is None,'delivery probe payload');return dict(host=host.observe(root))
    if action=='begin':answer=begin(root,value);descriptor=value
    else:
        need(type(value) is dict and set(value)=={'descriptorSha256','request'},'delivery envelope fields')
        descriptor=load(root,value['descriptorSha256'])
        if action=='part':answer=part(root,descriptor,value['request'])
        else:
            need(value['request'] is None,'delivery action payload');answer={'query':query,'install':install}[action](root,descriptor)
    return dict(descriptorSha256=digest(encoded(descriptor)),host=descriptor['host'],answer=answer)


def error_code(error):
    return {'delivery host changed':'HOST_CHANGED','delivery source changed':'SOURCE_CHANGED'}.get(str(error),
        'GUEST_IO_FAILURE' if isinstance(error,OSError) else 'REQUEST_REJECTED')


def main():
    p_=argparse.ArgumentParser();p_.add_argument('action',choices=sorted(ACTIONS|{'worker'}));p_.add_argument('root');a=p_.parse_args()
    root=host.path(a.root)
    if a.action=='worker':worker(root);return
    try:
        raw=sys.stdin.buffer.read(c.REQUEST_BYTES+1);need(len(raw)<=c.REQUEST_BYTES,'delivery request bound')
        answer=exchange(a.action,root,strict(raw) if raw else None);out=encoded(answer)+b'\n'
        need(len(out)<=c.RESPONSE_BYTES,'delivery response bound')
    except Exception as error:out=encoded(dict(schema=ERROR_SCHEMA,code=error_code(error)))+b'\n'
    sys.stdout.buffer.write(out)


if __name__=='__main__':main()
