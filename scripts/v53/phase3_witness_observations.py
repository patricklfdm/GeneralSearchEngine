"""Project exact candidate witnesses after the owning original-first replay.

Internal cohort hook only: no CLI accepting supplied PASS receipts. This does
not replay an original or establish Phase 3 acceptance on its own.
"""
from . import phase3_coverage as c

need, digest, encoded = c.need, c.digest, c.encoded


def prepare():
    raw = c.p.regular(c.p.ROOT, c.PLAN)
    source = c.catalogue()
    audited = c.validate(c.p.decode(raw), source,
                         c.p.decode(c.p.regular(c.p.ROOT, c.p.PLAN)),
                         c.p.decode(c.p.regular(c.p.ROOT, c.p.ACCEPTANCE)))
    return raw, dict(planSha256=digest(raw), sourceCatalogueSha256=digest(encoded(source)),
                     witnesses=audited['candidateWitnesses'])


def selected(plan, name, group):
    return [w for w in plan['witnesses'] if w['cohort'] == name and w['executionGroup'] == group]


def negative_rows(name, qualification, suite):
    if name == 'joining-process':
        return qualification['transactionNegatives'] if suite == 'transaction' else qualification[suite]['negatives']
    if name == 'joining-reply-loss' and suite == 'ballot':
        return qualification['ballotQualification']['negatives']
    return qualification['negatives']


def outcome(witness, qualification):
    name = witness['cohort']; selector = witness['selector']; original = qualification.get('original', {})
    if name == 'automatic-histories' and witness['unit'] == 'competition':
        if original['branch'] != selector['variant']:
            return 'NOT_APPLICABLE', 'original competition branch: ' + original['branch']
    vector = negative_rows(name, qualification, selector['suite'])
    exact = [v for v in vector if v.get('case') == selector['case'] and
             all(v.get(k) == selector.get(k) for k in ('stage',)) and
             ('suite' not in v or v['suite'] == selector['suite'])]
    if not exact and witness['condition'] == 'original-late-unused-prepare':
        need(not original['network'].get('lateUnusedPrepares'), 'witness missing original late PREPARE rejection')
        return 'NOT_APPLICABLE', 'no original late unused PREPARE'
    need(len(exact) == 1, 'witness missing/duplicate exact reader result')
    row = exact[0]; status = row['status']; reason = row['reason']
    need(type(reason) is str and reason, 'witness reader rejection reason')
    if status == 'NOT_APPLICABLE':
        need(witness['condition'] != 'always', 'witness unconditional result cannot be inapplicable')
    else:
        expected = witness['reason']
        if name == 'automatic-histories' and witness['unit'] == 'competition':
            expected = expected.format(node=original['firstCapture'])
        need(status == 'REJECTED' and reason == expected, 'witness exact rejection reason')
    # The owning check_result has already independently enforced its precise
    # original-derived NOT_APPLICABLE reason. No arbitrary exception is caught.
    return status, reason


def observe_group(plan, name, group, result, adapter, ctx, originals):
    wanted = selected(plan, name, group)
    if not wanted: return []
    need(result.get('schema') == adapter.SCHEMA and result.get('context') == ctx and
         result.get('status') == 'PARTIAL' and result.get('phase3Complete') is False,
         'witness owning replay context')
    if name == 'joining-process':
        children = result.get('cases')
        need(result.get('stage') == 'verify' and result.get('shard') == group and type(children) is list and
             [v.get('case') for v in children] == list(adapter.SHARDS[group]), 'witness complete joining group')
        members = {v['case']: v for v in children}
    else:
        need(result.get('profile' if name == 'profiles' else 'case') == group, 'witness exact group result')
        members = {group: result}
    observations = []; checked = set()
    for witness in wanted:
        unit = witness['unit']; returned = members[unit]
        need(returned.get('schema') == adapter.SCHEMA and returned.get('context') == ctx and
             returned.get('originalFirstDownloadedReplay') is True and returned.get('status') == 'PARTIAL' and
             returned.get('phase3Complete') is False, 'witness original-first result required')
        member = returned['member']; field = 'profile' if name == 'profiles' else 'case'
        need(member.get(field) == unit and member.get('status') == 'PASS' and member.get('phase3Complete') is False,
             'witness exact owning member')
        raw_path = name + '/' + adapter.artifact_name(ctx, 'raw', group)
        if name == 'joining-process': raw_path += '/' + adapter.m.slug(unit)
        need(raw_path in originals and returned.get('rawArchiveSha256') == originals[raw_path]['archiveSha256'],
             'witness original archive binding')
        qualification = member['qualification']
        if unit not in checked:
            adapter.m.check_result(qualification, unit); checked.add(unit)
        status, reason = outcome(witness, qualification)
        observations.append(dict(id=witness['id'], requirement=witness['requirement'], cohort=name, unit=unit,
            histories=witness['histories'], selector=witness['selector'], condition=witness['condition'],
            outcome=status, reason=reason, rawArchiveSha256=returned['rawArchiveSha256'],
            owningReplaySha256=digest(encoded(returned))))
    return observations


def finish(plan, observations):
    expected = {w['id']: w for w in plan['witnesses']}
    need(type(observations) is list and len(observations) == len(expected) and
         all(type(v) is dict for v in observations) and
         {v.get('id') for v in observations} == set(expected), 'witness complete observed set')
    ordered = []
    by_id = {v['id']: v for v in observations}
    for identity, witness in expected.items():
        value = by_id[identity]
        need(set(value) == {'id', 'requirement', 'cohort', 'unit', 'histories', 'selector', 'condition', 'outcome',
                            'reason', 'rawArchiveSha256', 'owningReplaySha256'}, 'witness observed fields')
        need(all(value.get(k) == witness[k] for k in ('requirement', 'cohort', 'unit', 'histories', 'selector', 'condition')),
             'witness observed selector binding')
        need(all(type(value[k]) is str and len(value[k]) == 64 and all(ch in '0123456789abcdef' for ch in value[k])
                 for k in ('rawArchiveSha256', 'owningReplaySha256')) and type(value['reason']) is str and value['reason'],
             'witness retained reason and provenance')
        need(value.get('outcome') in ('REJECTED', 'NOT_APPLICABLE') and
             (witness['condition'] != 'always' or value['outcome'] == 'REJECTED'), 'witness observed outcome')
        if value['outcome'] == 'REJECTED' and '{node}' not in witness['reason']:
            need(value['reason'] == witness['reason'], 'witness final rejection reason')
        ordered.append(value)
    return dict(status='PARTIAL', phase3Complete=False, runtimeQualified=False, frozenScenarioCoverageQualified=False,
                candidateWitnessesObserved=True, planSha256=plan['planSha256'], sourceCatalogueSha256=plan['sourceCatalogueSha256'],
                rejected=sum(v['outcome'] == 'REJECTED' for v in ordered),
                notApplicable=sum(v['outcome'] == 'NOT_APPLICABLE' for v in ordered), witnesses=ordered)
