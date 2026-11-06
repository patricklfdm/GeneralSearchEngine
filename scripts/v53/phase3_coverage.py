"""Inspect exact Phase 3 candidate witnesses; never confer evidence acceptance.

The unit is an original archive, not an independently schedulable negative or
cell. Grouped TCP/reply matrices keep their complete history sets. Conditional
selectors are catalogued without inventing an original to select a branch.
"""
import argparse
import importlib
import json
from pathlib import Path
import subprocess

from . import phase3_qualification_plan as p

PLAN = 'docs/v5x/v5.3/phase3-coverage-witnesses.json'
SCHEMA = 'gse-v53-phase3-coverage-witnesses-v1'
need, encoded, digest = p.need, p.encoded, p.digest
GROUPED = ('transfer-histories', 'automatic-histories')


def module(name):
    return importlib.import_module('.' + name, __package__)


def rows(values, suite, *, condition='always', variant='default'):
    items = values.items() if isinstance(values, dict) else values
    return [dict(selector=dict(suite=suite, case=k, variant=variant), reason=v,
                 condition=condition) for k, v in items]


def authored(values):
    """Keep stage/suite distinctions; discard expected outcomes, not evidence."""
    return [dict(selector={k: v[k] for k in ('suite', 'stage', 'case') if k in v} | {'variant': 'default'},
                 reason=v['reason'], condition='always') for v in values]


def negative_selectors(name, unit):
    """Fixed adapters only. No qualify(), producer, raw read, or mock original."""
    m = module(p.COHORTS[name][0])
    if name == 'profiles':
        reader = m.removal if unit in m.removal.PROFILES else m.joining
        result = rows(reader.NEGATIVES, 'ballot')
        if reader is m.joining:
            for row in result:
                if row['selector']['case'] in ('adoption-fence-missing', 'adoption-promise-missing'):
                    row['condition'] = 'original-adoption-transaction'
        return result
    if name == 'joining-reply-loss':
        return rows(m.gate.NEGATIVES, 'fault') + negative_selectors('profiles', '3-ADD')
    if name == 'remove-process':
        return rows(m.gate.NEGATIVES, 'ballot')
    if name == 'node-renames':
        selected = m.run.selected(unit)
        return (rows(m.gate.p.negative_cases(selected['cut']) | m.gate.EXTRA_NEGATIVES, 'physical') +
                rows(module('node_late_prepare').NEGATIVES, 'physical', condition='original-late-unused-prepare'))
    if name == 'joining-process':
        # Absence is determined by gate.negative_plan(original), never by the
        # scenario name or a synthetic original supplied to this inspector.
        return (rows(m.gate.NEGATIVES, 'authority', condition='original-authority-applicability') +
                rows(m.physical.NEGATIVES, 'physical') + rows(m.physical.transaction.NEGATIVES, 'transaction'))
    if name == 'learner-histories':
        if unit=='retained-cancellation':
            return (rows(m.byte_cases(m.run.pressure.NEGATIVES),'byte-pressure')+
                    rows(m.byte_cases(m.run.pressure.PHYSICAL_NEGATIVES),'byte-physical')+
                    rows(m.run.resources.NEGATIVES,'resource-observations')+
                    rows(dict(m.run.cancellation.NEGATIVES,**m.retention.NEGATIVES),'physical')+
                    rows(m.run.resources.HISTORY_NEGATIVES,'renewal-history'))
        return rows(m.negative_cases(unit), 'physical')
    if name in ('round-histories', 'carried-data-histories', 'carried-transition-histories', 'joint-floor-process'):
        return authored(m.negative_cases(unit))
    if name == 'transfer-histories':
        return rows(m.m.READERS[unit].NEGATIVES, 'physical')
    if name == 'automatic-histories':
        gate = m.m.gate
        if unit == 'higher-ballot-restart':
            return rows(gate.current.NEGATIVES, 'current') + rows(gate.restart.NEGATIVES, 'restart')
        if unit == 'reply-revocation':
            return rows(gate.replies.NEGATIVES, 'replies')
        need(unit == 'competition', 'coverage automatic unit')
        result = []
        for branch, suites in gate.suites(unit).items():
            for suite in suites:
                values = gate.export_vector(branch)[0] if suite == 'exports' else gate.COMPETING[suite].NEGATIVES
                # Prefix reasons retain the literal {node} template. Only the
                # original reader can bind firstCapture and choose this branch.
                result += rows(values, suite, condition='original-competition-' + branch, variant=branch)
        return result
    raise ValueError('coverage unknown cohort')


