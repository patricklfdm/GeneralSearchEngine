"""Owned initial bootstrap before service launch; explicitly offline source adapters.

Only immutable source/topology crosses filesystem views. Each receiver uses its
verified package's public bootstrap API and retains its own filesystem-bound seal.
"""
from copy import deepcopy
from pathlib import Path
import re
import time
from . import guest_bootstrap as b, cloud_guest as guest, cloud_package as package
from . import cloud_authority as a, performance_model as m, remote_command as c

FILES = {'plan.json','source.json','receipt.json'} | {f'node-{n}-{phase}.json' for n in (1,2,3) for phase in ('install','seal')}


class Bootstrap:
    offline = True
    def __init__(self, source, *, clock=time.monotonic, sleep=time.sleep, delivery=None):
        m.need(source.offline is True and source.scope == 'qualification-shared-source-paths', 'native bootstrap source delivery disabled')
        self.source,self.clock,self.sleep = source,clock,sleep; self.root=None
        m.need(delivery is None or delivery.offline is True,'native source transfer disabled')
        self.delivery=delivery

    def prepare(self, req, configs, endpoints, output, deadline, *, recheck):
        m.need(self.root is None and len(configs) == len(endpoints) == 3, 'owned bootstrap consumed/topology')
        m.need([v['binding']['node'] for v in configs] == ['node-1','node-2','node-3'] and
               configs[0]['mode'] in package.MODES[1:], 'owned bootstrap replicated member set')
        for cfg,ep in zip(configs,endpoints):
            guest.validate(cfg); normalized=deepcopy(cfg); normalized['binding']['node']='node-1'
            m.need(normalized == configs[0] and ep.offline is True and ep.value['binding'] == cfg['binding'] and
                   cfg['binding']['source'] == req['source'] and cfg['binding']['bundleSha256'] == req['bundleSha256'] and
                   cfg['binding']['attempt'] == req['attempt'], 'owned bootstrap exact group/package binding')
        self.root=Path(output); self.root.mkdir(mode=0o700); c.sync_directory(self.root.parent)
        result=dict(schema='gse-v51-owned-bootstrap-v1',status='FAIL',requestSha256=a.validate_request(req),
            sourceTransport=self.delivery.scope if self.delivery is not None else self.source.scope,
            sourcePreparation=self.source.scope,publicBootstrapVerified=False,engineWorkloadExecuted=False,
            paidCloud=False,fullRemoteQualification=False,members=[])
        c.write_once(self.root/'plan.json',dict(configs=configs,requestSha256=result['requestSha256'],
            sourceTransport=result['sourceTransport'],sourcePreparation=self.source.scope))
        def check(i,phase):
            m.need(self.clock()<deadline,'owned bootstrap original deadline'); recheck(i,phase)
            m.need(self.clock()<deadline,'owned bootstrap original deadline')
        def once(i,phase,request):
            ep=endpoints[i]; record=dict(request=request,status='FAIL',submits=0,queries=0)
            try:
                m.need(self.clock()<deadline,'owned bootstrap original deadline')
                record['queries']+=1; previous=ep.bootstrap('query-'+phase,request,deadline)
                m.need(previous == {'state':'NOT_FOUND'},'owned bootstrap destination consumed')
                # Publish a forced intent before the single mutation. The result
                # file below never replaces it, including after a lost response.
                c.write_once(self.root/f'node-{i+1}-{phase}-intent.json',request)
                record['submits']+=1
                try: answer=ep.bootstrap(phase,request,deadline)
                except (ConnectionError,TimeoutError): answer=None
                while True:
                    m.need(self.clock()<deadline,'owned bootstrap unresolved; no replay')
                    if answer is not None:
                        m.need(set(answer) <= {'state','result'} and answer.get('state') in ('NOT_FOUND','UNCERTAIN','SUCCEEDED'), 'owned bootstrap receipt state')
                        if answer['state']=='SUCCEEDED':
                            row=answer['result']
                            m.need(row['status']=='PASS' and row['node']==configs[i]['binding']['node'], 'owned bootstrap receipt member')
                            if phase=='install':
                                m.need(row == dict(status='PASS',node=configs[i]['binding']['node'],descriptorSha256=request['descriptorSha256'],
                                    files=len(b.expected_files(configs[i]))), 'owned bootstrap import identity')
                            record.update(status='PASS',receipt=answer); return row
                    self.sleep(min(.05,max(0,deadline-self.clock())))
                    m.need(self.clock()<deadline and record['queries']<4096,'owned bootstrap query budget')
                    record['queries']+=1
                    try: answer=ep.bootstrap('query-'+phase,request,deadline)
                    except (ConnectionError,TimeoutError): answer=None
            except (Exception,KeyboardInterrupt) as error:
                record['failure']=dict(type=type(error).__name__,message=str(error)[:2000]); raise
            finally: c.write_once(self.root/f'node-{i+1}-{phase}.json',record,maximum=262144)
        try:
            for i in range(3): check(i,'bootstrap')
            exports=self.source.prepare(configs,deadline)
            m.need(len(exports)==3 and [v['node'] for v in exports]==[v['binding']['node'] for v in configs], 'owned bootstrap source members')
            requests=[]; files=[]
            for cfg,row in zip(configs,exports):
                m.need(set(row)=={'node','folder','descriptorSha256'},'owned bootstrap source fields')
                folder=c.directory(row['folder']); value=b.descriptor(folder,row['descriptorSha256'],cfg)
                files.append(value['files']); requests.append(dict(config=cfg,folder=str(folder),descriptorSha256=row['descriptorSha256']))
            m.need(all(v==files[0] for v in files),'owned bootstrap source/topology disagreement')
            c.write_once(self.root/'source.json',dict(exports=exports,files=files[0]),maximum=262144)
            if self.delivery is not None:
                for i,request in enumerate(requests):
                    check(i,'transfer')
                    requests[i]=self.delivery.deliver(request['folder'],request['descriptorSha256'],configs[i],endpoints[i],
                        deadline,self.root/f'node-{i+1}-transfer')
                    check(i,'transferred')
            for i,request in enumerate(requests):
                check(i,'install'); once(i,'install',request); check(i,'seeded')
            for i,request in enumerate(requests):
                check(i,'seal'); row=once(i,'seal',request); result['members'].append(row); check(i,'sealed')
            result['identity']=b.group_identity(result['members'],configs)
            identity=result['identity']
            m.need(set(identity)=={'sourceSha256','manifestSha256','genesisSha256'} and
                   all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in identity.values()) and
                   identity['sourceSha256']==m.sha(m.canonical({k:v for k,v in files[0].items() if k.startswith('source/')})),
                   'owned bootstrap sealed source identity')
            result.update(status='PASS',publicBootstrapVerified=True)
        except (Exception,KeyboardInterrupt) as error:
            result['failure']=dict(type=type(error).__name__,message=str(error)[:2000]); raise
        finally: c.write_once(self.root/'receipt.json',result,maximum=262144)
        return result

    def retention_files(self):
        if self.root is None: return
        allowed=FILES | {f'node-{n}-{p}-intent.json' for n in (1,2,3) for p in ('install','seal')}
        c.directory(self.root)
        for path in sorted(self.root.iterdir()):
            if self.delivery is not None and path.name in {f'node-{n}-transfer' for n in (1,2,3)}:
                for name,raw in self.delivery.retention_files(path):yield 'bootstrap/'+path.name+'/'+name,raw
                continue
            m.need(path.name in allowed and path.is_file() and not path.is_symlink() and path.stat().st_size<=262144,'owned bootstrap retention inventory')
            yield 'bootstrap/'+path.name,path.read_bytes()
