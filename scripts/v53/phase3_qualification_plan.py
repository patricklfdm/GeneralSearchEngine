"""Source inspection and scheduling inventory, never runtime qualification.

No producer, Maven command, network call or evidence replay is executed here.
The hosted catalogues are read from their existing implementation. Their members
are complementary histories, not a coverage count for the frozen S/N matrix.
"""
import argparse
from collections import Counter
import importlib
import json
from pathlib import Path, PurePosixPath
import subprocess

from . import case_inventory as inventory

ROOT = Path(__file__).resolve().parents[2]
PLAN = 'docs/v5x/v5.3/phase3-qualification-plan.json'
ACCEPTANCE = 'docs/v5x/v5.3/acceptance-plan.json'
SCHEMA = 'gse-v53-phase3-qualification-plan-v1'
REQUIREMENTS = {
    '3A-activation': ('S02', 'S07', 'S09', 'S10'),
    '3B-transfer': ('S02', 'S04', 'S10'),
    '3B-recovery': ('S02', 'S04', 'S10'),
    '3C-learner': ('S03', 'S05', 'S09'),
    '3C-initialization': ('S03', 'S09', 'S10'),
    '3C-joint': ('S01', 'S03', 'S05', 'S09'),
    '3D-rounds': ('S01', 'S02', 'S07', 'S10'),
    '3D-automatic': ('S02', 'S07', 'S10'),
    '3D-removal': ('S01', 'S04', 'S10'),
    '3E-resources': ('S09',),
    '3E-coverage': ('S01', 'S02', 'S03', 'S04', 'S05', 'S07', 'S09', 'S10'),
    '3E-cohort': ('S01', 'S02', 'S03', 'S04', 'S05', 'S07', 'S09', 'S10'),
}
# Fixed module names: a plan cannot make the inspector import arbitrary code.
COHORTS = {
    'profiles': ('profile_matrix', 'PROFILES', 'profile_hosted'),
    'joining-reply-loss': ('joining_fault_cohort', 'KINDS', 'joining_fault_hosted'),
    'remove-process': ('remove_process_matrix', 'KINDS', 'remove_process_hosted'),
    'node-renames': ('node_rename_matrix', 'KINDS', 'node_rename_hosted'),
    'joining-process': ('joining_process_matrix', 'KINDS', 'joining_process_hosted'),
}
GAPS = ('component-cohorts', 'combined-resources', 'frozen-coverage', 'cohort-admission', 'final-source-execution')
need, encoded, digest = inventory.need, inventory.encoded, inventory.digest


def decode(data):
    def unique(rows):
        need(len(rows) == len(dict(rows)), 'qualification plan duplicate key')
        return dict(rows)
    return json.loads(data, object_pairs_hook=unique)


def regular(root, name):
    need(type(name) is str and name and '\\' not in name, 'qualification reference path')
    relative = PurePosixPath(name)
    need(not relative.is_absolute() and relative.as_posix() == name and
         all(p not in ('.', '..') for p in relative.parts), 'qualification reference path')
    path = root/name
    need(not any((root/p).is_symlink() for p in (relative, *relative.parents)), 'qualification linked reference')
    need(path.is_file() and 0 < path.stat().st_size <= 8*1024*1024, 'qualification missing/bounded reference: '+name)
    return path.read_bytes()


def catalogues():
    rows = {}
    for name, (matrix_name, field, hosted_name) in COHORTS.items():
        matrix = importlib.import_module('.'+matrix_name, __package__)
        hosted = importlib.import_module('.'+hosted_name, __package__)
        cases = list(getattr(matrix, field))
        need(cases and all(type(v) is str and v for v in cases) and len(set(cases)) == len(cases),
             'qualification catalogue members: '+name)
        groups = list(hosted.SHARDS.values()) if name == 'joining-process' else [(case,) for case in cases]
        need([v for group in groups for v in group] == cases, 'qualification whole-history partition: '+name)
        rows[name] = dict(matrix='scripts/v53/'+matrix_name+'.py', hosted='scripts/v53/'+hosted_name+'.py',
                          workflow=hosted.WORKFLOW, branch=hosted.BRANCH, cases=cases,
                          casesSha256=digest(encoded(cases)), members=len(cases), executionGroups=len(groups))
    return rows