def catalogue(catalogs=None):
    catalogs = p.catalogues() if catalogs is None else catalogs
    need(set(catalogs) == set(p.COHORTS), 'coverage exact cohorts')
    units, vectors = {}, {}
    for name, item in catalogs.items():
        hosted = module(p.COHORTS[name][2])
        # Each joining-process execution group contains three separate whole
        # archives. TCP and reply groups instead share one archive and vector.
        groups = hosted.SHARDS if name in (*GROUPED, 'joining-process') else {c: (c,) for c in item['cases']}
        need([c for group in groups.values() for c in group] == item['cases'], 'coverage exact whole-history partition')
        units[name] = {}
        for group, members in groups.items():
            members = list(members)
            archives = {group: members} if name in GROUPED else {c: [c] for c in members}
            for unit, histories in archives.items():
                vector = negative_selectors(name, unit)
                keys = [encoded(v['selector']) for v in vector]
                need(vector and len(keys) == len(set(keys)), 'coverage unique exact negative selectors')
                need(all(type(v['reason']) is str and v['reason'] and type(v['condition']) is str and
                         v['condition'] for v in vector), 'coverage source negative shape')
                sha = digest(encoded(vector)); vectors[sha] = vector
                units[name][unit] = dict(executionGroup=group, histories=histories, negativeVectorSha256=sha)
        need([h for v in units[name].values() for h in v['histories']] == item['cases'], 'coverage complete unit inventory')
    return dict(units=units, vectors=vectors)


def validate(value, source, qualification, acceptance):
    need(type(value) is dict and set(value) == {'schema', 'status', 'phase3Complete', 'acceptancePlanSha256', 'sourceCatalogueSha256',
         'requirements'}, 'coverage plan envelope')
    need(value['schema'] == SCHEMA and value['status'] == 'PLANNED' and value['phase3Complete'] is False,
         'coverage plan cannot grant acceptance')
    need(value['acceptancePlanSha256'] == digest(encoded(acceptance)), 'coverage frozen plan binding')
    need(value['sourceCatalogueSha256'] == digest(encoded(source)), 'coverage source catalogue drift')
    requirement_rows = value['requirements']
    need(type(requirement_rows) is list and all(type(v) is dict for v in requirement_rows) and
         [v.get('id') for v in requirement_rows] == list(p.REQUIREMENTS), 'coverage exact requirement order')
    owners = {v['id']: v for v in qualification['requirements']}
    all_ids, used, selected = set(), set(), []
    for row in requirement_rows:
        need(set(row) == {'id', 'witnesses', 'openWork'} and type(row['openWork']) is str and row['openWork'].strip(),
             'coverage open obligations required')
        need(type(row['witnesses']) is list and row['witnesses'], 'coverage candidate witnesses required')
        for witness in row['witnesses']:
            need(type(witness) is dict and set(witness) == {'id', 'cohort', 'unit', 'histories', 'selector', 'reason',
                 'condition', 'scope'}, 'coverage witness fields')
            identity = witness['id']; name = witness['cohort']; unit = witness['unit']
            need(type(identity) is str and identity and identity not in all_ids, 'coverage unique witness id')
            all_ids.add(identity)
            need(type(name) is str and name in owners[row['id']]['cohorts'] and name in source['units'],
                 'coverage requirement cohort binding')
            need(type(unit) is str and unit in source['units'][name], 'coverage exact archive unit')
            owned = source['units'][name][unit]
            need(witness['histories'] == owned['histories'], 'coverage indivisible history set')
            need(type(witness['selector']) is dict and type(witness['scope']) is str and witness['scope'].strip(),
                 'coverage explicit selector and scope')
            matching = [v for v in source['vectors'][owned['negativeVectorSha256']] if
                        encoded(v['selector']) == encoded(witness['selector'])]
            need(len(matching) == 1, 'coverage exact negative selector')
            expected = matching[0]
            need(witness['reason'] == expected['reason'] and witness['condition'] == expected['condition'],
                 'coverage exact reason and original applicability')
            used.add(name)
            selected.append(dict(requirement=row['id'], **witness, executionGroup=owned['executionGroup'],
                                 qualification='NOT_EVALUATED'))
    need(used == set(p.COHORTS), 'coverage orphan hosted cohort')
    return dict(schema=SCHEMA, status='PASS', execution='source-selector-audit-only',
                phase3Complete=False, runtimeQualified=False, frozenScenarioCoverageQualified=False,
                nativeHistoriesExecuted=0, candidateWitnesses=selected,
                conditionalWitnesses=sum(w['condition'] != 'always' for w in selected),
                openWork={v['id']: v['openWork'] for v in requirement_rows},
                frozenCoverage=dict(requiredPhase=5, coveredScenarioRows=[], coveredNegativeFamilies=[]))


