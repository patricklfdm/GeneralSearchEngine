"""Complete storage callbacks for an uninterrupted, independently reduced slot.

These callbacks bind successful original materializations to their owner and
force order. They neither prove crash recovery nor replace the physical reader.
The caller must first reduce the original control/barrier history and inventories.
"""
from .generation_install_evidence import transaction
from .membership_model import need

CURRENT = ['CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
           'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED']
VOTE_WRITE = ['CANDIDATE_CREATED', 'PREFIX_WRITTEN', 'CANDIDATE_WRITTEN',
              'CANDIDATE_FORCED', 'CANDIDATE_PARENT_FORCED', 'RENAMED', 'PARENT_FORCED']
CONTROL = {'BARRIER', 'RESERVE', 'PREPARE', 'READY', 'SEAL', 'INTENT', 'FINAL'}


def exact(events, node, scope, lower, upper, names, prefixes, reason):
    need(type(lower) is int and type(upper) is int and 0 <= lower <= upper < len(events), reason)
    rows = [v for v in events[lower:upper+1] if v.get('node') == node and
            v.get('event', '').startswith(prefixes)]
    need([v['event'] for v in rows] == names and all(v == dict(node=node, event=v['event'],
         **({'scope': scope} if scope is not None else {})) for v in rows), reason)
    return len(rows)


def applied_members(end, *, nonvoting=False):
    """Order is part of the writer contract; counts come from the reduced end."""
    files = {n.removeprefix('applied-end/') for n in end if n.startswith('applied-end/')}
    ordered = [('plan.json', 'PLAN'), *[(n+'.gsr', 'METADATA') for n in
               ('selector', 'certificate', 'catalog', 'statement')]]
    parents = [('parent-statement.gsr', 'PARENT_STATEMENT')]
    parents += [(f'ancestor-{i}-statement.gsr', f'ANCESTOR_{i}_STATEMENT') for i in range(5)]
    ordered += [(n, p) for n, p in parents if n in files]
    need(type(nonvoting) is bool and (not nonvoting or not any(n in files for n,_ in parents)),
         'joining slot nonvoting ancestor inventory')
    ordered += [('application.image', 'IMAGE')]
    if not nonvoting:ordered += [('ack.gsr', 'ACK')]
    ordered += [(n.replace('statement', 'ack'), p.replace('STATEMENT', 'ACK'))
                for n, p in parents if n in files]
    need(files == {n for n, _ in ordered}, 'joining slot applied member inventory')
    indices = [i for i in range(5) if f'ancestor-{i}-statement.gsr' in files]
    need(indices == list(range(len(indices))) and (not indices or 'parent-statement.gsr' in files),
         'joining slot applied ancestor order')
    return ordered


def application(end, kind, *, allow_data=False, nonvoting=False):
    # Default joining histories contain controls/barriers only. An explicitly
    # admitted DATA projection also materializes output's three core members
    # and directory. Claim/work/root plus each complete four-entry bundle are
    # removed by MembershipReplayFiles; the count never comes from the trace.
    need(kind in CONTROL or allow_data and kind=='DATA', 'joining slot unsupported application history')
    need(not nonvoting or kind=='FINAL','joining slot nonvoting FINAL required')
    names = ['APPLICATION_AUTHORITY_VALIDATED', 'REPLAY_RESERVED', 'REPLAY_DIRECTORY_CREATED',
             'REPLAY_CLAIM_CREATED', 'REPLAY_CLAIM_PREFIX_WRITTEN', 'REPLAY_CLAIM_WRITTEN',
             'REPLAY_CLAIM_FORCED', 'REPLAY_BEFORE_APPLICATION', 'REPLAY_APPLICATION_FINISHED']
    names += ['REPLAY_BEFORE_DELETE', 'REPLAY_DELETED'] * (11 if kind=='DATA' else 7)
    names += ['REPLAY_BEFORE_RETURN', 'APPLY_VALIDATED', 'APPLY_DIRECTORY_CREATED']
    for _, label in applied_members(end,nonvoting=nonvoting):
        if label == 'ACK': names.append('APPLY_END_FORCED')
        names += ['APPLY_'+label+'_'+suffix for suffix in ('CREATED', 'PREFIX_WRITTEN', 'WRITTEN', 'FORCED')]
    return names + (['APPLY_END_FORCED','APPLY_NONVOTING_DIRECTORY_FORCED'] if nonvoting else ['APPLY_ACK_DIRECTORY_FORCED']) + ['APPLY_BEFORE_RETURN']


def publication(members):
    return ['PUBLICATION_VALIDATED', *transaction(members)[0], *CURRENT, 'PUBLICATION_SELECTOR_FORCED']


def retirement(end, *, nonvoting=False):
    # Every original member, including the plan, has one deletion/parent-force
    # pair. Actual names/remaining bytes are checked by the physical replay;
    # generic callbacks alone cannot prove which file was deleted first.
    count = len(applied_members(end,nonvoting=nonvoting))
    return ['PUBLICATION_COVERAGE_VALIDATED', 'COVERED_END_VALIDATED',
            *(['COVERED_END_BEFORE_DELETE', 'COVERED_END_FILE_DELETED'] * count),
            'COVERED_END_BEFORE_DIRECTORY_DELETE', 'COVERED_END_DIRECTORY_DELETED',
            *['COVERED_VOTE_'+suffix for suffix in VOTE_WRITE], 'PUBLICATION_RETIRED']


