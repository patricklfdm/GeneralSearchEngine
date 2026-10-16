"""One declared bidirectional cut/heal, owned by an existing pinned voter.

An uncertain write remains consumed. Cleanup can only heal, and its presence
invalidates successful history evidence. No firewall commands or arbitrary paths.
"""
import argparse
import fcntl
import os
from pathlib import Path
import stat
import sys
import time
from . import remote_voter as v,remote_voter_guest as lifecycle,remote_partition_scope as scope
from .evidence import need,encoded,digest,strict

ACTIONS={'apply','query'}
ERROR_SCHEMA='gse-v52-partition-error-v1'
ERRORS=lifecycle.ERRORS
LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_partition_guest import main;main()"
STREAM_LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_partition_guest import stream_main;stream_main()"
FILE='network-blocks.txt'


def request(value):
    need(type(value) is dict and set(value)=={'operation','target'} and value['operation'] in ('cut','heal','cleanup'),
         'partition request fields')
    need(value['target'] in v.h.topology.NODES if value['operation']!='cleanup' else value['target'] is None,
         'partition declared target')
    return value


def body(value):
    request(value)
    if value['operation']!='cut':return b''
    return ''.join(a+' '+b+'\n' for a in v.h.topology.NODES for b in v.h.topology.NODES
                   if a!=b and value['target'] in (a,b)).encode('ascii')


def current(root):
    path=root/FILE
    if not path.exists() and not path.is_symlink():return None
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno());need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=128,
                                         'partition control file bound/type')
        return digest(stream.read(129))


def outcome(value,config,command):
    need(type(value) is dict and set(value)=={'configSha256','request','process','startNanos','endNanos','beforeSha256','afterSha256'} and
         value['configSha256']==digest(encoded(config)) and value['request']==request(command),'partition original result binding')
    v.c.validate_process(value['process'],config['host'])
    need(type(value['startNanos']) is int and type(value['endNanos']) is int and 0<value['startNanos']<value['endNanos'],
         'partition guest clock order')
    if value['beforeSha256'] is not None:v.c.hex_value(value['beforeSha256'],64,'partition prior file hash')
    need(value['afterSha256']==digest(body(command)),'partition resulting cut changed')
    return value


def query(control,config,command):
    request(command);store=control/'partition';op=command['operation']
    if store.exists() or store.is_symlink():v.host.observe(store)
    claim=store/(op+'-request.json');result=store/(op+'-result.json')
    state='NOT_ISSUED';answer=None
    if claim.exists() or claim.is_symlink():
        need(v.c.read(claim)==dict(configSha256=digest(encoded(config)),request=command),'partition consumed request changed')
        state='UNCERTAIN'
        if result.exists() or result.is_symlink():answer=outcome(v.c.read(result),config,command);state='APPLIED'
    elif claim.with_suffix('.json.writing').exists():state='UNCERTAIN'
    else:need(not result.exists() and not result.with_suffix('.json.writing').exists(),'partition orphaned result')
    return dict(state=state,request=command,result=answer,currentSha256=current(Path(config['root'])))


def publish(root,raw):
    path=root/'network-blocks.pending'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(path,root/FILE);v.c.sync_directory(root)


