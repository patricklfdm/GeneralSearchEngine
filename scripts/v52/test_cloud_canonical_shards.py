"""Whole canonical histories, closed grouping and v2 accounting migration.

Only in-memory/offline authorities are used; these are not cloud measurements.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_suite as suite, cloud_authority as a, cloud_control as control, cloud_offline as offline
from .test_cloud_authority import fixture, completion
from .test_cloud_drill_shards import deny_owner


def legacy_request(name='canonical-1'):
    req=fixture();plan=suite.read(suite.LEGACY_V2_PLAN);spec=plan['members'][name]
    req['selection']['binding']['suiteSha256']=suite.LEGACY_V2_SHA
    req['selection']['member']=dict(name=name,**deepcopy(spec),
        profiles={k:deepcopy(plan['histories'][k]) for k in spec['histories']})
    a.validate_request(req,domain='offline');return req


def legacy_ledger(req):
    value=a.empty_ledger(domain='offline')
    value['entries']=[dict(kind='RESERVED',requestSha256=a.validate_request(req,domain='offline'),
                           request=req,reservedCostMicrousd=80)]
    return value


class CanonicalShardsTest(unittest.TestCase):
    def test_two_two_one_preserves_every_original_profile_count_and_negative(self):
        old=suite.read(suite.LEGACY_V2_PLAN);new=suite.load()
        self.assertEqual(old['histories'],new['histories'])
        self.assertEqual(old['formalNegativeRules'],new['formalNegativeRules'])
        for repetition in (1,2,3):
            logical=f'canonical-{repetition}';units=[suite.member(name) for name in suite.LOGICAL_UNITS[logical]]
            self.assertEqual([2,2,1],[len(v['histories']) for v in units])
            self.assertEqual(old['members'][logical]['histories'],[h for unit in units for h in unit['histories']])
            for key in ('reads','updates','nominalM01Seconds'):
                self.assertEqual(old['members'][logical][key],sum(v[key] for v in units))
            for unit in units:self.assertEqual(logical,suite.logical_member(unit['name']))
        for name in ('experiment',*suite.DRILL_SHARDS):self.assertEqual(old['members'][name],new['members'][name])
        for key in old['totals']:
            if key!='members':self.assertEqual(old['totals'][key],new['totals'][key])
        self.assertEqual(15,new['totals']['members'])

    def test_each_canonical_shard_can_start_but_no_partial_set_or_history_qualifies(self):
        rows=[fixture(name,f'{i+1:032x}')['selection'] for i,name in enumerate(suite.MEMBERS)]
        for name in suite.CANONICAL_SHARDS:
            req=fixture(name);ledger=a.reserve(a.empty_ledger(domain='offline'),req,previous_cost=0,cost=1)
            self.assertEqual('PENDING',next(iter(a.inspect_ledger(ledger,domain='offline')['attempts'].values()))['status'])
            index=suite.MEMBERS.index(name)
            with self.assertRaisesRegex(ValueError,'incomplete'):suite.complete_selection(rows[:index]+rows[index+1:])
            wrong=deepcopy(req['selection']);wrong['member']['histories'].pop()
            with self.assertRaises(ValueError):suite.validate_selection(wrong)
            wrong=deepcopy(req['selection']);key=wrong['member']['histories'][0]
            wrong['member']['profiles'][key]['profile']['repetition']=4
            with self.assertRaises(ValueError):suite.validate_selection(wrong)
        self.assertFalse(suite.complete_selection(list(reversed(rows)))['qualified'])
        for old_name in ('canonical-1','canonical-2','canonical-3'):
            with self.assertRaises(ValueError):suite.member(old_name)
        with self.assertRaises(ValueError):suite.complete_selection([legacy_request()['selection'],*rows[1:]])

    def test_v2_costs_survive_but_allocation_and_same_sequence_migration_fail_closed(self):
        for name in ('canonical-1','canonical-3','failure-drill-m04'):
            with self.subTest(member=name):
                old=legacy_request(name);ledger=a.finish(legacy_ledger(old),old,completion(old,'FAIL'))
                current=fixture('canonical-2-minimum','d'*32,sequence='e'*32)
                updated=a.reserve(ledger,current,previous_cost=80,cost=20)
                self.assertEqual(100,a.inspect_ledger(updated,domain='offline')['reservedCostMicrousd'])
                self.assertEqual(ledger['entries'],updated['entries'][:2])
                for action in (lambda:a.reserve(ledger,old,previous_cost=80,cost=1),
                               lambda:a.lease(old,1000),lambda:deny_owner(old)):
                    with self.assertRaises(ValueError):action()
                current['selection']['binding']['sequence']=old['selection']['binding']['sequence']
                with self.assertRaisesRegex(ValueError,'sequence identity changed'):
                    a.reserve(ledger,current,previous_cost=80,cost=20)

    def test_v2_active_lease_waits_and_expired_lease_finishes_original_charge(self):
        old=legacy_request();lease=a.lease(old,1000,historical=True);lease['phase']='ACTIVE'
        store=offline.Store();provider=offline.Provider(store)
        store.put(a.LEDGER,legacy_ledger(old),0);store.put(a.LEASE,lease,0)
        before=deepcopy(store.get(a.LEASE))
        self.assertEqual('WAITING',control.reconcile(store,provider,trigger='workflow_dispatch',now=1089)['status'])
        self.assertEqual(before,store.get(a.LEASE));self.assertFalse(provider.events)
        result=control.reconcile(store,provider,trigger='workflow_dispatch',now=1090)
        self.assertEqual('PASS',result['status']);self.assertTrue(result['leaseReleased'])
        view=a.inspect_ledger(store.get(a.LEDGER)[1],domain='offline')
        self.assertEqual(80,view['reservedCostMicrousd'])
        self.assertEqual('FAIL',view['attempts'][a.validate_request(old,domain='offline')]['status'])
        self.assertFalse(any(v['action']=='create' for v in provider.events))

    def test_historical_validation_requires_exact_known_v2_plan_and_selection(self):
        old=legacy_request();wrong=deepcopy(old);wrong['selection']['member']['histories'].pop()
        with self.assertRaises(ValueError):a.validate_request(wrong,domain='offline')
        wrong=deepcopy(old);wrong['selection']['binding']['suiteSha256']='f'*64
        with self.assertRaises(ValueError):a.validate_request(wrong,domain='offline')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'plan.json';path.write_text('{}')
            with patch.object(suite,'LEGACY_V2_PLAN',path),self.assertRaisesRegex(ValueError,'legacy suite changed'):
                a.validate_request(old,domain='offline')


if __name__=='__main__':unittest.main()
