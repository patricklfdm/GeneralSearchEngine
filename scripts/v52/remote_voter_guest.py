"""Fixed loopback SSH lifecycle for a closed delivered receiver profile.

No shell payloads, package installation or cloud admission. Only exact M04
retained restart can admit a second generation after its original crash receipt.
Launch publication consumes the identity even if its reply or worker is lost.
"""
import argparse
import base64
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
from . import remote_voter as v
from .evidence import need, encoded, digest, strict

c,host,h=v.c,v.host,v.h
EXECUTION='loopback-ssh-voter-lifecycle-only'
SCHEMA='gse-v52-voter-lifecycle-v1'
ERROR_SCHEMA='gse-v52-voter-lifecycle-error-v1'
ERRORS={'HOST_CHANGED','SOURCE_CHANGED','REQUEST_REJECTED','GUEST_IO_FAILURE'}
ACTIONS={'probe','prepare','start','query','abort','collect','chunk','release','crash-terminal'}
CHUNK=512<<10
MAX_ARCHIVE=64<<20
MAX_FILES=4096
LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_voter_guest import main;main()"


def preparation(root,value):
    need(type(value) is dict and set(value)=={'node','binding','session','host'}|({'generation'} if 'generation' in value else set()),'lifecycle prepare fields')
    node=value['node'];need(node in h.topology.NODES,'lifecycle node');c.hex_value(value['session'],32,'lifecycle session')
    bound=value['binding'];need(bound.get('remoteVoterLifecycle')==EXECUTION,'lifecycle scope')
    need(bound['remoteReceivers'][node]['originalRoot']==str(root),'lifecycle receiver root')
    need(host.observe(root)==host.validate_pin(value['host']),'lifecycle host changed')
    source=h.source();need(all(source[k]==bound[k] for k in source),'voter source changed')
    gen=v.scope.generation(value);control=root/v.scope.control_name(node,gen)
    if gen==2 and not control.exists():
        from . import remote_restart_guest
        remote_restart_guest.predecessor(root,node,bound,check_live=True)
    if not control.exists() and not control.is_symlink():
        control.mkdir(mode=0o700);c.sync_directory(root)
        c.write_once(control/'preparation.json',value,c.REQUEST_BYTES)
        socket_dir=Path(tempfile.mkdtemp(prefix='v52-remote-voter-'))
        config=dict(schema=v.SCHEMA,execution='local-persistent-voters-only',node=node,root=str(root),
                    host=host.observe(control),binding=bound,socket=str(socket_dir/'channel'),session=value['session'])
        if 'generation' in value:config['generation']=gen
        try:
            v.validate_config(config,control)
            c.write_once(control/'config.json',config,c.REQUEST_BYTES)
        except BaseException:
            socket_dir.rmdir();raise
    need(c.read(control/'preparation.json',c.REQUEST_BYTES)==value,'lifecycle preparation changed')
    config=c.read(control/'config.json',c.REQUEST_BYTES);v.validate_config(config,control,fresh_socket=False)
    return config


def load(control,sha):
    c.hex_value(sha,64,'lifecycle configuration digest')
    config=c.read(c.directory(control)/'config.json',c.REQUEST_BYTES)
    need(digest(encoded(config))==sha,'lifecycle configuration changed')
    need(config['binding'].get('remoteVoterLifecycle')==EXECUTION,'lifecycle scope')
    v.validate_config(config,control,fresh_socket=False)
    return config


