"""Offline single-disk native-authority rehearsal, with retained original failures."""
import argparse
from pathlib import Path
from . import cloud_cleanup_fixture as review, cloud_native_authority as n
from . import cloud_native_cleanup as native, cloud_cleanup as cleanup
from . import cloud_cleanup_qualification as q, cloud_http_fake as f, cloud_fake
from . import cloud_gcp as g, performance_model as m, remote_command as c
from .cloud_http import Api


def fixture(source, case):
    m.need(case in review.CASES, 'single-disk fixture case'); review.a.digest(source,40)
    cfg=f.configuration(); clock=cloud_fake.Clock(); http=f.Http(cfg)
    api=Api(transport=http,tokens=lambda timeout:'offline-token',clock=clock.seconds)
    attempt=m.sha(('offline-single-disk:'+case).encode())[:32]
    guest=dict(attempt=attempt,user='gse-'+attempt[:24],publicKey=q.KEY)
    req=n.request(source,m.sha(b'offline-cleanup-qualification-manifest'),g.config(cfg),
        m.sha(b'offline-cleanup-only-sequence')[:32],attempt,'experiment',now=clock.wall(),
        guest_access_sha256=m.sha(m.canonical(guest)))
    store=g.Store(cfg,api,authority=n); provider=g.Compute(cfg,req,api,guest_access=guest,sleep=clock.sleep,authority=n)
    lease=n.lease(req,clock.wall()); generation=store.put(n.LEASE,lease,0)
    # Retain an earlier failed reservation to prove this rehearsal cannot reset charges.
    old=n.request(source,req['bundleSha256'],req['configurationSha256'],'a'*32,'b'*32,'experiment',
                  now=clock.wall(),guest_access_sha256=req['guestAccessSha256'])
    ledger=n.reserve(n.empty_ledger(),old,dict(previousCostMicrousd=0,maximumCostMicrousd=123))
    ledger=n.finish(ledger,old,dict(requestSha256=n.validate_request(old),status='FAIL'))
    ledger=n.reserve(ledger,req,dict(previousCostMicrousd=123,maximumCostMicrousd=1_000_000))
    store.put(n.LEDGER,ledger,0)
    cleanup.retain_context(store,req,cleanup.context(cfg,req,guest,authority=n),authority=n)
    row=next(r for r in lease['resources'] if r['spec']['kind']=='disk' and r['spec']['node']==1 and r['spec']['purpose']=='data')
    row['attempted']=True; generation=store.put(n.LEASE,lease,generation)
    if case=='lost-insert-response':
        # Execute the modeled insert, lose its response, and leave the retained ID unknown.
        send=http.send
        def lose(method,url,*args):
            response=send(method,url,*args)
            if method=='POST' and 'compute.googleapis.com' in url: raise ConnectionError('offline lost insert response')
            return response
        http.send=lose
        try: provider.create(row['spec'],clock.nanos()+30*10**9)
        except ConnectionError: pass
        else: raise ValueError('lost response not exercised')
        finally: http.send=send
    else:
        row['id']=provider.create(row['spec'],clock.nanos()+30*10**9)['id']
        generation=store.put(n.LEASE,lease,generation)
    m.need(len(http.resources)==1 and http.inserts==1, 'fixture allocated outside single disk')
    if case=='missing-context': del http.objects[cleanup.context_key(req,authority=n)]
    elif case=='reused-name': next(iter(http.resources.values()))['id']='99999999'
    elif case=='delete-denied': http.fault='delete-denied'
    elif case=='generation-conflict':
        def conflict(method,path,query,body):
            if method=='POST' and query.get('name')==n.LEASE: return 412,b''
        http.hook=conflict
    return cfg,clock,http,api,req,lease,ledger


def qualify(output, source):
    output=Path(output); output.mkdir(parents=True,exist_ok=False); rows=[]
    for case in review.CASES:
        root=output/case;root.mkdir()
        cfg,clock,http,api,req,lease,ledger=fixture(source,case)
        before=q.snapshot(http); marker=len(http.requests)
        c.write_once(root/'before.json',before)
        elapsed=0 if case=='active' else 5400 if case=='grace' else 6480
        clock.sleep(elapsed)
        result=native.reconcile(cfg,api,root/'reconciliation',trigger='manual',now=clock.wall())
        after=q.snapshot(http);c.write_once(root/'after.json',after)
        calls=http.requests[marker:];c.write_once(root/'http.json',calls)
        expected='WAITING' if case in ('active','grace') else 'PASS' if case in ('expired-disk','lost-insert-response') else 'FAIL'
        m.need(result['status']==expected,'single-disk unexpected result: '+case)
        store=g.Store(cfg,api,authority=n);current=store.get(n.LEDGER)[1]
        total,attempts=n.inspect_ledger(current)
        m.need(total==1_000_123 and current['entries'][:3]==ledger['entries'], 'qualification erased prior charges/history')
        m.need(not any(r['method']=='POST' and 'compute/v1/' in r['path'] for r in calls), 'cleanup created resource')
        if expected=='WAITING':
            m.need(before==after and all(r['method']=='GET' for r in calls), 'waiting changed authority/resources')
        elif expected=='PASS':
            m.need(not http.resources and store.get(n.LEASE) is None and attempts[n.validate_request(req)]['status']=='FAIL', 'disk cleanup or terminal event missing')
            completion=store.get(n.PREFIX+'attempts/'+n.validate_request(req)+'/completion.json')[1]
            m.need(completion['status']=='FAIL' and completion['engineWorkloadExecuted'] is False, 'fixture became workload success')
            deletes=[r for r in calls if r['method']=='DELETE' and 'compute/v1/' in r['path']]
            disk_id=next(iter(before['resources'].values()))['id']
            m.need(len(deletes)==1 and deletes[0]['path'].endswith('/'+disk_id), 'cleanup did not use original numeric disk ID')
            stable=q.snapshot(http)
            again=native.reconcile(cfg,api,root/'again',trigger='manual',now=clock.wall())
            m.need(again['status']=='PASS' and q.snapshot(http)==stable, 'empty rerun changed terminal state')
        else:
            m.need(store.get(n.LEASE) is not None and http.resources==before['resources'], 'blocked case erased lease/resource')
        rows.append(dict(case=case,status='PASS',observed=expected,attemptedResources=1,retainedCostMicrousd=total))
    receipt=dict(status='PASS',execution='offline-single-disk-cleanup-qualification',source=source,cases=rows,**review.BOUNDARY)
    c.write_once(output/'receipt.json',receipt);print(m.canonical(receipt).decode());return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    parser.add_argument('--source',required=True);args=parser.parse_args();qualify(args.output,args.source)
