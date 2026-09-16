"""Run the actual remote guest protocol on owned local JVMs with fake resource IDs."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from .cloud_common import canonical, plan, require, save, sha
from .cloud_preset_fake import PresetFake, run_one
from .cloud_presets import workload_request
from .cloud_runner import Runner
from .cloud_remote_probe import RemoteProbe
from .cloud_workload_io import sha_file
from .leader_harness import ports


class LocalBackend(PresetFake):
    def __init__(self,p,r,root):
        super().__init__(p,r);self.guest_root=Path(root).resolve();self.guest_root.mkdir()
        self.endpoints=','.join('127.0.0.1:'+str(v) for v in ports())

    def ssh(self,instance,arguments,timeout=None):
        args=[sys.executable,*arguments[1:]]
        result=subprocess.run(args,capture_output=True,timeout=timeout or 60)
        require(result.returncode==0,'local guest failed: '+result.stderr.decode(errors='replace')[-4000:])
        require(len(result.stdout)<=4<<20,'local guest response bound');return json.loads(result.stdout)

    def worker(self,instance,arguments,stderr):
        return subprocess.Popen([sys.executable,*arguments[1:]],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=stderr)

    def copy(self,instance,source,target,download=False):
        require(download,'local qualification uses a prepared immutable bundle')
        shutil.copyfile(source,target)

    def delete(self,row,expected_id):
        super().delete(row,expected_id)
        if row['kind']=='disks' and row.get('purpose')=='data' and not row.get('generation'):
            path=self.guest_root/f'volume-{row["node"]}'
            # Keep the old inode outside the guest namespace until its replacement
            # exists. Delete/recreate alone can silently reuse the same inode.
            if path.exists():path.rename(self.guest_root.parent/f'retired-fake-volume-{row["node"]}')


def run(root,archive,content):
    root=Path(root);require(not root.exists(),'fresh remote qualification');root.mkdir(parents=True)
    objects={};sequence='e'*32;manifest=json.loads((Path(content)/'bundle.json').read_bytes())
    for i,profile in enumerate(('experiment','failure-drill'),1):
        _,state=run_one(root/f'prerequisite-{i}',profile,1,sequence,i,objects=objects,source=manifest['source'])
        require(state['status']=='PASS','fake prerequisite failed')
    manifest=json.loads((Path(content)/'bundle.json').read_bytes())
    req=workload_request(manifest['source'],3,1,sha_file(archive),'canonical',sequence)
    backend=LocalBackend(plan(),req,root/'guest');backend.objects=objects
    workspace=root/'runner'
    runner=Runner(backend,None,workspace,approval=dict(maximumCostMicrousd=1_000_000,previousAttemptsCostMicrousd=2_000_000))
    probe=RemoteProbe(backend,archive,workspace,content,qualification=True);runner.probe=probe;probe.runner=runner
    try:state=runner.run()
    finally:
        for path in root.glob('retired-fake-volume-*'):shutil.rmtree(path)
    save(root/'result.json',dict(status=state['status'],execution='local-remote-workload-only',errors=state['errors']))
    require(state['status']=='PASS','remote qualification failed: '+json.dumps(state['errors']))
    return state


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);p.add_argument('--bundle',type=Path,required=True)
    a=p.parse_args();run(a.output,a.bundle/'bundle.tar.gz',a.bundle/'bundle')
    print('v50RemoteWorkload=PASS execution=local-remote-workload-only')
