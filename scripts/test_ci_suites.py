"""Mutate the actual CI and registry; external consumers remain independent."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import ci_inventory, ci_suites as s
from scripts.v51 import cloud_ci, cloud_runner_artifacts


class SuiteContractTest(unittest.TestCase):
    def setUp(self):
        self.registry = s.load_registry()
        self.workflow = s.read(s.ROOT, s.WORKFLOW)
        self.related = {".github/workflows/release.yml": s.read(s.ROOT, ".github/workflows/release.yml")}

    def check(self, workflow=None, registry=None, related=None):
        return s.validate_workflow(registry if registry is not None else self.registry,
                                   workflow if workflow is not None else self.workflow,
                                   related if related is not None else self.related)

    def rejected(self, workflow=None, registry=None, related=None):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            self.check(workflow, registry, related)

    def replace_job(self, job, before, after):
        prefix, tail = self.workflow.split("\n  " + job + ":\n", 1)
        self.assertIn(before, tail)
        return prefix + "\n  " + job + ":\n" + tail.replace(before, after, 1)

    def test_actual_inventory_matches_independent_cloud_consumer(self):
        names = self.check()
        self.assertEqual(40, len(self.registry["suites"]))
        self.assertEqual(42, len(s.job_blocks(self.workflow)))
        self.assertEqual(50, len(names))
        self.assertCountEqual(cloud_ci.expected_jobs(self.workflow), names)
        for key in ("v51-remote-rich-shards", "v51-owned-canonical-tapes", "v51-owned-canonical"):
            self.assertIsNotNone(next(v["matrix"] for v in self.registry["suites"] if v["id"] == key))

    def test_committed_inventory_matches_validated_current_topology(self):
        ci_inventory.check_document()

    def test_v52_whole_histories_use_independent_shared_build_lanes(self):
        commands = {
            "v52-foundation": ("phase1-foundation", "phase3-public-reads", "phase4-read-application", "phase4-read-compaction"),
            "v52-read-faults": ("phase4-public-faults", "phase4-read-identity", "phase4-read-import"),
            "v52-read-lifecycle": ("phase4-public-lifecycle", "phase4-read-resource"),
            "v52-read-protocol": ("phase4-read-protocol", "phase4-read-negatives"),
        }
        jobs = s.job_blocks(self.workflow)
        actual = {}
        for job, body in jobs.items():
            steps = s.steps(s.fields(body, 4)["steps"])
            calls = ["".join(values["run"]).strip() for values in steps.values()
                     if "run" in values and "scripts/verify-v52-" in "".join(values["run"])]
            if calls:
                actual[job] = calls
        self.assertEqual({job: ["scripts/verify-v52-" + gate + ".sh --skip-build" for gate in gates]
                          for job, gates in commands.items()}, actual)
        rows = {row["id"]: row for row in self.registry["suites"]}
        for job in commands:
            row = rows[job]
            self.assertEqual(["changes", "v51-verification-build"], row["needs"])
            self.assertEqual(("success", "success", "skipped"),
                             (row["fullResult"], row["integrationResult"], row["docsResult"]))
            self.assertIsNone(row["matrix"])
            self.assertIn(job, s.BUILD_CONSUMERS)

    def test_documentation_rejects_missing_and_stale_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); document = root / ci_inventory.DOCUMENT
            document.parent.mkdir()
            with patch.object(s, 'check', return_value=self.registry):
                with self.assertRaises(FileNotFoundError):ci_inventory.check_document(root)
                document.write_text(ci_inventory.render(root), encoding='utf-8')
                ci_inventory.check_document(root)
                document.write_text(document.read_text().replace('50 expanded full jobs', '38 expanded full jobs'), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'stale'):ci_inventory.check_document(root)

    def test_inventory_generation_propagates_invalid_source_contract(self):
        with patch.object(s, 'check', side_effect=ValueError('unregistered job')):
            with self.assertRaisesRegex(ValueError, 'unregistered job'):ci_inventory.render()

    def test_external_consumers_are_registered(self):
        interfaces = self.registry["externalInterfaces"]
        owned = next(v for v in interfaces if v["name"] == cloud_ci.OWNED_JOB)
        self.assertIn(cloud_ci.OWNED_STEP, owned["steps"])
        for role in ("build", "package"):
            selected = next(v for v in interfaces if v["name"] == cloud_runner_artifacts.JOBS[role])
            self.assertIn(cloud_runner_artifacts.STEPS[role], selected["steps"])
        release = next(v for v in interfaces if v["workflow"].endswith("release.yml") and v["job"] == "publish")
        self.assertEqual("production-release", release["environment"])
        self.assertIn("Publish approved artifacts to Maven Central", release["steps"])

    def test_schema_duplicates_unknown_and_missing_fields_fail(self):
        for key in self.registry:
            value = copy.deepcopy(self.registry);del value[key];self.rejected(registry=value)
        value = copy.deepcopy(self.registry);value["profile"] = "core";self.rejected(registry=value)
        value = copy.deepcopy(self.registry);value["schema"] = "future";self.rejected(registry=value)
        value = copy.deepcopy(self.registry);value["suites"].append(value["suites"][0]);self.rejected(registry=value)
        with self.assertRaises(ValueError):s.strict_json('{"schema":1,"schema":2}')
        for key in self.registry["suites"][0]:
            value = copy.deepcopy(self.registry);del value["suites"][0][key];self.rejected(registry=value)

    def test_registry_cannot_alone_remove_or_add_a_gate(self):
        value = copy.deepcopy(self.registry);value["suites"].pop();self.rejected(registry=value)
        value = copy.deepcopy(self.registry);extra = copy.deepcopy(value["suites"][0]);extra.update(id="new-gate", name="New gate")
        value["suites"].append(extra);self.rejected(registry=value)
        value = copy.deepcopy(self.registry);value["suites"][0]["docsResult"] = "success";self.rejected(registry=value)
        value = copy.deepcopy(self.registry);value["suites"][0]["fullResult"] = "skipped";self.rejected(registry=value)

    def test_workflow_new_missing_duplicate_and_aliased_job_rejected(self):
        self.rejected(self.workflow + "\n  orphan:\n    name: Orphan\n    steps:\n      - name: Noop\n        run: true\n")
        start = self.workflow.index("\n  reactor-core:\n");end = self.workflow.index("\n  v51-verification-build:\n")
        self.rejected(self.workflow[:start] + self.workflow[end:])
        self.rejected(self.workflow + self.workflow[start:end])
        self.rejected(self.workflow.replace("  reactor-core:\n", "  reactor-core: *other\n"))
        self.rejected(self.workflow.replace("  reactor-core:\n", "  'reactor-core':\n"))

    def test_names_needs_conditions_and_timeouts_rejected(self):
        for before, after in (("name: Reactor tests", "name: Renamed"),
                              ("needs: changes", "needs: [changes, compatibility]"),
                              (s.FULL_IF, "${{ false }}"),
                              ("timeout-minutes: 30", "timeout-minutes: 31"),
                              ("runs-on: ubuntu-latest", "runs-on: windows-latest")):
            self.rejected(self.replace_job("reactor-core", before, after))

    def test_required_cannot_omit_add_or_duplicate_dependencies(self):
        for replacement in ("", "      - unregistered\n", "      - changes\n"):
            self.rejected(self.replace_job("required", "      - reactor-core\n", replacement))
        self.rejected(self.replace_job("required", s.ALWAYS, "${{ success() }}"))
        self.rejected(self.replace_job("required", "name: Required", "name: Other"))

    def test_classifier_and_validator_binding_cannot_be_skipped_or_replaced(self):
        for job, before, after in (
            ("changes", "run: python3 -m scripts.ci_plan --output target/ci-shadow-plan", "run: echo run_full_ci=false"),
            ("changes", "id: scope", "id: scope\n        if: false"),
            ("changes", "run_full_ci: ${{ steps.scope.outputs.run_full_ci }}", "run_full_ci: 'false'"),
            ("required", "run: python3 -m scripts.ci_required", "run: true"),
            ("required", "CI_NEEDS_JSON: ${{ toJSON(needs) }}", "CI_NEEDS_JSON: '{}'"),
            ("required", "run: python3 -m scripts.ci_required", "if: false\n        run: python3 -m scripts.ci_required")):
            self.rejected(self.replace_job(job, before, after))
        for job in ("changes", "required"):
            self.rejected(self.replace_job(job, "fetch-depth: 0", "fetch-depth: 1"))

    def test_integration_cannot_omit_other_suites_or_change_canonical_condition(self):
        for suite in self.registry["suites"]:
            value = copy.deepcopy(self.registry)
            row = next(v for v in value["suites"] if v["id"] == suite["id"])
            row["integrationResult"] = "success" if row["integrationResult"] == "skipped" else "skipped"
            with self.subTest(job=suite["id"]):self.rejected(registry=value)
        self.rejected(self.replace_job("v51-owned-canonical", s.CANONICAL_IF, s.FULL_IF))
        self.rejected(self.replace_job("reactor-core", s.FULL_IF, s.CANONICAL_IF))

    def test_fixed_matrix_members_order_and_fail_fast_rejected(self):
        changes = [
            ("v51-owned-canonical", "repetition: [1, 2, 3]", "repetition: [1, 2]"),
            ("v51-owned-canonical", "repetition: [1, 2, 3]", "repetition: [1, 2, 3, 4]"),
            ("v51-owned-canonical", "repetition: [1, 2, 3]", "repetition: [3, 2, 1]"),
            ("v51-owned-canonical", "fail-fast: false", "fail-fast: true"),
            ("v51-remote-rich-shards", "shard: [published-controls, automatic-healthy, automatic-concurrent]", "shard: [published-controls]"),
            ("v51-remote-rich-shards", "fail-fast: false", "fail-fast: true"),
            ("v51-owned-canonical-tapes", "tape: v44-healthy", "tape: extra"),
            ("v51-owned-canonical-tapes", "mode: published-v4.4-local", "mode: candidate-v5.1-automatic"),
            ("v51-owned-canonical-tapes", "fail-fast: false", "fail-fast: true")]
        for job, before, after in changes:
            with self.subTest(job=job, after=after):self.rejected(self.replace_job(job, before, after))
        self.rejected(self.replace_job("reactor-core", "    steps:\n", "    strategy:\n      matrix:\n        os: [linux, mac]\n    steps:\n"))

    def test_unreviewed_matching_matrix_still_fails_real_cloud_consumer(self):
        value = copy.deepcopy(self.registry)
        suite = next(v for v in value["suites"] if v["id"] == "v51-owned-canonical")
        suite["matrix"]["repetition"] = [1, 2]
        workflow = self.replace_job("v51-owned-canonical", "repetition: [1, 2, 3]", "repetition: [1, 2]")
        self.check(workflow, value)  # Consistency alone is not external compatibility.
        with self.assertRaises(ValueError):cloud_ci.expected_jobs(workflow)

    def test_dynamic_or_ambiguous_matrix_values_rejected(self):
        for member in ("${{ inputs.shard }}", "*alias", "null", "true", "off", True, 0, "a, b", "a # comment"):
            with self.subTest(member=member), self.assertRaises(ValueError):
                s.strategy({"shard": [member]})

    def test_continue_on_error_at_job_or_step_rejected_even_false(self):
        for value in ("true", "false", "${{ always() }}"):
            self.rejected(self.replace_job("reactor-core", "    steps:\n", "    continue-on-error: " + value + "\n    steps:\n"))
            self.rejected(self.replace_job("reactor-core", "        run: scripts/verify-version-alignment.sh", "        continue-on-error: " + value + "\n        run: scripts/verify-version-alignment.sh"))

    def test_duplicate_mapping_and_cycle_rejected(self):
        self.rejected(self.replace_job("reactor-core", "    name: Reactor tests", "    name: Reactor tests\n    name: Reactor tests"))
        self.rejected(self.replace_job("reactor-core", "        run: scripts/verify-version-alignment.sh", "        run: true\n        run: scripts/verify-version-alignment.sh"))
        value = copy.deepcopy(self.registry);value["suites"][0]["needs"].append(value["suites"][1]["id"])
        value["suites"][1]["needs"].append(value["suites"][0]["id"]);self.rejected(registry=value)

    def test_artifact_identity_restore_provenance_and_retention_rejected(self):
        changes = [
            ("v51-verification-build", "artifact_id: ${{ steps.handoff.outputs.artifact-id }}", "artifact_id: '123'"),
            ("v51-foundation", "artifact-id: ${{ needs.v51-verification-build.outputs.artifact_id || 'missing-build-artifact' }}", "artifact-id: latest-build"),
            ("v51-remote-rich-shards", "artifact-ids: ${{ needs.v51-remote-rich-inputs.outputs.artifact_id || 'missing-rich-inputs-artifact' }}", "name: latest-rich-inputs"),
            ("v51-remote-rich", "artifact-ids: ${{ needs.v51-remote-rich-shards.outputs.published_controls || 'missing-rich-shard-artifact' }}", "artifact-ids: 123"),
            ("v51-foundation", "retention-days: 14", "retention-days: 1"),
            ("release-artifacts", "retention-days: 90", "retention-days: 14"),
            ("v51-foundation", "if: ${{ always() }}", "if: ${{ success() }}"),
            ("v51-verification-build", "if-no-files-found: error", "if-no-files-found: warn")]
        for job, before, after in changes:
            with self.subTest(job=job, before=before):self.rejected(self.replace_job(job, before, after))

    def test_external_step_name_or_false_condition_rejected(self):
        self.rejected(self.workflow.replace("name: " + cloud_ci.OWNED_STEP, "name: Hidden qualification"))
        self.rejected(self.workflow.replace("name: " + cloud_ci.OWNED_STEP, "name: " + cloud_ci.OWNED_STEP + "\n        if: false"))
        related = {key: value.replace("name: Build, sign, and inspect release artifacts", "name: Hidden signing") for key, value in self.related.items()}
        self.rejected(related=related)
        related = {key: value.replace("environment: production-release", "environment: unprotected") for key, value in self.related.items()}
        self.rejected(related=related)

    def test_plain_and_quoted_scalar_maps_preserve_literal_actions_expressions(self):
        self.assertEqual("**/target/**", s.scalar(("'**/target/**'", "")))
        self.assertEqual("${{ toJSON(needs) }}", s.scalar(('${{ toJSON(needs) }}', "")))
        for unsupported in ("&anchor", "*alias", "!tag", "[flow]", "{flow}"):
            with self.assertRaises(ValueError):s.scalar((unsupported, ""))


if __name__ == "__main__":unittest.main()
