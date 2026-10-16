"""V5.2 whole-history command claims; no SSH, provider or paid admission.

Only generic forced-file helpers are reused from V5.1. Its identity schemas and
executor remain unchanged. A consumed claim never authorizes handler replay.
"""
from copy import deepcopy
import fcntl
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid
from scripts.v51.remote_command import directory, sync_directory, write_once, read
from . import cloud_suite as suite, remote_topology as topology
from scripts.v51.performance_model import canonical as encoded
from .evidence import need, digest

COMMANDS=frozenset(('prepare-receiver','start-voter','execute-history','declared-fault','stop-voter','collect'))
SCHEMA='gse-v52-command-receipt-v1'
REQUEST_BYTES=64<<10
RESPONSE_BYTES=4<<20
COMMAND_LIMIT=64
TERMINAL=frozenset(('SUCCEEDED','FAILED','CANCELLED'))


def hex_value(value,size,label):
    need(type(value) is str and re.fullmatch('[0-9a-f]{%d}'%size,value),'remote '+label)


def boot_id():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def process_identity():
    return dict(bootId=boot_id(),pid=os.getpid(),startTicks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))


def validate_process(value,owner):
    need(type(value) is dict and set(value)=={'bootId','pid','startTicks'},'remote process fields')
    need(value['bootId']==owner['bootId'] and type(value['pid']) is int and 0<value['pid']<1<<31 and
         type(value['startTicks']) is int and 0<value['startTicks']<1<<64,'remote process identity')


def process_alive(value):
    if boot_id()!=value['bootId']:return False
    try:
        with Path('/proc/%d/stat'%value['pid']).open('r') as stream:raw=stream.read(4097)
    except (FileNotFoundError,ProcessLookupError):return False
    need(len(raw)<=4096,'remote process stat bound')
    fields=raw.rsplit(')',1)[1].split()
    need(len(fields)>19,'remote process stat fields')
    return fields[0] not in ('Z','X') and int(fields[19])==value['startTicks']


def binding(selection,history,node,boot,session):
    value=dict(schema='gse-v52-guest-binding-v1',selection=deepcopy(selection),history=history,node=node,bootId=boot,session=session)
    validate_binding(value);return value


def validate_binding(value):
    need(type(value) is dict and set(value)=={'schema','selection','history','node','bootId','session'},'remote binding fields')
    need(value['schema']=='gse-v52-guest-binding-v1','remote binding schema')
    suite.validate_selection(value['selection'])
    need(type(value['history']) is str and value['history'] in value['selection']['member']['histories'],'remote whole history')
    need(value['node'] in topology.NODES,'remote node')
    boot=value['bootId'];need(type(boot) is str and len(boot)==36,'remote boot identity')
    try:parsed=uuid.UUID(boot)
    except ValueError:raise ValueError('remote boot identity') from None
    need(str(parsed)==boot and parsed.int!=0,'remote boot identity')
    hex_value(value['session'],32,'session')
    need(len(encoded(value))+1<=REQUEST_BYTES,'remote binding byte limit')
    return value


def request(owner,command_id,command,payload):
    validate_binding(owner)
    value=dict(schema='gse-v52-guest-command-v1',bindingSha256=digest(encoded(owner)),commandId=command_id,command=command,payload=deepcopy(payload))
    validate_request(value,owner);return value


def validate_request(value,owner):
    need(type(value) is dict and set(value)=={'schema','bindingSha256','commandId','command','payload'},'remote command fields')
    need(value['schema']=='gse-v52-guest-command-v1' and value['bindingSha256']==digest(encoded(owner)),'remote command binding')
    hex_value(value['commandId'],32,'command identity')
    need(type(value['command']) is str and value['command'] in COMMANDS and type(value['payload']) is dict,'remote command kind/payload')
    need(len(encoded(value))+1<=REQUEST_BYTES,'remote command byte limit')


def envelope(value,state,**fields):
    return dict(schema=SCHEMA,bindingSha256=value['bindingSha256'],commandId=value['commandId'],requestSha256=digest(encoded(value)),state=state,**fields)


