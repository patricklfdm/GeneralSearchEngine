"""Fresh-process cleanup CLI over loopback TLS. No GCP/IAM/paid qualification."""
import argparse
from pathlib import Path
import subprocess
import sys
import time
from . import cloud_cleanup_qualification as q, cloud_cleanup_network_fixture as tls
from . import cloud_native_authority as n, cloud_cleanup_entry as entry, performance_model as m
from .remote_command import read, write_once

FAULTS = ('deny-oidc','deny-sts','deny-impersonation','deny-provider',
          'redirect-oidc','redirect-sts','redirect-impersonation','redirect-provider',
          'oversized-oidc','oversized-provider','tls-untrusted','tls-hostname','invalid-json-provider','malformed-resource','get-401','mutation-401','lease-cas','lost-delete')


def fresh_state(case):
    state, _, _ = q.case_state(case, authority=n)
    if case in ('active','grace'):
        _, provider, _, _ = q.restore(state)
        start = int(time.time())-(5401 if case == 'grace' else 0)
        q.rewrite(provider,n.LEASE,lambda lease:lease.update(startedAt=start,expiresAt=start+5400))
        state = q.snapshot(provider)
    return state


def replay(state, output, trigger, fault=None):
    output = Path(output); output.mkdir(parents=True,exist_ok=False)
    with tls.Fixture(state,trigger,fault) as fixture:
        code = fixture.run_cli(output/'entry')
        result = read(output/'entry/receipt.json')
        m.need(code == (0 if result['status'] in ('PASS','WAITING') else 2), 'cleanup CLI exit status')
        m.need(not fixture.errors and not fixture.forbidden_routes,'loopback server failed or redirect followed')
        write_once(output/'http.json',fixture.http.requests)
        write_once(output/'exchange.json',fixture.requests)
        write_once(output/'state.json',q.snapshot(fixture.http))
        if fault == 'lost-delete':
            # Fresh entry/token/policy state; no failed mutation is blindly retried.
            deleted = [v for v in fixture.http.requests if v['method']=='DELETE' and '/compute/' in v['path']]
            m.need(result['status']=='FAIL' and deleted,'lost delete was not exercised')
            before = len(fixture.http.requests)
            m.need(fixture.run_cli(output/'later')==0,'later cleanup did not reconcile')
            m.need(not any(v['method']=='DELETE' and '/compute/' in v['path'] for v in fixture.http.requests[before:]),
                   'later cleanup repeated deletion')
            write_once(output/'later-state.json',q.snapshot(fixture.http))
    return result