def inspection(control,config):
    sha=digest(encoded(config));answer=dict(state='PREPARED',started=None,identity=None,stopped=None,exited=None,
                                          serviceAlive=False,jvmAlive=False)
    if (control/'launch.json.writing').exists() and not (control/'launch.json').exists():
        answer['state']='UNCERTAIN';return answer
    if not (control/'launch.json').exists():
        need(not any((control/(name+suffix)).exists() for name in ('started','identity','stopped','exited') for suffix in ('.json','.json.writing')),
             'lifecycle orphaned launch evidence');return answer
    need(c.read(control/'launch.json')==dict(configSha256=sha),'lifecycle launch binding')
    answer['state']='STARTING'
    for key in ('started','identity','stopped','exited'):
        file=control/(key+'.json')
        if file.exists() or file.is_symlink():answer[key]=c.read(file,c.REQUEST_BYTES)
    started=answer['started'];identity=answer['identity']
    if started:
        need(set(started)=={'configSha256','service'} and started['configSha256']==sha,'lifecycle start binding')
        c.validate_process(started['service'],config['host']);answer['serviceAlive']=c.process_alive(started['service'])
    if identity:
        need(started and identity['service']==started['service'] and identity['host']==config['host'] and
             identity['session']==config['session'],'lifecycle process binding')
        c.validate_process(identity['jvm'],config['host']);answer['jvmAlive']=c.process_alive(identity['jvm'])
    if answer['exited']:
        need(started and answer['exited']==dict(configSha256=sha,service=started['service'],exitCode=answer['exited']['exitCode']) and
             type(answer['exited']['exitCode']) is int and answer['exited']['exitCode'] in (0,1),'lifecycle exit binding')
        answer['state']='EXITING' if answer['serviceAlive'] else 'FAILED'
        if not answer['serviceAlive'] and not answer['jvmAlive'] and answer['exited']['exitCode']==0:
            stop=answer['stopped']
            need(stop and stop['configSha256']==sha and stop['identity']==identity and stop['exitCode'] in (0,-9) and
                 stop['failure'] is None,'lifecycle terminal binding')
            if stop['exitCode']==-9:
                from . import remote_restart_guest
                remote_restart_guest.crash_receipt(Path(config['root']),config,sha);answer['state']='CRASHED'
            else:answer['state']='STOPPED'
    elif started and not answer['serviceAlive']:answer['state']='UNCERTAIN'
    elif identity and answer['serviceAlive'] and answer['jvmAlive'] and Path(config['socket']).exists():answer['state']='READY'
    return answer


def start(control,config):
    sha=digest(encoded(config));before=inspection(control,config)
    if before['state']!='PREPARED':return before
    try:c.write_once(control/'launch.json',dict(configSha256=sha))
    except FileExistsError:return inspection(control,config)
    with (control/'agent.log').open('xb') as log:
        subprocess.Popen([sys.executable,'-I','-c',LAUNCH,str(h.ROOT),'worker',str(control)],cwd=h.ROOT,
                         stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    return inspection(control,config)


def worker(control):
    config=c.read(control/'config.json',c.REQUEST_BYTES);sha=digest(encoded(config));own=v.process(os.getpid());code=1
    def terminate(signum,frame):raise RuntimeError('owned lifecycle cancelled')
    signal.signal(signal.SIGTERM,terminate)
    try:v.serve(control);code=0
    finally:
        # A duplicate/partial worker cannot overwrite the first owner's outcome.
        if (control/'started.json').exists() and c.read(control/'started.json')==dict(configSha256=sha,service=own):
            c.write_once(control/'exited.json',dict(configSha256=sha,service=own,exitCode=code))
    return code


def signal_owned(identity):
    """Pin the original kernel process before signaling; never signal a reused PID."""
    c.validate_process(identity,identity)
    if not c.process_alive(identity):return False
    try:fd=os.pidfd_open(identity['pid'])
    except ProcessLookupError:return False
    try:
        if not c.process_alive(identity):return False
        signal.pidfd_send_signal(fd,signal.SIGTERM);return True
    finally:os.close(fd)


def abort(control,config):
    before=inspection(control,config)
    if before['started'] and before['serviceAlive']:signal_owned(before['started']['service'])
    return inspection(control,config)


def selected(root,node):
    result={};total=directories=0
    for path in sorted(root.iterdir()):
        if path.name==node or path.name.startswith(node+'-'):
            need(not path.is_symlink(),'lifecycle collected symlink')
            paths=path.rglob('*') if path.is_dir() else [path]
            for item in paths:
                need(not item.is_symlink(),'lifecycle collected symlink')
                if item.is_dir():
                    directories+=1;need(directories<=h.bundle.LIMITS['directories'],'lifecycle directory bound');continue
                info=item.stat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'lifecycle regular unlinked file')
                total+=info.st_size
                need(len(result)<MAX_FILES and total<=MAX_ARCHIVE,'lifecycle collection bound')
                name=h.bundle.name(item.relative_to(root).as_posix());result[name]=dict(bytes=info.st_size,sha256=h.bundle.sha_file(item))
    need(result,'lifecycle empty collection');return result