def validate(plan, acceptance, catalogs, root=ROOT):
    """Validate planning completeness only; no input can confer runtime PASS."""
    need(type(plan) is dict and set(plan) == {'schema', 'status', 'phase3Complete', 'acceptancePlanSha256',
         'requirements', 'cohorts', 'gaps', 'laterPhases'}, 'qualification plan envelope')
    need(plan['schema'] == SCHEMA and plan['status'] == 'PLANNED' and plan['phase3Complete'] is False,
         'qualification plan cannot grant acceptance')
    need(plan['acceptancePlanSha256'] == digest(encoded(acceptance)), 'qualification frozen plan binding')
    materialized = inventory.generate(acceptance)
    frozen = inventory.validate(materialized, acceptance)
    need(all(r['requiredPhase'] == 5 for r in materialized['scenarios']), 'qualification owning acceptance phase')
    need(plan['laterPhases'] == {'publicOperationsAndReads': 4, 'completeFrozenCorrectnessMatrix': 5,
                              'measurementsAndCloud': 6}, 'qualification later-phase boundary')
    need(set(catalogs) == set(COHORTS) and type(plan['cohorts']) is dict and
         set(plan['cohorts']) == set(COHORTS), 'qualification cohort inventory')
    references = {PLAN, ACCEPTANCE, 'scripts/v53/phase3_qualification_plan.py', 'scripts/v53/case_inventory.py',
                  'docs/v5x/v5.3/PHASE_3_ENTRY_PLAN.md', 'docs/v5x/v5.3/RESOURCE_AND_LIFETIME_LIMITS.md'}
    for name, expected in catalogs.items():
        claim = plan['cohorts'][name]
        need(type(claim) is dict and set(claim) == {'members', 'casesSha256', 'status'} and
             type(claim['members']) is int and claim['members'] == expected['members'] and
             claim['casesSha256'] == expected['casesSha256'] and claim['status'] == 'ENTRY_READY_EXECUTION_PENDING',
             'qualification declared catalogue: '+name)
        references.update(expected[k] for k in ('matrix', 'hosted', 'workflow'))
    rows = plan['requirements']
    need(type(rows) is list and all(type(r) is dict and type(r.get('id')) is str for r in rows), 'qualification requirement rows')
    need(len(rows) == len(REQUIREMENTS) and {r['id'] for r in rows} == set(REQUIREMENTS), 'qualification requirement inventory')
    used_cohorts, used_gaps = set(), set()
    for row in rows:
        need(set(row) == {'id', 'title', 'families', 'implementation', 'tests', 'readers', 'docs', 'cohorts', 'gaps'},
             'qualification requirement fields')
        need(type(row['title']) is str and bool(row['title'].strip()) and
             row['families'] == list(REQUIREMENTS[row['id']]), 'qualification obligation/family binding')
        for field in ('implementation', 'tests', 'readers', 'docs'):
            names = row[field]
            need(type(names) is list and names and all(type(n) is str for n in names) and len(set(names)) == len(names),
                 'qualification requirement references: '+field)
            for name in names:
                prefixes = {'implementation': ('general-search-engine-replication/src/main/java/', 'scripts/v53/'),
                            'tests': ('general-search-engine-replication/src/test/java/', 'scripts/v53/test_'),
                            'readers': ('scripts/v53/',), 'docs': ('docs/v5x/v5.3/',)}
                need(name.startswith(prefixes[field]), 'qualification reference category: '+field)
            references.update(names)
        for field, allowed in (('cohorts', set(COHORTS)), ('gaps', set(GAPS))):
            values = row[field]
            need(type(values) is list and all(type(v) is str for v in values) and len(set(values)) == len(values) and
                 set(values) <= allowed and (field != 'gaps' or values), 'qualification requirement dependencies')
        used_cohorts.update(row['cohorts']); used_gaps.update(row['gaps'])
    need(used_cohorts == set(COHORTS) and used_gaps == set(GAPS), 'qualification orphan cohort/gap')
    gaps = plan['gaps']
    need(type(gaps) is list and all(type(g) is dict for g in gaps) and [g.get('id') for g in gaps] == list(GAPS),
         'qualification gap inventory/order')
    for gap in gaps:
        need(set(gap) == {'id', 'status', 'work', 'acceptance', 'dependsOn'} and gap['status'] == 'OPEN' and
             all(type(gap[k]) is str and gap[k].strip() for k in ('work', 'acceptance')), 'qualification gap cannot self-close')
        dependencies = gap['dependsOn']
        need(type(dependencies) is list and all(type(v) is str for v in dependencies) and
             len(set(dependencies)) == len(dependencies) and set(dependencies) <= set(GAPS[:GAPS.index(gap['id'])]),
             'qualification gap dependency order')
    files = {name: digest(regular(root, name)) for name in sorted(references)}
    return dict(schema=SCHEMA, status='PASS', execution='source-inventory-only', qualificationStatus='NOT_EVALUATED',
                phase3Complete=False, runtimeQualified=False, frozenScenarioCoverageQualified=False,
                requirements=len(rows), finalSourceNativeHistoriesExecuted=0,
                cohorts=catalogs, plannedHostedHistories=sum(v['members'] for v in catalogs.values()),
                frozenAcceptance=dict(scenarios=frozen['scenarios'], byScenario=frozen['byScenario'],
                                      negativeFamilies=frozen['negativeFamilies'], requiredPhase=5,
                                      state='PLANNED', coveredScenarioRows=[]),
                relatedFamilies=dict(sorted(Counter(f for row in rows for f in row['families']).items())),
                gaps=gaps, inspectedFiles=files, inspectedInputsSha256=digest(encoded(files)))


def inspect():
    plan_bytes = regular(ROOT, PLAN); acceptance_bytes = regular(ROOT, ACCEPTANCE)
    plan, acceptance = decode(plan_bytes), decode(acceptance_bytes)
    result = validate(plan, acceptance, catalogues())
    need(result['inspectedFiles'][PLAN] == digest(plan_bytes) and result['inspectedFiles'][ACCEPTANCE] == digest(acceptance_bytes),
         'qualification plan changed during inspection')
    return result, plan_bytes, acceptance_bytes


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, status='FAIL', execution='source-inventory-only', phase3Complete=False, runtimeQualified=False)
    try:
        result, plan, acceptance = inspect()
        # HEAD identifies a baseline, not proof that dirty working bytes ran.
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        status = subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True)
        (output/'plan.json').write_bytes(plan); (output/'acceptance-plan.json').write_bytes(acceptance)
        need(all(digest(regular(ROOT, name)) == sha for name, sha in result['inspectedFiles'].items()),
             'qualification inspected source changed')
        receipt.update(result, baseHead=head, worktreeStatus=status.splitlines())
    except BaseException as error:
        receipt.update(failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        (output/'receipt.json').write_bytes(encoded(receipt))
    print(json.dumps({k: receipt[k] for k in ('status', 'execution', 'requirements', 'plannedHostedHistories', 'phase3Complete')}, sort_keys=True))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new audit directory; no existing evidence is overwritten')
    run(parser.parse_args().output)
