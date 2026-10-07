"""Deterministic native latency/headroom regressions; never paid evidence."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock
from . import cloud_native_authority as n, cloud_authority as a, native_experiment_timing as t
from . import cloud_runner_admission as admission, cloud_runner_diagnostics as diagnostics
from . import cloud_fake, remote_command as c, performance_model as m, guest_transport as transport
from . import guest_owned_services as services, guest_owned_faults as faults
from . import guest_three_mode_evidence as evidence


def request(profile=True):
    return n.request('a'*40,'b'*64,'c'*64,'d'*32,'e'*32,'experiment',now=100,
                     guest_access_sha256='f'*64,**({'timing_profile':t.PROFILE} if profile else {}))


class NativeTimingTest(unittest.TestCase):
    def test_new_lease_and_old_lease_keep_distinct_immutable_expiries(self):
        old=n.lease(request(False),101);new=n.lease(request(),101)
        self.assertEqual((5501,1080),(old['expiresAt'],old['graceSeconds']))
        self.assertEqual((14501,1800),(new['expiresAt'],new['graceSeconds']))
        for lease in (old,new):
            n.validate_lease(lease)
            with self.assertRaisesRegex(ValueError,'expiry'):n.validate_lease(dict(lease,expiresAt=lease['expiresAt']+1))
        with self.assertRaises(ValueError):a.validate_request(request())
        for mutate in (lambda q:q.update(timingProfile='arbitrary'),lambda q:q.update(member='canonical-1'),
                       lambda q:q.pop('timingProfile'),lambda q:q.update(schema='gse-v51-native-request-v1')):
            q=request();mutate(q)
            with self.assertRaises(ValueError):n.validate_request(q)

    def test_native_vm_lifetime_and_readback_match_profile_without_changing_legacy(self):
        from . import cloud_http_fake as fake, cloud_gcp as g, guest_setup as setup
        for profile,seconds in ((False,5400),(True,14400)):
            with tempfile.TemporaryDirectory() as tmp:
                *_,clock,http,store,old=fake.fixture()
                req=request(profile);req['configurationSha256']=g.config(old.config)
                access=setup.generate(Path(tmp)/'keys',req['attempt'])
                req['guestAccessSha256']=m.sha(m.canonical(access))
                provider=g.Compute(old.config,req,old.api,authority=n,guest_access=access,sleep=clock.sleep)
                lease=n.lease(req,clock.wall())
                for row in lease['resources']:row['attempted']=True
                store.put(n.LEASE,lease,0)
                for spec in n.resources(req):
                    made=provider.create(spec,clock.nanos()+60*10**9)
                    if spec['kind']=='instance':
                        actual=old.api.call('GET',provider.url(spec,made['id']),deadline=clock.seconds()+30)
                        self.assertEqual(str(seconds),actual['scheduling']['maxRunDuration']['seconds'])
                        changed=deepcopy(actual);changed['scheduling']['maxRunDuration']['seconds']=str(seconds+1)
                        with self.assertRaises(ValueError):provider.inspect(spec,changed)

    def test_wider_timeline_is_accepted_only_for_the_bound_native_profile(self):
        value=dict(status='PASS',startNanos=0,endNanos=1200*10**9,modes=[dict(mode=mode,status='PASS',
            startNanos=i*400*10**9,endNanos=(i+1)*400*10**9) for i,mode in enumerate(evidence.package.MODES)])
        evidence.timeline(value,request())
        for q in (request(False),{}):
            with self.assertRaisesRegex(ValueError,'mode budget'):evidence.timeline(value,q)
        value['modes'][0]['endNanos']=901*10**9
        with self.assertRaises(ValueError):evidence.timeline(value,request())

    def test_long_lease_requires_price_coverage_through_grace(self):
        quote=dict(observedAt=100,expiresAt=200,region='us-west4',machineType='n2-standard-8',diskType='pd-balanced',
            pricedThroughSeconds=19800,retentionDays=30,vmMicrousdPerHour=500000,diskMicrousdPerGiBHour=200,
            otherCostsMicrousd={k:1 for k in ('requests','evidenceRetention','network','actions','failureOverhang')},
            sources={k:'https://cloud.google.com/price' for k in ('compute','disks','storage','network')})
        quote['sources']['actions']='https://docs.github.com/en/billing'
        self.assertGreater(admission.prices(quote,101),7_000_000)
        for seconds in (6480,7200,16200,19799):
            with self.assertRaises(ValueError) as caught:admission.prices(dict(quote,pricedThroughSeconds=seconds),101)
            self.assertEqual('PRICE_COVERAGE_INSUFFICIENT',diagnostics.failure('inputs',caught.exception)['code'])

    def test_three_slow_service_stops_fit_native_bound_without_replaying_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=cloud_fake.Clock();group=services.Services.__new__(services.Services)
            group.root=Path(tmp);group.clock=clock.seconds;group.sleep=clock.sleep
            group.provider=SimpleNamespace(req=request());group.clients=[];ends=[]
            for i in (1,2,3):
                cfg={'node':i}
                def shutdown(end):ends.append(end);clock.sleep(10)
                def ready(end,cfg=cfg):
                    clock.sleep(10)
                    return dict(ready=dict(configSha256=m.sha(m.canonical(cfg))),closed=dict(status='PASS',jvmStopped=True))
                group.clients.append((i,SimpleNamespace(shutdown=Mock(side_effect=shutdown),ready=ready),cfg))
            result=group.stop(clock.seconds()+600)
            self.assertEqual('PASS',result['status']);self.assertEqual(1,len(set(ends)))
            group.stop(clock.seconds()+600)
            self.assertEqual([1,1,1],[cl.shutdown.call_count for _,cl,_ in group.clients])

    def test_unstarted_fault_collection_sends_no_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            group=SimpleNamespace(clients=[],provider=SimpleNamespace(req=request()))
            cell=faults.Cell(group,Path(tmp)/'cell','maintenance');cell.succeeded=Mock()
            self.assertEqual([],cell.collect(100000));cell.succeeded.assert_not_called()

    def test_service_stop_bounds_retries_and_still_checks_other_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=cloud_fake.Clock();group=services.Services.__new__(services.Services)
            group.root=Path(tmp);group.clock=clock.seconds;group.sleep=clock.sleep
            group.provider=SimpleNamespace(req=request());group.clients=[]
            for i in (1,2):
                group.clients.append((i,Mock(shutdown=Mock(side_effect=ConnectionError()),
                    ready=Mock(side_effect=ConnectionError())),{}))
            with self.assertRaisesRegex(ValueError,'service stop failed'):group.stop(clock.seconds()+1800)
            self.assertEqual('FAIL',c.read(group.root/'stop.json')['status'])
            for _,client,_ in group.clients:
                client.shutdown.assert_called_once();self.assertEqual(2,client.ready.call_count)
            self.assertLess(clock.seconds(),1800)

    def test_native_isolation_watchdog_is_bounded_and_still_invalidates_evidence(self):
        from .test_guest_owned_faults import HandlerTest
        from . import guest_fault_service as service
        from unittest.mock import patch
        fixture=HandlerTest();fixture.setUp()
        try:
            fixture.s.config['execution']='native-v51-guest-service';fixture.handler.case='no-quorum'
            with patch.object(service.package,'command',return_value=['java','worker']):
                self.assertEqual(t.PROFILE,service.argv('/package',fixture.s.config,'start')[-1])
                self.assertEqual('setup',service.argv('/package',fixture.s.config,'setup')[-1])
            with patch.object(service.threading,'Timer') as timer:
                fixture.call('fault',dict(action='isolate'))
                self.assertEqual(t.CONTROLS['isolation'],timer.call_args.args[0]);timer.call_args.args[1]()
                self.assertTrue(c.read(fixture.root/'isolation.json')['watchdog'])
        finally:fixture.doCleanups()


class NativeObservationTest(unittest.TestCase):
    def setUp(self):
        self.clock=cloud_fake.Clock();self.req=c.request(c.binding('a'*40,'b'*64,'c'*32,'node-1'),'d'*32,'fault',{})
        self.limits=dict(failures=3,uncertain=3,queries=t.MAX_QUERIES)
        self.client=Mock();self.end=self.clock.seconds()+180
    def observe(self):
        return c.submit_and_observe(self.client,self.req,self.end,clock=self.clock.seconds,sleep=self.clock.sleep,limits=self.limits)
    def reply(self,state):
        return dict(schema='gse-v51-command-receipt-v1',state=state,bindingSha256=self.req['bindingSha256'],
                    commandId=self.req['commandId'],requestSha256=m.sha(m.canonical(self.req)))
    def test_lost_submit_only_queries_and_three_transient_failures_fail_fast(self):
        self.client.submit.side_effect=ConnectionError();self.client.query.side_effect=ConnectionError()
        with self.assertRaisesRegex(ValueError,'transient failures exhausted') as caught:self.observe()
        self.client.submit.assert_called_once();self.assertEqual(2,self.client.query.call_count)
        self.assertLess(self.clock.seconds(),self.end-170)
        self.assertEqual('RUNTIME_RETRY_EXHAUSTED',diagnostics.runtime_failure('execution',caught.exception)['code'])
    def test_three_uncertain_replies_fail_fast_without_second_submission(self):
        self.client.submit.return_value=self.reply('UNCERTAIN');self.client.query.return_value=self.reply('UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'uncertain replies exhausted'):self.observe()
        self.client.submit.assert_called_once();self.assertEqual(2,self.client.query.call_count)
    def test_terminal_authentication_failure_is_never_retried(self):
        self.client.submit.side_effect=transport.ProcessError('SSH_AUTHENTICATION')
        with self.assertRaises(transport.ProcessError):self.observe()
        self.client.query.assert_not_called()
    def test_healthy_running_command_can_complete_after_many_polls(self):
        self.client.submit.return_value=self.reply('RUNNING')
        self.client.query.side_effect=[self.reply('RUNNING')]*100+[self.reply('SUCCEEDED')]
        self.assertEqual('SUCCEEDED',self.observe()['state']);self.client.submit.assert_called_once()
    def test_query_limit_is_closed_and_lost_reply_can_be_recovered(self):
        self.limits['queries']=2;self.client.submit.return_value=self.reply('RUNNING');self.client.query.return_value=self.reply('RUNNING')
        with self.assertRaisesRegex(ValueError,'query limit exhausted'):self.observe()
        self.client.reset_mock();self.client.submit.side_effect=ConnectionError();self.client.query.return_value=self.reply('SUCCEEDED')
        self.assertEqual('SUCCEEDED',self.observe()['state']);self.client.submit.assert_called_once();self.client.query.assert_called_once()
