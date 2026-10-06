"""Complete guest package delivery over bounded pinned connections; no cloud admission."""
import base64
from copy import deepcopy
import math
import hashlib
from pathlib import Path
import secrets
import time
from . import cloud_package as package, guest_package_receiver as receiver, guest_delivery_receiver as r
from . import guest_transport as transport, performance_model as m, remote_command as c


def describe(archive, manifest, binding, provider, access_sha):
    archive = Path(archive); size = archive.stat().st_size
    m.need(archive.is_file() and not archive.is_symlink() and 0 < size <= package.MAX_BYTES, 'package source archive')
    parts = []; digest = hashlib.sha256()
    with archive.open('rb') as stream:
        while raw := stream.read(receiver.PART_BYTES):
            parts.append(dict(index=len(parts), bytes=len(raw), sha256=m.sha(raw))); digest.update(raw)
    m.need(binding['bundleSha256'] == digest.hexdigest() and manifest['source'] == binding['source'] and
           m.sha(m.canonical(package.read(archive.parent/'package/workload.json'))) == binding['workloadSha256'] and
           binding['attempt'] == provider['attempt'] and binding['node'] == 'node-'+str(provider['node']), 'package source/provider binding')
    return receiver.descriptor(dict(schema='gse-v51-package-transfer-v1', binding=deepcopy(binding),
        instanceId=provider['instanceId'], diskId=provider['diskId'], guestAccessSha256=access_sha, archiveBytes=size,
        manifestSha256=m.sha((archive.parent/'package/manifest.json').read_bytes()),
        buildManifestSha256=manifest['buildManifestSha256'], parts=parts))


def trusted_source():
    modules = {v.__name__.rsplit('.',1)[1]:Path(v.__file__).read_text() for v in (r, package, receiver)}
    return ("import sys,types\np=types.ModuleType('trusted');p.__path__=[];sys.modules['trusted']=p\n"
        "for name,source in "+repr(modules)+".items():\n"
        " q=types.ModuleType('trusted.'+name);q.__package__='trusted';sys.modules[q.__name__]=q\n"
        " exec(compile(source,'<trusted-package-'+name+'>','exec'),q.__dict__)\n"
        "sys.modules['trusted.guest_package_receiver'].main()\n")