def validate_receipt(result,value,owner):
    need(type(result) is dict and len(encoded(result))+1<=RESPONSE_BYTES,'remote response byte/type limit')
    state=result.get('state');base=envelope(value,state)
    need(all(result.get(k)==v for k,v in base.items()),'remote response identity')
    fields=set(base)
    if state in ('NOT_FOUND','BUSY','CANCEL_REQUESTED'):pass
    elif state=='UNCERTAIN':
        fields.add('reason');need(type(result.get('reason')) is str and len(result['reason'])<=256,'remote uncertainty reason')
    elif state=='RUNNING' or state in TERMINAL:
        fields.update(('process','startedNanos'));validate_process(result.get('process'),owner)
        need(type(result.get('startedNanos')) is int and 0<result['startedNanos']<1<<64,'remote start clock')
        if state in TERMINAL:
            fields.add('endedNanos');need(type(result.get('endedNanos')) is int and result['startedNanos']<=result['endedNanos']<1<<64,'remote end clock')
            need(('result' in result)!=('error' in result),'remote terminal outcome')
            if 'result' in result:
                fields.add('result');need(state!='FAILED' and type(result['result']) is dict,'remote terminal result')
            else:
                fields.add('error');error=result['error']
                need(state!='SUCCEEDED' and type(error) is dict and set(error)=={'type','message'} and
                     all(type(error[k]) is str for k in error) and len(error['type'])<=128 and len(error['message'])<=2000,'remote terminal error')
    else:raise ValueError('remote response state')
    need(set(result)==fields,'remote response fields');return result


class Cancelled(Exception):pass


