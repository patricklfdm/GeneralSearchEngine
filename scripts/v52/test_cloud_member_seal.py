"""Pure correlation models; native close tests exercise original wire effects."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import cloud_member_seal as s, cloud_prepared as prepared
from .test_cloud_prepared import arguments


def fixture(**options):
    args = arguments(**options); plan = prepared.prepare(**args); req = plan['request']; source = args['proof']['source']
    cfg = dict(schema='gse-v52-preflight-config-v1', provider=args['configuration'], projectNumber=args['project_number'],
               layout=args['resource_layout'], policy=args['ownership_policy'])
    lease = s.a.lease(req, 1001); lease['phase'] = 'ACTIVE'
    for i, row in enumerate(lease['resources'], 1): row.update(attempted=True, id=str(100+i))
    claim = s.a.resource_claim(lease)
    clean = dict(status='PASS', checks=[dict(name=r['spec']['name'], expectedId=r['id'], absent=True, observed=None)
        for r in lease['resources']], errors=[], leftovers=[])
    manifest = {'synthetic': 'original fixture manifest'}
    completed = dict(schema='gse-v52-owned-completion-v1', execution=req['execution'], requestSha256=s.digest(s.encoded(req)),
        status='PASS', evidenceSha256=s.digest(s.encoded(manifest)), cleanupSha256=s.digest(s.encoded(clean)))
    original = args['original_ledger']['ledger'] if args['original_ledger'] else s.a.empty_ledger(domain='native')
    ledger = s.a.finish(s.a.reserve(original, req, previous_cost=plan['reservation']['previousCostMicrousd'], cost=4_000_000), req, completed)
    context = dict(schema=s.credentials.SCHEMA, **s.credentials.selection(cfg['provider'], cfg['projectNumber'], 'runner'),
                   source=source['source'], runId=123456, runAttempt=2)
    return dict(cfg=cfg, source=source, request=req, manifest=manifest, completed=completed, clean=clean,
                ledger=dict(generation=10, value=ledger), claim=claim, plan=plan, context=context, started=1010, now=1100)


class SealTest(unittest.TestCase):
    def setUp(self):
        self.args = fixture(); self.value = s.create(**self.args)
        self.restored = {k: self.args[k] for k in ('request', 'manifest', 'completed')}
        self.restored['cleanup'] = self.args['clean']

    def match(self, value=None):
        return s.match(value or self.value, self.args['cfg'], self.args['source'], self.restored, self.args['ledger'], now=1100)

    def test_compact_non_qualified_seal_matches_originals(self):
        self.assertEqual(dict(run='123456', attempt=2), self.match())
        self.assertFalse(self.value['fullRemoteQualification']); self.assertLess(len(s.encoded(self.value)), 16384)
        self.assertNotIn('ledger', self.value); self.assertNotIn('claim', self.value)

    def test_cleanup_foreign_id_missing_terminal_or_failed_completion_cannot_seal(self):
        for mutate in (lambda v:v['clean']['checks'][0].update(expectedId='999'), lambda v:v['clean']['checks'].pop(),
                       lambda v:v['completed'].update(status='FAIL', evidenceSha256=None),
                       lambda v:v['ledger']['value']['entries'].pop(), lambda v:v['ledger']['value']['entries'][0].update(reservedCostMicrousd=1)):
            args = deepcopy(self.args); mutate(args)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): s.create(**args)

    def test_context_environment_job_workflow_source_and_unknown_fields_reject(self):
        for change in (dict(environment='v51-cloud-benchmark'), dict(job='other'), dict(workflow='.github/workflows/ci.yml'),
                       dict(source='f'*40), dict(event='push'), dict(runAttempt=True), dict(token='must not leak')):
            args = deepcopy(self.args); args['context'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError): s.create(**args)

    def test_later_failed_attempt_costs_are_preserved_and_not_part_of_original_prefix(self):
        req = prepared.prepare(**arguments(member='canonical-1', attempt='d'*32))['request']
        completion = dict(self.args['completed'], status='FAIL', evidenceSha256=None, requestSha256=s.digest(s.encoded(req)))
        original = self.args['ledger']['value']
        self.args['ledger'] = dict(generation=12, value=s.a.finish(s.a.reserve(original, req, previous_cost=4_000_000, cost=2_000_000), req, completion))
        self.match(); self.assertEqual(6_000_000, s.a.inspect_ledger(self.args['ledger']['value'], domain='native')['reservedCostMicrousd'])
        self.args['ledger']['value']['entries'][0]['reservedCostMicrousd'] = 1
        with self.assertRaises(ValueError): self.match()

    def test_immutable_object_change_or_generation_rollback_rejects(self):
        for key in ('manifest', 'completed', 'cleanup'):
            original = self.restored[key]; self.restored[key] = dict(original, altered=True)
            with self.subTest(key=key), self.assertRaises(ValueError): self.match()
            self.restored[key] = original
        self.args['ledger']['generation'] = 9
        with self.assertRaisesRegex(ValueError, 'ledger prefix'): self.match()

    def test_tampered_public_fields_and_copied_dictionary_cannot_publish(self):
        for change in (dict(fullRemoteQualification=True), dict(reservedCostMicrousd=1), dict(completionSha256='f'*64),
                       dict(ledgerPrefixSha256='f'*64), dict(ledgerEntries=1), dict(completedAt=1101)):
            with self.subTest(change=change), self.assertRaises(ValueError): self.match(dict(self.value, **change))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/'public'
            with self.assertRaisesRegex(ValueError, 'closed session'): s.publish(self.value, output)
            self.assertFalse(output.exists())


if __name__ == '__main__': unittest.main()
