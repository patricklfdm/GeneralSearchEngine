"""Fixed SSH control entry. Detached original executors outlive SSH channels."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from scripts.v51.performance_model import strict_json
from . import remote_command as c,remote_slots as slots,remote_host as host
from .evidence import need,encoded

LAUNCH="import sys;sys.path.insert(0,sys.argv.pop(1));from scripts.v52.remote_ssh_guest import main;main()"
ERRORS={'HOST_CHANGED','SOURCE_CHANGED','REQUEST_REJECTED','GUEST_IO_FAILURE'}


def argv(checkout,action,root):return [sys.executable,'-I','-c',LAUNCH,str(checkout),action,str(root)]


def load(root):
    root=c.directory(root);value=c.read(root/'config.json',c.REQUEST_BYTES)
    need(host.check(value)==root,'SSH guest configuration root')
    need(root.stat().st_uid==os.getuid() and root.stat().st_mode & 0o077==0,'SSH guest root ownership')
    return value,c.CommandStore(root/'store',value['owner'])


def prepare(value):
    root=host.check(value)
    if not root.exists() and not root.is_symlink():
        root.mkdir(mode=0o700);c.sync_directory(root.parent)
        c.write_once(root/'config.json',value,c.REQUEST_BYTES)
        c.CommandStore(root/'store',value['owner'],create=True)
    previous,_=load(root);need(previous==value,'SSH guest preparation changed')
    return dict(state='PREPARED_NOT_EXECUTED')


def request(value,config):
    slots.validate(value,config['owner'])
    need(value['command']=='execute-history','SSH guest whole-history command only')
    return value


def launch_claim(value,config):
    return dict(configSha256=host.sha(config),request=value)


def query(root,config,store,value):
    request(value,config);answer=store.query(value)
    if (root/'launch.json').exists() or (root/'launch.json').is_symlink():
        need(c.read(root/'launch.json',c.REQUEST_BYTES)==launch_claim(value,config),'SSH guest launch identity changed')
        if answer['state']=='NOT_FOUND':return c.envelope(value,'UNCERTAIN',reason='original launch consumed; no durable handler receipt')
    elif (root/'launch.json.writing').exists():
        return c.envelope(value,'UNCERTAIN',reason='original launch publication incomplete')
    return answer


def submit(root,config,store,value):
    request(value,config)
    # Force the launch identity before spawning. Partial launch publication is
    # consumed uncertainty, never permission to create another executor.
    previous=query(root,config,store,value)
    if previous['state']!='NOT_FOUND':return previous
    try:c.write_once(root/'launch.json',launch_claim(value,config),c.REQUEST_BYTES)
    except FileExistsError:return query(root,config,store,value)
    with (root/'executor.stdout').open('xb') as out,(root/'executor.stderr').open('xb') as err:
        subprocess.Popen(argv(config['checkout'],'worker',root),cwd=config['checkout'],
                         stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
    # A short claim observation is not a history timeout. The caller's later
    # queries have their own exchange deadline and the original command identity.
    until=time.monotonic()+5
    while time.monotonic()<until:
        answer=query(root,config,store,value)
        if answer['state']!='UNCERTAIN':return answer
        time.sleep(.02)
    return answer


def worker(root):
    config,store=load(root);claim=c.read(root/'launch.json',c.REQUEST_BYTES)
    need(set(claim)=={'configSha256','request'} and claim['configSha256']==host.sha(config),'SSH guest worker claim')
    value=request(claim['request'],config);identity=c.process_identity();c.validate_process(identity,config['owner'])
    # Also excludes an accidental second worker before any history handler entry.
    c.write_once(root/'executor.json',dict(configSha256=host.sha(config),process=identity))
    status='FAIL'
    try:
        from .remote_owned_history import execute_local
        result=execute_local(store.root,value);status=result['state']
    finally:
        c.write_once(root/'executor-exit.json',dict(configSha256=host.sha(config),process=identity,state=status))


def inspect(root,config):
    result=dict(executor=None,exited=None,alive=False)
    for name,key in (('executor.json','executor'),('executor-exit.json','exited')):
        if (root/name).exists():
            value=c.read(root/name);need(value['configSha256']==host.sha(config),'SSH guest executor binding')
            c.validate_process(value['process'],config['owner']);result[key]=value
    if result['executor'] is not None:result['alive']=c.process_alive(result['executor']['process'])
    return validate_inspection(result,config)


def validate_inspection(result,config):
    need(type(result) is dict and set(result)=={'executor','exited','alive'} and type(result['alive']) is bool,'SSH guest inspection fields')
    for key in ('executor','exited'):
        value=result[key]
        if value is None:continue
        fields={'configSha256','process'} | ({'state'} if key=='exited' else set())
        need(type(value) is dict and set(value)==fields and value['configSha256']==host.sha(config),'SSH guest executor binding')
        c.validate_process(value['process'],config['owner'])
        if key=='exited':need(value['state'] in c.TERMINAL | {'FAIL'},'SSH guest executor exit state')
    need(result['executor'] is not None or not result['alive'],'SSH guest absent executor alive')
    if result['exited'] is not None:
        need(result['executor'] is not None and result['executor']['process']==result['exited']['process'],'SSH guest exit process changed')
    return result


def exchange(action,root,envelope):
    config,store=load(root)
    need(type(envelope) is dict and set(envelope)=={'configSha256','request'} and envelope['configSha256']==host.sha(config),
         'SSH guest request configuration')
    value=envelope['request']
    if action=='inspect':need(value is None,'SSH guest inspection payload');return config,inspect(root,config)
    request(value,config)
    if action=='submit':answer=submit(root,config,store,value)
    elif action=='query':answer=query(root,config,store,value)
    elif action=='cancel':answer=store.cancel(value)
    else:raise ValueError('SSH guest action')
    return config,answer


def reply(config,answer):
    return dict(schema='gse-v52-ssh-reply-v1',configSha256=host.sha(config),host=host.observe(Path(config['root']).parent),answer=answer)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=('probe','prepare','submit','query','cancel','inspect','worker'));p.add_argument('root',type=Path);a=p.parse_args()
    if a.action=='worker':worker(a.root);return
    try:
        raw=sys.stdin.buffer.read(c.REQUEST_BYTES+1);need(len(raw)<=c.REQUEST_BYTES,'SSH guest request bound')
        if a.action=='probe':need(not raw,'SSH guest probe payload');result=dict(schema='gse-v52-ssh-probe-v1',host=host.observe(a.root))
        else:
            value=strict_json(raw)
            if a.action=='prepare':
                need(host.validate(value)==a.root,'SSH guest preparation path');answer=prepare(value);config=value
            else:config,answer=exchange(a.action,a.root,value)
            result=reply(config,answer)
        data=encoded(result)+b'\n';need(len(data)<=c.RESPONSE_BYTES,'SSH guest response bound');sys.stdout.buffer.write(data)
    except Exception as error:
        code={'SSH guest host changed':'HOST_CHANGED','SSH guest source changed':'SOURCE_CHANGED'}.get(str(error),
              'GUEST_IO_FAILURE' if isinstance(error,OSError) else 'REQUEST_REJECTED')
        # No traceback, credentials or arbitrary exception text crosses SSH.
        sys.stdout.buffer.write(encoded(dict(schema='gse-v52-ssh-error-v1',code=code))+b'\n')


if __name__=='__main__':main()
