"""Independent device model; no host block device or provider is opened."""
from copy import deepcopy
from contextlib import ExitStack
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import cloud_volume_guest as v,cloud_volume_paths as paths,cloud_storage as storage
from .test_cloud_identity import public_key


def request():
    return dict(schema=v.SCHEMA,source=dict(source='a'*40,checkoutSha256='b'*64),requestSha256='c'*64,
        resourceClaimSha256='d'*64,resourceIdentitySha256='e'*64,attempt='f'*32,node=1,
        instanceId='123',diskId='456',bootDiskId='789',sizeGiB=100,bootSizeGiB=30,
        guest=dict(schema=v.guest.SCHEMA,instanceId='123',privateAddress='10.0.0.1',user='gse-'+'f'*24,
            bootId=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),uid=1001,gid=1002),publicKey=public_key())


class Block:
    """Separate state machine produces Linux-shaped reads from modeled writes."""
    clock=staticmethod(time.monotonic)
    def __init__(self,value,fault=None):
        self.value=deepcopy(value);self.fault=fault;self.commands=[];self.formats=0;self.alias_reads=0
        self.exists=self.formatted=self.attached=False;self.uid=self.gid=0;self.mode=0o755
        self.uuid='12345678-1234-1234-1234-123456789abc';self.resolved='/dev/sdb'
    def target(self):return dict(exists=self.exists,directory=self.exists,symlink=False,empty=not self.formatted,
        uid=self.uid if self.exists else None,gid=self.gid if self.exists else None,mode=self.mode if self.exists else None)
    def blocks(self):
        def row(name,kind,size,mm,parent=None,mount=None):
            return dict(name=name,type=kind,size=size,ro=False,**{'maj:min':mm},pkname=parent,mountpoints=[mount],fstype=None,label=None,uuid=None)
        boot=row('/dev/sda','disk',self.value['bootSizeGiB']<<30,'8:0')
        root=row('/dev/sda1','part',(self.value['bootSizeGiB']<<30)-4096,'8:1','/dev/sda','/')
        data=row('/dev/sdb','disk',self.value['sizeGiB']<<30,'8:16',mount=v.MOUNT if self.attached else None)
        if self.formatted:data.update(fstype='ext4',label='gse-'+self.value['attempt'][:12],uuid=self.uuid)
        return dict(blockdevices=[boot,root,data])
    def mounts(self):
        rows=[dict(source='/dev/sda1',target='/',fstype='ext4',options='rw,relatime',**{'maj:min':'8:1'})]
        if self.attached:rows.append(dict(source='/dev/sdb',target=v.MOUNT,fstype='ext4',options='rw,nodev,nosuid',**{'maj:min':'8:16'}))
        if self.fault=='wrong-mount' and self.attached:rows[-1]['maj:min']='8:0'
        return dict(filesystems=rows)
    def run(self,argv,deadline):
        if self.clock()>=deadline:raise TimeoutError('model original deadline')
        self.commands.append(deepcopy(argv))
        if argv[:2]==['readlink','-e']:
            if 'data-' in argv[-1]:
                self.alias_reads+=1
                if self.fault=='alias-drift' and self.alias_reads>1:return b'/dev/sdc'
                return self.resolved.encode()
            return b'/dev/sda'
        if argv==v.LSBLK:return v.encoded(self.blocks())
        if argv==v.FINDMNT:return v.encoded(self.mounts())
        if argv[:2]==['wipefs','--no-act']:
            return v.encoded(dict(signatures=[dict(type='ext4',offset='0x438')] if self.formatted or self.fault=='used' else []))
        if argv==['mkdir','-m','0755','/mnt/gse-v52']:self.exists=True
        elif argv==['mkfs.ext4','-L','gse-'+self.value['attempt'][:12],'/dev/sdb']:
            if self.formatted:raise AssertionError('model refuses repeated format')
            self.formatted=True;self.formats+=1
            if self.fault=='lost-format':raise ConnectionError('lost original format reply')
        elif argv==['mount','-t','ext4','-o','nodev,nosuid','/dev/sdb','/mnt/gse-v52']:
            if not self.formatted or not self.exists or self.attached:raise AssertionError('invalid model mount')
            self.attached=True
            if self.fault=='lost-mount':raise ConnectionError('lost original mount reply')
        elif argv==['chown',str(self.value['guest']['uid'])+':'+str(self.value['guest']['gid']),'/mnt/gse-v52']:
            self.uid,self.gid=self.value['guest']['uid'],self.value['guest']['gid']
        elif argv==['chmod','0700','/mnt/gse-v52']:self.mode=0o700
        else:raise AssertionError('undeclared model write '+str(argv))
        return b''


