"""Deterministic HTTP fixture, with no sockets, SDK, credentials or subprocesses.

It models wire responses rather than calling production resource/body decoders.
This is not a provider emulator or live compatibility qualification.
"""
from copy import deepcopy
import re
import threading
import urllib.parse as url
from .evidence import need, encoded, strict


class Server:
    offline = True

    def __init__(self, configuration):
        self.config = deepcopy(configuration); self.objects = {}; self.resources = {}; self.operations = {}
        self.events = []; self.serial = 100; self.seconds = 10.0; self.lock = threading.RLock()
        self.fault = lambda stage, request: None
        self.image = dict(name=configuration['imageName'],id=configuration['imageId'],status='READY')

    def clock(self): return self.seconds
    def sleep(self, seconds): self.seconds += seconds

    def send(self, method, endpoint, headers, body, timeout, maximum):
        need(headers.get('Authorization') == 'Bearer offline-not-a-credential', 'offline fixture credential')
        record = dict(method=method,url=endpoint,body=body)
        self.events.append(deepcopy(record))
        replaced = self.fault('before', record)
        if replaced is not None: return replaced
        with self.lock: result = self.handle(method, endpoint, headers, body)
        replaced = self.fault('after', record)
        return result if replaced is None else replaced

    def metadata(self, key, row):
        return dict(bucket=self.config['bucket'],name=key,generation=str(row[0]),size=str(len(row[1])),contentType=row[2])

    def handle(self, method, endpoint, headers, body):
        parsed = url.urlsplit(endpoint); params = url.parse_qs(parsed.query,strict_parsing=True) if parsed.query else {}
        need(all(len(v)==1 for v in params.values()), 'offline duplicate query')
        q = {k:v[0] for k,v in params.items()}; path = parsed.path
        if parsed.netloc == 'storage.googleapis.com':
            base = '/storage/v1/b/'+self.config['bucket']+'/o/'
            upload = '/upload/storage/v1/b/'+self.config['bucket']+'/o'
            if method=='POST' and path==upload:
                need(set(q)=={'uploadType','name','ifGenerationMatch'} and q['uploadType']=='media','offline upload query')
                key=q['name']; old=self.objects.get(key)
                if int(q['ifGenerationMatch']) != (old[0] if old else 0): return 412,b''
                self.serial+=1;row=(self.serial,body,headers['Content-Type']);self.objects[key]=row
                return 200,encoded(self.metadata(key,row))
            need(path.startswith(base),'offline bucket/path'); key=url.unquote(path[len(base):]); row=self.objects.get(key)
            if row is None: return 404,b''
            if method=='GET':
                if not q:return 200,encoded(self.metadata(key,row))
                need(set(q)=={'alt','generation','ifGenerationMatch'} and q['alt']=='media','offline media query')
                if q['generation']!=str(row[0]) or q['ifGenerationMatch']!=str(row[0]):return 412,b''
                return 200,row[1]
            need(method=='DELETE' and set(q)=={'ifGenerationMatch'},'offline object mutation')
            if q['ifGenerationMatch']!=str(row[0]):return 412,b''
            del self.objects[key];return 204,b''
        need(parsed.netloc=='compute.googleapis.com','offline endpoint')
        image_path='/compute/v1/projects/'+self.config['imageProject']+'/global/images/'+self.config['imageName']
        if method=='GET' and path==image_path:return 200,encoded(self.image)
        base='/compute/v1/projects/'+self.config['project']
        scopes=(base+'/global',base+'/zones/'+self.config['zone'])
        scope=next((s for s in scopes if path.startswith(s+'/')),None);need(scope is not None,'offline compute scope')
        suffix=path[len(scope)+1:].split('/')
        if suffix[0]=='operations':
            need(method=='GET','offline operation mutation')
            if len(suffix)==2:
                op=self.operations.get((scope,suffix[1]));return (404,b'') if op is None else (200,encoded(op))
            need(set(q)=={'filter','maxResults'} and q['maxResults']=='100','offline operation query')
            match=re.fullmatch('clientOperationId = "([0-9a-f-]{36})"',q['filter']);need(match is not None,'offline operation filter')
            return 200,encoded(dict(items=[v for (s,_),v in self.operations.items() if s==scope and v['clientOperationId']==match[1]]))
        kind=suffix[0];need(kind in ('firewalls','disks','instances'),'offline resource kind')
        if method=='POST':
            need(len(suffix)==1 and set(q)=={'requestId'},'offline insert target');value=strict(body);name=value['name']
            key=(scope,kind,name)
            if key in self.resources:return 409,b''
            self.serial+=1;identity=str(self.serial);observed=deepcopy(value);observed['id']=identity
            if kind=='disks':
                observed['status']='READY'
                if 'sourceImage' in observed:observed['sourceImageId']=self.config['imageId']
            if kind=='instances':
                observed['status']='RUNNING';observed['networkInterfaces'][0]['networkIP']='10.0.0.'+str(self.serial%200+1)
            self.resources[key]=observed
            return 200,encoded(self.operation(scope,kind,name,identity,q['requestId'],'insert'))
        need(len(suffix)==2,'offline resource address');address=suffix[1]
        matches=[(k,v) for k,v in self.resources.items() if k[:2]==(scope,kind) and (v['id']==address or k[2]==address)]
        if not matches:return 404,b''
        need(len(matches)==1,'offline ambiguous resource');key,value=matches[0]
        if method=='GET':need(not q,'offline resource GET query');return 200,encoded(value)
        need(method=='DELETE' and set(q)=={'requestId'} and re.fullmatch('[1-9][0-9]*',address), 'offline name-based delete')
        del self.resources[key]
        return 200,encoded(self.operation(scope,kind,value['name'],value['id'],q['requestId'],'delete'))

    def operation(self, scope, kind, name, identity, request, action):
        value=dict(name='operation-'+request,clientOperationId=request,operationType=action,
            targetLink='https://www.googleapis.com'+scope+'/'+kind+'/'+name,targetId=identity,status='DONE')
        self.operations[(scope,value['name'])]=value
        return value
