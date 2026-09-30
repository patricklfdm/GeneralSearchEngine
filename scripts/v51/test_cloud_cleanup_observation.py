"""Offline models of native observations; never establish real cloud qualification."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from . import cloud_cleanup_observation as o, cloud_cleanup_qualification as q
from . import cloud_cleanup_entry_qualification as eq, cloud_native_cleanup as native
from . import cloud_native_authority as n, cloud_http, performance_model as m


def timestamp(value):return datetime.fromtimestamp(value,timezone.utc).isoformat()


def fixture(case='expired-manual',trigger='manual',*,retained_status=None,terminal=False):
    state,now,_=q.case_state(case,authority=n);clock,http,api,_=q.restore(state)
    invocation=eq.fixture(state['configuration'],trigger);cfg=invocation['configuration'];source=invocation['source']
    if retained_status is not None:
        store=o.g.Store(cfg['provider'],api,authority=n);req=store.get(n.LEASE)[1]['request']
        completion=dict(schema=n.COMPLETION_SCHEMA,execution=n.EXECUTION,paidCloud=True,
                        requestSha256=n.validate_request(req),status=retained_status)
        store.put(n.PREFIX+'attempts/'+n.validate_request(req)+'/completion.json',completion,0)
        if terminal:
            generation,ledger=store.get(n.LEDGER);store.put(n.LEDGER,n.finish(ledger,req,completion),generation)
    before=o.capture(cfg,source,api=api,wall=lambda:now-2)
    with tempfile.TemporaryDirectory() as temp:
        inner=native.reconcile(cfg['provider'],api,Path(temp)/'reconcile',trigger=trigger,now=now)
    after=(o.capture(cfg,source,before=before,api=api,wall=lambda:now+2)
           if before['status']=='OBSERVED' else deepcopy(before))
    binding=o.entry.identity(cfg,invocation['env'],trigger=trigger,source=source,checkout=source)
    # Model a future completed native entry. These synthetic records and their
    # observation execution tags stay offline; no provider credential is obtained.
    receipt=dict(binding,status=inner['status'],execution='gcp-native-cleanup-entry',credentialExchangeCompleted=True,
                 effectiveIamQualified=False,checkedAt=now,reconciliation=dict(inner,execution=n.CLEANUP_EXECUTION))
    run=dict(invocation['observation'],status='completed',conclusion='success')
    steps=[dict(name=name,status='completed',conclusion='success') for name in
           ('Bind cleanup entry and exact run attempt','Authenticate exact cleanup identity',
            'Reconcile retained expired lease','Retain cleanup diagnostics')]
    job=dict(run_id=binding['runId'],run_attempt=binding['runAttempt'],head_sha=source,name='cleanup',
             status='completed',conclusion='success',started_at=timestamp(now-1),completed_at=timestamp(now+1),steps=steps)
    observed=dict(before=deepcopy(run),attempt=deepcopy(run),after=deepcopy(run),jobs=dict(total_count=1,jobs=[job]))
    return dict(cfg=cfg,source=source,before=before,after=after,binding=binding,receipt=receipt,observed_run=observed),http,api


class CleanupObservationTest(unittest.TestCase):
    def test_positive_states_and_both_triggers_remain_review_only(self):
        for trigger in ('manual','schedule'):
            for case,expected in [('no-lease','NO_LEASE'),('active','ACTIVE_OR_GRACE'),('grace','ACTIVE_OR_GRACE'),
                                  ('expired-manual','EXPIRED_ABSENCE_CONFIRMED'),('empty-reservation','EXPIRED_ABSENCE_CONFIRMED'),('lost-insert-ack','EXPIRED_ABSENCE_CONFIRMED')]:
                with self.subTest(case=case,trigger=trigger):
                    values,_,_=fixture(case,trigger);result=o.review(**values)
                    self.assertEqual('STATE_MATCH',result['status'],result);self.assertEqual(expected,result['case'])
                    self.assertEqual('offline-cleanup-observation',result['execution'])
                    for key in o.BOUNDARY:self.assertIs(result[key],False)

    def test_capture_only_reads_and_does_not_reconcile_expired_resources(self):
        state,now,_=q.case_state('expired-manual',authority=n);_,http,api,_=q.restore(state)
        cfg=eq.fixture(state['configuration'],'manual')['configuration'];original=q.snapshot(http)
        result=o.capture(cfg,eq.SOURCE,api=api,wall=lambda:now)
        self.assertEqual('OBSERVED',result['status']);self.assertEqual(13,len(result['resources']))
        self.assertEqual(original,q.snapshot(http));self.assertTrue(all(r['method']=='GET' for r in http.requests))
        wrapped=o.Reads(api)
        for method in ('POST','DELETE'):
            with self.assertRaises(ValueError):wrapped.call(method,'unused',deadline=wrapped.deadline)

    def test_read_denial_is_not_absence_and_never_leaks_provider_text(self):
        values,http,api=fixture('no-lease');http.hook=lambda *args:(403,b'private provider credentials')
        result=o.capture(values['cfg'],values['source'],api=api)
        self.assertEqual('BLOCKED',result['status']);self.assertEqual('ApiError',result['failure']['type'])
        self.assertNotIn('private',m.canonical(result).decode())

    def test_control_change_during_collection_blocks_snapshot(self):
        state,now,_=q.case_state('active',authority=n);_,http,api,_=q.restore(state);calls=[]
        def hook(method,path,query,body):
            if path.path.endswith('active.json') and 'alt' not in query:
                calls.append(1)
                if len(calls)==2:q.rewrite(http,n.LEASE,lambda lease:None)
        http.hook=hook;cfg=eq.fixture(state['configuration'],'manual')['configuration']
        result=o.capture(cfg,eq.SOURCE,api=api,wall=lambda:now)
        self.assertEqual('BLOCKED',result['status']);self.assertEqual('stable-control',result['failure']['phase'])

    def test_snapshot_keeps_original_total_deadline(self):
        calls=[];api=Mock(clock=lambda:10,offline=True)
        api.call.side_effect=lambda *args,**kwargs:calls.append(kwargs)
        wrapper=o.Reads(api);wrapper.call('GET','unused',deadline=1000)
        self.assertEqual(190,calls[0]['deadline'])

    def test_failed_unresolved_and_foreign_resource_states_never_pass(self):
        for case in ('pending-insert','missing-operation','reused-name','delete-denied','missing-reservation','missing-context','changed-context'):
            with self.subTest(case=case):
                values,_,_=fixture(case);self.assertEqual('BLOCKED',o.review(**values)['status'])

    def test_observation_chain_generation_and_clock_drift_block(self):
        base,_,_=fixture()
        changes=[lambda v:v['after'].update(referenceSha256='0'*64),
                 lambda v:v['after'].update(source='0'*40),
                 lambda v:v['after'].update(collectorSha256='0'*64),
                 lambda v:v['after'].update(execution='read-only-native-cleanup-observation'),
                 lambda v:v['before'].update(status='BLOCKED'),
                 lambda v:v['after'].update(startedAt=v['receipt']['checkedAt']-5),
                 lambda v:v['receipt'].update(checkedAt=v['before']['lease'][1]['expiresAt']),
                 lambda v:v['after'].update(lease=v['before']['lease']),
                 lambda v:v['after'].update(ledger=None),
                 lambda v:v['after'].update(cleanupReady=True)]
        for change in changes:
            v=deepcopy(base);change(v);self.assertEqual('BLOCKED',o.review(**v)['status'])

    def test_independent_absence_needs_every_original_operation_and_exact_id(self):
        base,_,_=fixture()
        changes=[lambda v:v['after']['resources'].pop(),
                 lambda v:v['after']['resources'].append(deepcopy(v['after']['resources'][0])),
                 lambda v:v['after']['resources'][0]['operation'].update(state='UNKNOWN',id=None),
                 lambda v:v['after']['resources'][0]['operation'].update(id='999999'),
                 lambda v:v['after']['resources'][0].update(queriedId='999999'),
                 lambda v:v['after']['resources'][0].update(byName=v['before']['resources'][0]['byName']),
                 lambda v:v['after']['resources'][0].update(byId=v['before']['resources'][0]['byId']),
                 lambda v:v['receipt']['reconciliation']['cleanup']['checks'].pop()]
        for change in changes:
            v=deepcopy(base);change(v);self.assertEqual('BLOCKED',o.review(**v)['status'])

    def test_charge_and_completion_cannot_be_rewritten(self):
        base,_,_=fixture()
        changes=[lambda v:v['after']['ledger'][1]['entries'][0].update(maximumCostMicrousd=1),
                 lambda v:v['after']['ledger'][1]['entries'][-1].update(completionSha256='0'*64),
                 lambda v:v['after']['completion'][1].update(status='PASS'),
                 lambda v:v['after']['context'][1].update(requestSha256='0'*64)]
        for change in changes:
            v=deepcopy(base);change(v);self.assertEqual('BLOCKED',o.review(**v)['status'])

    def test_existing_owner_completion_is_preserved_and_finished_only_once(self):
        for status in ('PASS','FAIL'):
            for terminal in (False,True):
                with self.subTest(status=status,terminal=terminal):
                    values,_,_=fixture(retained_status=status,terminal=terminal)
                    result=o.review(**values);self.assertEqual('STATE_MATCH',result['status'],result)
                    self.assertEqual(values['before']['completion'],values['after']['completion'])
                    self.assertEqual(2,len(values['after']['ledger'][1]['entries']))
                    generation,completion=values['after']['completion']
                    values['after']['completion']=(generation+1,completion)
                    self.assertEqual('BLOCKED',o.review(**values)['status'])

    def test_receipt_and_exact_completed_run_and_steps_are_bound(self):
        base,_,_=fixture()
        changes=[lambda v:v['binding'].update(serviceAccount='wrong'),
                 lambda v:v['receipt'].update(execution='offline-native-cleanup-entry'),
                 lambda v:v['receipt'].update(credentialExchangeCompleted=False),
                 lambda v:v['receipt'].update(source='0'*40),
                 lambda v:v['observed_run']['after'].update(run_attempt=3),
                 lambda v:v['observed_run']['before'].update(event='pull_request'),
                 lambda v:v['observed_run']['attempt'].update(head_sha='0'*40),
                 lambda v:v['observed_run']['jobs'].update(total_count=2),
                 lambda v:v['observed_run']['jobs']['jobs'][0]['steps'][1].update(conclusion='skipped'),
                 lambda v:v['observed_run']['jobs']['jobs'][0].update(run_attempt=1)]
        for change in changes:
            v=deepcopy(base);change(v);self.assertEqual('BLOCKED',o.review(**v)['status'])

    def test_waiting_does_not_accept_any_resource_or_control_change(self):
        base,_,_=fixture('active')
        for key in ('lease','ledger','context','completion','resources'):
            v=deepcopy(base);v['after'][key]=[1,{}] if key=='completion' else None
            self.assertEqual('BLOCKED',o.review(**v)['status'])

    def test_empty_pass_does_not_hide_pending_ledger_reservation(self):
        values,_,_=fixture('no-lease');reserved,_,_=fixture('active')
        values['before']['ledger']=values['after']['ledger']=reserved['before']['ledger']
        values['after']['referenceSha256']=m.sha(m.canonical(values['before']))
        self.assertEqual('BLOCKED',o.review(**values)['status'])


if __name__=='__main__':unittest.main()
