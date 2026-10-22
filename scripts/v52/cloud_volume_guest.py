"""Fixed V5.2 root volume receiver, delivered from the admitted controller source.

No installed guest module, caller-selected path or command is executed. The
controller brackets this protocol with live provider/lease observations; a root
receipt alone grants neither cloud admission nor workload qualification.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import signal
import stat
import subprocess
import sys
import time
import uuid
from . import cloud_guest_identity as guest

MOUNT='/mnt/gse-v52'
PARENT='/var/lib/gse-v52-volume'
SCHEMA='gse-v52-native-volume-request-v1'
RECEIPT='gse-v52-native-volume-startup-v1'
MAX_BYTES=512<<10
MAX_SECONDS=300
FAILURE_SCHEMA='gse-v52-volume-rejection-v1'
# Only fixed receiver vocabulary crosses the SSH boundary, never exception text.
FAILURE_CODES=frozenset('V52_VOLUME_'+name for name in '''
ABSENT_TARGET ACTION ALREADY_MOUNTED ARGUMENTS BEFORE_WRITE_DRIFT BLOCK_COUNT
BLOCK_FIELDS BLOCK_IDENTITIES BLOCK_MISSING BLOCK_TOPOLOGY BOOT_DISK BOOT_LAYOUT
BUDGET_FIELDS CLOCK_BINDING CLOCK_EXPIRED COMMAND_FAILED COMMAND_OUTPUT_BOUND
DATA_DISK DEVICE_ALIAS DEVICE_CHANGED DIGEST DUPLICATE_FIELD ENVELOPE
EXCHANGE_DEADLINE EXISTING_FILESYSTEM FILESYSTEM GUEST_BINDING GUEST_BOOT INTEGER
INVOKING_ACCOUNT METADATA_IDENTITY MOUNT_COUNT MOUNT_FIELDS MOUNT_IDENTITY
MOUNT_OPTIONS MOUNT_OWNER NONFINITE OBSERVATION_BOUND OBSERVATION_FIELDS
ORIGINAL_BUDGET ORIGINAL_CLAIM ORIGINAL_COMMANDS PRIVATE_DIRECTORY PROCESS_FIELDS
READINESS_CHANGED RECORD_BOUND RECORD_TYPE REQUEST_BOUND REQUEST_SCOPE RESOURCE_ID
RESPONSE_BOUND RETAINED_VOLUME ROOT_ACCOUNT ROOT_ANCESTRY ROOT_CYCLE ROOT_DIRECTORY
ROOT_MOUNT SIGNATURES SOURCE SSH_KEY STARTUP_CLAIM STARTUP_RECEIPT TARGET_NOT_EMPTY
TARGET_TYPE WHOLE_DEVICE WRITE_SCOPE HISTORY_ACCOUNT HISTORY_ACTION HISTORY_ANCESTOR
HISTORY_ARGUMENTS HISTORY_BOOT HISTORY_CLAIM_CHANGED HISTORY_ENVELOPE
HISTORY_MOUNT_CHANGED HISTORY_PARENT_CHANGED HISTORY_VOLUME IO_FAILED REJECTED
'''.split())
READ_TIMEOUT_CODES=frozenset(('V52_VOLUME_CLOCK_EXPIRED','V52_VOLUME_EXCHANGE_DEADLINE'))


def rejection(error,action,envelope):
    code='V52_VOLUME_REJECTED'
    if type(error) is ValueError and str(error) in FAILURE_CODES:code=str(error)
    elif isinstance(error,(TimeoutError,subprocess.TimeoutExpired)):code='V52_VOLUME_EXCHANGE_DEADLINE'
    elif isinstance(error,OSError):code='V52_VOLUME_IO_FAILED'
    return dict(schema=FAILURE_SCHEMA,code=code,action=action if action in ('clock','prepare','query','check') else None,
                envelopeSha256=digest(envelope) if envelope is not None else None)


LSBLK=['lsblk','--json','--bytes','--paths','--list','--all','--output',
       'NAME,TYPE,SIZE,RO,MAJ:MIN,PKNAME,MOUNTPOINTS,FSTYPE,LABEL,UUID']
FINDMNT=['findmnt','--json','--list','--output','SOURCE,TARGET,FSTYPE,OPTIONS,MAJ:MIN']


def need(value,message):
    if not value:raise ValueError('V52_VOLUME_'+message)


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(encoded(value)).hexdigest()


def decode(raw):
    need(type(raw) is bytes and len(raw)<=MAX_BYTES,'RESPONSE_BOUND')
    def pairs(rows):
        value=dict(rows);need(len(value)==len(rows),'DUPLICATE_FIELD');return value
    def constant(_):raise ValueError('V52_VOLUME_NONFINITE')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)


def hex_value(value,n=64):need(type(value) is str and re.fullmatch('[0-9a-f]{%d}'%n,value),'DIGEST')
def integer(value,low,high):need(type(value) is int and low<=value<=high,'INTEGER')
def device(value):
    need(type(value) is str and re.fullmatch(r'/dev/(sd[a-z]+|nvme[0-9]+n[0-9]+)',value),'WHOLE_DEVICE');return value


def validate(value):
    fields={'schema','source','requestSha256','resourceClaimSha256','resourceIdentitySha256','attempt','node',
            'instanceId','diskId','bootDiskId','sizeGiB','bootSizeGiB','guest','publicKey'}
    need(type(value) is dict and set(value)==fields and value['schema']==SCHEMA,'REQUEST_SCOPE')
    for name in ('requestSha256','resourceClaimSha256','resourceIdentitySha256'):hex_value(value[name])
    hex_value(value['attempt'],32)
    source=value['source'];need(type(source) is dict and set(source)=={'source','checkoutSha256'},'SOURCE')
    hex_value(source['source'],40);hex_value(source['checkoutSha256'])
    integer(value['node'],1,3)
    for name in ('sizeGiB','bootSizeGiB'):integer(value[name],1,4096)
    for name in ('instanceId','diskId','bootDiskId'):
        need(type(value[name]) is str and re.fullmatch('[1-9][0-9]{0,19}',value[name]),'RESOURCE_ID')
    need(value['diskId']!=value['bootDiskId'],'BOOT_DISK')
    observed=guest.validate(value['guest'])
    need(observed['instanceId']==value['instanceId'] and observed['user']=='gse-'+value['attempt'][:24],'GUEST_BINDING')
    need(type(value['publicKey']) is str and re.fullmatch('ssh-ed25519 [A-Za-z0-9+/]+={0,2}',value['publicKey']),'SSH_KEY')
    need(len(encoded(value))<=16384,'REQUEST_BOUND');return value


def directory(path,private=False):
    path=Path(path)
    for entry in (path,*path.parents):
        info=entry.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid() and info.st_mode&0o022==0,'ROOT_DIRECTORY')
    if private:need(stat.S_IMODE(path.stat().st_mode)==0o700,'PRIVATE_DIRECTORY')
    return path


def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)


def write(path,value):
    raw=encoded(value)+b'\n';need(len(raw)<=MAX_BYTES,'RECORD_BOUND');path=Path(path)
    temporary=path.with_name(path.name+'.writing')
    with os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as out:
        out.write(raw);out.flush();os.fsync(out.fileno())
    os.link(temporary,path,follow_symlinks=False);sync(path.parent);temporary.unlink();sync(path.parent)


def read(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_mode&0o077==0,'RECORD_TYPE')
        return decode(stream.read(MAX_BYTES+1))


def account(value,deadline):
    need(time.monotonic()<deadline,'EXCHANGE_DEADLINE')
    need((os.getuid(),os.geteuid(),os.getgid(),os.getegid())==(0,0,0,0),'ROOT_ACCOUNT')
    expected=value['guest'];user=pwd.getpwnam(expected['user'])
    need((user.pw_uid,user.pw_gid)==(expected['uid'],expected['gid']) and
         (os.environ.get('SUDO_USER'),os.environ.get('SUDO_UID'),os.environ.get('SUDO_GID'))==
         (user.pw_name,str(user.pw_uid),str(user.pw_gid)),'INVOKING_ACCOUNT')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==expected['bootId'],'GUEST_BOOT')
    actual=guest.metadata()
    need(actual==dict(instanceId=value['instanceId'],privateAddress=expected['privateAddress'],
        sshKeys=user.pw_name+':'+value['publicKey'],blockProjectSshKeys='TRUE',enableOslogin='FALSE'),'METADATA_IDENTITY')
    need(time.monotonic()<deadline,'EXCHANGE_DEADLINE')


def target():
    path=Path(MOUNT);directory(path.parent)
    if not path.exists() and not path.is_symlink():
        return dict(exists=False,directory=False,symlink=False,empty=True,uid=None,gid=None,mode=None)
    info=path.lstat();isdir=stat.S_ISDIR(info.st_mode)
    return dict(exists=True,directory=isdir,symlink=stat.S_ISLNK(info.st_mode),empty=isdir and next(path.iterdir(),None) is None,
                uid=info.st_uid,gid=info.st_gid,mode=stat.S_IMODE(info.st_mode))


def aliases(value):return ['/dev/disk/by-id/google-gse-'+kind+'-'+str(value['node']) for kind in ('data','boot')]


class Linux:
    clock=staticmethod(time.monotonic)
    def __init__(self,value):self.value=validate(value);self.allowed=None;self.mapping=None
    def target(self):return target()
    def run(self,argv,deadline):
        names=aliases(self.value)
        reads=(argv==LSBLK or argv==FINDMNT or len(argv)==3 and argv[:2]==['readlink','-e'] and argv[2] in names or
            len(argv)==6 and argv[:5]==['wipefs','--no-act','--json','--output','TYPE,OFFSET'] and device(argv[5]))
        if not reads:
            need(self.allowed is not None and argv in self.allowed,'WRITE_SCOPE')
            account(self.value,deadline)
            need([self.run(['readlink','-e',name],deadline).decode().strip() for name in names]==self.mapping,'DEVICE_CHANGED')
        need(time.monotonic()<deadline,'EXCHANGE_DEADLINE')
        # Stream bounds prevent a misbehaving helper from filling memory. The
        # controller sends only this fixed source; no installed code is imported.
        import selectors
        proc=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            start_new_session=True,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C','LC_ALL':'C'})
        out=bytearray();err=bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                for stream in (proc.stdout,proc.stderr):os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ)
                while selector.get_map():
                    need(time.monotonic()<deadline,'EXCHANGE_DEADLINE')
                    for key,_ in selector.select(min(.2,deadline-time.monotonic())):
                        chunk=os.read(key.fd,65536)
                        if not chunk:selector.unregister(key.fileobj);continue
                        result=out if key.fileobj is proc.stdout else err;result.extend(chunk)
                        need(len(result)<=65536,'COMMAND_OUTPUT_BOUND')
            proc.wait(timeout=max(.001,deadline-time.monotonic()))
            need(proc.returncode==0,'COMMAND_FAILED')
            need(time.monotonic()<deadline,'EXCHANGE_DEADLINE');return bytes(out)
        finally:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait(timeout=5);proc.stdout.close();proc.stderr.close()


def observe(backend,value,deadline):
    def run(argv):
        need(backend.clock()<deadline,'EXCHANGE_DEADLINE');raw=backend.run(argv,deadline)
        need(type(raw) is bytes and len(raw)<=65536 and backend.clock()<deadline,'OBSERVATION_BOUND');return raw
    data,boot=aliases(value);mapping=[device(run(['readlink','-e',name]).decode().strip()) for name in (data,boot)]
    result=dict(device=data,resolved=mapping[0],bootDevice=mapping[1],lsblk=decode(run(LSBLK)),
        findmnt=decode(run(FINDMNT)),wipefs=decode(run(['wipefs','--no-act','--json','--output','TYPE,OFFSET',mapping[0]])),target=backend.target())
    need([run(['readlink','-e',name]).decode().strip() for name in (data,boot)]==mapping,'DEVICE_CHANGED')
    return result


def topology(raw,value):
    need(type(raw) is dict and set(raw)=={'device','resolved','bootDevice','lsblk','findmnt','wipefs','target'},'OBSERVATION_FIELDS')
    need(raw['device']==aliases(value)[0],'DEVICE_ALIAS');data,boot=device(raw['resolved']),device(raw['bootDevice'])
    need(data!=boot,'BOOT_DISK');rows=raw['lsblk']['blockdevices']
    need(type(rows) is list and 2<=len(rows)<=128,'BLOCK_COUNT')
    need(all(type(v) is dict and set(v)=={'name','type','size','ro','maj:min','pkname','mountpoints','fstype','label','uuid'} for v in rows),'BLOCK_FIELDS')
    need(len({v['name'] for v in rows})==len({v['maj:min'] for v in rows})==len(rows),'BLOCK_IDENTITIES')
    by_name={v['name']:v for v in rows}
    need(data in by_name and boot in by_name,'BLOCK_MISSING')
    for row in rows:need(re.fullmatch('[0-9]+:[0-9]+',row['maj:min']) and type(row['mountpoints']) is list,'BLOCK_TOPOLOGY')
    disk=by_name[data];original=by_name[boot]
    need(disk['type']=='disk' and disk['pkname'] is None and disk['ro'] is False and
         type(disk['size']) is int and disk['size']==value['sizeGiB']*(1<<30) and not any(v['pkname']==data for v in rows),'DATA_DISK')
    need(original['type']=='disk' and original['pkname'] is None and type(original['size']) is int and
         original['size']==value['bootSizeGiB']*(1<<30),'BOOT_LAYOUT')
    mounts=raw['findmnt']['filesystems'];need(type(mounts) is list and 1<=len(mounts)<=512,'MOUNT_COUNT')
    need(all(type(v) is dict and set(v)=={'source','target','fstype','options','maj:min'} and
             all(type(x) is str for x in v.values()) for v in mounts),'MOUNT_FIELDS')
    roots=[v for v in mounts if v['target']=='/'];need(len(roots)==1,'ROOT_MOUNT')
    root=next((v for v in rows if v['maj:min']==roots[0]['maj:min']),None);seen=set()
    while root is not None and root['pkname'] is not None:
        need(root['name'] not in seen,'ROOT_CYCLE');seen.add(root['name']);root=by_name.get(root['pkname'])
    need(root is original,'ROOT_ANCESTRY')
    own=raw['target'];need(type(own) is dict and set(own)=={'exists','directory','symlink','empty','uid','gid','mode'} and
        all(type(own[k]) is bool for k in ('exists','directory','symlink','empty')) and
        not own['symlink'] and (not own['exists'] or own['directory']),'TARGET_TYPE')
    if own['exists']:
        for name in ('uid','gid'):integer(own[name],0,(1<<32)-1)
        integer(own['mode'],0,0o7777)
    else:need(not own['directory'] and own['empty'] and all(own[k] is None for k in ('uid','gid','mode')),'ABSENT_TARGET')
    return disk,mounts


def blank(raw,value):
    disk,mounts=topology(raw,value);own=raw['target']
    need(own['empty'] and (not own['exists'] or own['uid']==0 and type(own['mode']) is int and own['mode']&0o022==0),'TARGET_NOT_EMPTY')
    need(not any(v['target']==MOUNT or v['target'].startswith(MOUNT+'/') or v['maj:min']==disk['maj:min'] for v in mounts) and
         not any(disk['mountpoints']),'ALREADY_MOUNTED')
    need(not disk['fstype'] and not disk['label'] and not disk['uuid'] and raw['wipefs']=={'signatures':[]},'EXISTING_FILESYSTEM')
    return disk


def commands(raw,value):
    blank(raw,value);uid,gid=value['guest']['uid'],value['guest']['gid']
    return ([] if raw['target']['exists'] else [['mkdir','-m','0755',MOUNT]])+[
        ['mkfs.ext4','-L','gse-'+value['attempt'][:12],raw['resolved']],
        ['mount','-t','ext4','-o','nodev,nosuid',raw['resolved'],MOUNT],
        ['chown',str(uid)+':'+str(gid),MOUNT],['chmod','0700',MOUNT]]


def mounted(raw,before,value):
    disk,mounts=topology(raw,value);previous,_=topology(before,value)
    need(raw['resolved']==before['resolved'] and raw['bootDevice']==before['bootDevice'] and
         disk['maj:min']==previous['maj:min'],'MOUNT_IDENTITY')
    own=[v for v in mounts if v['maj:min']==disk['maj:min'] or v['target']==MOUNT or v['target'].startswith(MOUNT+'/')]
    need(len(own)==1 and own[0]['target']==MOUNT and own[0]['maj:min']==disk['maj:min'] and own[0]['fstype']=='ext4' and
         {'rw','nodev','nosuid'}<=set(own[0]['options'].split(',')) and 'ro' not in own[0]['options'].split(','),'MOUNT_OPTIONS')
    need(disk['mountpoints']==[MOUNT] and disk['fstype']=='ext4' and disk['label']=='gse-'+value['attempt'][:12] and
         type(disk['uuid']) is str and str(uuid.UUID(disk['uuid']))==disk['uuid'] and uuid.UUID(disk['uuid']).int!=0,'FILESYSTEM')
    signatures=raw['wipefs']['signatures'];need(type(signatures) is list and len(signatures)==1 and signatures[0]['type']=='ext4','SIGNATURES')
    own=raw['target'];need(own['exists'] and own['directory'] and (own['uid'],own['gid'],own['mode'])==
        (value['guest']['uid'],value['guest']['gid'],0o700),'MOUNT_OWNER')
    return dict(device=raw['resolved'],majorMinor=disk['maj:min'],uuid=disk['uuid'],mount=MOUNT,
                uid=own['uid'],gid=own['gid'])


def replay(startup,value):
    validate(value)
    need(type(startup) is dict and set(startup)=={'schema','requestSha256','budgetSha256','status','before','second','after','commands','volume','failureCode'} and
         startup['schema']==RECEIPT and startup['requestSha256']==digest(value) and startup['status']=='PASS' and startup['failureCode'] is None,'STARTUP_RECEIPT')
    hex_value(startup['budgetSha256']);blank(startup['before'],value)
    need(startup['second']==startup['before'] and startup['commands']==commands(startup['before'],value),'ORIGINAL_COMMANDS')
    need(mounted(startup['after'],startup['before'],value)==startup['volume'],'RETAINED_VOLUME');return startup['volume']


def sample(value,nonce):
    hex_value(nonce,32)
    return dict(schema='gse-v52-volume-clock-v1',requestSha256=digest(value),bootId=value['guest']['bootId'],
                nonce=nonce,sampledNanos=time.monotonic_ns())


def budget(value,token):
    need(type(token) is dict and set(token)=={'sample','expiresNanos'},'BUDGET_FIELDS');row=token['sample']
    need(type(row) is dict and set(row)=={'schema','requestSha256','bootId','nonce','sampledNanos'} and
         row['schema']=='gse-v52-volume-clock-v1' and row['requestSha256']==digest(value) and
         row['bootId']==value['guest']['bootId'],'CLOCK_BINDING');hex_value(row['nonce'],32)
    integer(row['sampledNanos'],1,(1<<63)-1);integer(token['expiresNanos'],row['sampledNanos']+1,row['sampledNanos']+MAX_SECONDS*10**9)
    need(row['sampledNanos']<=time.monotonic_ns()<token['expiresNanos'],'CLOCK_EXPIRED');return token['expiresNanos']/10**9


def process():
    return dict(pid=os.getpid(),startTicks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]))


def alive(value):
    need(type(value) is dict and set(value)=={'pid','startTicks'},'PROCESS_FIELDS')
    integer(value['pid'],1,(1<<31)-1);integer(value['startTicks'],1,(1<<63)-1)
    try:raw=Path('/proc/'+str(value['pid'])+'/stat').read_text()
    except (FileNotFoundError,ProcessLookupError):return False
    fields=raw.rsplit(')',1)[1].split();return fields[0] not in ('Z','X') and int(fields[19])==value['startTicks']


def _perform(action,value,token,backend):
    validate(value);need(action in ('clock','prepare','query','check'),'ACTION')
    if action=='clock':account(value,time.monotonic()+30);return sample(value,token)
    deadline=budget(value,token);account(value,deadline)
    parent=Path(PARENT);directory(parent.parent)
    if action=='prepare':
        try:parent.mkdir(mode=0o700);sync(parent.parent)
        except FileExistsError:pass
    answer=dict(schema='gse-v52-volume-answer-v1',requestSha256=digest(value),budgetSha256=digest(token),
                action=action,state='NOT_FOUND',startup=None,readiness=None,process=None)
    if not parent.exists() and not parent.is_symlink():return answer
    directory(parent,True);folder=parent/(value['requestSha256']+'-node-'+str(value['node']))
    if action=='prepare':
        try:folder.mkdir(mode=0o700)
        except FileExistsError:pass
        else:
            sync(parent);write(folder/'claim.json',dict(request=value,budget=token));write(folder/'process.json',process())
            result=dict(schema=RECEIPT,requestSha256=digest(value),budgetSha256=digest(token),status='FAIL',
                before=None,second=None,after=None,commands=[],volume=None,failureCode=None)
            try:
                result['before']=observe(backend,value,deadline);blank(result['before'],value)
                account(value,deadline);result['second']=observe(backend,value,deadline)
                need(result['second']==result['before'],'BEFORE_WRITE_DRIFT')
                plan=commands(result['before'],value);backend.allowed=plan;backend.mapping=[result['before']['resolved'],result['before']['bootDevice']]
                for index,argv in enumerate(plan):
                    need(backend.clock()<deadline,'EXCHANGE_DEADLINE');write(folder/('intent-'+str(index)+'.json'),dict(argv=argv))
                    backend.run(argv,deadline);need(backend.clock()<deadline,'EXCHANGE_DEADLINE');result['commands'].append(argv)
                result['after']=observe(backend,value,deadline);result['volume']=mounted(result['after'],result['before'],value)
                account(value,deadline);result['status']='PASS'
            except BaseException:
                result['failureCode']='V52_VOLUME_INITIALIZATION_FAILED'
            finally:write(folder/'startup.json',result)
    if not folder.exists() and not folder.is_symlink():return answer
    directory(folder,True);answer['state']='UNCERTAIN'
    try:claim=read(folder/'claim.json')
    except FileNotFoundError:return answer
    need(type(claim) is dict and set(claim)=={'request','budget'} and claim['request']==value,'ORIGINAL_CLAIM')
    if action in ('prepare','query'):need(claim['budget']==token,'ORIGINAL_BUDGET')
    try:startup=read(folder/'startup.json')
    except FileNotFoundError:
        try:original=read(folder/'process.json')
        except FileNotFoundError:return answer
        if alive(original):answer.update(state='RUNNING',process=original)
        return answer
    need(startup['budgetSha256']==digest(claim['budget']) and startup['requestSha256']==digest(value),'STARTUP_CLAIM')
    answer.update(state='FAILED',startup=startup)
    if startup['status']!='PASS':return answer
    replay(startup,value);answer['state']='SUCCEEDED'
    if action=='check':
        observation=observe(backend,value,deadline);now=mounted(observation,startup['before'],value)
        need(now==startup['volume'],'READINESS_CHANGED')
        answer['readiness']=dict(startupSha256=digest(startup),volume=now,observation=observation)
    need(backend.clock()<deadline,'EXCHANGE_DEADLINE');return answer


def main():
    value=None;action=sys.argv[1] if len(sys.argv)==2 else None
    try:
        need(len(sys.argv)==2,'ARGUMENTS');raw=sys.stdin.buffer.read(20001);need(len(raw)<=20000,'REQUEST_BOUND')
        value=decode(raw);need(type(value) is dict and set(value)=={'request','token'},'ENVELOPE')
        req=validate(value['request']);action=sys.argv[1];token=value['token']
        end=time.monotonic()+30 if action=='clock' else budget(req,token)
        def expired(*_):raise TimeoutError('V52_VOLUME_EXCHANGE_DEADLINE')
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,end-time.monotonic()))
        try:result=_perform(action,req,token,Linux(req))
        finally:signal.setitimer(signal.ITIMER_REAL,0)
        output=encoded(result)+b'\n';need(len(output)<=MAX_BYTES,'RESPONSE_BOUND');sys.stdout.buffer.write(output);return 0
    except BaseException as error:
        sys.stdout.buffer.write(encoded(rejection(error,action,value))+b'\n')
        print('V52_VOLUME_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
