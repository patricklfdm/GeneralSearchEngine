"""Fixed GET-only restoration of five selected original native attempts.

No object list, writes, arbitrary URLs, workload execution or acceptance entry.
The native factory owns credentials; offline models exercise the same decoder.
"""
from copy import deepcopy
import os
from pathlib import Path
import re
import time
from scripts.v51 import cloud_http as h
from . import cloud_authority as a,cloud_control as control,cloud_provider as p,cloud_suite as suite
from . import cloud_credentials as credentials,cloud_preflight_read as preflight,cloud_inputs as inputs
from . import cloud_artifacts as artifacts,cloud_evidence_parts as parts,cloud_retention as retention
from . import cloud_read_retry
from .evidence import need,encoded,digest,strict


class _Api(cloud_read_retry.Api):
    read_scope='evidence-read'
    def __init__(self,owner,**kw):self.owner=owner;super().__init__(**kw)
    def authorize(self,method,endpoint,body):
        self.owner.guard()
        need(method=='GET' and body is None and endpoint in self.owner.allowed,
             'V5.2 evidence read outside selected immutable objects')


class _Objects:
    def initialize(self,cfg,source,transport,tokens,clock,output):
        self.cfg=deepcopy(cfg);self.source=deepcopy(source);self.configuration=preflight.f.configuration(cfg)
        self.base=p.STORAGE+'storage/v1/b/'+cfg['provider']['bucket']+'/o/'
        self.allowed=set();self.keys=set();self.receipts=[];self.closed=False;self.output=Path(output)
        self.output.mkdir(parents=True,exist_ok=False)
        self.api=_Api(self,transport=transport,tokens=tokens,clock=clock)
        self.allow(a.LEDGER)
    def guard(self):
        need(not self.closed and preflight.f.configuration(self.cfg)==self.configuration and
             type(self.api) is _Api and self.api.owner is self,'V5.2 evidence reader closed/configuration')
        if type(self) is _NativeObjects:
            token=self.api.tokens;need(type(token) is credentials.NetworkCredentials and type(self.api.transport) is h.Network and
                not token.closed and token.binding['source']==self.source['source'] and all(
                    token.binding[k]==v for k,v in credentials.selection(self.cfg['provider'],self.cfg['projectNumber'],'runner').items()),
                'V5.2 evidence native reader changed')
        else:
            from .cloud_provider_offline import Server
            need(type(self) is OfflineObjects and type(self.api.transport) is Server,'V5.2 evidence offline reader changed')
    def endpoint(self,key):return self.base+p.url.quote(key,safe='')
    def allow(self,key):
        need(type(key) is str and key.startswith(a.PREFIX) and len(key)<=1024 and
             re.fullmatch('[a-zA-Z0-9./_-]+',key) and all(v not in ('','..','.') for v in key.split('/')),
             'V5.2 evidence object key')
        self.keys.add(key);self.allowed.add(self.endpoint(key))
    def get(self,key):
        self.guard();need(key in self.keys and len(self.receipts)<len(suite.MEMBERS)*(parts.MAX_PARTS+8)+2,'V5.2 evidence original object count/scope')
        endpoint=self.endpoint(key);end=self.api.clock()+30
        metadata=self.api.call('GET',endpoint,deadline=end,maximum=65536)
        need(type(metadata) is dict and metadata.get('bucket')==self.cfg['provider']['bucket'] and metadata.get('name')==key,
             'V5.2 evidence object identity')
        generation=a.numeric(metadata.get('generation'));size=metadata.get('size')
        need(type(size) is str and re.fullmatch('[1-9][0-9]{0,7}',size) and int(size)<=p.MAX_OBJECT and
             metadata.get('contentType')=='application/json','V5.2 evidence object size/type')
        media=p.query(endpoint,alt='media',generation=generation,ifGenerationMatch=generation);self.allowed.add(media)
        try:raw=self.api.call('GET',media,deadline=end,raw=True,maximum=p.MAX_OBJECT)
        finally:self.allowed.discard(media)
        need(len(raw)==int(size),'V5.2 evidence original object truncated')
        second=self.api.call('GET',endpoint,deadline=end,maximum=65536)
        need(second==metadata,'V5.2 evidence original object generation changed')
        value=strict(raw);need(type(value) is dict,'V5.2 evidence original JSON object')
        row=dict(key=key,generation=int(generation),bytes=len(raw),sha256=digest(raw))
        self.receipts.append(row);artifacts.save(self.output/f'{len(self.receipts):05}.json',row)
        return dict(generation=int(generation),value=value)
    def close(self):
        self.closed=True;self.api.token=None;self.api.expires=0
        self.api.transport.close() if hasattr(self.api.transport,'close') else None
        if hasattr(self.api.tokens,'close'):self.api.tokens.close()


class OfflineObjects(_Objects):
    """Synthetic HTTP responses, never a native credential or cloud receipt."""
    def __init__(self,cfg,source,server,output):
        from .cloud_provider_offline import Server
        need(type(server) is Server and server.config==cfg['provider'],'V5.2 evidence offline fixture')
        self.initialize(cfg,source,server,lambda timeout:'offline-not-a-credential',server.clock,output)


class _NativeObjects(_Objects):
    def __init__(self,cfg,source,output):
        tokens=credentials.open_network(cfg['provider'],cfg['projectNumber'],dict(os.environ),role='runner',source=source['source'])
        try:self.initialize(cfg,source,h.Network(),tokens,time.monotonic,output)
        except BaseException:tokens.close();raise


