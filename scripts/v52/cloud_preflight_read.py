"""Fixed V5.2 read-only provider entry. No resource or control writes exist here."""
import argparse
from copy import deepcopy
import math
import os
from pathlib import Path
import time
from scripts.v51 import cloud_http as http, cloud_cleanup_credentials as exchange
from . import cloud_preflight as f, cloud_credentials as credentials, cloud_authority as a, cloud_inputs as inputs
from . import cloud_artifacts as artifacts
from .evidence import need, encoded, strict

ROOT = Path(__file__).resolve().parents[2]
_NATIVE = object()


class _Reader:
    def initialize(self, cfg, source, role, tokens, transport, clock, output=None):
        self.configuration = deepcopy(cfg); self.context = f.context(cfg, source, role)
        self.source, self.role = source, role
        self.tokens, self.transport, self.clock = tokens, transport, clock
        self.token = None; self.closed = False; self.calls = 0; self.phase = 'initial'
        self.output = Path(output) if output is not None else None
        if self.output is not None: self.output.mkdir()

    def guard(self):
        need(not self.closed and not self.tokens.closed, 'V5.2 preflight reader closed')
        need(encoded(f.context(self.configuration,self.source,self.role)) == encoded(self.context), 'V5.2 preflight configuration changed')
        bound = self.tokens.binding; selected = self.context['credentialSelection']
        need(bound['source']==self.source and all(bound[k]==v for k,v in selected.items()), 'V5.2 preflight credentials changed')
        if type(self) is NetworkReader:
            need(type(self.tokens) is credentials.NetworkCredentials and type(self.transport) is http.Network,
                 'V5.2 native read adapters changed')
        else:
            from .cloud_preflight_offline import Server
            need(type(self) is OfflineReader and type(self.tokens) is credentials.OfflineCredentials and
                 type(self.transport) is Server, 'V5.2 offline read adapters changed')

    def request(self, name, generation=None):
        self.guard()
        if name in ('lease','ledger'): return f.control_query(self.configuration, name, generation)
        need(generation is None, 'V5.2 unexpected read generation')
        queries = f.plan(self.configuration, self.role); need(name in queries, 'V5.2 provider read outside scope')
        return queries[name]

    def remaining(self, end):
        value = end-self.clock()
        need(type(value) in (int,float) and math.isfinite(value) and 0<value<=30, 'V5.2 original read deadline')
        return value

    def read(self, name, *, generation=None, deadline=None):
        query = self.request(name, generation); self.phase = name
        end = self.clock()+30 if deadline is None else deadline
        for attempt in range(2):
            self.remaining(end)
            if self.token is None or self.clock() >= self.token.usable_until:
                token = self.tokens(self.remaining(end))
                need(type(token) is http.AccessToken and math.isfinite(token.usable_until) and
                     token.usable_until > self.clock(), 'V5.2 read credential expiry')
                exchange.bearer(token.value); self.token = token
            # Refresh may have taken time or exposed source/configuration drift.
            need(encoded(self.request(name,generation)) == encoded(query), 'V5.2 read scope changed after refresh')
            need(self.calls < 128, 'V5.2 preflight exchange count'); self.calls += 1
            request=dict(query, body=deepcopy(query['body']))
            if self.output is not None: artifacts.save(self.output/f'{self.calls:03}-request.json',request)
            status, raw = self.transport.send(query['method'],query['url'],
                {'Authorization':'Bearer '+self.token.value,'Content-Type':'application/json'},
                encoded(query['body']) if query['body'] is not None else None,
                self.remaining(end),query['maximum'])
            self.remaining(end)
            need(type(status) is int and type(raw) is bytes and len(raw)<=query['maximum'], 'V5.2 read response bound/type')
            # Never retain error bodies, which may contain arbitrary provider text.
            if self.output is not None:
                artifacts.save(self.output/f'{self.calls:03}-response.json',dict(status=status,bytes=len(raw) if status==200 else 0))
                if status==200:
                    with (self.output/f'{self.calls:03}-body.json').open('xb') as stream: stream.write(raw)
            if status==401:
                self.token = None
                if attempt==0: continue  # Every generated request, including CRM POST, is read-only.
            if status==404 and query['absent']: return None
            if status!=200: raise http.ApiError(status, query['method'])
            return raw

    def object(self, name):
        end=self.clock()+30
        raw=self.read(name,deadline=end); first=strict(raw) if raw is not None else None
        identity=f.control_metadata(self.configuration,name,first)
        if identity is None: return None
        generation,size=identity
        raw=self.read(name,generation=generation,deadline=end)
        need(len(raw)==size, 'V5.2 control observation truncated')
        value=strict(raw); second=self.read(name,deadline=end)
        need(second is not None and encoded(strict(second))==encoded(first), 'V5.2 control metadata changed')
        return f.snapshot(dict(generation=int(generation),value=value),name)

    def close(self):
        if self.closed:return
        self.closed=True;self.token=None
        try:self.transport.close()
        finally:self.tokens.close()