def verify(case, state, result, after, calls, exchange, fault):
    expected = ('PASS' if fault=='get-401' else 'FAIL') if fault else (
        'WAITING' if case in ('active','grace') else 'PASS' if case in
        ('no-lease','expired-manual','expired-schedule','empty-reservation','lost-insert-ack') else 'FAIL')
    m.need(result['status']==expected,'network cleanup outcome: '+case)
    m.need(all(result[k] is False for k in ('identityAuthenticated','activationAllowed','cleanupReady','paidCloud',
           'fullRemoteQualification','effectiveIamQualified')),'loopback entry claimed readiness')
    compute = [v for v in calls if v['path'].startswith('/compute/')]
    m.need(all(v['method']!='POST' for v in compute) and
           all(v['path'].rsplit('/',1)[-1].isdecimal() for v in compute if v['method']=='DELETE'), 'network cleanup scope')
    stages = [v['stage'] for v in exchange if v['stage']!='provider']
    if fault=='get-401': m.need(stages==['oidc','sts','impersonation']*2,'GET refresh count')
    elif not fault or fault in ('mutation-401','lease-cas','lost-delete','invalid-json-provider','redirect-provider','deny-provider'):
        # Mutation 401 drops cached credentials for the next distinct operation,
        # but never repeats the same mutation in the original call.
        m.need(stages and len(stages)%3==0 and stages==['oidc','sts','impersonation']*(len(stages)//3),'exchange order')
    if fault=='mutation-401':
        sent=[v for v in exchange if v['method']=='DELETE' and v['host']=='compute.googleapis.com']
        m.need(len(sent)==len(state['resources']) and after['resources']==state['resources'],'mutation replay or loss')
    if fault and (fault.split('-',1)[0] in ('deny','redirect','oversized','tls') or fault=='invalid-json-provider'):
        m.need(after==state and all(v['method']=='GET' for v in calls),'rejected exchange changed state')
    if not fault and case in ('no-lease','active','grace','missing-context','changed-context','missing-reservation'):
        m.need(after==state and all(v['method']=='GET' for v in calls),'blocked cleanup changed state')
    if case not in ('no-lease','missing-reservation'):
        _,_,_,store=q.restore(after); total,attempts=n.inspect_ledger(store.get(n.LEDGER)[1])
        m.need(total==1_000_000,'cleanup lost charge')
        if expected=='PASS':
            m.need(not after['resources'] and store.get(n.LEASE) is None and
                   all(v['status']=='FAIL' for v in attempts.values()),'network cleanup false workload acceptance')
        else: m.need(store.get(n.LEASE) is not None,'failed cleanup released lease')
    return expected


def qualify(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False);rows=[];started=time.monotonic()
    for case,fault in [(case,None) for case in q.CASES]+[('expired-manual',fault) for fault in FAULTS]:
        paired=[]
        for trigger in entry.TRIGGERS:
            root=output/((fault or case)+'-'+trigger);root.mkdir()
            state=fresh_state(case);write_once(root/'input.json',state)
            cmd=[sys.executable,'-m','scripts.v51.cloud_cleanup_network_qualification','replay',str(root/'replay'),
                 '--state',str(root/'input.json'),'--trigger',trigger]
            if fault:cmd+=['--fault',fault]
            done=subprocess.run(cmd,capture_output=True,timeout=45)
            (root/'stdout').write_bytes(done.stdout);(root/'stderr').write_bytes(done.stderr)
            m.need(done.returncode==0,'network cleanup child: '+root.name)
            result=read(root/'replay/entry/receipt.json');after=read(root/'replay/state.json')
            calls=read(root/'replay/http.json');exchange=read(root/'replay/exchange.json')
            expected=verify(case,state,result,after,calls,exchange,fault)
            if fault=='lost-delete':
                later=read(root/'replay/later-state.json');_,_,_,store=q.restore(later)
                m.need(not later['resources'] and store.get(n.LEASE) is None and
                       n.inspect_ledger(store.get(n.LEDGER)[1])[0]==1_000_000,'lost response recovery state')
            # Token/descriptor values and private upstream errors cannot reach evidence.
            for path in (root/'replay').rglob('*'):
                if path.is_file():
                    for secret in (tls.auth.SUBJECT_SECRET,tls.auth.FEDERATED_SECRET,tls.auth.ACCOUNT_SECRET,'private issuer/provider'):
                        m.need(secret.encode() not in path.read_bytes(),'secret in retained network evidence')
            paired.append([v for v in calls if v['path'].startswith('/compute/')])
            row=dict(case=fault or case,trigger=trigger,status='PASS',observed=expected,requests=len(exchange))
            rows.append(row);print(m.canonical(row).decode(),flush=True)
        m.need(paired[0]==paired[1],'manual/scheduled network compute paths differ')
    receipt=dict(schema='gse-v51-cleanup-network-qualification-v1',status='PASS',execution='loopback-tls-native-cleanup',
        source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True)),
        inputs={p.name:m.sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('cloud_*.py'))},
        elapsedSeconds=round(time.monotonic()-started,3),network='loopback-only',identityAuthenticated=False,effectiveIamQualified=False,activationAllowed=False,
        paidCloud=False,cleanupReady=False,fullRemoteQualification=False,cases=rows)
    write_once(output/'receipt.json',receipt);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    run=sub.add_parser('qualify');run.add_argument('output',type=Path)
    child=sub.add_parser('replay');child.add_argument('output',type=Path);child.add_argument('--state',type=Path,required=True)
    child.add_argument('--trigger',choices=entry.TRIGGERS,required=True);child.add_argument('--fault',choices=FAULTS)
    args=p.parse_args()
    if args.command=='qualify':qualify(args.output)
    else:replay(read(args.state),args.output,args.trigger,args.fault)
