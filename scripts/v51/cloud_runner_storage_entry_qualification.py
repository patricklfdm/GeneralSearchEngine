"""Offline preparation + Runner storage + independent reader qualification."""
import argparse
from copy import deepcopy
from pathlib import Path
from . import cloud_runner_storage as s, cloud_runner_storage_plan as plan, cloud_runner_storage_entry as entry
from . import cloud_runner_storage_qualification as storage_q, cloud_cleanup_qualification as cleanup_q
from . import cloud_cleanup_observation as observation, cloud_http_fake as f, cloud_http as h, cloud_fake
from . import cloud_native_authority as n, cloud_preflight as p, cloud_gcp as g, performance_model as m
from .remote_command import read, write_once


def fixture(*,source='1'*40,now=None,cfg=None):
    cfg=read(p.CONFIG) if cfg is None else deepcopy(cfg);clock=cloud_fake.Clock();http=f.Http(cfg['provider'])
    if now is not None:clock.now=(now-10000)*10**9
    api=h.Api(transport=http,tokens=lambda _: 'offline-token',clock=clock.seconds)
    old=n.request(source,'2'*64,g.config(cfg['provider']),'3'*32,'4'*32,'experiment',now=clock.wall(),guest_access_sha256='5'*64)
    ledger=n.reserve(n.empty_ledger(),old,dict(previousCostMicrousd=0,maximumCostMicrousd=12_000_000))
    ledger=n.finish(ledger,old,s.completion(old));http.objects[n.LEDGER]=(1000,m.canonical(ledger),'application/json')
    before=observation.capture(cfg,source,api=api,wall=clock.wall)
    pricing=dict(observedAt=clock.wall(),expiresAt=clock.wall()+86400,pricedThroughSeconds=6480,retentionDays=30,
        stages={stage:dict(requests=100000,retention=100000,actions=100000,failureOverhang=100000) for stage in ('prepare','run')},
        sources=['https://cloud.google.com/storage/pricing','https://docs.github.com/en/billing'])
    value=plan.make(cfg,source,'operator@example.org',pricing,before,now=clock.wall(),
        identities={key:character*32 for key,character in zip(('prepareAttempt','prepareSequence','runAttempt','runSequence'),'6789')},offline=True)
    preparer=plan.OfflinePreparation(value,transport=http,clock=clock.seconds,now=clock.wall())
    return cfg,clock,http,value,preparer


def runner(manifest,http,clock):
    value=manifest['plan'];req=value['requests']['run']
    backend=storage_q.Http(value['configuration']['provider'],req)
    backend.objects=deepcopy(http.objects);backend.serial=http.serial
    api=s.OfflineApi(backend.configuration,req,manifest['baseline'],maximum_cost=plan.COST,transport=backend,clock=clock.seconds)
    return api,backend


def independent(http,clock):
    reader=f.Http(http.configuration);reader.objects=deepcopy(http.objects);reader.serial=http.serial
    return h.Api(transport=reader,tokens=lambda _: 'independent-offline-token',clock=clock.seconds)


def qualify(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);rows=[]
    cfg,clock,http,value,api=fixture()
    prepared=plan.prepare(api,output/'healthy/prepare',wall=clock.wall)
    m.need(prepared['status']=='PREPARED','offline storage canary preparation')
    api,backend=runner(prepared['manifest'],http,clock);result=s.run(api)
    after=entry.capture(cfg,prepared['manifest'],api=independent(backend,clock),wall=clock.wall)
    reviewed=entry.check_state(cfg,prepared['manifest'],after,native=False)
    m.need(reviewed['retainedCostMicrousd']==14_000_000,'two separate storage reservations')
    write_once(output/'healthy/result.json',result);write_once(output/'healthy/after.json',after)
    write_once(output/'healthy/review.json',reviewed)
    rows.append(dict(case='prepared-run-reviewed',status='PASS'))
    # Lose each of the eight original preparation mutation replies after commit.
    for cut in range(8):
        cfg,clock,http,value,api=fixture();send=http.send;count=0
        def lose(method,url,*args):
            nonlocal count
            response=send(method,url,*args)
            if method!='GET':
                current=count;count+=1
                if current==cut:raise ConnectionError('injected preparation reply loss')
            return response
        http.send=lose;root=output/('lost-prepare-'+str(cut))
        result=plan.prepare(api,root/'prepare',wall=clock.wall)
        m.need(result['status']=='FAIL' and count==cut+1,'preparation original mutation replayed')
        state=cleanup_q.snapshot(http);write_once(root/'interrupted.json',state)
        for trigger in ('manual','schedule'):
            receipt,after,calls=storage_q.replay(root/trigger,state,trigger,api.lease['expiresAt']+api.lease['graceSeconds'])
            m.need(receipt['status']=='PASS','interrupted preparation cleanup')
            _,restored,raw,_=cleanup_q.restore(after);store=g.Store(cfg['provider'],raw,authority=n)
            total,attempts=n.inspect_ledger(store.get(n.LEDGER)[1])
            m.need(store.get(n.LEASE) is None and total==(12_000_000 if cut==0 else 13_000_000) and
                   all(v['status']=='FAIL' for v in attempts.values()), 'preparation cleanup lost charge or passed workload')
            for key,row in state['objects'].items():
                if key not in (n.LEASE,n.LEDGER):m.need(after['objects'].get(key)==row,'preparation cleanup changed evidence')
        rows.append(dict(case='lost-prepare-'+str(cut),status='PASS'))
    result=dict(schema='gse-v51-runner-storage-entry-qualification-v1',execution='offline-storage-entry-qualification',
                status='PASS',paidCloud=False,cases=rows,**plan.FLAGS)
    write_once(output/'receipt.json',result);print(m.canonical(result).decode());return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);qualify(parser.parse_args().output)
