"""Concrete synthetic provider reader. No real resources or permission evidence."""
from copy import deepcopy
from urllib.parse import urlsplit, parse_qs, unquote
from . import cloud_preflight as f, cloud_authority as a
from .evidence import need, encoded, strict


class Server:
    offline=True
    def __init__(self,cfg,role,clock):
        self.configuration=deepcopy(cfg); self.clock=clock; self.calls=[]; self.closed=False
        c=cfg['provider']; paths=f.plan(cfg,role)
        self.rows={name:dict(permissions=sorted(f.permission_spec(role,name)[0])) for name in ('projectPermissions','bucketPermissions')}
        self.rows['bucket']=dict(name=c['bucket'],projectNumber=cfg['projectNumber'],location='US-WEST4',
            iamConfiguration=dict(uniformBucketLevelAccess=dict(enabled=True)))
        if role=='runner':
            names=dict(project=c['project'],region=c['region'],zone=c['zone'],machine=c['machineType'],diskType=c['diskType'],
                       network=c['network'],subnetwork=c['subnetwork'],image=c['imageName'])
            for i,(name,value) in enumerate(names.items()):
                self.rows[name]=dict(id=str(100+i),name=value,selfLink=paths[name]['url'].split('?',1)[0])
            regional={'CPUS':1000,'N2_CPUS':1000,'SSD_TOTAL_GB':10000,'INSTANCES':1000}
            self.rows['project']['quotas']=[dict(metric=k,limit=v,usage=0) for k,v in {'CPUS_ALL_REGIONS':1000,'FIREWALLS':1000}.items()]
            self.rows['region'].update(status='UP',quotas=[dict(metric=k,limit=v,usage=0) for k,v in regional.items()])
            self.rows['zone'].update(status='UP',region=self.rows['region']['selfLink'])
            self.rows['machine'].update(guestCpus=4,memoryMb=16384)
            self.rows['subnetwork'].update(network=self.rows['network']['selfLink'],region=self.rows['region']['selfLink'],
                                          privateIpGoogleAccess=True,ipCidrRange='10.52.0.0/24')
            self.rows['image'].update(id=c['imageId'],status='READY',architecture='X86_64',diskSizeGb='10')
        self.routes={v['url']:(name,v) for name,v in paths.items()}
        self.objects={};self.change=lambda server,call:None;self.reply=None

    def send(self,method,url,headers,body,timeout,maximum):
        need(not self.closed,'offline reader closed')
        need(headers['Authorization'].startswith('Bearer '),'offline reader bearer')
        call=dict(method=method,url=url,body=strict(body) if body is not None else None,timeout=timeout,maximum=maximum)
        self.calls.append(call);self.change(self,call)
        if self.reply is not None:return self.reply
        if url in self.routes:
            name,expected=self.routes[url]
            need(method==expected['method'] and call['body']==expected['body'] and maximum==expected['maximum'], 'offline provider query')
            return 200,encoded(self.rows[name])
        prefix=f.p.STORAGE+'storage/v1/b/'+self.configuration['provider']['bucket']+'/o/'
        need(method=='GET' and body is None and url.startswith(prefix),'offline provider route')
        key=unquote(urlsplit(url).path.rsplit('/',1)[-1]);need(key in (a.LEASE,a.LEDGER),'offline named control')
        name='lease' if key==a.LEASE else 'ledger';params=parse_qs(urlsplit(url).query)
        if key not in self.objects:return 404,b''
        generation,value=self.objects[key];raw=encoded(value)
        if 'alt' in params:
            need(url==f.control_query(self.configuration,name,str(generation))['url'],'offline generation selector')
            return 200,raw
        need(url==f.control_query(self.configuration,name)['url'],'offline object metadata')
        return 200,encoded(dict(name=key,bucket=self.configuration['provider']['bucket'],generation=str(generation),
                               size=str(len(raw)),contentType='application/json'))

    def close(self):self.closed=True
