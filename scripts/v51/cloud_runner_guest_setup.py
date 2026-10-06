"""Internal native resource/IAP/volume/package chain, with one preparation deadline.

No CLI or workflow invokes this yet. Successful preparation is PARTIAL with the
original active lease/reservation; it cannot stand in for a paid workload result.
Native preparation failure uses the original owner's bounded cleanup/retention.
"""
import base64
from copy import deepcopy
from functools import lru_cache
import io
import math
from pathlib import Path
import secrets
import tempfile
import time
import zipfile
import zlib
from . import cloud_runner_resources as resources, cloud_runner_iap as iap
from . import cloud_native_authority as n, cloud_package as package, cloud_runner_artifacts as artifacts
from . import guest_delivery_receiver as r, guest_native_volume as volume, guest_native_package as native_package
from . import guest_package_delivery as delivery, guest_package_receiver as receiver
from . import performance_model as m, remote_command as c


@lru_cache(maxsize=3)
def trusted_source(kind):
    m.need(kind in ('volume','package','session'),'native guest receiver kind')
    names = ('performance_model','performance_plan','cloud_workload_contract','remote_command','guest_setup',
             'guest_transport','guest_volume','guest_delivery_receiver','guest_root_policy','guest_root_receiver',
             'guest_native_volume','cloud_package','guest_package_receiver','guest_native_package','guest_native_session')
    modules = {name:(Path(__file__).parent/(name+'.py')).read_text() for name in names}
    encoded = base64.b64encode(zlib.compress(m.canonical(modules))).decode()
    # Preserve dependency order explicitly; canonical JSON sorts its keys.
    source = ("import sys,types,json,zlib,base64\np=types.ModuleType('trusted');p.__path__=[];sys.modules['trusted']=p\n"
        "sources=json.loads(zlib.decompress(base64.b64decode("+repr(encoded)+")))\n"
        "for name in "+repr(names)+":\n"
        " q=types.ModuleType('trusted.'+name);q.__package__='trusted';q.__file__='/trusted-controller/scripts/v51/'+name+'.py'\n"
        " sys.modules[q.__name__]=q;exec(compile(sources[name],q.__file__,'exec'),q.__dict__)\n"
        "sys.modules['trusted.guest_native_"+kind+"'].main()\n")
    m.need(len(source) < 65536,'native trusted source bound')
    return source


class _VolumeEndpoint:
    def __init__(self, api, target, value, recheck):
        self.api,self.target,self.value,self.recheck = api,target,volume.validate(value),recheck
        self.started = False; self.budget = None; self.calls = []

    def call(self, action, token):
        m.need(len(self.calls) < 4096,'native volume connection bound')
        self.recheck(); self.calls.append(dict(action=action))
        remote = ['sudo','-n','-u','root','-g','root','--','/usr/bin/python3','-I','-c',trusted_source('volume'),
                  action,base64.b64encode(m.canonical(self.value)).decode(),token]
        raw = iap._network_exchange(self.api,self.target,remote,b'',self.api.deadline,maximum=1 << 20)
        self.recheck(); return m.strict_json(raw)

    def exchange(self, action):
        m.need(action in ('prepare','query','check') and self.api.clock() < self.api.deadline,'native volume action/deadline')
        if not self.started:
            self.started = True; nonce = secrets.token_hex(16)
            try: sample = self.call('clock',nonce)
            except (ConnectionError,TimeoutError): raise ValueError('native volume clock unavailable; no mutation admitted') from None
            r.validate_sample(sample,volume.identity(self.value),nonce)
            remaining = math.floor((self.api.deadline-self.api.clock())*10**9)
            self.budget = r.validate_budget(dict(schema='gse-v51-helper-deadline-v1',sample=sample,
                expiresNanos=sample['sampledNanos']+remaining),volume.identity(self.value))
        m.need(self.budget is not None,'native volume clock cannot renew')
        answer = self.call(action,base64.b64encode(m.canonical(self.budget)).decode())
        m.need(answer['schema'] == 'gse-v51-native-volume-transport-v1' and
               answer['requestSha256'] == m.sha(m.canonical(self.value)) and
               answer['deadlineSha256'] == m.sha(m.canonical(self.budget)) and
               answer['state'] in ('SUCCEEDED','FAILED','NOT_FOUND','UNCERTAIN') and self.api.clock() < self.api.deadline,
               'native volume reply identity/deadline')
        return answer

    def prepare(self):
        answer = None
        try: answer = self.exchange('prepare')
        except (ConnectionError,TimeoutError): pass
        while answer is None or answer['state'] in ('NOT_FOUND','UNCERTAIN'):
            left = self.api.deadline-self.api.clock(); m.need(left > 0,'native volume unresolved; no resubmit')
            self.api.provider().sleep(min(.2,left))
            try: answer = self.exchange('query')
            except (ConnectionError,TimeoutError): answer = None
        m.need(answer['state'] == 'SUCCEEDED','native volume failed; no reformat')
        checked = self.exchange('check')
        m.need(checked['state'] == 'SUCCEEDED' and checked['startup'] == answer['startup'] and
               checked['readiness']['startupSha256'] == m.sha(m.canonical(answer['startup'])) and
               checked['readiness']['volume'] == answer['startup']['volume'],'native volume readiness binding')
        return checked


