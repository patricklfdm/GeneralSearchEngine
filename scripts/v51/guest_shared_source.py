"""One authenticated V4.4 backup reused byte-for-byte by three fresh bootstraps."""
from copy import deepcopy
from pathlib import Path
import time
import tempfile
from . import cloud_package as package, guest_bootstrap as boot, guest_producer_source as producer
from . import performance_model as m, performance_plan, performance_semantics, remote_collection as parts, remote_command as c


class SharedSource:
    def __init__(self, output, *, clock=time.monotonic, sleep=time.sleep):
        self.root=Path(output);self.clock=clock;self.remote=producer.RemoteSource(clock=clock,sleep=sleep)
        self.modes=[];self.config=None;self.files=None;self.deadline=None

    def selection(self, config):return config['mode'],list(package.MODES)

    def normalized(self, config):
        value=deepcopy(config);value.update(mode=self.config['mode'],root=self.config['root'],groupId=self.config['groupId'])
        return value

    def prepare(self, configs, deadline, *, endpoint, output):
        mode,order=self.selection(configs[0])
        m.need(len(self.modes)<len(order) and mode==order[len(self.modes)], 'shared source mode order/consumed')
        if self.config is None:
            self.config=deepcopy(configs[0]);self.deadline=deadline
            self.root.mkdir(mode=0o700)
        normalized=self.normalized(configs[0])
        m.need(normalized==self.config and deadline==self.deadline and self.clock()<deadline, 'shared source identity/original deadline')
        self.modes.append(mode)  # A failed preparation also consumes this mode.
        # export() checks the derived producer configuration as an absolute path.
        # Do not resolve symlinks: the existing directory check must reject them.
        output=Path(output).absolute();c.directory(output.parent);output.mkdir(mode=0o700)
        c.write_once(output/'plan.json',dict(configs=configs,deadline=deadline))
        if len(self.modes)==1:
            rows=self.remote.prepare(configs,deadline,endpoint=endpoint,output=output/'original')
            row=rows[0];folder=Path(row['folder']);descriptor=boot.descriptor(folder,row['descriptorSha256'],configs[0])
            parts.unpack(folder/'parts',self.root/'seed',m.sha(m.canonical(configs[0])),expected_members=descriptor['files'])
            self.files={k:v for k,v in descriptor['files'].items() if k.startswith('source/')}
            c.write_once(self.root/'identity.json',dict(config=self.config,files=self.files,sourceSha256=m.sha(m.canonical(self.files))))
        # Decode the backup independently before every export; an unchanged path
        # or a cached PASS receipt is not sufficient authority to copy its bytes.
        performance_semantics.source_backup(self.root/'seed/source',m.initial(performance_plan.load()))
        actual={f'source/{n}':dict(bytes=(self.root/'seed/source'/n).stat().st_size,
            sha256=m.sha((self.root/'seed/source'/n).read_bytes())) for n in boot.SOURCE}
        m.need(actual==self.files, 'shared source backup changed')
        raw=output/'source';raw.mkdir(mode=0o700);(raw/'source').mkdir(mode=0o700)
        for n in boot.SOURCE:(raw/'source'/n).write_bytes((self.root/'seed/source'/n).read_bytes())
        for n,text in boot.topology_values(configs[0]).items():
            (raw/n).write_text(text)
        local=deepcopy(configs[0]);local['root']=str(raw)
        exports=[]
        for cfg in configs:
            folder=output/cfg['binding']['node'];row=boot.export(raw,folder,cfg,producer_config=local)
            exports.append(dict(row,folder=str(folder)))
        m.need(self.clock()<deadline,'shared source export deadline')
        c.write_once(output/'receipt.json',dict(status='PASS',sourceSha256=m.sha(m.canonical(self.files)),exports=exports))
        return exports


class Source:
    offline=True
    scope='authenticated-shared-source'
    def __init__(self, shared):self.shared=shared;self.root=None
    def prepare(self, configs, deadline, *, endpoint, output):
        m.need(self.root is None, 'shared source adapter consumed');self.root=Path(output)
        return self.shared.prepare(configs,deadline,endpoint=endpoint,output=output)
    def retention_files(self):
        if self.root is None or not self.root.exists():return
        # Retain original producer descriptors and all derived source exports,
        # including incomplete work. The common packer enforces byte/file bounds.
        with tempfile.TemporaryDirectory(prefix='gse-v51-source-retention-') as scratch:
            destination=Path(scratch)/'parts'
            parts.pack(self.root,destination,m.sha(m.canonical(dict(scope=self.scope))))
            for path in sorted(destination.iterdir()):yield path.name,path.read_bytes()
