"""Planning guards only: these tests never execute or qualify a native history."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import phase3_qualification_plan as p


class Phase3QualificationPlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = p.decode((p.ROOT/p.PLAN).read_bytes())
        cls.acceptance = p.decode((p.ROOT/p.ACCEPTANCE).read_bytes())
        cls.catalogs = p.catalogues()

    def check(self, plan=None, acceptance=None, catalogs=None):
        return p.validate(self.plan if plan is None else plan,
                          self.acceptance if acceptance is None else acceptance,
                          self.catalogs if catalogs is None else catalogs)

    def rejected(self, mutate, reason):
        value = deepcopy(self.plan); mutate(value)
        with self.assertRaisesRegex(ValueError, reason): self.check(plan=value)

    def test_current_sources_and_complete_planning_inventory(self):
        result = self.check()
        self.assertEqual(12, result['requirements'])
        self.assertEqual(512, result['plannedHostedHistories'])
        self.assertEqual({'profiles':7, 'joining-reply-loss':3, 'remove-process':52,
                          'node-renames':4, 'joining-process':360, 'learner-histories':2, 'transfer-histories':21, 'round-histories':7, 'carried-data-histories':4,
                          'carried-transition-histories':2, 'automatic-histories':50},
                         {k:v['members'] for k,v in result['cohorts'].items()})
        self.assertEqual(120, result['cohorts']['joining-process']['executionGroups'])
        self.assertEqual(2, result['cohorts']['transfer-histories']['executionGroups'])
        self.assertEqual(7, result['cohorts']['round-histories']['executionGroups'])
        self.assertEqual(4, result['cohorts']['carried-data-histories']['executionGroups'])
        self.assertEqual(2, result['cohorts']['carried-transition-histories']['executionGroups'])
        self.assertEqual(3, result['cohorts']['automatic-histories']['executionGroups'])
        self.assertEqual(3310, result['frozenAcceptance']['scenarios'])
        self.assertEqual(24, result['frozenAcceptance']['negativeFamilies'])
        self.assertEqual([], result['frozenAcceptance']['coveredScenarioRows'])
        self.assertEqual(0, result['finalSourceNativeHistoriesExecuted'])
        self.assertEqual('source-inventory-only', result['execution'])
        self.assertEqual('NOT_EVALUATED', result['qualificationStatus'])
        for field in ('phase3Complete', 'runtimeQualified', 'frozenScenarioCoverageQualified'):
            self.assertIs(False, result[field])

    def test_phase_or_runtime_pass_cannot_be_supplied_in_plan(self):
        for field, value in [('phase3Complete',True), ('phase3Complete',0), ('status','PASS'), ('runtimeQualified',True)]:
            with self.subTest(field=field,value=value):
                self.rejected(lambda v:v.update({field:value}), 'qualification plan')

    def test_missing_duplicate_or_unknown_requirement_rejects(self):
        for action in (lambda v:v['requirements'].pop(),
                       lambda v:v['requirements'].__setitem__(1,deepcopy(v['requirements'][0])),
                       lambda v:v['requirements'][0].update(id='new-authority')):
            self.rejected(action, 'requirement inventory')

    def test_related_families_cannot_be_mislabelled_covered(self):
        self.rejected(lambda v:v['requirements'][0].update(families=['S06']), 'family binding')
        self.rejected(lambda v:v['requirements'][0].update(covered=True), 'requirement fields')

    def test_public_and_final_acceptance_phase_remain_owned_separately(self):
        self.rejected(lambda v:v['laterPhases'].update(publicOperationsAndReads=3), 'later-phase boundary')
        changed = deepcopy(self.acceptance); changed['scenarios'][0]['requiredPhase'] = 3
        plan = deepcopy(self.plan); plan['acceptancePlanSha256'] = p.digest(p.encoded(changed))
        with self.assertRaisesRegex(ValueError, 'owning acceptance phase'): self.check(plan,changed)

    def test_frozen_plan_hash_and_complete_axes_remain_bound(self):
        changed = deepcopy(self.acceptance); changed['scenarios'][0]['cuts'].pop()
        with self.assertRaisesRegex(ValueError, 'frozen plan binding'): self.check(acceptance=changed)
        plan = deepcopy(self.plan); plan['acceptancePlanSha256'] = p.digest(p.encoded(changed))
        with self.assertRaisesRegex(ValueError, 'frozen scenario counts changed'): self.check(plan,changed)

    def test_workflow_catalogue_counts_and_cases_cannot_drift_silently(self):
        for action in (lambda v:v['cohorts'].pop('node-renames'),
                       lambda v:v['cohorts']['node-renames'].update(members=True),
                       lambda v:v['cohorts']['joining-process'].update(members=359),
                       lambda v:v['cohorts']['joining-process'].update(casesSha256='0'*64),
                       lambda v:v['cohorts']['profiles'].update(status='PASS')):
            self.rejected(action,'qualification .*catalogue|qualification cohort inventory')
        catalogs = deepcopy(self.catalogs)
        catalogs['node-renames']['casesSha256'] = p.digest(p.encoded(list(reversed(catalogs['node-renames']['cases']))))
        with self.assertRaisesRegex(ValueError,'declared catalogue'): self.check(catalogs=catalogs)

    def test_joining_groups_preserve_the_exact_whole_history_partition(self):
        from . import joining_process_hosted as hosted
        groups = dict(hosted.SHARDS); first = next(iter(groups)); groups[first] = tuple(reversed(groups[first]))
        with patch.object(hosted,'SHARDS',groups), self.assertRaisesRegex(ValueError,'whole-history partition'):
            p.catalogues()

    def test_transfer_groups_cannot_drop_or_split_original_histories(self):
        from . import transfer_history_hosted as hosted
        self.assertEqual([3,18],[len(v) for v in hosted.SHARDS.values()])
        groups=dict(hosted.SHARDS);groups['tcp-lifetimes']=groups['tcp-lifetimes'][:-1]
        split=dict(hosted.SHARDS);split['first']=split['tcp-lifetimes'][:1];split['tcp-lifetimes']=split['tcp-lifetimes'][1:]
        for value in (groups,split):
            with patch.object(hosted,'SHARDS',value),self.assertRaisesRegex(ValueError,'whole-matrix partition'):
                p.catalogues()

    def test_empty_unknown_duplicate_dependencies_and_orphans_reject(self):
        for action in (lambda v:v['requirements'][0].update(gaps=[]),
                       lambda v:v['requirements'][0].update(gaps=['unknown']),
                       lambda v:v['requirements'][0].update(cohorts=['profiles','profiles'])):
            self.rejected(action,'requirement dependencies')
        self.rejected(lambda v:[r.update(cohorts=[]) for r in v['requirements']], 'orphan cohort/gap')

    def test_automatic_groups_preserve_both_histories_and_complete_reply_matrix(self):
        from . import automatic_history_hosted as hosted
        self.assertEqual([1,1,48],[len(v) for v in hosted.SHARDS.values()])
        groups=dict(hosted.SHARDS);groups['reply-revocation']=groups['reply-revocation'][:-1]
        split=dict(hosted.SHARDS);split['extra']=split['reply-revocation'][:1];split['reply-revocation']=split['reply-revocation'][1:]
        for value in (groups,split):
            with patch.object(hosted,'SHARDS',value),self.assertRaisesRegex(ValueError,'whole-matrix partition'):
                p.catalogues()

    def test_gaps_cannot_be_removed_reordered_or_self_certified(self):
        self.rejected(lambda v:v['gaps'].pop(), 'gap inventory/order')
        self.rejected(lambda v:v['gaps'].reverse(), 'gap inventory/order')
        self.rejected(lambda v:v['gaps'][0].update(status='PASS'), 'gap cannot self-close')
        self.rejected(lambda v:v['gaps'][0].update(acceptance=' '), 'gap cannot self-close')
        self.rejected(lambda v:v['gaps'][0].update(dependsOn=['final-source-execution']), 'gap dependency order')
        self.rejected(lambda v:v['gaps'][0].update(dependsOn=['component-cohorts']), 'gap dependency order')

    def test_source_test_and_reader_references_are_mandatory(self):
        for field in ('implementation','tests','readers','docs'):
            with self.subTest(field=field):
                self.rejected(lambda v:v['requirements'][0].update({field:[]}), 'requirement references')
        self.rejected(lambda v:v['requirements'][0].update(tests=['docs/v5x/v5.3/PHASE_3_ENTRY_PLAN.md']), 'reference category')
        self.rejected(lambda v:v['requirements'][0].update(readers=['scripts/v53/missing-reader.py']), 'missing/bounded reference')

    def test_reference_paths_cannot_escape_or_follow_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root/'real').write_bytes(b'real'); (root/'link').symlink_to('real')
            (root/'directory').mkdir(); (root/'alias').symlink_to('directory',target_is_directory=True)
            (root/'directory/file').write_bytes(b'inner')
            for name in ('../outside','/etc/passwd','directory/../real','./real','directory//file','directory\\file'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError,'reference path'): p.regular(root,name)
            for name in ('link','alias/file'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError,'linked reference'): p.regular(root,name)
            self.assertEqual(b'real',p.regular(root,'real'))

    def test_duplicate_json_keys_reject(self):
        with self.assertRaisesRegex(ValueError,'duplicate key'): p.decode('{"status":"PLANNED","status":"PASS"}')

    def test_generated_report_is_source_inspection_only_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(p.subprocess,'check_output',side_effect=['a'*40+'\n',' M local.py\n']):
            output = Path(temp)/'new'
            result = p.run(output)
            self.assertEqual('a'*40,result['baseHead'])
            self.assertEqual([' M local.py'],result['worktreeStatus'])
            self.assertEqual(result,p.decode((output/'receipt.json').read_bytes()))
            original = (output/'receipt.json').read_bytes()
            with self.assertRaises(FileExistsError): p.run(output)
            self.assertEqual(original,(output/'receipt.json').read_bytes())

    def test_failed_inspection_leaves_failed_receipt(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(p,'inspect',side_effect=ValueError('missing original source')):
            output = Path(temp)/'failed'
            with self.assertRaisesRegex(ValueError,'missing original source'): p.run(output)
            result = p.decode((output/'receipt.json').read_bytes())
            self.assertEqual('FAIL',result['status']); self.assertIs(False,result['phase3Complete'])

    def test_drift_during_audit_refuses_pass(self):
        original = p.inspect
        def changed():
            result, plan, acceptance = original()
            result['inspectedFiles'][p.PLAN] = '0'*64
            return result,plan,acceptance
        with tempfile.TemporaryDirectory() as temp, patch.object(p,'inspect',side_effect=changed), \
             patch.object(p.subprocess,'check_output',side_effect=['a'*40+'\n','']):
            output = Path(temp)/'changed'
            with self.assertRaisesRegex(ValueError,'inspected source changed'): p.run(output)
            self.assertEqual('FAIL',json.loads((output/'receipt.json').read_text())['status'])


if __name__ == '__main__': unittest.main()