class _PackageEndpoint(delivery.Endpoint):
    def __init__(self, api, target, value, recheck):
        native_package.validate(value)
        super().__init__(target,volume.v.MOUNT,value)
        self.api,self.recheck = api,recheck
    def call(self, action, data, deadline, token, index=None):
        m.need(len(self.calls) < 4096 and deadline == self.api.deadline,'native package original deadline')
        self.recheck(); self.calls.append(dict(action=action,index=index))
        remote = ['/usr/bin/python3','-I','-c',trusted_source('package'),action,
                  base64.b64encode(m.canonical(self.value)).decode(),token,*([] if index is None else [str(index)])]
        raw = iap._network_exchange(self.api,self.target,remote,data,deadline,maximum=4096,request_maximum=receiver.PART_BYTES)
        self.recheck(); return m.strict_json(raw)
    def exchange(self, action, data, deadline, index=None):
        return self._exchange(action,data,deadline,index)


def _archive(originals, proof, output):
    """Recheck the admitted original bytes, never an unbound sidecar tar."""
    path = Path(originals)/'package.zip'
    m.need(path.is_file() and not path.is_symlink() and path.stat().st_size <= artifacts.MAX_BYTES,'native package original ZIP')
    raw = path.read_bytes()
    m.need(m.sha(raw) == proof['artifacts']['package']['sha256'],'native package original changed')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = archive.infolist()
        m.need(len({row.filename for row in rows}) == len(rows) and
               archive.getinfo('guest.tar.gz').file_size <= package.MAX_BYTES,'native package archive inventory')
        data = archive.read('guest.tar.gz')
    m.need(m.sha(data) == proof['archiveSha256'],'native package archive changed')
    path = Path(output)/'guest.tar.gz'; path.write_bytes(data)
    manifest = package.unpack(path,Path(output)/'package',proof['archiveSha256'],proof['source'])
    m.need(m.sha((Path(output)/'package/manifest.json').read_bytes()) == proof['packageManifestSha256'] and
           manifest['buildManifestSha256'] == proof['buildManifestSha256'] and
           m.sha(m.canonical(package.read(Path(output)/'package/workload.json'))) == proof['workloadSha256'],
           'native package admitted manifests')
    return path,manifest