class OfflineReader(_Reader):
    execution='offline-v52-provider-observations'
    def __init__(self, cfg, source, role, env, descriptor, invocation, issuer, server, output=None):
        from .cloud_preflight_offline import Server
        need(type(server) is Server and server.clock is invocation.clock, 'V5.2 offline observation server')
        tokens=credentials.OfflineCredentials(cfg['provider'],cfg['projectNumber'],env,descriptor,invocation,issuer,
            role=role,source=source,checkout_sha=source)
        self.initialize(cfg,source,role,tokens,server,invocation.clock.seconds,output)


class NetworkReader(_Reader):
    execution='native-v52-provider-observations'
    def __init__(self,cfg,source,role,env,output,ticket):
        need(ticket is _NATIVE,'V5.2 native preflight factory required')
        f.context(cfg,source,role)
        tokens=credentials.open_network(cfg['provider'],cfg['projectNumber'],env,role=role,source=source)
        try:self.initialize(cfg,source,role,tokens,http.Network(),time.monotonic,output)
        except BaseException:tokens.close();raise


def collect(reader, *, wall):
    reader.guard(); started=int(wall()); before={name:reader.object(name) for name in ('ledger','lease')}
    rows={}
    for name in f.plan(reader.configuration,reader.role):
        rows[name]=strict(reader.read(name))
        if name.endswith('Permissions'):
            need(f.permissions(rows[name],reader.role,name)['status']=='PASS','V5.2 missing/forbidden '+name)
    after={name:reader.object(name) for name in ('lease','ledger')}
    value=dict(schema='gse-v52-provider-observations-v1',context=deepcopy(reader.context),execution=reader.execution,
        startedAt=started,completedAt=int(wall()),planSha256=f.digest(encoded(f.plan(reader.configuration,reader.role))),
        observations=rows,controlBefore=before,controlAfter=after,credentials=reader.tokens.receipt())
    return value


def source_configuration(source):
    need(credentials.checkout(time.monotonic()+30,time.monotonic)==source,'V5.2 preflight source changed')
    path=ROOT/f.CONFIG_PATH
    raw=inputs.regular(path,65536); cfg=strict(raw); f.configuration(cfg)
    # The fixed path must actually be tracked by this exact clean source.
    tracked=inputs.build.git(ROOT,'show',source+':'+f.CONFIG_PATH)
    need(tracked==raw,'V5.2 preflight configuration not in source')
    return cfg


def collect_native(source, output, *, role='runner'):
    """No injected transport/token/configuration/clock; no provider mutations."""
    output=Path(output); need(not any(p.is_symlink() for p in (output,*output.parents)), 'V5.2 preflight output symlink')
    output.mkdir(parents=True,exist_ok=False); reader=None; phase='source'
    try:
        cfg=source_configuration(source); phase='credentials'
        reader=NetworkReader(cfg,source,role,dict(os.environ),output/'reads',_NATIVE)
        phase='observations'; value=collect(reader,wall=time.time)
        phase='final-source'
        need(encoded(source_configuration(source))==encoded(cfg),'V5.2 preflight configuration changed')
        reader.tokens.recheck(time.monotonic()+30)
        value['credentials']=reader.tokens.receipt();value['completedAt']=int(time.time())
        artifacts.save(output/'observations.json',value);phase='evaluation'
        receipt=f.evaluate(cfg,source,role,value,now=int(time.time()))
        artifacts.save(output/'receipt.json',receipt);return receipt
    except BaseException as error:
        label=reader.phase if phase=='observations' and reader is not None else phase
        result=dict(status='FAIL',phase=label,code='V52_PREFLIGHT_'+label.upper().replace('-','_')+'_REJECTED',
                    errorType=type(error).__name__,**f.FLAGS)
        if type(error) is http.ApiError:result['httpStatus']=error.status
        if type(error) in (credentials.ContextError,exchange.CredentialError):result['credentialCode']=error.reason_code
        artifacts.save(output/'failure.json',result)
        raise
    finally:
        if reader is not None:reader.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--role',choices=tuple(credentials.ROLES),default='runner');args=parser.parse_args()
    result=collect_native(args.source,args.output,role=args.role);print(encoded(result).decode())
    raise SystemExit(0 if result['status']=='PREFLIGHT_OBSERVED_NOT_ADMITTED' else 2)