class Endpoint:
    offline = False
    def __init__(self, target, parent, value):
        receiver.descriptor(value); m.need(target['instanceId'] == value['instanceId'], 'package pinned instance')
        self.target, self.parent, self.value = target, str(parent), deepcopy(value)
        self.deadline = self.budget = None; self.started = False
        self.calls = []; self.failures = []
    def argv(self, remote): return transport.ssh_args(self.target, remote)
    def remote(self, action, token, *tail):
        return ['python3','-I','-c',trusted_source(),action,self.parent,
                base64.b64encode(m.canonical(self.value)).decode(),token,*tail]
    def process(self, remote, data, deadline, **options):
        return transport.process(self.argv(remote),data,deadline,**options)
    def call(self, action, data, deadline, token, index=None):
        m.need(len(self.calls) < 4096, 'package connection count bound')
        self.calls.append(dict(action=action, index=index))
        remote = ['python3', '-I', '-c', trusted_source(), action, self.parent,
                  base64.b64encode(m.canonical(self.value)).decode(), token, *([] if index is None else [str(index)])]
        try:
            raw = transport.process(self.argv(remote), data, deadline, maximum=4096, request_maximum=receiver.PART_BYTES)
            return m.strict_json(raw)
        except Exception as error:
            if len(self.failures) < 8: self.failures.append(dict(action=action, type=type(error).__name__, message=str(error)[:1500]))
            raise
    def exchange(self, action, data, deadline, index=None):
        m.need(self.offline is True and self.value['schema'] == 'gse-v51-package-transfer-v1',
               'live package delivery disabled pending paid admission')
        return self._exchange(action,data,deadline,index)

    def _exchange(self, action, data, deadline, index=None):
        m.need(action in ('begin','part','query','finish') and isinstance(data,bytes) and
               (action == 'part' or data == b''), 'package transfer input')
        now = time.monotonic(); m.need(type(deadline) in (int,float) and math.isfinite(deadline) and 0 < deadline-now <= 600, 'package original deadline')
        if not self.started:
            self.started = True; self.deadline = deadline; nonce = secrets.token_hex(16)
            try: sample = self.call('clock', b'', deadline, nonce)
            except (ConnectionError, TimeoutError) as error:
                raise ValueError('package clock unavailable; no delivery admitted: '+str(error)) from error
            r.validate_sample(sample, receiver.identity(self.value), nonce)
            remaining = math.floor((deadline-time.monotonic())*10**9)
            self.budget = r.validate_budget(dict(schema='gse-v51-helper-deadline-v1', sample=sample,
                expiresNanos=sample['sampledNanos']+remaining), receiver.identity(self.value))
        m.need(self.budget is not None and deadline == self.deadline, 'package clock/deadline cannot renew')
        answer = self.call(action, data, deadline, base64.b64encode(m.canonical(self.budget)).decode(), index)
        m.need(type(answer) is dict and set(answer) == {'schema','deadlineSha256','receipt'} and
               answer['schema'] == 'gse-v51-package-transport-v1' and answer['deadlineSha256'] == m.sha(m.canonical(self.budget)) and
               time.monotonic() < deadline, 'package transport identity/deadline')
        return answer['receipt']

    def client(self, config):
        m.need(self.offline is True, 'live delivered client disabled')
        return self._client(config)

    def _client(self, config):
        m.need(config['binding'] == self.value['binding'] and
               config['packageManifestSha256'] == self.value['manifestSha256'], 'delivered client binding/scope')
        endpoint = self
        class Client(transport.Local):
            offline=endpoint.offline
            def args(self, action, *tail):
                remote = endpoint.remote('service',base64.b64encode(m.canonical(config)).decode(),action,*tail)
                return endpoint.argv(remote)
            def exchange(self, action, value, deadline, *tail, binary=False, maximum=c.RESPONSE_BYTES):
                remote=endpoint.remote('service',base64.b64encode(m.canonical(config)).decode(),action,*tail)
                raw=endpoint.process(remote,m.canonical(value) if value is not None else b'',deadline,maximum=maximum)
                return raw if binary else m.strict_json(raw)
        base = Path(self.parent)/(self.value['binding']['attempt']+'-'+self.value['binding']['node'])/'package'
        return Client(base, config)

    def bootstrap(self, action, request, deadline):
        m.need(self.offline is True, 'bootstrap original package deadline/scope')
        return self._bootstrap(action,request,deadline)

    def _bootstrap(self, action, request, deadline):
        m.need(self.budget is not None and deadline == self.deadline and
               time.monotonic() < deadline, 'bootstrap original package deadline/scope')
        m.need(action in ('install','seal','query-install','query-seal') and len(self.calls) < 4096, 'bootstrap controller action/bound')
        self.calls.append(dict(action='bootstrap-'+action,index=None))
        remote = self.remote('bootstrap',base64.b64encode(m.canonical(self.budget)).decode(),
            action,base64.b64encode(m.canonical(request)).decode())
        raw = self.process(remote,b'',deadline,maximum=262144)
        answer = m.strict_json(raw)
        m.need(set(answer) == {'schema','action','requestSha256','deadlineSha256','receipt'} and
               answer['schema'] == 'gse-v51-package-bootstrap-v1' and answer['action'] == action and
               answer['requestSha256'] == m.sha(m.canonical(request)) and
               answer['deadlineSha256'] == m.sha(m.canonical(self.budget)) and time.monotonic() < deadline,
               'bootstrap transport identity/deadline')
        return answer['receipt']

    def source(self, action, request, data, deadline, index=None):
        m.need(self.offline is True, 'source original package deadline/scope')
        return self._source(action,request,data,deadline,index)

    def _source(self, action, request, data, deadline, index=None):
        m.need(self.budget is not None and deadline==self.deadline and
               time.monotonic()<deadline,'source original package deadline/scope')
        m.need(action in ('begin','chunk','finish','query') and len(self.calls)<4096 and
               isinstance(data,bytes) and len(data)<=receiver.PART_BYTES and (action=='chunk' or data==b'') and
               (type(index) is int if action=='chunk' else index is None),'source controller action/bound')
        from . import guest_source_transfer as source
        source.validate(request)
        self.calls.append(dict(action='source-'+action,index=index))
        remote=self.remote('source',base64.b64encode(m.canonical(self.budget)).decode(),
            action,base64.b64encode(m.canonical(request)).decode(),*([str(index)] if index is not None else []))
        raw=self.process(remote,data,deadline,maximum=65536,request_maximum=receiver.PART_BYTES)
        answer=m.strict_json(raw)
        m.need(set(answer)=={'schema','action','requestSha256','deadlineSha256','receipt'} and
               answer['schema']=='gse-v51-package-source-v1' and answer['action']==action and
               answer['requestSha256']==m.sha(m.canonical(request)) and
               answer['deadlineSha256']==m.sha(m.canonical(self.budget)) and time.monotonic()<deadline,
               'source transport identity/deadline')
        return answer['receipt']

    def producer(self,action,request,deadline,*,node=None,index=None):
        m.need(self.offline is True, 'producer original package deadline/scope')
        return self._producer(action,request,deadline,node=node,index=index)

    def _producer(self,action,request,deadline,*,node=None,index=None):
        m.need(self.budget is not None and deadline==self.deadline and
               time.monotonic()<deadline,'producer original package deadline/scope')
        m.need(action in ('prepare','query','manifest','chunk') and len(self.calls)<4096 and
               (node in ('node-1','node-2','node-3') if action in ('manifest','chunk') else node is None) and
               (type(index) is int and 0<=index<65 if action=='chunk' else index is None),'producer controller action/bound')
        from . import guest_source_producer as source
        source.validate(request)
        self.calls.append(dict(action='producer-'+action,node=node,index=index))
        remote=self.remote('producer',base64.b64encode(m.canonical(self.budget)).decode(),
            action,base64.b64encode(m.canonical(request)).decode(),*([node] if node is not None else []),
            *([str(index)] if index is not None else []))
        raw=self.process(remote,b'',deadline,maximum=receiver.PART_BYTES if action=='chunk' else 131072,
                              retain_partial=action=='chunk')
        m.need(time.monotonic()<deadline,'producer late response')
        if action=='chunk':return raw
        answer=m.strict_json(raw)
        m.need(set(answer)=={'schema','action','requestSha256','deadlineSha256','receipt'} and
               answer['schema']=='gse-v51-package-producer-v1' and answer['action']==action and
               answer['requestSha256']==m.sha(m.canonical(request)) and answer['deadlineSha256']==m.sha(m.canonical(self.budget)),
               'producer transport identity')
        return answer['receipt']


