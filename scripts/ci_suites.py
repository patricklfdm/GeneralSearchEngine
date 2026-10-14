"""Closed CI inventory checks, using only the Python standard library.

This is deliberately not a YAML loader. Only this repository's explicit job,
step, scalar-map and fixed-matrix spelling is accepted. Unknown/duplicate
structure fails rather than disappearing from the required suite inventory.
No commands or expressions in the registry/workflow are evaluated.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = "scripts/ci_suite_registry.json"
WORKFLOW = ".github/workflows/ci.yml"
SCHEMA = "gse-ci-suites-v2"
FULL_IF = "${{ needs.changes.outputs.run_full_ci == 'true' }}"
CANONICAL_IF = "${{ needs.changes.outputs.run_canonical == 'true' }}"
PLAN_OUTPUTS = ("run_full_ci", "profile", "run_canonical", "plan", "plan_sha256")
ALWAYS = "${{ always() }}"
LIMIT = 512 * 1024
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*\Z")
MATRIX_VALUE = re.compile(r"[a-z][a-z0-9.-]*\Z")
RESTORE_ACTION = "./.github/actions/v51-restore-build"
RETAIN_ACTION = "./.github/actions/v51-retain-build"
RESTORE_STEP = "Validate and restore V5.1 verification inputs"
RETAIN_STEP = "Retain restored build provenance including failures"
DOWNLOAD_STEP = "Download this run's exact-source verification inputs"
BUILD_ID = "${{ needs.v51-verification-build.outputs.artifact_id || 'missing-build-artifact' }}"
BUILD_CONSUMERS = frozenset((
    "v51-foundation", "v51-remote-faults", "v51-admission-resources", "v51-promise-crashes",
    "v51-public-reads-faults", "v51-public-recovery-pressure", "v51-public-hardening",
    "v51-protocol-selection", "v51-candidate-crashes", "v51-reclamation", "v51-full-size-runtime",
))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(text):
    need(isinstance(text, str) and len(text.encode("utf-8")) <= LIMIT, "JSON input missing/oversized")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError("invalid JSON constant: " + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def keys(value, expected, label):
    need(type(value) is dict and set(value) == set(expected), label + " fields")


def text(value):
    return type(value) is str and bool(value) and not any(ord(c) < 32 for c in value)


def unique_strings(value, label):
    need(type(value) is list and all(text(v) for v in value) and len(value) == len(set(value)), label)


def read(root, path):
    file = root / path
    need(file.is_file() and not file.is_symlink() and file.stat().st_size <= LIMIT, "missing/unsafe/oversized file: " + path)
    return file.read_text(encoding="utf-8")


def content(value):
    """Strip only full comment/blank lines, never text inside a scalar."""
    return [line for line in value.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def job_blocks(workflow):
    need(workflow.count("\njobs:\n") == 1 and "\t" not in workflow, "explicit jobs block required")
    result = {}; current = None
    for line in workflow.split("\njobs:\n", 1)[1].splitlines():
        match = re.fullmatch(r"  ([a-z][a-z0-9-]*):", line)
        if match:
            current = match[1]
            need(current not in result, "duplicate job: " + current)
            result[current] = []
        elif line.strip() and not line.lstrip().startswith("#"):
            need(current is not None and line.startswith("    "), "unreviewed job structure")
            result[current].append(line)
    need(result, "empty jobs")
    return {key: "\n".join(lines) + "\n" for key, lines in result.items()}


def fields(block, indent):
    result = {}; current = None
    for line in content(block):
        match = re.fullmatch(r" {" + str(indent) + r"}([\w-]+):(?: (.*))?", line)
        if match:
            current = match[1]
            need(current not in result, "duplicate field: " + current)
            result[current] = [match[2] or "", []]
        else:
            need(current is not None and line.startswith(" " * (indent + 2)), "unreviewed field structure: " + line[:100])
            result[current][1].append(line)
    return {key: (value, "\n".join(lines)) for key, (value, lines) in result.items()}


def scalar(pair):
    value, block = pair
    need(not block and bool(value), "explicit scalar required")
    if value.startswith("'"):
        need(re.fullmatch(r"'(?:[^']|'')*'", value), "single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.startswith('"'):
        result = strict_json(value)
        need(type(result) is str, "double-quoted scalar")
        return result
    need(not value.startswith(("&", "*", "!", "{", "[")), "explicit scalar required")
    # Actions expressions are literals here, not YAML flow maps.
    return value


def string_map(pair, indent):
    value, block = pair
    need(not value, "explicit mapping required")
    result = {}
    for key, (value, children) in fields(block, indent).items():
        if value == "|":
            lines = children.splitlines()
            need(lines and all(line.startswith(" " * (indent + 2)) for line in lines), "scalar block indent")
            result[key] = "\n".join(line[indent + 2:] for line in lines) + "\n"
        else:
            result[key] = scalar((value, children))
    return result


def dependencies(pair):
    if pair is None:
        return []
    value, block = pair
    if value.startswith("[") and value.endswith("]") and not block:
        values = value[1:-1].split(", ")
    elif not value:
        lines = content(block)
        need(all(re.fullmatch(r"      - [a-z][a-z0-9-]*", line) for line in lines), "explicit needs list")
        values = [line[8:] for line in lines]
    else:
        values = [scalar(pair)]
    unique_strings(values, "duplicate/empty needs")
    need(values and all(IDENTIFIER.fullmatch(v) for v in values), "invalid needs")
    return values


def steps(pair):
    value, block = pair
    need(not value, "explicit steps required")
    result = {}; current = None
    for line in content(block):
        match = re.fullmatch(r"      - name: (.+)", line)
        if match:
            current = match[1]
            need(current not in result, "duplicate step: " + current)
            result[current] = []
        else:
            need(current is not None and line.startswith("        "), "explicit named step required")
            result[current].append(line)
    need(result, "empty steps")
    parsed = {key: fields("\n".join(lines), 8) for key, lines in result.items()}
    for name, values in parsed.items():
        need("continue-on-error" not in values, "continue-on-error step: " + name)
    return parsed


def load_actions(root=ROOT):
    return {path: read(root, path[2:] + "/action.yml") for path in (RESTORE_ACTION, RETAIN_ACTION)}


def composite_steps(source, input_name):
    """Read only our two local actions, not an arbitrary nested action graph."""
    need("\t" not in source, "composite indentation")
    metadata = fields(source, 0)
    keys(metadata, {"name", "description", "inputs", "runs"}, "composite metadata")
    scalar(metadata["name"]); scalar(metadata["description"])
    need(not metadata["inputs"][0] and not metadata["runs"][0], "composite explicit mappings")
    inputs = fields(metadata["inputs"][1], 2)
    keys(inputs, {input_name}, "composite inputs")
    need(not inputs[input_name][0], "composite input mapping")
    spec = fields(inputs[input_name][1], 4)
    keys(spec, {"description", "required"}, "composite input")
    scalar(spec["description"])
    need(spec["required"] == ("true", ""), "composite input must be required")
    runs = fields(metadata["runs"][1], 2)
    keys(runs, {"using", "steps"}, "composite runs")
    need(scalar(runs["using"]) == "composite" and not runs["steps"][0], "composite execution")
    return steps(("", "\n".join("  " + line for line in runs["steps"][1].splitlines())))


def expand_steps(parsed, job, actions):
    """Expand reviewed data bindings for contract comparison, without evaluation."""
    result = {}; calls = []
    for name, values in parsed.items():
        uses = scalar(values["uses"]) if "uses" in values else ""
        if not uses.startswith("./"):
            expanded = {name: values}
        else:
            need(job in BUILD_CONSUMERS and uses in (RESTORE_ACTION, RETAIN_ACTION), "unreviewed local action: " + job)
            restore = uses == RESTORE_ACTION
            keys(values, {"uses", "with"} if restore else {"uses", "with", "if"}, "composite caller")
            need(name == (RESTORE_STEP if restore else RETAIN_STEP), "composite caller name")
            inputs = string_map(values["with"], 10)
            input_name = "artifact-id" if restore else "artifact-name"
            keys(inputs, {input_name}, "composite caller inputs")
            expected = BUILD_ID if restore else job + "-build-inputs-${{ github.sha }}"
            need(inputs[input_name] == expected, "composite artifact binding: " + job)
            if not restore:
                need(scalar(values["if"]) == ALWAYS, "provenance caller must always run")
            expanded = composite_steps(actions[uses], input_name)
            if restore:
                need(list(expanded) == [DOWNLOAD_STEP, RESTORE_STEP], "composite restore step sequence")
                keys(expanded[DOWNLOAD_STEP], {"uses", "with"}, "composite download")
                run = expanded[RESTORE_STEP]
                keys(run, {"run", "shell"}, "composite restore")
                need(scalar(run["shell"]) == "bash", "composite restore shell")
                command = run["run"]
                need(command[0] == ">-" and content(command[1]) == [
                    '          python3 -m scripts.ci_v51_bundle restore --source "$GITHUB_SHA"',
                    '          --bundle target/ci-v51-build',
                    '          --receipt "$RUNNER_TEMP/v51-build/restore.json"'], "composite restore command")
                # Only one simple command: explicit composite bash preserves its exit status.
                del run["shell"]
                token = "${{ inputs.artifact-id || 'missing-build-artifact' }}"
            else:
                need(list(expanded) == [RETAIN_STEP], "composite provenance step sequence")
                keys(expanded[RETAIN_STEP], {"uses", "if", "with"}, "composite provenance")
                need(scalar(expanded[RETAIN_STEP]["if"]) == ALWAYS, "provenance child must always run")
                token = "${{ inputs.artifact-name }}"
            # The sole input is data in an action's with map, never in shell source.
            changed = 0
            for step in expanded.values():
                for key, pair in list(step.items()):
                    if token in pair[1]:
                        need(key == "with" and pair[1].count(token) == 1, "composite input location")
                        step[key] = (pair[0], pair[1].replace(token, inputs[input_name])); changed += 1
            need(changed == 1 and "${{ inputs." not in str(expanded), "composite unresolved input")
            calls.append(uses)
        need(not set(result).intersection(expanded), "duplicate expanded step")
        result.update(expanded)
    if calls:
        need(calls == [RESTORE_ACTION, RETAIN_ACTION], "restore/provenance action pair")
        order = list(result)
        need(order.index(RETAIN_STEP) == order.index(RESTORE_STEP) + 1, "provenance must follow restore")
        # Both prerequisites must remain visible and precede artifact consumption.
        for prerequisite, action in (("Check out source", "actions/checkout@"), ("Set up Java 21", "actions/setup-java@")):
            need(prerequisite in result and order.index(prerequisite) < order.index(DOWNLOAD_STEP) and
                 scalar(result[prerequisite]["uses"]).startswith(action), "composite prerequisite: " + prerequisite)
    return result


def matrix_value(value):
    return (type(value) is str and MATRIX_VALUE.fullmatch(value) is not None and
            value not in {"true", "false", "null", "yes", "no", "on", "off"})


def strategy(matrix):
    """Render only the reviewed fixed matrix grammar; preserve member order."""
    need(type(matrix) is dict and len(matrix) == 1, "one fixed matrix axis required")
    axis, rows = next(iter(matrix.items()))
    need(IDENTIFIER.fullmatch(axis) and type(rows) is list and rows, "invalid matrix axis")
    lines = ["      fail-fast: false", "      matrix:"]
    if axis == "include":
        columns = None
        for row in rows:
            need(type(row) is dict and row and all(IDENTIFIER.fullmatch(k) and matrix_value(v)
                                                 for k, v in row.items()), "matrix include row")
            columns = columns or list(row)
            need(list(row) == columns, "matrix include columns")
        need(len({json.dumps(row, sort_keys=True) for row in rows}) == len(rows), "duplicate matrix row")
        lines.append("        include:")
        for row in rows:
            for index, (key, value) in enumerate(row.items()):
                lines.append(("          - " if index == 0 else "            ") + key + ": " + value)
    else:
        need(all((type(v) is int and v > 0) or matrix_value(v) for v in rows) and
             len(set(rows)) == len(rows), "matrix members")
        lines.append("        " + axis + ": [" + ", ".join(str(v) for v in rows) + "]")
    return lines


def expanded_names(registry):
    names = [v["name"] for v in registry["metaJobs"].values()]
    for suite in registry["suites"]:
        matrix = suite["matrix"]
        variants = [{}] if matrix is None else matrix.get("include")
        if variants is None:
            variants = [dict(zip(matrix, row)) for row in itertools.product(*matrix.values())]
        for variant in variants:
            name = suite["name"]
            for key, value in variant.items():
                name = name.replace("${{ matrix." + key + " }}", str(value))
            need("${{" not in name, "unresolved matrix display name")
            names.append(name)
    unique_strings(names, "duplicate expanded job name")
    return names


def validate_registry(value):
    keys(value, {"schema", "workflow", "metaJobs", "suites", "externalInterfaces"}, "registry")
    need(value["schema"] == SCHEMA and value["workflow"] == WORKFLOW, "registry schema/workflow")
    need(value["metaJobs"] == {"changes": {"name": "Change scope"}, "required": {"name": "Required"}}, "meta jobs")
    suites = value["suites"]
    need(type(suites) is list and suites, "empty suites")
    for suite in suites:
        keys(suite, {"id", "name", "needs", "matrix", "domain", "timeoutMinutes", "inputs", "outputs", "evidence", "fullResult", "docsResult", "integrationResult"}, "suite")
        need(text(suite["id"]) and IDENTIFIER.fullmatch(suite["id"]) and text(suite["name"]) and text(suite["domain"]), "suite identity")
        unique_strings(suite["needs"], "suite needs")
        need("changes" in suite["needs"] and suite["id"] not in suite["needs"], "suite scope/self dependency")
        need(type(suite["timeoutMinutes"]) is int and suite["timeoutMinutes"] > 0, "suite timeout")
        need(suite["fullResult"] == "success" and suite["docsResult"] == "skipped", "only unchanged full/docs results allowed")
        need(suite["integrationResult"] == ("skipped" if suite["id"] == "v51-owned-canonical" else "success"),
             "integration may only omit the whole canonical suite")
        if suite["matrix"] is not None:
            strategy(suite["matrix"])
        need(type(suite["outputs"]) is dict and all(text(k) and text(v) for k, v in suite["outputs"].items()), "suite outputs")
        for direction in ("inputs", "evidence"):
            need(type(suite[direction]) is list, "artifact list")
            for artifact in suite[direction]:
                keys(artifact, {"step", "uses", "if", "id", "with"}, "artifact")
                need(text(artifact["step"]) and text(artifact["uses"]) and
                     (artifact["if"] is None or text(artifact["if"])) and
                     (artifact["id"] is None or text(artifact["id"])), "artifact identity")
                need(type(artifact["with"]) is dict and artifact["with"] and all(type(v) is str for v in artifact["with"].values()), "artifact options")
    unique_strings([s["id"] for s in suites], "duplicate suites")
    identifiers = {s["id"] for s in suites} | {"changes"}
    need(not (identifiers & {"required"}) and all(set(s["needs"]) <= identifiers for s in suites), "unknown suite dependency")
    # Dependency cycles cannot produce a valid Required result.
    remaining = {s["id"]: set(s["needs"]) - {"changes"} for s in suites}
    while remaining:
        ready = {key for key, deps in remaining.items() if not deps}
        need(ready, "suite dependency cycle")
        remaining = {key: deps - ready for key, deps in remaining.items() if key not in ready}
    need(type(value["externalInterfaces"]) is list and value["externalInterfaces"], "external interfaces")
    for interface in value["externalInterfaces"]:
        keys(interface, {"workflow", "job", "name", "environment", "steps"}, "external interface")
        need(interface["workflow"] in (WORKFLOW, ".github/workflows/release.yml") and
             text(interface["job"]) and text(interface["name"]), "external identity")
        need(interface["environment"] is None or text(interface["environment"]), "external environment")
        unique_strings(interface["steps"], "external step names")
    expanded_names(value)
    return value


def load_registry(root=ROOT):
    return validate_registry(strict_json(read(root, REGISTRY)))


def artifacts(parsed_steps, direction):
    result = []
    for name, values in parsed_steps.items():
        if "uses" not in values:
            continue
        uses = scalar(values["uses"]).split(" #", 1)[0]
        if uses.startswith("actions/" + direction + "-artifact@"):
            result.append(dict(step=name, uses=uses, id=scalar(values["id"]) if "id" in values else None,
                               **{"if": scalar(values["if"]) if "if" in values else None},
                               with_=string_map(values["with"], 10)))
            result[-1]["with"] = result[-1].pop("with_")
    return result


def validate_workflow(registry, workflow, related, actions=None):
    validate_registry(registry)
    header = fields(workflow.split("\njobs:\n", 1)[0], 0)
    need(set(header) == {"name", "on", "permissions", "concurrency", "env"} and scalar(header["name"]) == "CI",
         "CI routing fields")
    need(not header["on"][0] and content(header["on"][1]) == ["  pull_request:", "  push:", "    branches:", "      - master",
         "  workflow_dispatch:", "  schedule:", "    - cron: '17 10 * * *'"], "CI routing triggers")
    need(string_map(header["permissions"], 2) == {"contents": "read", "actions": "read"}, "CI read-only permissions")
    need(string_map(header["concurrency"], 2) == {
         "group": "ci-${{ github.workflow }}-${{ github.event_name }}-${{ github.event_name == 'pull_request' && github.ref || github.run_id }}",
         "cancel-in-progress": "${{ github.event_name == 'pull_request' }}"}, "CI concurrency isolation")
    actions = load_actions() if actions is None else actions
    blocks = job_blocks(workflow)
    suites = {s["id"]: s for s in registry["suites"]}
    need(set(blocks) == set(suites) | set(registry["metaJobs"]), "workflow/registry job inventory differs")
    parsed = {key: fields(body, 4) for key, body in blocks.items()}
    for key, values in parsed.items():
        allowed = {"name", "runs-on", "timeout-minutes", "needs", "if", "strategy", "env", "outputs", "steps"}
        need(set(values) <= allowed, "unreviewed job field: " + key)
        need({"name", "runs-on", "timeout-minutes", "steps"} <= set(values), "missing job field: " + key)
        expected = suites.get(key, registry["metaJobs"].get(key))
        need(scalar(values["name"]) == expected["name"], "job display name: " + key)
        need(scalar(values["runs-on"]) == "ubuntu-latest", "runner changed: " + key)
        parsed_steps = expand_steps(steps(values["steps"]), key, actions)
        if key in suites:
            need(scalar(values["if"]) == (CANONICAL_IF if key == "v51-owned-canonical" else FULL_IF), "profile condition: " + key)
            need(dependencies(values.get("needs")) == expected["needs"], "needs changed: " + key)
            need(scalar(values["timeout-minutes"]) == str(expected["timeoutMinutes"]), "timeout changed: " + key)
            matrix = expected["matrix"]
            if matrix is None:
                need("strategy" not in values, "unreviewed matrix: " + key)
            else:
                need("strategy" in values and not values["strategy"][0] and
                     content(values["strategy"][1]) == strategy(matrix), "fixed matrix changed: " + key)
            actual_outputs = string_map(values["outputs"], 6) if "outputs" in values else {}
            need(actual_outputs == expected["outputs"], "producer outputs changed: " + key)
            need(artifacts(parsed_steps, "download") == expected["inputs"], "artifact inputs changed: " + key)
            need(artifacts(parsed_steps, "upload") == expected["evidence"], "artifact evidence changed: " + key)
        elif key == "required":
            need(scalar(values["if"]) == ALWAYS, "Required must always run")
            need(set(dependencies(values.get("needs"))) == set(suites) | {"changes"}, "Required needs differ")
            need("strategy" not in values and scalar(values["timeout-minutes"]) == "2", "Required execution boundary")
            checkout = parsed_steps.get("Check out the Required validator", {})
            need(string_map(checkout.get("with", ("", "")), 10) ==
                 {"persist-credentials": "false", "fetch-depth": "0"}, "Required complete comparison history")
            gate = parsed_steps.get("Require every CI gate", {})
            need(gate.get("run") == ("python3 -m scripts.ci_required", "") and "if" not in gate and
                 string_map(gate["env"], 10) == {"CI_NEEDS_JSON": "${{ toJSON(needs) }}", "GH_TOKEN": "${{ github.token }}"}, "Required validator binding")
        else:
            need("if" not in values and "needs" not in values and "strategy" not in values, "classifier must run")
            checkout = parsed_steps.get("Check out comparison history", {})
            need(string_map(checkout.get("with", ("", "")), 10) == {"fetch-depth": "0"}, "classifier complete comparison history")
            need(string_map(values["outputs"], 6) == {key: "${{ steps.scope.outputs." + key + " }}" for key in PLAN_OUTPUTS}, "classifier output binding")
            scope = parsed_steps.get("Classify the complete change set", {})
            need(scope.get("run") == ("python3 -m scripts.ci_plan --output target/ci-shadow-plan", "") and scope.get("id") == ("scope", "") and "if" not in scope,
                 "classifier execution binding")
            need(string_map(scope.get("env", ("", "")), 10) == {"GH_TOKEN": "${{ github.token }}"}, "read-only health token binding")
            shadow = parsed_steps.get("Observe the CI shadow plan", {})
            need(set(shadow) == {"run", "env"} and shadow["run"] ==
                 ("python3 -m scripts.ci_shadow_plan --output target/ci-shadow-plan", "") and
                 string_map(shadow["env"], 10) == {"ACTUAL_RUN_FULL_CI": "${{ steps.scope.outputs.run_full_ci }}",
                                                "CI_PROFILE": "${{ steps.scope.outputs.profile }}"},
                 "shadow observation binding")
            retained = parsed_steps.get("Retain the CI shadow plan", {})
            need(set(retained) == {"if", "uses", "with"} and scalar(retained["if"]) == ALWAYS and
                 scalar(retained["uses"]).split(" #", 1)[0] == "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02" and
                 string_map(retained["with"], 10) == {
                     "name": "ci-shadow-plan-${{ github.run_id }}-${{ github.run_attempt }}",
                     "path": "target/ci-shadow-plan", "if-no-files-found": "warn", "retention-days": "14"},
                 "shadow observation retention")
            order = list(parsed_steps)
            need(order.index("Classify the complete change set") < order.index("Observe the CI shadow plan") <
                 order.index("Retain the CI shadow plan"), "shadow observation order")
    for interface in registry["externalInterfaces"]:
        source = workflow if interface["workflow"] == WORKFLOW else related[interface["workflow"]]
        jobs = job_blocks(source)
        need(interface["job"] in jobs, "external job missing")
        values = fields(jobs[interface["job"]], 4)
        need(scalar(values["name"]) == interface["name"], "external job name changed")
        if interface["environment"] is not None:
            need(scalar(values["environment"]) == interface["environment"], "external environment changed")
        actual = steps(values["steps"])
        need(set(interface["steps"]) <= set(actual), "external step missing/renamed: " + interface["job"])
        for name in interface["steps"]:
            need("run" in actual[name] and "if" not in actual[name], "external step must execute visibly: " + name)
    return expanded_names(registry)


def check(root=ROOT):
    registry = load_registry(root)
    related = {v["workflow"]: read(root, v["workflow"]) for v in registry["externalInterfaces"] if v["workflow"] != WORKFLOW}
    validate_workflow(registry, read(root, WORKFLOW), related, load_actions(root))
    return registry


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        registry = check()
        print(json.dumps(dict(status="PASS", suites=len(registry["suites"]), jobs=len(expanded_names(registry)))))
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as error:
        print(json.dumps(dict(status="FAIL", reason=str(error))))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
