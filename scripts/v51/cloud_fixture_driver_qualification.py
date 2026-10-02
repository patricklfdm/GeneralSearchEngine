"""Offline preparation/probe/expiry evidence; never invokes network credentials."""
import argparse
from pathlib import Path
from urllib.parse import unquote,urlsplit,parse_qs
from . import cloud_fixture_driver as f, cloud_object_probes as probes
from . import cloud_http_fake as fake, cloud_fake, cloud_http as h, cloud_native_authority as n
from . import cloud_cleanup_entry_qualification as entries, cloud_cleanup_entry as entry
from . import cloud_cleanup_observation as observations, cloud_cleanup_qualification as q
from . import cloud_native_cleanup as cleanup, performance_model as m, remote_command as c


def fixture(source='c'*40):
    clock=cloud_fake.Clock();invocation=entries.fixture(fake.configuration(),'manual');cfg=invocation['configuration'];invocation.update(source=source,checkout=source)
    invocation['env'].update(GITHUB_SHA=source,GITHUB_WORKFLOW_SHA=source)
    http=fake.Http(cfg['provider']);api=h.Api(transport=http,tokens=lambda _: 'offline-token',clock=clock.seconds)
    before=observations.capture(cfg,invocation['source'],api=api,wall=clock.wall)
    prices=dict(observedAt=clock.wall(),expiresAt=clock.wall()+86400,region='us-west4',diskType='pd-balanced',
                diskMicrousdPerGiBHour=200,pricedThroughSeconds=14400,
                otherCostsMicrousd=dict(requests=1000,retention30Days=1000,actions=1000,failureOverhang=1000),
                sources=['https://cloud.google.com/compute/disks-image-pricing'])
    value=f.make(cfg,invocation['source'],'operator@example.com',q.KEY,prices,before,now=clock.wall(),attempt='a'*32,sequence='b'*32,offline=True)
    policy=f.PreparationApi(value,clock.wall(),transport=http,tokens=lambda _: 'offline-token',clock=clock.seconds)
    return value,clock,http,api,policy,invocation


class ManualTransport:
    offline=True
    def __init__(self,http,request,denial=403,*,preconditions_first=True,allow=()):
        self.http,self.keys,self.denial=http,f.objects(request),denial
        self.preconditions_first=preconditions_first;self.allow=set(allow);self.requests=[]
    def send(self,method,url,headers,body,timeout,maximum):
        parsed=urlsplit(url);query=parse_qs(parsed.query)
        key=query['name'][0] if method=='POST' else unquote(parsed.path.split('/o/',1)[-1])
        self.requests.append(dict(method=method,key=key,query=query))
        # The real provider returned 412 before the expected permission denial.
        # Exercise both orders without applying a mutation during this check.
        if self.preconditions_first and 'ifGenerationMatch' in query:
            current=self.http.objects.get(key);generation=current[0] if current else 0
            supplied=int(query['ifGenerationMatch'][0])
            if supplied!=generation or supplied==0 and method!='POST':return 412,b''
        forbidden=key==self.keys['outside'] or key==self.keys['existing'] and method in ('POST','DELETE')
        if forbidden and (method,key) not in self.allow:
            return self.denial,b''
        return self.http.send(method,url,headers,body,timeout,maximum)