def collect(control,config):
    terminal=inspection(control,config);need(terminal['state']=='STOPPED','lifecycle collection requires stopped original processes')
    if 'remotePartition' in config['binding']:
        from . import remote_partition_guest
        remote_partition_guest.seal(control,config)
    root=Path(config['root']);archive=root/'voter-collection.tar.gz';manifest=root/'voter-collection.json'
    index=selected(root,config['node']);sha=digest(encoded(config))
    if manifest.exists():
        result=c.read(manifest,c.RESPONSE_BYTES)
        need(result['configSha256']==sha and result['members']==index and archive.stat().st_size==result['bytes'] and
             h.bundle.sha_file(archive)==result['sha256'],'lifecycle collection changed');return result
    # Partial archive/staging consumes this export, retaining failure evidence.
    staging=root/'voter-collection';staging.mkdir(mode=0o700)
    for name in index:
        path=staging/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,path)
    need(h.bundle.members(staging)==index,'lifecycle collection changed during copy')
    h.bundle.pack(staging,archive)
    need(selected(root,config['node'])==index and 0<archive.stat().st_size<=MAX_ARCHIVE,'lifecycle collection changed/bound')
    result=dict(schema=SCHEMA,configSha256=sha,node=config['node'],bytes=archive.stat().st_size,
                sha256=h.bundle.sha_file(archive),members=index,terminal=terminal)
    c.write_once(manifest,result,c.RESPONSE_BYTES);return result


def chunk(control,config,value):
    need(type(value) is dict and set(value)=={'sha256','offset'},'lifecycle chunk fields')
    root=Path(config['root']);meta=c.read(root/'voter-collection.json',c.RESPONSE_BYTES)
    need(meta['configSha256']==digest(encoded(config)) and value['sha256']==meta['sha256'],'lifecycle chunk identity')
    offset=value['offset'];need(type(offset) is int and 0<=offset<meta['bytes']<=MAX_ARCHIVE and offset%CHUNK==0,'lifecycle chunk offset')
    fd=os.open(root/'voter-collection.tar.gz',os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno());need(stat.S_ISREG(info.st_mode) and info.st_size==meta['bytes'],'lifecycle archive type/size')
        stream.seek(offset);data=stream.read(min(CHUNK,meta['bytes']-offset))
    need(len(data)==min(CHUNK,meta['bytes']-offset),'lifecycle truncated chunk')
    return dict(sha256=meta['sha256'],offset=offset,data=base64.b64encode(data).decode('ascii'))


def release(control,config):
    seen=inspection(control,config)
    need(seen['state'] in ('STOPPED','FAILED','CRASHED') and not seen['serviceAlive'] and not seen['jvmAlive'],
         'lifecycle release requires stopped owner')
    socket_dir=host.path(config['socket']).parent;host.observe(socket_dir)
    socket_dir.rmdir();return dict(released=True)


def exchange(action,root,value):
    need(action in ACTIONS,'lifecycle action')
    if action=='probe':need(value is None,'lifecycle probe fields');return dict(host=host.observe(root))
    if action=='prepare':return dict(config=preparation(root,value))
    need(type(value) is dict and set(value)=={'configSha256','request'},'lifecycle request fields')
    config=load(root,value['configSha256']);request=value['request']
    if action=='chunk':answer=chunk(root,config,request)
    else:
        need(request is None,'lifecycle action payload')
        if action=='crash-terminal':
            from . import remote_restart_guest
            answer=remote_restart_guest.terminal(root,config)
        else:answer={'start':start,'query':inspection,'abort':abort,'collect':collect,'release':release}[action](root,config)
    return dict(configSha256=digest(encoded(config)),host=config['host'],answer=answer)


def error_code(error):
    return {'lifecycle host changed':'HOST_CHANGED','voter host changed':'HOST_CHANGED','voter source changed':'SOURCE_CHANGED'}.get(
        str(error),'GUEST_IO_FAILURE' if isinstance(error,OSError) else 'REQUEST_REJECTED')


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=sorted(ACTIONS|{'worker'}));p.add_argument('root');a=p.parse_args()
    root=host.path(a.root)
    if a.action=='worker':raise SystemExit(worker(root))
    try:
        data=sys.stdin.buffer.read(c.REQUEST_BYTES+1);need(len(data)<=c.REQUEST_BYTES,'lifecycle request bound')
        result=exchange(a.action,root,strict(data) if data else None)
        raw=encoded(result)+b'\n';need(len(raw)<=c.RESPONSE_BYTES,'lifecycle response bound')
    except Exception as error:raw=encoded(dict(schema=ERROR_SCHEMA,code=error_code(error)))+b'\n'
    sys.stdout.buffer.write(raw)


if __name__=='__main__':main()