class VolumeTest(unittest.TestCase):
    def setUp(self):
        private=tempfile.TemporaryDirectory();self.addCleanup(private.cleanup);self.root=Path(private.name)
        self.value=request();self.block=Block(self.value);self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(v,'PARENT',str(self.root/'root-claims')))
        self.context=self.stack.enter_context(patch.object(v,'account'))
        # Only root ancestor/account observation is modeled here. Real immutable
        # files, exclusive claims, fsync and original-result parsing still run.
        def private_dir(path,private=False):
            path=Path(path);self.assertFalse(path.is_symlink());self.assertTrue(path.is_dir())
            if private:self.assertEqual(0o700,stat.S_IMODE(path.stat().st_mode))
            return path
        self.stack.enter_context(patch.object(v,'directory',side_effect=private_dir))
        self.token=self.grant()
    def grant(self):
        row=v.sample(self.value,'a'*32);return dict(sample=row,expiresNanos=row['sampledNanos']+240*10**9)
    def call(self,action,token=None):return v._perform(action,self.value,self.token if token is None else token,self.block)
    def raw(self):return v.observe(self.block,self.value,time.monotonic()+240)
    def folder(self):return Path(v.PARENT)/(self.value['requestSha256']+'-node-1')

    def test_original_blank_device_and_independent_retained_and_current_replay(self):
        original=self.call('prepare');self.assertEqual('SUCCEEDED',original['state']);self.assertEqual(1,self.block.formats)
        self.assertEqual(original['startup']['volume'],v.replay(original['startup'],self.value))
        checked=self.call('check',self.grant());self.assertEqual(original['startup'],checked['startup'])
        self.assertEqual(checked['readiness']['volume'],original['startup']['volume'])
        self.assertEqual(self.call('query')['startup'],original['startup'])
        before=len(self.block.commands);self.call('prepare');self.assertEqual(before,len(self.block.commands))
        self.assertTrue((self.folder()/'intent-1.json').exists());self.assertNotIn('-F',str(self.block.commands))

    def test_sizes_come_from_request_and_accept_configured_layout_not_v51_constant(self):
        for size in (1,101,4096):
            with self.subTest(size=size):
                self.value['sizeGiB']=size;self.block=Block(self.value)
                self.assertEqual(size<<30,v.blank(self.raw(),self.value)['size'])
                wrong=self.raw();wrong['lsblk']['blockdevices'][-1]['size']+=1
                with self.assertRaisesRegex(ValueError,'DATA_DISK'):v.blank(wrong,self.value)

    def test_closed_request_and_wrong_identity_reject_before_claim(self):
        cases=[dict(extra=True),dict(schema='gse-v51-native-volume-request-v2'),dict(node=True),dict(sizeGiB=0),
            dict(bootDiskId='456'),dict(instanceId='001'),dict(publicKey='ssh-rsa AAA'),dict(attempt='a'*32)]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(ValueError):v._perform('prepare',dict(self.value,**change),self.token,self.block)
        self.assertFalse(Path(v.PARENT).exists());self.assertEqual(0,self.block.formats)

    def test_dirty_disk_boot_disk_alias_and_mount_fail_before_writes(self):
        raw=self.raw()
        changes=[lambda r:r.update(resolved='/dev/sda'),lambda r:r['lsblk']['blockdevices'][2].update(ro=True),
            lambda r:r['lsblk']['blockdevices'][2].update(fstype='ext4'),lambda r:r['lsblk']['blockdevices'][2].update(mountpoints=['[SWAP]']),
            lambda r:r['lsblk']['blockdevices'][0].update(size=1),lambda r:r['lsblk']['blockdevices'][1].update(pkname='/dev/sdb'),
            lambda r:r['lsblk']['blockdevices'][1].update(pkname='/dev/sda1'),lambda r:r['wipefs'].update(signatures=[dict(type='gpt',offset='0')]),
            lambda r:r['target'].update(exists=True,directory=True,empty=False,uid=0,gid=0,mode=0o755),
            lambda r:r['target'].update(exists=True,directory=True,uid=0,gid=0,mode=0o777),
            lambda r:r['target'].update(symlink=True),lambda r:r['lsblk']['blockdevices'].append(deepcopy(r['lsblk']['blockdevices'][2])),
            lambda r:r['findmnt']['filesystems'].append(dict(source='/dev/sdb',target='/elsewhere',fstype='ext4',options='rw',**{'maj:min':'8:16'})),
            lambda r:r['findmnt']['filesystems'].append(dict(source='/dev/other',target=v.MOUNT+'/nested',fstype='ext4',options='rw',**{'maj:min':'9:0'}))]
        for change in changes:
            bad=deepcopy(raw);change(bad)
            with self.assertRaises(ValueError):v.blank(bad,self.value)
        self.assertEqual(0,self.block.formats)

    def test_lost_format_mount_reply_and_bad_after_observation_never_reformat(self):
        for index,fault in enumerate(('lost-format','lost-mount','wrong-mount')):
            self.value['requestSha256']=str(index)*64;self.block=Block(self.value,fault);self.token=self.grant()
            first=self.call('prepare');self.assertEqual('FAILED',first['state']);self.assertEqual(1,self.block.formats)
            count=len(self.block.commands);self.assertEqual(first,self.call('prepare'));self.assertEqual(count,len(self.block.commands))
            self.assertEqual('FAILED',self.call('query')['state'])

    def test_partial_claim_missing_executor_and_live_executor_are_not_reinitialization(self):
        parent=Path(v.PARENT);parent.mkdir(mode=0o700);folder=self.folder();folder.mkdir(mode=0o700)
        self.assertEqual('UNCERTAIN',self.call('prepare')['state']);self.assertEqual([],self.block.commands)
        v.write(folder/'claim.json',dict(request=self.value,budget=self.token))
        self.assertEqual('UNCERTAIN',self.call('query')['state'])
        v.write(folder/'process.json',v.process());self.assertEqual('RUNNING',self.call('query')['state'])
        with patch.object(v,'alive',return_value=False):self.assertEqual('UNCERTAIN',self.call('query')['state'])
        self.assertEqual(0,self.block.formats)

    def test_fresh_query_grant_cannot_rewrite_original_initialization_budget(self):
        self.call('prepare');changed=deepcopy(self.token);changed['expiresNanos']-=1
        with self.assertRaisesRegex(ValueError,'ORIGINAL_BUDGET'):self.call('prepare',changed)
        with self.assertRaisesRegex(ValueError,'ORIGINAL_BUDGET'):self.call('query',changed)
        self.assertEqual('SUCCEEDED',self.call('check',changed)['state']);self.assertEqual(1,self.block.formats)

    def test_alias_and_second_observation_drift_fail_before_format(self):
        self.block.fault='alias-drift';self.assertEqual('FAILED',self.call('prepare')['state']);self.assertEqual(0,self.block.formats)
        self.value['requestSha256']='0'*64;self.token=self.grant();self.block=Block(self.value)
        calls=0
        def mutate(*args):
            nonlocal calls
            calls+=1
            if calls==2:self.block.fault='used'
        self.context.side_effect=mutate
        self.assertEqual('FAILED',self.call('prepare')['state']);self.assertEqual(0,self.block.formats)

    def test_readiness_uuid_owner_options_and_retained_command_mutations_reject(self):
        startup=self.call('prepare')['startup'];good=deepcopy(startup)
        changes=[lambda r:r['after']['target'].update(uid=0),lambda r:r['after']['target'].update(mode=0o755),
            lambda r:r['after']['findmnt']['filesystems'][-1].update(options='rw'),lambda r:r['after']['lsblk']['blockdevices'][-1].update(uuid='0'*36),
            lambda r:r['commands'].append(['sh','-c','true']),lambda r:r['second']['target'].update(empty=False),
            lambda r:r['before']['wipefs'].update(signatures=[dict(type='ext4',offset='0')])]
        for change in changes:
            bad=deepcopy(good);change(bad)
            with self.assertRaises((ValueError,KeyError)):v.replay(bad,self.value)
        self.block.uuid='aaaaaaaa-1234-1234-1234-123456789abc'
        with self.assertRaisesRegex(ValueError,'READINESS_CHANGED'):self.call('check',self.grant())
        self.assertEqual(1,self.block.formats)

    def test_original_deadline_and_source_boot_nonce_bounds(self):
        for change in (lambda t:t.update(expiresNanos=t['sample']['sampledNanos']+301*10**9),
            lambda t:t.update(expiresNanos=1),lambda t:t['sample'].update(bootId='foreign'),
            lambda t:t['sample'].update(requestSha256='0'*64),lambda t:t['sample'].update(sampledNanos=True)):
            token=deepcopy(self.token);change(token)
            with self.assertRaises(ValueError):self.call('prepare',token)
        self.assertFalse(Path(v.PARENT).exists())

    def test_live_backend_rejects_unapproved_write_before_starting_process(self):
        with patch.object(v.subprocess,'Popen') as spawn:
            for argv in (['mkfs.ext4','-F','/dev/sda'],['mount','/dev/sda',v.MOUNT],['sh','-c','true']):
                with self.assertRaises(ValueError):v.Linux(self.value).run(argv,time.monotonic()+30)
            spawn.assert_not_called()

    def test_output_and_json_duplicates_are_bounded(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":NaN}',b'x'*(v.MAX_BYTES+1)):
            with self.assertRaises(ValueError):v.decode(raw)
        self.block.run=lambda *args:b'x'*65537
        with self.assertRaisesRegex(ValueError,'OBSERVATION_BOUND'):self.raw()


class ReceiverDiagnosticTest(unittest.TestCase):
    def test_receiver_codes_remain_closed_and_timeout_is_distinct(self):
        envelope=dict(request=request(),token='b'*32)
        for error,code in ((ValueError('V52_VOLUME_MOUNT_OWNER'),'V52_VOLUME_MOUNT_OWNER'),
                           (TimeoutError('private timeout text'),'V52_VOLUME_EXCHANGE_DEADLINE'),
                           (subprocess.TimeoutExpired(['private'],1),'V52_VOLUME_EXCHANGE_DEADLINE'),
                           (ValueError('private detail'),'V52_VOLUME_REJECTED'),
                           (OSError('private pathname'),'V52_VOLUME_IO_FAILED')):
            reply=v.rejection(error,'check',envelope)
            self.assertEqual(code,reply['code']);self.assertNotIn('private',str(reply))
        self.assertEqual('V52_VOLUME_CLOCK_EXPIRED',v.rejection(ValueError('V52_VOLUME_CLOCK_EXPIRED'),'check',envelope)['code'])

    def test_cli_expired_grant_and_unknown_failure_have_nonzero_bound_response(self):
        import io
        value=request();sample=v.sample(value,'a'*32)
        envelope=dict(request=value,token=dict(sample=sample,expiresNanos=sample['sampledNanos']+1))
        for action,body in (('check',envelope),('clock',dict(request=value,token='a'*32))):
            output=io.BytesIO();errors=io.StringIO()
            with patch.object(v.sys,'argv',['volume',action]),patch.object(v.sys,'stdin',SimpleNamespace(buffer=io.BytesIO(v.encoded(body)))), \
                 patch.object(v.sys,'stdout',SimpleNamespace(buffer=output)),patch.object(v.sys,'stderr',errors), \
                 patch.object(v,'_perform',side_effect=RuntimeError('private runtime detail')):
                status=v.main()
            self.assertEqual(2,status);answer=v.decode(output.getvalue())
            self.assertEqual('V52_VOLUME_CLOCK_EXPIRED' if action=='check' else 'V52_VOLUME_REJECTED',answer['code'])
            self.assertEqual(v.digest(body),answer['envelopeSha256']);self.assertNotIn('private',output.getvalue().decode()+errors.getvalue())


class RootBoundaryTest(unittest.TestCase):
    def test_privileged_invoking_user_metadata_and_boot_are_independently_checked(self):
        value=request();entry=SimpleNamespace(pw_name=value['guest']['user'],pw_uid=1001,pw_gid=1002)
        metadata=dict(instanceId='123',privateAddress='10.0.0.1',sshKeys=entry.pw_name+':'+value['publicKey'],
                      blockProjectSshKeys='TRUE',enableOslogin='FALSE')
        with ExitStack() as stack:
            for name in ('getuid','geteuid','getgid','getegid'):stack.enter_context(patch.object(v.os,name,return_value=0))
            stack.enter_context(patch.object(v.pwd,'getpwnam',return_value=entry))
            stack.enter_context(patch.dict(os.environ,dict(SUDO_USER=entry.pw_name,SUDO_UID='1001',SUDO_GID='1002')))
            observed=stack.enter_context(patch.object(v.guest,'metadata',return_value=metadata))
            v.account(value,time.monotonic()+30)
            os.environ['SUDO_UID']='0'
            with self.assertRaisesRegex(ValueError,'INVOKING_ACCOUNT'):v.account(value,time.monotonic()+30)
            os.environ['SUDO_UID']='1001';observed.return_value=dict(metadata,instanceId='124')
            with self.assertRaisesRegex(ValueError,'METADATA_IDENTITY'):v.account(value,time.monotonic()+30)
            value['guest']['bootId']='00000000-0000-4000-8000-000000000001'
            with self.assertRaisesRegex(ValueError,'GUEST_BOOT'):v.account(value,time.monotonic()+30)

    def test_failed_helper_remains_terminal_even_if_deadline_passes_at_exit(self):
        end=time.monotonic()+10;finished=[False];clock=time.monotonic
        proc=subprocess.Popen([sys.executable,'-c','raise SystemExit(7)'],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        wait=proc.wait
        def exited(*args,**kwargs):
            result=wait(*args,**kwargs);finished[0]=True;return result
        with patch.object(v.subprocess,'Popen',return_value=proc),patch.object(proc,'wait',side_effect=exited), \
             patch.object(v.time,'monotonic',side_effect=lambda:end+1 if finished[0] else clock()):
            with self.assertRaisesRegex(ValueError,'V52_VOLUME_COMMAND_FAILED'):
                v.Linux(request()).run(v.LSBLK,end)
        self.assertEqual(7,proc.returncode);self.assertTrue(proc.stdout.closed and proc.stderr.closed)

    def test_actual_trusted_receiver_reports_expired_grant_without_cloud_or_root_io(self):
        value=request();sample=v.sample(value,'a'*32)
        envelope=dict(request=value,token=dict(sample=sample,expiresNanos=sample['sampledNanos']+1))
        result=subprocess.run([sys.executable,'-I','-S','-c',storage.trusted_source('volume'),'check'],
            input=v.encoded(envelope),capture_output=True,timeout=10)
        self.assertEqual(2,result.returncode)
        error=storage.iap.transport.exit_error(result.returncode,result.stderr,ssh=True);error.partial_output=result.stdout
        result=storage.diagnostic.remote_error(error,'check',envelope)
        self.assertEqual('V52_VOLUME_CLOCK_EXPIRED',result.code);self.assertTrue(result.retryable)

    def test_trusted_source_is_standalone_and_cli_rejects_unprivileged_entry(self):
        self.assertNotEqual(0,os.getuid())
        value=request();source=storage.trusted_source('volume')
        result=subprocess.run([sys.executable,'-I','-S','-c',source,'clock'],input=v.encoded(dict(request=value,token='a'*32)),
            capture_output=True,timeout=10)
        self.assertEqual(2,result.returncode)
        response=v.decode(result.stdout)
        self.assertEqual('V52_VOLUME_ROOT_ACCOUNT',response['code'])
        self.assertEqual(v.digest(dict(request=value,token='a'*32)),response['envelopeSha256'])
        self.assertEqual(b'V52_VOLUME_REJECTED\n',result.stderr)
        self.assertNotIn('scripts.v51',source)

    def test_record_atomic_publication_and_symlink_read_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'one';v.write(path,dict(value=1));self.assertEqual(dict(value=1),v.read(path))
            with self.assertRaises(FileExistsError):v.write(path,dict(value=2))
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaises(OSError):v.read(link)
            self.assertEqual(dict(value=1),v.read(path))


class HistoryPathsTest(unittest.TestCase):
    def test_owned_parent_consumption_query_and_wrong_mount_do_not_replay(self):
        # Real private filesystem operations, synthetic cloud request and mount
        # observation. No real mount or root operation occurs.
        target=Path(__file__).resolve().parents[2]/'target';target.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target) as directory,patch.object(v,'MOUNT',directory):
            value=request();value['guest'].update(uid=os.getuid(),gid=os.getgid())
            dev=Path(directory).stat().st_dev
            volume=dict(device='/dev/sdb',majorMinor=str(os.major(dev))+':'+str(os.minor(dev)),uuid='12345678-1234-1234-1234-123456789abc',
                mount=directory,uid=os.getuid(),gid=os.getgid());history='a'*64
            self.assertEqual('NOT_FOUND',paths.perform('query',value,volume,history)['state'])
            first=paths.perform('prepare',value,volume,history);self.assertEqual('SUCCEEDED',first['state'])
            self.assertEqual(first,paths.perform('query',value,volume,history));self.assertEqual(first,paths.perform('prepare',value,volume,history))
            self.assertFalse(Path(first['root']).exists())
            with self.assertRaisesRegex(ValueError,'HISTORY_MOUNT_CHANGED'):paths.perform('query',value,dict(volume,majorMinor='0:0'),history)
            (Path(first['root']).parent/'claim.json').unlink()
            self.assertEqual('UNCERTAIN',paths.perform('prepare',value,volume,history)['state'])
            self.assertFalse((Path(first['root']).parent/'claim.json').exists())


if __name__=='__main__':unittest.main()
