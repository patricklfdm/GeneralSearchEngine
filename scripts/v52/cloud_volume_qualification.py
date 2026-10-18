"""Real namespace-root file/account qualification; block devices remain modeled."""
import argparse
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
from . import cloud_storage as storage,cloud_volume_guest as volume
from . import test_cloud_volume as fixture
from scripts.v51 import guest_root_isolation


def run(output,allow_sudo=False):
    root=Path(output).absolute();root.mkdir(parents=True,exist_ok=False)
    prefix=['unshare','--user','--map-root-user','--mount','--propagation','private']
    probe=subprocess.run([*prefix,'true'],capture_output=True,timeout=10);sudo=probe.returncode!=0
    volume.need(not sudo or allow_sudo,'ISOLATION_UNAVAILABLE')
    if sudo:
        prefix=['sudo','-n','unshare','--mount','--propagation','private']
        subprocess.run([*prefix,'true'],check=True,timeout=10,capture_output=True)
    parent_ns=os.readlink('/proc/self/ns/mnt');rows=[]
    value=fixture.request();value['guest']['gid']=1001
    metadata=dict(instanceId=value['instanceId'],privateAddress=value['guest']['privateAddress'],
        sshKeys=value['guest']['user']+':'+value['publicKey'],blockProjectSshKeys='TRUE',enableOslogin='FALSE')
    original=storage.trusted_source('volume')
    ending="raise SystemExit(sys.modules['trusted_v52.cloud_volume_guest'].main())\n"
    volume.need(original.endswith(ending),'ISOLATION_SOURCE')
    base=original[:-len(ending)]+"from copy import deepcopy\nimport time,os,json\nfrom pathlib import Path\nv=sys.modules['trusted_v52.cloud_volume_guest']\n"
    base+="v.guest.metadata=lambda: "+repr(metadata)+"\n"+inspect.getsource(fixture.Block)+"\nvalue="+repr(value)+"\nblock=Block(value)\n"
    operations="""
case,phase=sys.argv[1:]
folder=Path(v.PARENT)/(value['requestSha256']+'-node-1')
if phase=='query-killed':token=v.read(folder/'claim.json')['budget']
else:
 sample=v.sample(value,'a'*32);token=dict(sample=sample,expiresNanos=sample['sampledNanos']+240*10**9)
expected=None
if case=='metadata-drift':v.guest.metadata=lambda:dict(instanceId='0') ;expected='V52_VOLUME_METADATA_IDENTITY'
if case=='writable-parent':Path('/var/lib').chmod(0o777);expected='V52_VOLUME_ROOT_DIRECTORY'
if case=='symlink-parent':Path(v.PARENT).symlink_to('/var');expected='V52_VOLUME_ROOT_DIRECTORY'
if case=='lost-format':block.fault='lost-format'
if case=='expired-budget':token['expiresNanos']=token['sample']['sampledNanos'];expected='V52_VOLUME_INTEGER'
if case=='killed-claim' and phase=='first':v.observe=lambda *args:os.kill(os.getpid(),9)
try:
 answer=v._perform('prepare',value,token,block)
 if expected:raise AssertionError('expected receiver rejection')
 if case=='killed-claim':
  assert phase=='query-killed' and answer['state']=='UNCERTAIN' and not block.commands
  assert v._perform('query',value,token,block)['state']=='UNCERTAIN'
 elif case=='lost-format':
  assert answer['state']=='FAILED' and block.formats==1
  assert v._perform('prepare',value,token,block)==answer and block.formats==1
 else:
  assert answer['state']=='SUCCEEDED' and block.formats==1
  assert v._perform('check',value,token,block)['startup']==answer['startup']
  if case=='changed-claim':
   changed=deepcopy(value);changed['source']['source']='0'*40
   replacement=v.sample(changed,'b'*32)
   changed_token=dict(sample=replacement,expiresNanos=replacement['sampledNanos']+240*10**9)
   try:v._perform('prepare',changed,changed_token,block)
   except ValueError as error:assert str(error)=='V52_VOLUME_ORIGINAL_CLAIM'
   else:raise AssertionError('changed claim accepted')
   assert block.formats==1
except ValueError as error:
 assert expected==str(error),(expected,str(error))
 assert not folder.exists() and block.formats==0
print(json.dumps(dict(case=case,status='PASS',effectiveUid=os.geteuid(),modelFormats=block.formats,realBlockDeviceWritten=False)))
"""
    for case in ('success','lost-format','metadata-drift','writable-parent','symlink-parent','changed-claim','expired-budget','killed-claim'):
        base_dir=root/case;base_dir.mkdir(mode=0o700);fs=base_dir/'rootfs';fs.mkdir(mode=0o700)
        for name in ('var','var/lib','usr','lib','lib64','proc','dev','etc'):(fs/name).mkdir(mode=0o755)
        (fs/'dev/null').touch(mode=0o600);(fs/'account').write_text(value['guest']['user'])
        (fs/'etc/passwd').write_text('root:x:0:0:root:/root:/bin/sh\n'+value['guest']['user']+':x:1001:1001:fixture:/nonexistent:/bin/false\n')
        (fs/'etc/group').write_text('root:x:0:\nfixture:x:1001:\n')
        source=base+operations
        def execute(phase):
            args=[*prefix,sys.executable,str(Path(guest_root_isolation.__file__).resolve()),str(fs),parent_ns,
                str(os.getuid()) if sudo else '0',str(os.getgid()) if sudo else '0',
                '/usr/bin/python3','-I','-S','-c',source,case,phase]
            result=subprocess.run(args,capture_output=True,timeout=60)
            (base_dir/(phase+'.stdout')).write_bytes(result.stdout);(base_dir/(phase+'.stderr')).write_bytes(result.stderr)
            return result
        first=execute('first')
        if case=='killed-claim':
            volume.need(first.returncode!=0 and (fs/str(volume.PARENT).lstrip('/')/(value['requestSha256']+'-node-1')/'claim.json').is_file(),'KILL_NOT_OBSERVED')
            first=execute('query-killed')
        volume.need(first.returncode==0,'ROOT_QUALIFICATION_FAILED_'+case)
        row=json.loads(first.stdout);volume.need(row['status']=='PASS' and row['effectiveUid']==0,'ROOT_QUALIFICATION_RESULT')
        rows.append(row);print(json.dumps(row),flush=True)
    result=dict(status='PASS',execution='isolated-root-files-and-modeled-blocks',source=storage.inputs.build.git(storage.ROOT,'rev-parse','HEAD').decode().strip(),
        receiverSha256=storage.digest(original.encode()),modelSha256=storage.digest(inspect.getsource(fixture.Block).encode()),
        cases=rows,namespaceSudo=sudo,paidCloud=False,realBlockDeviceWritten=False,fullRemoteQualification=False)
    (root/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output');parser.add_argument('--allow-sudo-namespace',action='store_true');a=parser.parse_args()
    run(a.output,a.allow_sudo_namespace)
