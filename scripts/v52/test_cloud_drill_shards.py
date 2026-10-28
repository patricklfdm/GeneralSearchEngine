"""Closed sharding, legacy accounting/cleanup and hosted routing regressions."""
from copy import deepcopy
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_suite as suite, cloud_authority as a, cloud_control as control, cloud_offline as offline
from . import cloud_runner_host as host
from .test_cloud_authority import fixture, completion


def legacy_request():
    req=fixture();plan=suite.read(suite.LEGACY_PLAN);spec=plan['members']['failure-drill']
    req['selection']['binding']['suiteSha256']=suite.LEGACY_SHA
    req['selection']['member']=dict(name='failure-drill',**deepcopy(spec),
        profiles={k:deepcopy(plan['histories'][k]) for k in spec['histories']})
    a.validate_request(req,domain='offline');return req


def deny_owner(req):
    store=offline.Store();return control.OfflineOwner(store,offline.Provider(store),req)


class DrillShardsTest(unittest.TestCase):
    def test_exact_partition_keeps_original_histories_profiles_counts_and_negatives(self):
        old=suite.read(suite.LEGACY_PLAN);new=suite.load()
        self.assertEqual(old['histories'],new['histories'])
        self.assertEqual(old['formalNegativeRules'],new['formalNegativeRules'])
        units=[suite.member(name) for name in suite.DRILL_SHARDS]
        self.assertEqual([3,3,3,2,2],[len(v['histories']) for v in units])
        self.assertEqual(old['members']['failure-drill']['histories'],[h for v in units for h in v['histories']])
        self.assertEqual((358,45),(sum(v['reads'] for v in units),sum(v['updates'] for v in units)))
        self.assertEqual(list(suite.DRILL_SHARDS),new['logicalMembers']['failure-drill'])

    def test_each_shard_may_start_but_partial_duplicate_and_legacy_sets_never_qualify(self):
        rows=[fixture(name,f'{i+1:032x}')['selection'] for i,name in enumerate(suite.MEMBERS)]
        for name in suite.DRILL_SHARDS:
            req=fixture(name);ledger=a.reserve(a.empty_ledger(domain='offline'),req,previous_cost=0,cost=1)
            self.assertEqual(1,a.inspect_ledger(ledger,domain='offline')['reservedCostMicrousd'])
            index=suite.MEMBERS.index(name)
            with self.assertRaises(ValueError):suite.complete_selection(rows[:index]+rows[index+1:])
            changed=deepcopy(rows);changed[index]=deepcopy(rows[0])
            with self.assertRaises(ValueError):suite.complete_selection(changed)
        with self.assertRaises(ValueError):suite.complete_selection([legacy_request()['selection'],*rows[1:]])
        self.assertFalse(suite.complete_selection(rows)['qualified'])

    def test_old_ledger_cost_is_preserved_but_new_old_suite_attempt_is_rejected(self):
        old=legacy_request();sha=a.validate_request(old,domain='offline')
        ledger=a.empty_ledger(domain='offline');ledger['entries']=[dict(kind='RESERVED',requestSha256=sha,request=old,reservedCostMicrousd=80)]
        ledger=a.finish(ledger,old,completion(old,'FAIL'))
        current=fixture(next(iter(suite.DRILL_SHARDS)),'d'*32,sequence='e'*32)
        updated=a.reserve(ledger,current,previous_cost=80,cost=20)
        self.assertEqual(100,a.inspect_ledger(updated,domain='offline')['reservedCostMicrousd'])
        self.assertEqual(ledger['entries'],updated['entries'][:2])
        for action in (lambda:a.reserve(ledger,old,previous_cost=80,cost=1),lambda:a.lease(old,1000),
                       lambda:deny_owner(old)):
            with self.assertRaises(ValueError):action()

    def test_expired_old_lease_can_still_be_cleaned_without_reexecution(self):
        old=legacy_request();sha=a.validate_request(old,domain='offline')
        ledger=a.empty_ledger(domain='offline');ledger['entries']=[dict(kind='RESERVED',requestSha256=sha,request=old,reservedCostMicrousd=80)]
        lease=a.lease(old,1000,historical=True);lease['phase']='ACTIVE'
        store=offline.Store();provider=offline.Provider(store)
        store.put(a.LEDGER,ledger,0);store.put(a.LEASE,lease,0)
        self.assertEqual('WAITING',control.reconcile(store,provider,trigger='workflow_dispatch',now=1089)['status'])
        result=control.reconcile(store,provider,trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',result['status']);self.assertTrue(result['leaseReleased'])
        view=a.inspect_ledger(store.get(a.LEDGER)[1],domain='offline')
        self.assertEqual(80,view['reservedCostMicrousd']);self.assertEqual('FAIL',view['attempts'][sha]['status'])
        self.assertFalse(any(v['action']=='create' for v in provider.events))

    def test_legacy_selection_requires_original_frozen_bytes(self):
        old=legacy_request();old['selection']['member']['histories'].pop()
        with self.assertRaises(ValueError):a.validate_request(old,domain='offline')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'plan';path.write_bytes(b'{}')
            old=legacy_request()
            with patch.object(suite,'LEGACY_PLAN',path),self.assertRaises(ValueError):
                a.validate_request(old,domain='offline')


class HostRoutingTest(unittest.TestCase):
    def env(self,operation='run'):
        return dict(V52_EXECUTION_HOST='github-hosted',RUNNER_ENVIRONMENT='github-hosted',
                    RUNNER_OS='Linux',RUNNER_ARCH='X64',V52_OPERATION=operation)

    def test_only_declared_complete_shards_are_hosted_execution_units(self):
        for name in suite.HOSTED_MEMBERS:host.require_member(name,self.env())
        for name in ('failure-drill','canonical-1','canonical-3','experiment','m03-p4'):
            with self.assertRaises(ValueError):host.require_member(name,self.env())
        for name in suite.MEMBERS:host.require_member(name,dict(V52_EXECUTION_HOST='self-hosted'))

    def test_hosted_wrapper_calls_operator_once_without_local_runner_dependency(self):
        from . import cloud_operator, cloud_self_hosted
        with patch.dict(os.environ,self.env(),clear=True), \
             patch.object(host.shutil,'disk_usage',return_value=SimpleNamespace(free=8<<30)), \
             patch.object(cloud_operator,'execute_native',return_value={'status':'MODEL'}) as run, \
             patch.object(cloud_self_hosted,'execute') as local:
            self.assertEqual({'status':'MODEL'},host.execute('a'*40,Path('unused-output')))
            run.assert_called_once_with('a'*40,Path('unused-output'));local.assert_not_called()
        with patch.dict(os.environ,self.env('verify-set'),clear=True), \
             patch.object(cloud_operator,'execute_native') as run:
            with self.assertRaises(ValueError):host.execute('a'*40,Path('unused-output'))
            run.assert_not_called()

    def test_self_hosted_wrapper_preserves_dedicated_checks_and_archive_entry(self):
        from . import cloud_operator, cloud_self_hosted
        env=dict(self.env('verify-set'),V52_EXECUTION_HOST='self-hosted',RUNNER_ENVIRONMENT='self-hosted')
        with patch.dict(os.environ,env,clear=True), \
             patch.object(cloud_self_hosted,'configuration',return_value={'mode':'model'}) as configuration, \
             patch.object(cloud_self_hosted,'check') as check, \
             patch.object(cloud_self_hosted,'execute',return_value={'status':'LOCAL_MODEL'}) as local, \
             patch.object(cloud_operator,'execute_native') as run:
            self.assertEqual({'status':'LOCAL_MODEL'},host.execute('a'*40,Path('unused-output')))
            configuration.assert_called_once();check.assert_called_once_with(env,{'mode':'model'})
            local.assert_called_once_with('a'*40,Path('unused-output'));run.assert_not_called()

    def test_forged_host_wrong_operation_and_low_disk_reject_before_paid_work(self):
        with patch.object(host.shutil,'disk_usage',return_value=SimpleNamespace(free=8<<30)):
            self.assertEqual(21600,host.check(self.env())['jobPlatformLimitSeconds'])
            self.assertEqual('soft',host.check(self.env('prepare'))['timeBudget'])
            for changes in (dict(RUNNER_ENVIRONMENT='self-hosted'),dict(RUNNER_OS='Windows'),
                            dict(V52_OPERATION='verify-set'),dict(V52_EXECUTION_HOST='foreign')):
                with self.assertRaises(ValueError):host.check(dict(self.env(),**changes))
        with patch.object(host.shutil,'disk_usage',return_value=SimpleNamespace(free=1)),self.assertRaises(ValueError):
            host.check(self.env())


if __name__=='__main__':unittest.main()