def apply(control,config,command):
    request(command);store=control/'partition';root=Path(config['root']);op=command['operation']
    if not store.exists():store.mkdir(mode=0o700);v.c.sync_directory(control)
    v.host.observe(store)
    fd=os.open(store/'lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode) and os.fstat(fd).st_nlink==1,'partition lock type')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        before=query(control,config,command)
        if before['state']!='NOT_ISSUED':return before
        if op!='cleanup':
            need(not any(store.glob('cleanup-*')),'partition cleanup consumed history')
            need(lifecycle.inspection(control,config)['state']=='READY','partition requires original ready voter')
        if op=='cut':
            need(before['currentSha256'] is None and not any(store.glob('heal-*')),'partition original cut requires fresh control')
        if op=='heal':
            cut=query(control,config,dict(operation='cut',target=command['target']))
            need(cut['state']=='APPLIED' and cut['currentSha256']==digest(body(cut['request'])),'partition heal requires original cut')
        began=time.monotonic_ns()
        v.c.write_once(store/(op+'-request.json'),dict(configSha256=digest(encoded(config)),request=command))
        # Cleanup is distinct from the measured transition. It may replace a
        # partial pending file safely, but never repairs its consumed receipt.
        if op=='cleanup':(root/'network-blocks.pending').unlink(missing_ok=True)
        publish(root,body(command))
        result=dict(configSha256=digest(encoded(config)),request=command,process=v.process(os.getpid()),startNanos=began,
                    endNanos=time.monotonic_ns(),beforeSha256=before['currentSha256'],afterSha256=current(root))
        outcome(result,config,command);v.c.write_once(store/(op+'-result.json'),result)
        return query(control,config,command)
    finally:os.close(fd)


def exchange(action,control,value):
    need(action in ACTIONS and type(value) is dict and set(value)=={'configSha256','request'},'partition envelope fields')
    config=lifecycle.load(control,value['configSha256'])
    need(config['binding'].get('remotePartition')==scope.EXECUTION and scope.history(config['binding']) is not None,
         'partition undeclared history')
    answer={'apply':apply,'query':query}[action](control,config,value['request'])
    return dict(configSha256=value['configSha256'],host=config['host'],answer=answer)


def prepared_exchange(action,control,value,config):
    """An already-loaded owner executes fixed commands; no per-fault imports.

    Source/artifact admission ran before READY. The existing service owns its
    already-loaded JVM, while every command still checks immutable configuration,
    directory identity, original lifecycle and consumed transition receipts.
    """
    need(action in ACTIONS and type(value) is dict and set(value)=={'configSha256','request'} and
         value['configSha256']==digest(encoded(config)),'partition envelope fields')
    need(v.c.read(control/'config.json',v.c.REQUEST_BYTES)==config and v.host.observe(control)==config['host'],
         'partition prepared owner changed')
    need(config['binding'].get('remotePartition')==scope.EXECUTION and scope.history(config['binding']) is not None,
         'partition undeclared history')
    answer={'apply':apply,'query':query}[action](control,config,value['request'])
    return dict(configSha256=value['configSha256'],host=config['host'],answer=answer)


def stream_main():
    parser=argparse.ArgumentParser();parser.add_argument('control');parser.add_argument('sha');args=parser.parse_args()
    def write(value):
        raw=encoded(value)+b'\n';need(len(raw)<=v.FRAME,'partition stream response bound')
        sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
    try:
        control=v.host.path(args.control);config=lifecycle.load(control,args.sha)
        need(config['binding'].get('remotePartition')==scope.EXECUTION and scope.history(config['binding']) is not None,
             'partition undeclared history')
        write(dict(ready=True,configSha256=args.sha,host=config['host'],process=v.process(os.getpid())))
        for _ in range(8):
            value=v.receive(sys.stdin.buffer)
            if value is None:return
            need(set(value)=={'action','value'},'partition stream fields')
            write(prepared_exchange(value['action'],control,value['value'],config))
        # Bounded original control session. Additional observations require a
        # freshly authenticated channel, never an implicit repeated mutation.
    except Exception as error:write(dict(schema=ERROR_SCHEMA,code=lifecycle.error_code(error)))


def seal(control,config):
    """Export the actual healed bytes only after both original owners stopped."""
    need(lifecycle.inspection(control,config)['state']=='STOPPED','partition seal requires stopped voters')
    store=control/'partition'
    need(not any(store.glob('cleanup-*')) and not (Path(config['root'])/'network-blocks.pending').exists(),
         'partition cleanup/partial history cannot qualify')
    target=v.c.read(store/'cut-request.json')['request']['target']
    for op in ('cut','heal'):
        need(query(control,config,dict(operation=op,target=target))['state']=='APPLIED','partition missing original transition')
    need(current(Path(config['root']))==digest(b''),'partition collection must be healed')
    path=store/'final.json';value=dict(configSha256=digest(encoded(config)),currentSha256=digest(b''))
    if not path.exists():v.c.write_once(path,value)
    need(v.c.read(path)==value,'partition final collection changed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=sorted(ACTIONS));parser.add_argument('control');a=parser.parse_args()
    try:
        raw=sys.stdin.buffer.read(v.c.REQUEST_BYTES+1);need(len(raw)<=v.c.REQUEST_BYTES,'partition request bound')
        answer=exchange(a.action,v.host.path(a.control),strict(raw));raw=encoded(answer)+b'\n'
        need(len(raw)<=v.c.RESPONSE_BYTES,'partition response bound')
    except Exception as error:raw=encoded(dict(schema=ERROR_SCHEMA,code=lifecycle.error_code(error)))+b'\n'
    sys.stdout.buffer.write(raw)


if __name__=='__main__':main()
