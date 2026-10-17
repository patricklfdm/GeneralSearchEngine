from copy import deepcopy
import unittest
from unittest.mock import patch
from . import cloud_prepared as p, cloud_inputs as inputs, cloud_access as access, cloud_authority as a
from .test_cloud_provider import configuration
from .test_cloud_identity import public_key
from .test_cloud_authority import completion
from .test_cloud_inputs import binding
from .evidence import encoded, digest


def proof():
    return dict(schema=inputs.PROOF, status='INPUTS_VERIFIED_NOT_ADMITTED', source=binding(),
        buildManifestSha256='1'*64, controlsManifestSha256=p.suite.load()['controlsManifestSha256'],
        packageSha256='2'*64, packageBytes=100, inputManifestSha256='3'*64, **inputs.FLAGS)


def arguments(*, domain='native', member='experiment', attempt='b'*32, baseline=None):
    cfg = configuration(); layout = dict(bootDiskGiB=50, dataDiskGiB=100)
    quote = dict(schema='gse-v52-operator-estimate-v1', currency='USD', configurationSha256=p.provider.config(cfg),
        layoutSha256=digest(encoded(layout)), createdAt=900, expiresAt=10000, coverageSeconds=7200, costMicrousd=4_000_000,
        includes=list(p.INCLUDES), priceSources=['https://cloud.google.com/compute/all-pricing'])
    return dict(configuration=cfg, project_number='123456', proof=proof(), guest_access=access.descriptor(attempt, public_key()),
        resource_layout=layout, ownership_policy=dict(leaseSeconds=600, operationGraceSeconds=300, budgetMicrousd=200_000_000),
        original_ledger=deepcopy(baseline), quote=quote, source='a'*40, sequence='c'*32, member=member, now=1000, domain=domain)