def qualify(output, source):
    root=Path(output);root.mkdir(parents=True,exist_ok=False);cases=[]
    for case in ('prepared-probes-expiry','lost-create-expiry','precondition-inconclusive',
                 'unexpected-canary-delete','lost-canary-overwrite'):
        out=root/case;out.mkdir();value,clock,http,reader,api,invocation=fixture(source)
        c.write_once(out/'before.json',q.snapshot(http))
        send=http.send
        if case=='lost-create-expiry':
            def lose(method,url,*args):
                result=send(method,url,*args)
                if method=='POST' and url.startswith('https://compute.googleapis.com'):raise ConnectionError('offline lost original insert response')
                return result
            http.send=lose
        prepared=f.execute(value,api,out/'prepare',now=clock.wall(),sleep=clock.sleep)
        http.send=send
        m.need(prepared['status']==('FAIL' if case=='lost-create-expiry' else 'PREPARED'),'preparation outcome')
        m.need(http.inserts==1 and len(http.resources)==1,'single disk allocation count')
        if case!='lost-create-expiry':
            cfg=value['configuration'];binding=entry.identity(cfg,invocation['env'],trigger='manual',source=source,checkout=source)
            key=f.objects(value['request'])['existing']
            allow=[('DELETE',key)] if case=='unexpected-canary-delete' else [('POST',key)] if case=='lost-canary-overwrite' else []
            transport=ManualTransport(http,value['request'],412 if case=='precondition-inconclusive' else 403,allow=allow)
            if case=='lost-canary-overwrite':
                original=transport.send
                def lose_canary(method,url,*args):
                    result=original(method,url,*args)
                    if method=='POST' and parse_qs(urlsplit(url).query).get('name')==[key]:raise ConnectionError('offline lost canary response')
                    return result
                transport.send=lose_canary
            protected={k:v for k,v in http.objects.items() if k not in f.objects(value['request']).values()}
            probe=probes.OfflineApi(cfg,binding,n.validate_request(value['request']),transport=transport,
                                   tokens=lambda _: 'offline-token',clock=clock.seconds)
            result=probes.run(cfg,probe,out/'probes',now=clock.wall())
            c.write_once(out/'probe-http.json',transport.requests)
            after=probes.capture(cfg,prepared['probeManifest'],api=reader,wall=clock.wall);c.write_once(out/'objects-after.json',after)
            m.need(result['status']==('PROBES_RECORDED' if case=='prepared-probes-expiry' else 'FAIL'),'probe outcome')
            if case=='prepared-probes-expiry':c.write_once(out/'object-review.json',probes.review(cfg,result,after))
            elif case=='precondition-inconclusive':m.need(result['cases'][-1]['httpStatus']==412,'precondition masqueraded as permission denial')
            elif case=='unexpected-canary-delete':
                m.need(key not in http.objects and result['cases'][-1]['outcome']=='UNEXPECTED_SUCCESS','unexpected delete evidence')
            else:
                m.need(http.objects[key][0]!=prepared['probeManifest']['baseline']['existing'][0] and
                       result['failure']==dict(phase='overwrite-denied',type='ConnectionError'),'lost overwrite evidence')
            m.need(all(http.objects.get(k)==v for k,v in protected.items()),'probe changed control state')
        preserved=q.snapshot(http);c.write_once(out/'prepared-state.json',preserved)
        for elapsed,label in ((0,'active'),(5400,'grace'),(1080,'expired')):
            clock.sleep(elapsed)
            result=cleanup.reconcile(api.cfg,reader,out/label,trigger='manual',now=clock.wall())
            m.need(result['status']==('PASS' if label=='expired' else 'WAITING'),'reconcile outcome')
            if label!='expired':m.need(q.snapshot(http)==preserved,'active/grace state changed')
        total,attempts=n.inspect_ledger(f.Store(api.cfg,reader,value['request']).get(n.LEDGER)[1])
        m.need(total==f.COST and attempts[n.validate_request(value['request'])]['status']=='FAIL' and
               not http.resources and http.inserts==1,'cleanup lost accounting or repeated allocation')
        c.write_once(out/'after.json',q.snapshot(http));c.write_once(out/'http.json',http.requests)
        cases.append(dict(case=case,status='PASS',insertRequests=1,retainedCostMicrousd=total))
    receipt=dict(status='PASS',execution='offline-fixture-driver-qualification',source=source,cases=cases,
                 paidCloud=False,applied=False,**f.BOUNDARY)
    c.write_once(root/'receipt.json',receipt);print(m.canonical(receipt).decode());return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--source',required=True);args=parser.parse_args();qualify(args.output,args.source)