def restore(reader,chosen,output,*,progress=lambda stage,**kw:None):
    """Select hashes from one original ledger, then restore their complete bytes."""
    reader.guard();need(type(chosen) is dict and set(chosen)==set(suite.MEMBERS),'V5.2 evidence selected nine-execution map')
    need(len(set(chosen.values()))==len(suite.MEMBERS),'V5.2 evidence repeated original request')
    for sha in chosen.values():a.hex_value(sha)
    output=Path(output);need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 evidence restore output link')
    output.mkdir(parents=True,exist_ok=False);rows=[];receipt=dict(status='FAIL',fullRemoteQualification=False,paidCloud=False)
    try:
        original=reader.get(a.LEDGER);artifacts.save(output/'ledger-before.json',original)
        view=a.inspect_ledger(original['value'],domain='native');requests={}
        for name,sha in chosen.items():
            entry=view['attempts'].get(sha);need(entry is not None and entry['status']=='PASS','V5.2 evidence original attempt not successful')
            req=entry['request'];bound=req['selection']['binding']
            need(req['selection']['member']['name']==name and bound['source']==reader.source['source'] and
                 bound['checkoutSha256']==reader.source['checkoutSha256'] and req['configurationSha256']==p.config(reader.cfg['provider']),
                 'V5.2 evidence selected request source/configuration')
            requests[name]=req
        suite.complete_selection([v['selection'] for v in requests.values()])
        for name,req in requests.items():
            progress('restore-member',name=name,completed=len(rows));root=output/name;root.mkdir()
            prefix=control.attempt_key(req);reader.allow(prefix+'completion.json');reader.allow(p.context_key(req))
            context=reader.get(p.context_key(req))
            need(context['value']==p.context(reader.cfg['provider'],req,domain='native'),'V5.2 evidence original provider context')
            completed=reader.get(prefix+'completion.json');a.validate_completion(completed['value'],req)
            sha=chosen[name];terminal=next(v for v in original['value']['entries'] if v['kind']=='FINISHED' and v['requestSha256']==sha)
            need(completed['value']['status']=='PASS' and terminal['completionSha256']==digest(encoded(completed['value'])),
                 'V5.2 evidence original terminal hash')
            key=control.cleanup_key(req,completed['value']['cleanupSha256']);reader.allow(key);clean=reader.get(key)
            need(digest(encoded(clean['value']))==completed['value']['cleanupSha256'],'V5.2 evidence original cleanup hash')
            key=retention.prefix(req)+'manifest.json';reader.allow(key);manifest=reader.get(key)
            parts.validate(manifest['value'],req)
            need(digest(encoded(manifest['value']))==completed['value']['evidenceSha256'],'V5.2 evidence original manifest hash')
            for label,value in (('context',context),('completion',completed),('cleanup',clean),('manifest',manifest)):
                artifacts.save(root/(label+'.json'),value)
            def chunk(ordinal):
                progress('restore-part',name=name,completed=ordinal,total=len(manifest['value']['parts']))
                key=retention.chunk_key(req,ordinal);reader.allow(key);return reader.get(key)['value']
            parts.restore(manifest['value'],req,chunk,root/'files')
            rows.append(dict(root=str(root/'files'),request=req,manifest=manifest['value'],completed=completed['value'],cleanup=clean['value']))
        final=reader.get(a.LEDGER);a.inspect_ledger(final['value'],domain='native')
        count=len(original['value']['entries']);need(final['generation']>=original['generation'] and
            final['value']['entries'][:count]==original['value']['entries'] and
            (final['generation']!=original['generation'] or final['value']==original['value']),
            'V5.2 evidence ledger history changed during restoration')
        artifacts.save(output/'ledger-after.json',final)
        receipt.update(status='ORIGINALS_RESTORED_NOT_QUALIFIED',execution='native-v52-evidence-reads' if type(reader) is _NativeObjects else 'offline-v52-evidence-reads',
            source=reader.source,selected=chosen,objects=len(reader.receipts),originalLedgerSha256=digest(encoded(original)),
            finalLedgerSha256=digest(encoded(final)),readIndexSha256=digest(encoded(reader.receipts)))
        return dict(inputs=rows,ledger=final['value'],receipt=receipt)
    except BaseException as error:
        receipt['failure']=dict(type=type(error).__name__,**cloud_read_retry.failure(error));raise
    finally:
        receipt['restoredMembers']=[v['request']['selection']['member']['name'] for v in rows]
        artifacts.save(output/'receipt.json',receipt)


def restore_native(source,chosen,output,*,progress=lambda stage,**kw:None):
    """Internal GET-only factory; no externally supplied credentials or provider."""
    cfg=preflight.source_configuration(source);binding=inputs.checkout(preflight.ROOT,source);output=Path(output)
    need(not any(p.is_symlink() for p in (output,*output.parents)),'V5.2 evidence native output link')
    output.mkdir(parents=True,exist_ok=False);reader=None
    receipt=dict(status='FAIL',fullRemoteQualification=False,paidCloud=False);failure=None
    try:
        reader=_NativeObjects(cfg,binding,output/'reads');value=restore(reader,chosen,output/'originals',progress=progress)
        need(preflight.source_configuration(source)==cfg and inputs.checkout(preflight.ROOT,source)==binding,
             'V5.2 evidence source changed during restoration')
        reader.api.tokens.recheck(time.monotonic()+30)
        artifacts.save(output/'credentials.json',reader.api.tokens.receipt())
        receipt=deepcopy(value['receipt']);receipt['configurationSha256']=preflight.f.configuration(cfg)
        return value
    except BaseException as error:
        failure=error;receipt['failure']=dict(type=type(error).__name__);raise
    finally:
        try:
            if reader is not None:reader.close()
        finally:
            try:artifacts.save(output/'receipt.json',receipt)
            except BaseException:
                if failure is None:raise