class PreparedTest(unittest.TestCase):
    def setUp(self):
        self.args = arguments(); self.plan = p.prepare(**self.args)
        self.approval = p.approval_template(self.plan); self.approval['confirmed'] = True
        self.confirmation = p.validate(self.plan, 1000)

    def review(self, **changes):
        args = dict(current_inputs=self.args['proof'], current_configuration=self.args['configuration'], project_number='123456',
                    current_ledger=None, active_lease=None, now=1001)
        args.update(changes)
        return p.review(self.plan, self.approval, self.confirmation, **args)

    def test_exact_review_binds_whole_member_inputs_and_returns_no_authority(self):
        with patch('scripts.v51.cloud_http.Network.send', side_effect=AssertionError('network forbidden')):
            result = self.review()
        self.assertEqual('APPROVAL_BOUND_NOT_ADMITTED', result['status'])
        self.assertTrue(all(result[k] is False for k in p.FLAGS))
        self.assertEqual(5, len(self.plan['request']['selection']['member']['histories']))
        self.assertEqual(self.args['proof']['packageSha256'], self.plan['request']['selection']['binding']['packageSha256'])

    def test_offline_and_native_plans_are_distinct_without_promoting_adapters(self):
        offline = p.prepare(**arguments(domain='offline')); p.validate(offline, 1000)
        self.assertNotEqual(p.validate(offline, 1000), self.confirmation)
        from .cloud_provider_offline import Server
        api = p.provider.OfflineApi(Server(self.args['configuration'])); store = p.provider.Store(self.args['configuration'], api)
        with self.assertRaisesRegex(ValueError, 'domain'): p.provider.Provider(store, self.plan['request'])

    def test_all_five_members_can_be_first_without_prior_successes(self):
        for name in p.suite.MEMBERS:
            plan = p.prepare(**arguments(member=name)); p.validate(plan, 1000)
            self.assertEqual(p.suite.member(name), plan['request']['selection']['member'])

    def test_same_cohort_permits_changed_access_between_attempts_and_arbitrary_member_order(self):
        ledger = a.empty_ledger(domain='native'); previous = 0; shared = None
        for i, name in enumerate(reversed(p.suite.MEMBERS)):
            args = arguments(member=name, attempt=f'{i+1:032x}', baseline=dict(generation=i+1, ledger=ledger))
            args['guest_access'] = access.descriptor(f'{i+1:032x}', public_key(i+1))
            plan = p.prepare(**args); req = plan['request']
            if shared is None: shared = a.identity(req)
            else: self.assertEqual(shared, a.identity(req))
            ledger = a.reserve(ledger, req, previous_cost=previous, cost=4_000_000); previous += 4_000_000
            ledger = a.finish(ledger, req, completion(req))
        self.assertEqual(list(reversed(p.suite.MEMBERS)), a.inspect_ledger(ledger, domain='native')['sequences']['c'*32]['passed'])

    def test_plan_copies_inputs_and_does_not_write_ledger(self):
        ledger = a.empty_ledger(domain='native'); args = arguments(baseline=dict(generation=1, ledger=ledger))
        plan = p.prepare(**args); self.assertEqual([], ledger['entries'])
        args['configuration']['project'] = 'changed'; args['proof']['source']['source'] = 'f'*40
        args['quote']['priceSources'].append('https://docs.github.com/changed'); args['original_ledger']['ledger']['entries'].append({})
        p.validate(plan, 1000)

    def test_approval_starts_unconfirmed(self):
        self.approval = p.approval_template(self.plan)
        self.assertIs(False, self.approval['confirmed'])
        with self.assertRaisesRegex(ValueError, 'operator approval'): self.review()

    def test_approval_flags_expiry_request_cost_and_confirmation_are_exact(self):
        original = deepcopy(self.approval)
        for key, value in (('confirmed', 1), ('planSha256', 'f'*64), ('requestSha256', 'f'*64),
                           ('expiresAt', 9999), ('costMicrousd', 5_000_000), ('previousCostMicrousd', 1), ('extra', True)):
            self.approval = dict(original, **{key:value})
            with self.assertRaisesRegex(ValueError, 'operator approval'): self.review()
        self.approval = original; self.confirmation = 'f'*64
        with self.assertRaisesRegex(ValueError, 'operator approval'): self.review()

    def test_approval_cannot_move_to_another_member_attempt_sequence_or_source(self):
        for key, val in (('member', 'canonical-3'), ('sequence', 'd'*32), ('guest_access', access.descriptor('d'*32, public_key()))):
            self.plan = p.prepare(**dict(self.args, **{key:val}))
            with self.assertRaisesRegex(ValueError, 'operator approval'): self.review()
        args = deepcopy(self.args); args['source'] = 'f'*40; args['proof']['source']['source'] = 'f'*40
        self.plan = p.prepare(**args)
        with self.assertRaisesRegex(ValueError, 'operator approval'): self.review()

    def test_expiry_is_fresh_approval_only_and_not_an_experiment_lifetime(self):
        self.assertEqual(4600, self.plan['expiresAt'])
        self.review(now=4599)
        for now in (999, 4600, 10001, True):
            with self.assertRaises(ValueError): self.review(now=now)
        self.assertNotIn('maxRuntimeSeconds', self.plan['request']['policy'])
        self.assertEqual(7200, self.plan['estimate']['coverageSeconds'])

    def test_quote_expiry_shortens_approval_window(self):
        args = deepcopy(self.args); args['quote']['expiresAt'] = 1100
        plan = p.prepare(**args); self.assertEqual(1100, plan['expiresAt']); p.validate(plan, 1099)
        with self.assertRaises(ValueError): p.validate(plan, 1100)

    def test_every_plan_field_is_recomputed_including_boolean_integer_distinctions(self):
        for mutate in (lambda v:v.update(expiresAt=v['expiresAt']+1), lambda v:v.update(paidAdmission=True),
                       lambda v:v.update(resourcesCreated=0), lambda v:v['reservation'].update(previousCostMicrousd=False),
                       lambda v:v['warnings'].update(exceeded=0), lambda v:v['request']['selection']['member']['histories'].pop(),
                       lambda v:v['request']['selection']['binding'].update(packageSha256='f'*64)):
            wrong = deepcopy(self.plan); mutate(wrong)
            with self.assertRaises(ValueError): p.validate(wrong, 1000)

    def test_current_inputs_must_be_independently_replayed_and_match(self):
        for key in ('packageSha256', 'buildManifestSha256', 'inputManifestSha256'):
            current = dict(self.args['proof'], **{key:'f'*64})
            with self.assertRaisesRegex(ValueError, 'current build/package'): self.review(current_inputs=current)
        current = deepcopy(self.args['proof']); current['source']['java']['java.vendor'] = 'other'
        with self.assertRaisesRegex(ValueError, 'current build/package'): self.review(current_inputs=current)

    def test_configuration_project_number_and_active_lease_drift_reject(self):
        for key, value in (('current_configuration', dict(self.args['configuration'], imageId='999')),
                           ('project_number', '789'), ('active_lease', {})):
            with self.assertRaises(ValueError): self.review(**{key:value})

    def test_absent_ledger_is_distinct_from_new_empty_generation(self):
        current = dict(generation=1, ledger=a.empty_ledger(domain='native'))
        with self.assertRaisesRegex(ValueError, 'lease/ledger changed'): self.review(current_ledger=current)

    def test_same_ledger_content_with_changed_generation_rejects(self):
        base = dict(generation=12, ledger=a.empty_ledger(domain='native'))
        self.args = arguments(baseline=base); self.plan = p.prepare(**self.args)
        self.approval = p.approval_template(self.plan); self.approval['confirmed'] = True; self.confirmation = p.validate(self.plan, 1000)
        self.review(current_ledger=base)
        with self.assertRaisesRegex(ValueError, 'lease/ledger changed'): self.review(current_ledger=dict(base, generation=13))

    def test_pending_reservation_or_reused_attempt_rejects_preparation(self):
        req = self.plan['request']; ledger = a.reserve(a.empty_ledger(domain='native'), req, previous_cost=0, cost=1)
        for current in (ledger, a.finish(ledger, req, completion(req, 'FAIL'))):
            with self.assertRaises(ValueError): p.prepare(**arguments(baseline=dict(generation=2, ledger=current)))

    def test_member_already_passed_cannot_be_retried_under_new_attempt(self):
        req = self.plan['request']; ledger = a.reserve(a.empty_ledger(domain='native'), req, previous_cost=0, cost=1)
        ledger = a.finish(ledger, req, completion(req))
        with self.assertRaisesRegex(ValueError, 'member already passed'):
            p.prepare(**arguments(attempt='d'*32, baseline=dict(generation=2, ledger=ledger)))

    def test_failed_attempt_cost_is_retained_and_retry_is_new_whole_attempt(self):
        req = self.plan['request']; ledger = a.reserve(a.empty_ledger(domain='native'), req, previous_cost=0, cost=4_000_000)
        ledger = a.finish(ledger, req, completion(req, 'FAIL'))
        plan = p.prepare(**arguments(attempt='d'*32, baseline=dict(generation=2, ledger=ledger)))
        self.assertEqual(4_000_000, plan['reservation']['previousCostMicrousd'])
        self.assertEqual(8_000_000, plan['warnings']['reservedCostMicrousd'])

    def test_existing_sequence_cannot_rebind_package_source_layout_or_policy(self):
        req = self.plan['request']; ledger = a.reserve(a.empty_ledger(domain='native'), req, previous_cost=0, cost=1)
        ledger = a.finish(ledger, req, completion(req, 'FAIL'))
        for change in (lambda v:v['proof'].update(packageSha256='d'*64), lambda v:v['proof']['source'].update(checkoutSha256='d'*64),
                       lambda v:v['ownership_policy'].update(leaseSeconds=700)):
            args = arguments(attempt='d'*32, baseline=dict(generation=2, ledger=ledger)); change(args)
            with self.assertRaises(ValueError): p.prepare(**args)

    def test_time_and_cost_are_soft_but_ownership_bounds_and_integer_overflow_remain_finite(self):
        args = deepcopy(self.args); args['quote'].update(costMicrousd=201_000_000, coverageSeconds=1)
        plan = p.prepare(**args); p.validate(plan, 1000)
        self.assertTrue(plan['warnings']['exceeded']); self.assertEqual(201_000_000, plan['reservation']['costMicrousd'])
        for mutate in (lambda v:v['ownership_policy'].update(leaseSeconds=0), lambda v:v['quote'].update(costMicrousd=1<<63),
                       lambda v:v.update(now=a.MAX_INTEGER)):
            bad = deepcopy(args); mutate(bad)
            with self.assertRaises(ValueError): p.prepare(**bad)

    def test_quote_cost_scope_configuration_currency_and_numeric_types_reject(self):
        for key, value in (('configurationSha256', '0'*64), ('layoutSha256', '0'*64), ('currency', 'EUR'),
                           ('includes', ['three-vms']), ('createdAt', 1001), ('expiresAt', 1000),
                           ('coverageSeconds', True), ('costMicrousd', True), ('costMicrousd', 0)):
            args = deepcopy(self.args); args['quote'][key] = value
            with self.assertRaises(ValueError): p.prepare(**args)

    def test_quote_source_urls_do_not_accept_credentials_arbitrary_hosts_or_query_secrets(self):
        for link in ('http://cloud.google.com/pricing', 'https://cloud.google.com.evil.invalid/pricing',
                     'https://user:password@cloud.google.com/pricing', 'https://cloud.google.com/pricing?token=secret',
                     'https://docs.github.com/x\ny'):
            args = deepcopy(self.args); args['quote']['priceSources'] = [link]
            with self.assertRaises(ValueError): p.prepare(**args)

    def test_build_source_and_missing_guest_access_reject(self):
        args = deepcopy(self.args); args['source'] = 'f'*40
        with self.assertRaisesRegex(ValueError, 'source mismatch'): p.prepare(**args)
        wrong = deepcopy(self.plan); wrong['request'].pop('guestAccess'); wrong['request']['schema'] = 'gse-v52-owned-request-v1'
        with self.assertRaisesRegex(ValueError, 'guest access required'): p.validate(wrong, 1000)

    def test_baseline_generation_and_domains_cannot_be_coerced(self):
        for current in (dict(generation=True, ledger=a.empty_ledger(domain='native')),
                        dict(generation=0, ledger=a.empty_ledger(domain='native')),
                        dict(generation=1, ledger=a.empty_ledger(domain='offline'))):
            with self.assertRaises(ValueError): p.prepare(**arguments(baseline=current))


if __name__ == '__main__': unittest.main()