def inspect():
    checked, qualification_bytes, acceptance_bytes = p.inspect()
    source = catalogue(checked['cohorts']); plan_bytes = p.regular(p.ROOT, PLAN)
    result = validate(p.decode(plan_bytes), source, p.decode(qualification_bytes), p.decode(acceptance_bytes))
    # Use the owning cohort's complete reader manifest, not sys.modules (which
    # changes with import/test order). Hashing a constant is not executing it.
    files = dict(checked['inspectedFiles'])
    names = {PLAN, *module('remove_process_matrix').reader_manifest()['files']}
    files.update({n: digest(p.regular(p.ROOT, n)) for n in sorted(names)})
    need(files[PLAN] == digest(plan_bytes), 'coverage plan changed during inspection')
    result.update(sourceCatalogueSha256=digest(encoded(source)), inspectedFiles=dict(sorted(files.items())),
                  inspectedInputsSha256=digest(encoded(dict(sorted(files.items())))),
                  sourceArchiveUnits=sum(map(len, source['units'].values())),
                  plannedHostedHistories=checked['plannedHostedHistories'],
                  plannedExecutionGroups=sum(v['executionGroups'] for v in checked['cohorts'].values()))
    return result, source, plan_bytes


def run(output):
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    result = dict(schema=SCHEMA, status='FAIL', execution='source-selector-audit-only', phase3Complete=False,
                  runtimeQualified=False, frozenScenarioCoverageQualified=False, nativeHistoriesExecuted=0)
    try:
        audited, source, plan_bytes = inspect()
        result.update(audited, baseHead=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=p.ROOT, text=True).strip(),
                      worktreeStatus=subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=p.ROOT, text=True).splitlines())
        (output/'plan.json').write_bytes(plan_bytes); (output/'catalogue.json').write_bytes(encoded(source))
        need(all(digest(p.regular(p.ROOT, n)) == sha for n, sha in result['inspectedFiles'].items()),
             'coverage inspected source changed')
    except BaseException as error:
        result.update(status='FAIL', failure=dict(type=type(error).__name__, message=str(error))); raise
    finally:
        (output/'receipt.json').write_bytes(encoded(result))
    print(json.dumps({k: result[k] for k in ('status', 'execution', 'sourceArchiveUnits', 'plannedHostedHistories', 'phase3Complete')}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='new audit directory; no original evidence is changed')
    run(parser.parse_args().output)
