"""Owned JVM crash capture and exact retained-generation reopen admission."""
import os
from pathlib import Path
import shutil
import stat
from . import remote_voter as v,remote_voter_scope as scope
from .evidence import need,digest,encoded


def inventory(root):
    root=v.c.directory(root);values={};total=0;directories=0
    for path in root.rglob('*'):
        need(not path.is_symlink(),'restart retained symlink')
        if path.is_dir():
            directories+=1;need(directories<=4096,'restart retained directory bound');continue
        info=path.stat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'restart retained file type')
        total+=info.st_size
        need(info.st_size<=8<<20 and total<=64<<20 and len(values)<4096,'restart retained bound')
        values[v.h.bundle.name(path.relative_to(root).as_posix())]=dict(bytes=info.st_size,sha256=v.h.bundle.sha_file(path))
    need(values,'restart retained empty');return dict(sorted(values.items()))


def capture(worker,control,sha,identity):
    need(worker.generation==1 and worker.proc.returncode==-9 and not worker.reader.is_alive(),
         'restart requires original SIGKILL exit')
    need(v.c.read(control/'crash-request.json')==dict(configSha256=sha,identity=identity),'restart crash claim')
    root=Path(worker.root);source=root/worker.node;before=inventory(source);target=root/(worker.node+'-pre-reopen')
    target.mkdir(mode=0o700)
    for name in before:
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,path)
        with path.open('rb') as stream:os.fsync(stream.fileno())
    for path in sorted([target,*[p for p in target.rglob('*') if p.is_dir()]],key=lambda p:len(p.parts),reverse=True):v.c.sync_directory(path)
    need(inventory(source)==inventory(target)==before,'restart capture changed')
    receipt=dict(configSha256=sha,identity=identity,generation=1,exitCode=-9,preReopen=before)
    v.c.write_once(control/'crash.json',receipt,v.c.RESPONSE_BYTES);return receipt


def crash_receipt(root,config,sha):
    root=Path(root);control=root/scope.control_name(config['node'],1)
    need(config['binding'].get('remoteRestart')==scope.RESTART_EXECUTION and scope.generation(config)==1,'restart declared crash scope')
    value=v.c.read(control/'crash.json',v.c.RESPONSE_BYTES)
    need(type(value) is dict and set(value)=={'configSha256','identity','generation','exitCode','preReopen'} and
         value['configSha256']==sha and value['generation']==1 and value['exitCode']==-9 and
         value['identity']==v.c.read(control/'identity.json'),'restart original crash identity')
    need(v.c.read(control/'crash-request.json')==dict(configSha256=sha,identity=value['identity']),'restart original crash claim')
    need(inventory(root/(config['node']+'-pre-reopen'))==value['preReopen'],'restart retained bytes changed')
    return value


def predecessor(root,node,binding,*,check_live):
    from . import remote_voter_guest as guest
    root=Path(root);control=root/scope.control_name(node)
    config=v.c.read(control/'config.json',v.c.REQUEST_BYTES);sha=digest(encoded(config))
    need(config['binding']==binding and scope.generation(config)==1 and config['node']==node and config['root']==str(root) and
         v.host.observe(control)==config['host'],'restart predecessor configuration changed')
    observed=guest.inspection(control,config)
    need(observed['state']=='CRASHED' and not observed['serviceAlive'] and not observed['jvmAlive'],'restart original owners not stopped')
    receipt=crash_receipt(root,config,sha)
    if check_live:need(inventory(root/node)==receipt['preReopen'],'restart authority changed before reopen')
    return receipt


def terminal(control,config):
    from . import remote_voter_guest as guest
    observed=guest.inspection(control,config);need(observed['state']=='CRASHED','restart original crash incomplete')
    receipt=crash_receipt(Path(config['root']),config,digest(encoded(config)))
    last=None;count=0
    with (control/'events.jsonl').open('rb') as stream:
        while True:
            row=v.receive(stream)
            if row is None:break
            count+=1;need(count<=2*v.MAX_CALLS+1,'restart event bound');last=row
    need(last and last['seq']==observed['stopped']['lastSequence']==count and last['kind']=='STOPPED' and
         last['exitCode']==-9 and last['failure'] is None,'restart original terminal event')
    return dict(crash=receipt,event=last)