def deliver(endpoint, archive, deadline):
    m.need(endpoint.offline is True and endpoint.value['schema'] == 'gse-v51-package-transfer-v1',
           'live package delivery disabled pending paid admission')
    return _deliver(endpoint,archive,deadline)


def _deliver(endpoint, archive, deadline):
    value = receiver.descriptor(endpoint.value)
    def observe(action, data=b'', index=None):
        answer = None
        try: answer = endpoint.exchange(action, data, deadline, index)
        except (ConnectionError, TimeoutError): pass
        while True:
            if answer is not None:
                count = answer.get('completedParts'); state = answer.get('state')
                m.need(type(count) is int and 0 <= count <= len(value['parts']) and state in
                       ('RECEIVING','READY','SUCCEEDED','FAILED','NOT_FOUND','UNCERTAIN') and
                       all(answer.get(k) == v for k,v in receiver.envelope(value,state,count).items()), 'package receipt identity')
                if state not in ('NOT_FOUND','UNCERTAIN'): return answer
            left = deadline-time.monotonic(); m.need(left > 0, 'package unresolved; no replay')
            time.sleep(min(.05,left))
            try: answer = endpoint.exchange('query', b'', deadline)
            except (ConnectionError, TimeoutError): answer = None
    answer = observe('begin'); m.need(answer['state'] == 'RECEIVING' and answer['completedParts'] == 0, 'package destination already consumed')
    with Path(archive).open('rb') as stream:
        for part in value['parts']:
            raw = stream.read(part['bytes'])
            m.need(len(raw) == part['bytes'] and m.sha(raw) == part['sha256'], 'controller package bytes changed')
            answer = observe('part', raw, part['index'])
            m.need(answer['state'] in ('RECEIVING','READY') and answer['completedParts'] == part['index']+1,
                   'package part failed: '+str(answer))
        m.need(stream.read(1) == b'', 'controller package trailing bytes')
    answer = observe('finish'); m.need(answer['state'] == 'SUCCEEDED', 'package installation failed: '+str(answer))
    expected = str(Path(endpoint.parent)/(value['binding']['attempt']+'-'+value['binding']['node'])/'package')
    m.need(answer['installed']['package'] == expected and answer['installed']['manifestSha256'] == value['manifestSha256'], 'package installed path/manifest')
    return answer
