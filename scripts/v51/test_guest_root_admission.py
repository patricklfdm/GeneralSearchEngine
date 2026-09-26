"""Independent modeled root contexts; no privileged process or filesystem write."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from . import cloud_authority as a, guest_delivery, guest_setup, guest_root_admission as root
from . import performance_model as m

ROOT = Path(__file__).resolve().parents[2]
BOOT = '12345678-1234-1234-1234-123456789abc'


def fixture(directory):
    access = guest_setup.generate(directory/'key', 'c'*32)
    req = a.request('a'*40, 'b'*64, 'd'*64, 'e'*32, 'c'*32, 'experiment', now=100,
                    guest_access_sha256=m.sha(m.canonical(access)))
    lease = a.lease(req, 100)
    for index, row in enumerate(lease['resources'], 1): row.update(attempted=True, id=str(index))
    def resource(kind, purpose):
        return next(row for row in lease['resources'] if row['spec']['kind'] == kind and
                    row['spec']['purpose'] == purpose and row['spec'].get('node') == 1)
    vm, data, boot = resource('instance', 'voter'), resource('disk', 'data'), resource('disk', 'boot')
    facts = dict(instance=vm['spec']['name'], bootDiskId=boot['id'],
                 provider=dict(instanceId=vm['id'], diskId=data['id'], node=1, sizeGiB=100, attempt=req['attempt']))
    helper = guest_delivery.pack(ROOT, req['source'])
    value = root.plan(req, lease, facts, access, helper)
    budget = dict(schema='gse-v51-helper-deadline-v1', sample=dict(schema='gse-v51-helper-clock-v1',
        requestSha256=m.sha(m.canonical(value['delivery'])), nonce='f'*32, bootId=BOOT, sampledNanos=1_000_000_000),
        expiresNanos=11_000_000_000)
    account = dict(user=access['user'], uid=1001, gid=1001)
    observed = dict(planSha256=m.sha(m.canonical(value)), bootId=BOOT, ids=dict(uid=0, euid=0, gid=0, egid=0),
        account=account, invoker=deepcopy(account),
        metadata=dict(instanceId=vm['id'], sshKeys=access['user']+':'+access['publicKey'], blockProjectSshKeys='TRUE', enableOslogin='FALSE'),
        ancestors=[dict(path=p, kind='directory', uid=0, mode=0o755) for p in ('/', '/var', '/var/lib')],
        parent=dict(exists=False), claim=dict(state='ABSENT', planSha256=None, deadlineSha256=None))
    return req, lease, facts, access, helper, value, budget, observed


class RootAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        (self.req, self.lease, self.facts, self.access, self.helper, self.value, self.budget,
         self.observed) = fixture(Path(self.temp.name))

    def assess(self): return root.assess(self.value, self.observed, self.budget, 2_000_000_000)

    def test_valid_plan_stays_offline_and_does_not_mutate_inputs(self):
        before = deepcopy((self.value, self.observed, self.budget))
        answer = self.assess()
        self.assertEqual(answer['decision'], 'INSTALL_ONCE')
        self.assertEqual(answer['execution'], 'offline-root-admission-only')
        for key in ('paidCloud', 'privilegedExecution', 'nativeWritesEnabled', 'fullRemoteQualification'):
            self.assertIs(answer[key], False)
        self.assertEqual(before, (self.value, self.observed, self.budget))

    def test_plan_copies_caller_owned_authority(self):
        self.access['user'] = 'foreign'; self.req['source'] = 'f'*40; self.facts['provider']['diskId'] = '999'
        self.assertEqual(root.validate_plan(self.value), self.value)
        self.assess()

    def test_unretained_unattempted_or_changed_resource_cannot_be_admitted(self):
        for kind, purpose in (('instance', 'voter'), ('disk', 'data'), ('disk', 'boot')):
            for change in ({'attempted': False, 'id': None}, {'id': '999'}):
                lease = deepcopy(self.lease)
                row = next(row for row in lease['resources'] if row['spec']['kind'] == kind and
                           row['spec']['purpose'] == purpose and row['spec'].get('node') == 1)
                row.update(change)
                with self.subTest(kind=kind, purpose=purpose, change=change), self.assertRaises(ValueError):
                    root.plan(self.req, lease, self.facts, self.access, self.helper)

    def test_foreign_request_access_and_provider_shape_rejected(self):
        for change in (lambda req, facts:req.update(guestAccessSha256='0'*64),
                       lambda req, facts:facts['provider'].update(node=True),
                       lambda req, facts:facts['provider'].update(sizeGiB=50),
                       lambda req, facts:facts['provider'].update(attempt='f'*32),
                       lambda req, facts:facts.update(instance='foreign')):
            req, facts = deepcopy(self.req), deepcopy(self.facts); change(req, facts)
            with self.assertRaises(ValueError): root.plan(req, self.lease, facts, self.access, self.helper)

    def test_helper_tamper_or_wrong_workload_does_not_produce_plan(self):
        with self.assertRaises(ValueError): root.plan(self.req, self.lease, self.facts, self.access, self.helper[:-1])
        req = dict(self.req, source='f'*40); lease = a.lease(req, 100)
        for row, old in zip(lease['resources'], self.lease['resources']): row.update(attempted=True, id=old['id'])
        with self.assertRaises(ValueError): root.plan(req, lease, self.facts, self.access, self.helper)

    def test_closed_scope_cannot_be_opened_with_flags_paths_or_actions(self):
        for change in ({'paidCloud':True}, {'privilegedExecution':True}, {'nativeWritesEnabled':True},
                       {'fullRemoteQualification':0}, {'destination':'/tmp/other'},
                       {'allowedActions':['install','query','check','format']}, {'extra':1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                root.validate_plan(dict(self.value, **change))

    def test_nonroot_and_boolean_identities_rejected(self):
        for key in ('uid', 'euid', 'gid', 'egid'):
            for bad in (1001, False, '0'):
                observed = deepcopy(self.observed); observed['ids'][key] = bad
                with self.subTest(key=key, bad=bad), self.assertRaisesRegex(ValueError, 'effective identity'):
                    root.assess(self.value, observed, self.budget, 2_000_000_000)

    def test_wrong_invoker_or_root_workload_user_rejected(self):
        for which, change in (('invoker',{'user':'foreign'}), ('invoker',{'uid':1002}),
                              ('account',{'uid':0}), ('account',{'gid':False})):
            observed = deepcopy(self.observed); observed[which].update(change)
            with self.subTest(which=which, change=change), self.assertRaises(ValueError):
                root.assess(self.value, observed, self.budget, 2_000_000_000)

    def test_metadata_changes_rejected(self):
        for key in self.observed['metadata']:
            observed = deepcopy(self.observed); observed['metadata'][key] = 'foreign'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'metadata'):
                root.assess(self.value, observed, self.budget, 2_000_000_000)

    def test_linked_writable_foreign_missing_or_duplicate_ancestors_rejected(self):
        for change in ({'kind':'symlink'}, {'uid':1001}, {'uid':False}, {'mode':0o1777}, {'path':'/tmp'}):
            observed = deepcopy(self.observed); observed['ancestors'][1].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'ancestor'):
                root.assess(self.value, observed, self.budget, 2_000_000_000)
        self.observed['ancestors'].pop()
        with self.assertRaisesRegex(ValueError, 'ancestor'): self.assess()

    def test_parent_requires_exact_private_root_directory(self):
        good = dict(exists=True, kind='directory', uid=0, mode=0o700)
        self.observed['parent'] = good; self.assess()
        for change in ({'kind':'symlink'}, {'uid':1001}, {'uid':False}, {'mode':0o755}, {'exists':1}):
            self.observed['parent'] = dict(good, **change)
            with self.subTest(change=change), self.assertRaises(ValueError): self.assess()
        self.observed['parent'] = dict(exists=0)
        with self.assertRaises(ValueError): self.assess()

    def test_boot_request_and_original_deadline_rejected(self):
        for now in (999_999_999, 11_000_000_000, True):
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, 'deadline'):
                root.assess(self.value, self.observed, self.budget, now)
        self.observed['bootId'] = 'ffffffff-ffff-ffff-ffff-ffffffffffff'
        with self.assertRaisesRegex(ValueError, 'boot'): self.assess()
        self.observed['bootId'] = BOOT; self.observed['planSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'plan'): self.assess()

    def test_consumed_terminal_claim_only_allows_query_under_same_budget(self):
        self.observed['parent'] = dict(exists=True, kind='directory', uid=0, mode=0o700)
        for state in ('SUCCEEDED', 'FAILED'):
            self.observed['claim'] = dict(state=state, planSha256=m.sha(m.canonical(self.value)),
                                          deadlineSha256=m.sha(m.canonical(self.budget)))
            self.assertEqual(self.assess()['decision'], 'QUERY_ONLY')
        self.budget['expiresNanos'] += 1
        with self.assertRaisesRegex(ValueError, 'retained claim binding'): self.assess()

    def test_partial_claim_never_authorizes_resubmit(self):
        self.observed['parent'] = dict(exists=True, kind='directory', uid=0, mode=0o700)
        self.observed['claim'] = dict(state='PARTIAL', planSha256=None, deadlineSha256=None)
        self.assertEqual(self.assess()['decision'], 'FAIL_UNCERTAIN')
        self.observed['parent'] = dict(exists=False)
        with self.assertRaisesRegex(ValueError, 'without parent'): self.assess()


if __name__ == '__main__': unittest.main()
