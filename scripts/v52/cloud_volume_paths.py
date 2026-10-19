"""Fixed unprivileged per-history directories on a separately verified mount."""
import os
from pathlib import Path
import stat
import sys
from . import cloud_volume_guest as v


def context(value,volume):
    v.validate(value);expected=value['guest']
    v.need((os.getuid(),os.geteuid(),os.getgid(),os.getegid())==(expected['uid'],expected['uid'],expected['gid'],expected['gid']),'HISTORY_ACCOUNT')
    v.need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==expected['bootId'],'HISTORY_BOOT')
    v.need(type(volume) is dict and set(volume)=={'device','majorMinor','uuid','mount','uid','gid'} and
           volume['mount']==v.MOUNT and (volume['uid'],volume['gid'])==(expected['uid'],expected['gid']),'HISTORY_VOLUME')
    path=Path(v.MOUNT)
    for entry in (path,*path.parents):
        info=entry.lstat()
        v.need(stat.S_ISDIR(info.st_mode) and info.st_uid in (0,expected['uid']) and info.st_mode&0o022==0,'HISTORY_ANCESTOR')
    info=path.stat()
    v.need(info.st_uid==expected['uid'] and info.st_gid==expected['gid'] and stat.S_IMODE(info.st_mode)==0o700 and
           str(os.major(info.st_dev))+':'+str(os.minor(info.st_dev))==volume['majorMinor'],'HISTORY_MOUNT_CHANGED')
    return path


def perform(action,value,volume,history):
    v.need(action in ('prepare','query'),'HISTORY_ACTION');v.hex_value(history)
    mount=context(value,volume);parent=mount/('history-'+history)
    claim=dict(requestSha256=v.digest(value),historySha256=history,volume=volume)
    answer=dict(schema='gse-v52-history-parent-v1',claimSha256=v.digest(claim),state='NOT_FOUND',root=None,host=None)
    if action=='prepare':
        try:parent.mkdir(mode=0o700)
        except FileExistsError:pass
        else:v.sync(mount);v.write(parent/'claim.json',claim)
    if not parent.exists() and not parent.is_symlink():return answer
    info=parent.lstat()
    v.need(stat.S_ISDIR(info.st_mode) and (info.st_uid,info.st_gid)==(value['guest']['uid'],value['guest']['gid']) and
           stat.S_IMODE(info.st_mode)==0o700 and info.st_dev==mount.stat().st_dev,'HISTORY_PARENT_CHANGED')
    try:original=v.read(parent/'claim.json')
    except FileNotFoundError:return dict(answer,state='UNCERTAIN')
    v.need(original==claim,'HISTORY_CLAIM_CHANGED');context(value,volume)
    return dict(answer,state='SUCCEEDED',root=str(parent/('node-'+str(value['node']))),
        host=dict(bootId=value['guest']['bootId'],uid=info.st_uid,parentDevice=info.st_dev,parentInode=info.st_ino))


def main():
    try:
        v.need(len(sys.argv)==2,'HISTORY_ARGUMENTS');raw=sys.stdin.buffer.read(20001);v.need(len(raw)<=20000,'REQUEST_BOUND')
        value=v.decode(raw);v.need(type(value) is dict and set(value)=={'request','volume','history'},'HISTORY_ENVELOPE')
        answer=perform(sys.argv[1],value['request'],value['volume'],value['history'])
        sys.stdout.buffer.write(v.encoded(answer)+b'\n');return 0
    except BaseException:print('V52_HISTORY_PARENT_REJECTED',file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
