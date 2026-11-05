"""In-memory mutations after admission; never rewrite retained originals."""
import copy

from . import publication_generation_resources as g

NEGATIVES = {
    'old-generation-owner': 'generation resources exact owner extents',
    'old-image-owner': 'generation resources exact owner extents',
    'new-generation-owner': 'generation resources unexpected custody transition',
    'new-image-owner': 'generation resources unexpected custody transition',
    'journal-owner': 'generation resources exact owner extents',
    'authority-owner': 'generation resources exact owner extents',
    'completion-owner': 'generation resources exact owner extents',
    'replay-input-owner': 'generation resources exact owner extents',
    'generation-custody-gap': 'generation resources unexpected custody transition',
    'non-atomic-completion': 'generation resources unexpected custody transition',
}


def rebuild(trace):
    state = {}; limits = tuple(trace[k] for k in ('metadataLimit', 'stagingLimit', 'queueLimit'))
    for i, row in enumerate(trace['changes']):
        row['sequence'] = i
        for field in ('removed', 'added'): row[field].sort(key=g.t.order_key)
        for value in row['removed']:
            g.need(state.pop(g.t.key(value), None) == value, 'generation negatives original removal')
        for value in row['added']:
            g.need(g.t.key(value) not in state, 'generation negatives occupied charge')
            state[g.t.key(value)] = value
        row['usage'] = g.t.usage(state, limits)
    trace['transitions'] = len(trace['changes']); trace['current'] = copy.deepcopy(trace['changes'][-1]['usage'])
    # Mutations must still be legal, balanced accounting histories. Rejection
    # must come from physical-to-owner/interval binding, not a broken journal.
    g.t.replay(trace)


def mutate(transactions, traces, boundaries, name):
    g.need(name in NEGATIVES, 'generation negatives unknown mutation')
    plan = g.plans(transactions, boundaries)[0]; node = plan['node']; trace = traces[node]
    old_generation = next(key for key in plan['old'] if key[0] == 'GENERATION')
    old_image = next(key for key in plan['old'] if key[0] == 'APPLICATION')
    keys = {'old-generation-owner': old_generation, 'old-image-owner': old_image,
            'new-generation-owner': plan['generation'], 'new-image-owner': plan['image'],
            'journal-owner': ('JOURNAL', 'membership-grants'), 'authority-owner': ('MISC', 'current-authority'),
            'completion-owner': g.COMPLETION, 'replay-input-owner': g.TEMPORARIES[1]}
    if name in keys:
        key = keys[name]
        for row in trace['changes']:
            for value in row['removed']+row['added']:
                if g.t.key(value) == key: value['owner'] = 'wrong-'+value['owner']
    else:
        def change(event, removed=(), added=()):
            return dict(event=event, removed=list(removed), added=list(added))
        if name == 'generation-custody-gap':
            at = plan['sequences'][8]
            value = dict(unit=old_generation[0], owner=old_generation[1], bytes=plan['old'][old_generation], claimSource='')
            inserted = [change('RELEASE', [value]), change('RESERVE', added=[value])]
        else:
            at = next(i for i in range(plan['sequences'][0]+1, plan['sequences'][1]+1)
                      if trace['changes'][i]['event'] == 'EXTEND_COMMIT')
            original = trace['changes'][at]
            inserted = [change('RELEASE', original['removed']), change('RESERVE', added=original['added'])]
            trace['changes'][at] = change('EXTEND_COMMIT')
        trace['changes'][at:at] = copy.deepcopy(inserted)
        for boundary in boundaries:
            if boundary['node'] == node and boundary['sequence'] >= at: boundary['sequence'] += len(inserted)
    rebuild(trace)
    for boundary in boundaries:
        if boundary['node'] == node: boundary['usage'] = copy.deepcopy(trace['changes'][boundary['sequence']]['usage'])


def qualify(transactions, traces, boundaries):
    original = g.replay(transactions, traces, boundaries)
    results = []
    for name, reason in NEGATIVES.items():
        copied = copy.deepcopy((transactions, traces, boundaries))
        mutate(*copied, name)
        try: g.replay(*copied)
        except ValueError as error:
            g.need(str(error) == reason, 'generation negatives unrelated rejection: '+name+': '+str(error))
        else: raise ValueError('generation negatives accepted mutation: '+name)
        results.append(dict(case=name, status='REJECTED', reason=reason))
    return dict(status='PASS', scope='conditional-publication-generation-negatives', original=original, negatives=results,
                wholeRuntimePhysicalCustodyQualified=False, finalSourceCohortQualified=False, phase3Complete=False)
