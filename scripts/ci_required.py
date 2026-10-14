"""Validate GitHub's complete needs object; full/docs coverage is unchanged."""
from __future__ import annotations

import json
import os

from scripts import ci_observation, ci_plan, ci_suites as suites


def evaluate(needs, registry, expected_plan=None):
    suites.validate_registry(registry)
    expected_ids = {v["id"] for v in registry["suites"]} | {"changes"}
    errors = []

    def reject(job, actual, expected, reason):
        errors.append(dict(job=job, actual=actual, expected=expected, reason=reason))

    if type(needs) is not dict:
        reject("needs", type(needs).__name__, "object", "invalid needs schema")
        return dict(status="FAIL", profile=None, errors=errors)
    for key in sorted(set(needs) - expected_ids):
        reject(key, "unexpected", "absent", "unregistered dependency")
    valid = {}
    for key in sorted(expected_ids):
        if key not in needs:
            reject(key, "missing", "result and outputs", "dependency missing; not a skip")
            continue
        value = needs[key]
        if type(value) is not dict or set(value) != {"result", "outputs"}:
            reject(key, "invalid fields", "result and outputs", "invalid dependency schema")
            continue
        outputs = value["outputs"]
        if type(outputs) is not dict or not all(type(k) is str and type(v) is str for k, v in outputs.items()):
            reject(key, "invalid outputs", "string map", "invalid output schema")
            continue
        valid[key] = value
    changes = valid.get("changes")
    profile = None
    if changes is not None:
        if changes["result"] != "success":
            reject("changes", changes["result"], "success", "classifier did not succeed")
        try:
            plan = ci_plan.checked_outputs(changes["outputs"], registry, expected_plan)
            profile = plan["profile"]
        except (ValueError, KeyError, TypeError):
            reject("changes", "invalid", "source-bound execution plan", "invalid classifier output")
    for suite in registry["suites"]:
        key = suite["id"]
        if key not in valid:
            continue
        result = valid[key]["result"]
        expected = suite[profile + "Result"] if profile else "unavailable until classifier succeeds"
        if profile is None or result != expected:
            reject(key, result, expected, "unexpected suite result")
    return dict(status="FAIL" if errors else "PASS", profile=profile, errors=errors)


def main(env=None, root=suites.ROOT):
    env = os.environ if env is None else env
    try:
        needs = suites.strict_json(env.get("CI_NEEDS_JSON"))
        registry = suites.check(root)
        claimed = ci_plan.checked_outputs(needs["changes"]["outputs"], registry)
        producer_env = ci_observation.producer_environment(claimed, env)
        expected, _ = ci_plan.compute(root, producer_env, ci_plan.event(env))
        result = evaluate(needs, registry, expected)
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
        result = dict(status="FAIL", profile=None, errors=[dict(job="Required", reason=str(error))])
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