def validate_slot(events, node, scope, own, end, members, kind, *, allow_data=False, nonvoting=False):
    count = 0
    for phase in ('ACCEPT', 'PROOF', 'CERTIFICATE'):
        count += exact(events, node, scope, own[phase+'_VALIDATED'], own[phase+'_BEFORE_RETURN'],
                       [phase+'_VALIDATED', *[phase+'_'+s for s in VOTE_WRITE], phase+'_BEFORE_RETURN'],
                       (phase+'_',), 'joining slot complete '+phase.lower()+' storage order')
    count += exact(events, node, scope, own['APPLICATION_AUTHORITY_VALIDATED'], own['APPLY_BEFORE_RETURN'],
                   application(end, kind, allow_data=allow_data, nonvoting=nonvoting), ('APPLICATION_AUTHORITY_', 'REPLAY_', 'APPLY_'),
                   'joining slot complete application storage order')
    count += exact(events, node, scope, own['PUBLICATION_VALIDATED'], own['PUBLICATION_SELECTOR_FORCED'],
                   publication(members), ('PUBLICATION_', 'INSTALL_', 'CURRENT_'),
                   'joining slot complete publication storage order')
    count += exact(events, node, scope, own['PUBLICATION_COVERAGE_VALIDATED'], own['PUBLICATION_RETIRED'],
                   retirement(end,nonvoting=nonvoting), ('PUBLICATION_', 'COVERED_END_', 'COVERED_VOTE_'),
                   'joining slot complete covered retirement order')
    return count


# Observation-only mutations; physical files must remain identical to the
# independently validated original before this focused replay is reused.
NEGATIVE_SPECS = {
    'accept-prefix': ('accept', 'ACCEPT_PREFIX_WRITTEN', 'remove'),
    'proof-created': ('proof', 'PROOF_CANDIDATE_CREATED', 'remove'),
    'certificate-written': ('certificate', 'CERTIFICATE_CANDIDATE_WRITTEN', 'remove'),
    'replay-reservation': ('application', 'REPLAY_RESERVED', 'remove'),
    'replay-claim-written': ('application', 'REPLAY_CLAIM_WRITTEN', 'remove'),
    'replay-deletion': ('application', 'REPLAY_DELETED', 'remove'),
    'replay-duplicate-deletion': ('application', 'REPLAY_DELETED', 'duplicate'),
    'apply-created': ('application', 'APPLY_DIRECTORY_CREATED', 'remove'),
    'apply-image-prefix': ('application', 'APPLY_IMAGE_PREFIX_WRITTEN', 'remove'),
    'apply-parent-written': ('application', 'APPLY_PARENT_STATEMENT_WRITTEN', 'remove'),
    'apply-ancestor-written': ('application', 'APPLY_ANCESTOR_0_ACK_WRITTEN', 'remove'),
    'apply-duplicate-created': ('application', 'APPLY_METADATA_CREATED', 'duplicate'),
    'publication-member-force': ('publication', 'INSTALL_MEMBER_FORCED', 'remove'),
    'publication-image-written': ('publication', 'INSTALL_IMAGE_WRITTEN', 'remove'),
    'publication-selector-written': ('publication', 'INSTALL_SELECTOR_WRITTEN', 'remove'),
    'publication-current-validated': ('publication', 'CURRENT_VALIDATED', 'remove'),
    'publication-duplicate-member': ('publication', 'INSTALL_MEMBER_FORCED', 'duplicate'),
    'publication-wrong-scope': ('publication', 'INSTALL_MEMBER_FORCED', 'scope'),
    'publication-member-before-write': ('publication', 'INSTALL_MEMBER_FORCED', 'swap'),
    'covered-end-before-delete': ('covered retirement', 'COVERED_END_BEFORE_DELETE', 'remove'),
    'covered-end-deletion': ('covered retirement', 'COVERED_END_FILE_DELETED', 'remove'),
    'covered-directory-deletion': ('covered retirement', 'COVERED_END_DIRECTORY_DELETED', 'remove'),
    'covered-vote-prefix': ('covered retirement', 'COVERED_VOTE_PREFIX_WRITTEN', 'remove'),
    'covered-vote-parent-force': ('covered retirement', 'COVERED_VOTE_PARENT_FORCED', 'remove'),
    'covered-duplicate-deletion': ('covered retirement', 'COVERED_END_FILE_DELETED', 'duplicate'),
    'covered-vote-wrong-scope': ('covered retirement', 'COVERED_VOTE_PARENT_FORCED', 'scope'),
}
NEGATIVES = {'slot-'+name: 'joining slot complete '+stage+(' order' if stage=='covered retirement' else ' storage order')
             for name, (stage, _, _) in NEGATIVE_SPECS.items()}


def mutate(events, name):
    need(name in NEGATIVES, 'joining slot unknown mutation')
    stage, point, mode = NEGATIVE_SPECS[name.removeprefix('slot-')]
    # INSTALL_* also occurs during selection; choose only a publication's
    # original interval. Parent/ancestor callbacks may first appear later.
    def publication_point(i):
        last = next((v['event'] for v in reversed(events[:i]) if v.get('node')=='node-1' and
                     v['event'] in ('PUBLICATION_VALIDATED','PUBLICATION_SELECTOR_FORCED')), None)
        return last == 'PUBLICATION_VALIDATED'
    at = next(i for i, v in enumerate(events) if v.get('node')=='node-1' and v['event']==point and
              (stage!='publication' or publication_point(i)))
    if mode=='remove': events.pop(at)
    elif mode=='duplicate': events.insert(at, dict(events[at]))
    elif mode=='scope': events[at]['scope']='closed-owner'
    else:
        previous = next(i for i in range(at-1,-1,-1) if events[i].get('node')=='node-1')
        events[previous], events[at] = events[at], events[previous]