class CommandStore:
    def __init__(self,root,owner,*,create=False):
        validate_binding(owner);self.root,self.owner=Path(root).absolute(),deepcopy(owner)
        if create:
            need(boot_id()==owner['bootId'],'remote foreign boot cannot create store')
            directory(self.root.parent);self.root.mkdir(mode=0o700);sync_directory(self.root.parent)
            write_once(self.root/'binding.json',self.owner,REQUEST_BYTES)
            (self.root/'commands').mkdir(mode=0o700);sync_directory(self.root)
        directory(self.root);directory(self.root/'commands')
        need(read(self.root/'binding.json',REQUEST_BYTES)==self.owner,'remote store ownership')

    def command_path(self,value):
        validate_request(value,self.owner);return self.root/'commands'/value['commandId']

    def query(self,value):
        path=self.command_path(value)
        if not path.exists() and not path.is_symlink():return envelope(value,'NOT_FOUND')
        directory(path)
        if not (path/'request.json').exists() and not (path/'request.json').is_symlink():
            return envelope(value,'UNCERTAIN',reason='claim without durable request')
        need(read(path/'request.json',REQUEST_BYTES)==value,'remote command ID reused with changed request')
        for name,state in (('terminal.json',TERMINAL),('started.json',{'RUNNING'})):
            if (path/name).exists() or (path/name).is_symlink():
                result=validate_receipt(read(path/name,RESPONSE_BYTES),value,self.owner)
                need(result['state'] in state,'remote receipt filename/state')
                if name=='started.json' and not process_alive(result['process']):
                    return envelope(value,'UNCERTAIN',reason='original executor absent; consumed claim retained')
                return result
        return envelope(value,'UNCERTAIN',reason='claimed before handler entry')

    def cancelled(self,value):
        path=self.command_path(value)/'cancel.json'
        if not path.exists() and not path.is_symlink():return False
        need(read(path,RESPONSE_BYTES)==envelope(value,'CANCEL_REQUESTED'),'remote cancellation identity');return True

    def checkpoint(self,value):
        if self.cancelled(value):raise Cancelled('retain original dispatched outcomes; do not replay')

    def cancel(self,value):
        result=self.query(value);need(result['state']!='NOT_FOUND','remote cancel unknown command')
        if result['state'] in TERMINAL:return result
        try:write_once(self.command_path(value)/'cancel.json',envelope(value,'CANCEL_REQUESTED'))
        except FileExistsError:need(self.cancelled(value),'remote incomplete cancel publication')
        return envelope(value,'CANCEL_REQUESTED')

    def execute(self,value,handler):
        value=deepcopy(value)
        path=self.command_path(value)
        if path.exists() or path.is_symlink():return self.query(value)
        need(boot_id()==self.owner['bootId'],'remote foreign boot cannot execute')
        lock=os.open(self.root/'executor.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            need(stat.S_ISREG(os.fstat(lock).st_mode),'remote executor lock type')
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return envelope(value,'BUSY')
            if path.exists() or path.is_symlink():return self.query(value)
            count=0
            with os.scandir(self.root/'commands') as entries:
                for _ in entries:
                    count+=1;need(count<COMMAND_LIMIT,'remote command count bound')
            path.mkdir(mode=0o700);sync_directory(path.parent)
            write_once(path/'request.json',value,REQUEST_BYTES)
            process=process_identity();validate_process(process,self.owner);started=time.monotonic_ns()
            write_once(path/'started.json',envelope(value,'RUNNING',process=process,startedNanos=started))
            try:
                self.checkpoint(value)
                # Payload semantics and lifecycle ordering belong to the trusted
                # adapter. This module never accepts shell or argv execution.
                result=handler(value['command'],deepcopy(value['payload']),lambda:self.checkpoint(value))
                terminal=envelope(value,'CANCELLED' if self.cancelled(value) else 'SUCCEEDED',process=process,
                                  startedNanos=started,endedNanos=time.monotonic_ns(),result=result)
                validate_receipt(terminal,value,self.owner)
            except BaseException as error:
                terminal=envelope(value,'CANCELLED' if isinstance(error,Cancelled) else 'FAILED',process=process,
                                  startedNanos=started,endedNanos=time.monotonic_ns(),
                                  error=dict(type=type(error).__name__[:128],message=str(error)[:2000]))
            write_once(path/'terminal.json',terminal,RESPONSE_BYTES);return terminal
        finally:os.close(lock)


def submit_and_observe(transport,value,owner,*,clock=time.monotonic,sleep=time.sleep,request_seconds=30,
                       warn_after=300,warn=lambda:None,failures_limit=3,uncertain_limit=3):
    """One submit; bounded failed exchanges; RUNNING duration is a soft budget.

    Each transport exchange has its own finite deadline. Only queries follow a
    lost submit response. Actual business/API deadlines are not changed here.
    """
    validate_binding(owner);value=deepcopy(value);owner=deepcopy(owner)
    validate_request(value,owner)
    need(type(request_seconds) in (int,float) and math.isfinite(request_seconds) and 0<request_seconds<=300,'remote exchange budget')
    need(type(warn_after) in (int,float) and math.isfinite(warn_after) and warn_after>0,'remote soft budget')
    need(all(type(v) is int and 1<=v<=10 for v in (failures_limit,uncertain_limit)),'remote failure thresholds')
    failures=uncertain=0;started=clock();warned=False;result=None
    def exchange(method):
        nonlocal failures
        deadline=clock()+request_seconds
        try:
            response=method(value,deadline)
            if clock()>deadline:raise TimeoutError('remote exchange late; observe original command')
            need(response is not None,'remote missing response')
            failures=0;return response
        except (ConnectionError,TimeoutError) as error:
            if getattr(error,'retryable',True) is False:raise
            failures+=1;need(failures<failures_limit,'remote transient failures exhausted; never resubmit')
            return None
    result=exchange(transport.submit)
    while True:
        if not warned and clock()-started>warn_after:warned=True;warn()
        if result is not None:
            validate_receipt(result,value,owner)
            if result['state'] in TERMINAL or result['state']=='BUSY':return result
            need(result['state'] in ('RUNNING','UNCERTAIN','NOT_FOUND'),'remote observation state')
            if result['state']=='RUNNING':uncertain=0
            else:
                uncertain+=1;need(uncertain<uncertain_limit,'remote uncertain replies exhausted; never resubmit')
        sleep(1);result=exchange(transport.query)