def _stage(api, key, root, guests, originals, proof, *, endpoints=(_VolumeEndpoint,_PackageEndpoint), continuation=None):
    output = Path(root)/'guest-setup'; output.mkdir()
    m.need(api.state == 'done' and not api.failed and len(guests) == 3 and api.clock() < api.deadline,
           'native guest resource stage/deadline')
    lease = deepcopy(api.lease); records = []; prepared = []
    with tempfile.TemporaryDirectory(prefix='gse-v51-admitted-package-') as temporary:
        archive,manifest = _archive(originals,proof,temporary)
        for node,guest in enumerate(guests,1):
            m.need(guest['node'] == node and guest['status'] == 'IDENTITY_VERIFIED','native guest inventory')
            row = next(row for row in lease['resources'] if row['spec']['kind'] == 'instance' and row['spec']['node'] == node)
            facts = guest['facts']; provider = api.provider()
            pin = Path(root)/'iap'/('node-'+str(node)+'.known_hosts'); pin_raw = pin.read_bytes()
            target = dict(project=api.cfg['project'],zone=api.cfg['zone'],instance=row['spec']['name'],instanceId=row['id'],
                user=api.value['guestAccess']['user'],key=str(Path(key).resolve()),knownHosts=str(pin.resolve()))
            def recheck(row=row,node=node,facts=facts,guest=guest,pin=pin,pin_raw=pin_raw,provider=provider):
                m.need(api.clock() < api.deadline and api.store.get(n.LEASE) == (api.generation,lease) and
                       api.store.get(n.LEDGER)[1] == api.reserved,'native guest durable authority/deadline')
                host = provider.guest_host_key(row['spec'],row['id'],deadline=api.deadline)['publicKey']
                m.need(provider.guest_facts(lease,node,deadline=api.deadline) == facts and
                       m.sha(host.encode()) == guest['hostKeySha256'] and pin.read_bytes() == pin_raw ==
                       ('gse-v51-'+row['id']+' '+host+'\n').encode(),'native guest provider/host identity changed')
            binding = dict(schema='gse-v51-guest-binding-v1',source=proof['source'],bundleSha256=proof['archiveSha256'],
                workloadSha256=proof['workloadSha256'],attempt=api.req['attempt'],node='node-'+str(node))
            value = volume.validate(dict(schema=volume.SCHEMA,binding=binding,provider=facts['provider'],bootDiskId=facts['bootDiskId'],
                access=api.value['guestAccess'],requestSha256=n.validate_request(api.req)))
            base = output/('node-'+str(node)); base.mkdir(); c.write_once(base/'request.json',value)
            disk = endpoints[0](api,target,value,recheck); transfer = None
            try:
                recheck(); checked = disk.prepare(); c.write_once(base/'volume.json',checked)
                desc = delivery.describe(archive,manifest,binding,facts['provider'],m.sha(m.canonical(value['access'])))
                desc.update(schema='gse-v51-native-package-transfer-v1',nativeVolume=dict(request=value,
                    volume=checked['readiness']['volume'],startupSha256=checked['readiness']['startupSha256']))
                c.write_once(base/'package-request.json',desc)
                transfer = endpoints[1](api,target,desc,recheck)
                installed = delivery._deliver(transfer,archive,api.deadline); c.write_once(base/'package.json',installed)
                final = disk.exchange('check'); recheck()
                m.need(final['readiness']['volume'] == checked['readiness']['volume'] and
                       final['startup'] == checked['startup'],'native guest post-package mount changed')
                c.write_once(base/'readiness.json',final)
                records.append(dict(node=node,status='PACKAGE_READY',instanceId=row['id'],diskId=facts['provider']['diskId'],
                    packageManifestSha256=desc['manifestSha256'],startupSha256=desc['nativeVolume']['startupSha256']))
                prepared.append(dict(endpoint=transfer,disk=disk,installed=installed,facts=facts,
                    startup=final['startup'],recheck=recheck))
            finally:
                c.write_once(base/'connections.json',dict(volume=disk.calls,package=transfer.calls if transfer is not None else []))
        if continuation is not None: continuation(api,archive,prepared)
    return records


def prepare_native(cfg, env, source, checkout, preflight, precheck_root, value, approved, artifacts, key, output):
    """Fixed fresh native admission; no transport/backend/target/command overrides."""
    proof = deepcopy(value['artifacts'])
    return resources._prepare_native(cfg,env,source,checkout,preflight,precheck_root,value,approved,artifacts,key,output,
        guest_stage=lambda api,key,root,guests:_stage(api,key,root,guests,artifacts,proof))
