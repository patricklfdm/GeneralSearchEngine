"""Exact generation custody during an independently admitted publication.

The caller admits original physical histories and publication captures first.
Expected identities/extents come from those admitted files, never allocation
labels or totals. This conditional reader does not qualify other lifetimes.
"""
from . import publication_resource_evidence as p
from . import resource_transitions as t

need = t.need
MAXIMUM = 64*t.MIB
COMPLETION = ('APPLICATION', 'publication-completion')
TEMPORARIES = tuple(('APPLICATION', name) for name in
                    ('applied-end', 'application-replay-input', 'application-replay-output'))
FIXED = {('JOURNAL', 'membership-grants'): 32*t.MIB,
         ('MISC', 'current-authority'): 2*t.MIB}


def extents(files):
    """Retain distinct slot/image names even when their contents are identical."""
    result = {}
    for slot in ('a', 'b'):
        prefix = 'generations/'+slot+'/'
        members = {n[len(prefix):]: raw for n, raw in files.items()
                   if n.startswith(prefix) and raw is not None}
        if not members: continue
        images = {n: raw for n, raw in members.items() if n.endswith('.image')}
        metadata = sum(len(raw) for n, raw in members.items() if n not in images)
        need('generation.gsr' in members and images and 0 < metadata <= 32*t.MIB and
             all(0 < len(raw) <= MAXIMUM for raw in images.values()), 'generation resources original extents')
        result['GENERATION', slot] = metadata
        result.update({('APPLICATION', 'generation-'+slot+':'+n): len(raw) for n, raw in images.items()})
    need(result, 'generation resources missing original generation')
    return result


def watched(key):
    return key[0] in ('GENERATION', 'MISC', 'JOURNAL') or key == COMPLETION or key in TEMPORARIES or \
           key[0] == 'APPLICATION' and key[1].startswith('generation-')


def plans(transactions, boundaries):
    """The capture inventories have already matched independent pre/post states."""
    result = []; seen = set(); previous = {}
    for rows in transactions:
        need(len(rows) == len(p.POINTS), 'generation resources complete publication')
        node = rows[0]['node']; sequences = []
        for row, point in zip(rows, p.POINTS):
            at = row['eventIndex']
            need(type(at) is int and 0 <= at < len(boundaries) and at not in seen and
                 row['node'] == node and row['point'] == point, 'generation resources original boundary')
            seen.add(at); boundary = boundaries[at]; sequence = boundary['sequence']
            need(boundary['node'] == node and type(boundary['eventIndex']) is int and boundary['eventIndex'] == at and
                 type(sequence) is int and sequence >= 0 and (not sequences or sequence >= sequences[-1]),
                 'generation resources exact boundary sequence')
            need(p.usage(boundary['usage']) == row['storage'], 'generation resources original storage boundary')
            sequences.append(sequence)
        need(sequences[0] > previous.get(node, -1), 'generation resources overlapping publication')
        previous[node] = sequences[-1]
        before, after = rows[0]['files'], rows[-1]['files']
        output=p.output_reserved(before,after,rows[0]['storage'])
        for row, (point, files, charges) in zip(rows, p.derived(before, after,output=output)):
            need(row['point'] == point and row['files'] == files and row['storage'] == charges,
                 'generation resources admitted publication inventory')
        old, final = extents(before), extents(after)
        need(all(final.get(key) == size for key, size in old.items()), 'generation resources retained original extent')
        added = {key: size for key, size in final.items() if key not in old}
        generations = [key for key in added if key[0] == 'GENERATION']
        images = [key for key in added if key[0] == 'APPLICATION']
        need(len(generations) == len(images) == 1 and len(added) == 2,
             'generation resources single new publication generation')
        result.append(dict(node=node, sequences=sequences, boundaries=[boundaries[row['eventIndex']] for row in rows], old=old, final=final,
                           generation=generations[0], image=images[0],output=output))
    need(result, 'generation resources missing publications')
    return result


def bind(plan, changes, initial):
    """Check every mutation, including those between physical callbacks."""
    seq = plan['sequences']; generation, image = plan['generation'], plan['image']
    temporaries=TEMPORARIES if plan['output'] else TEMPORARIES[:-1]
    expected = {**FIXED, **plan['old'], COMPLETION: MAXIMUM,
                **dict.fromkeys(temporaries, MAXIMUM)}
    state = dict(initial); reserved = transferred = reloaded = False; released = set(); checks = 0
    boundary = dict(zip(p.POINTS, seq))

    def match():
        actual = {key: value for key, value in state.items() if watched(key)}
        need(set(actual) == set(expected) and all(not actual[key]['claimSource'] and
             actual[key]['bytes'] == size for key, size in expected.items()),
             'generation resources exact owner extents')

    match()
    for row in changes[seq[0]+1:seq[-1]+1]:
        at, event = row['sequence'], row['event']
        removed = {t.key(v): v for v in row['removed'] if watched(t.key(v))}
        added = {t.key(v): v for v in row['added'] if watched(t.key(v))}
        if removed or added:
            if event == 'RESERVE' and set(added) == {generation} and not removed:
                need(not reserved and seq[0] < at <= seq[1], 'generation resources reservation interval')
                reserved = True; expected[generation] = plan['final'][generation]
            elif event == 'EXTEND_COMMIT' and set(removed) == {COMPLETION} and set(added) == {image}:
                need(reserved and not transferred and seq[0] < at <= seq[1], 'generation resources completion transfer interval')
                transferred = True; del expected[COMPLETION]; expected[image] = MAXIMUM
            elif event == 'GENERATION_RELOAD' and set(removed) == set(added) == {image}:
                need(transferred and not reloaded and seq[7] < at <= seq[8], 'generation resources reload interval')
                reloaded = True; expected[image] = plan['final'][image]
            elif event == 'RELEASE' and len(removed) == 1 and not added and next(iter(removed)) in temporaries:
                key = next(iter(removed))
                need(reloaded and key not in released and seq[8] < at <= seq[9], 'generation resources completion release interval')
                released.add(key); del expected[key]
            else: raise ValueError('generation resources unexpected custody transition')
        elif event == 'GENERATION_RELOAD':
            # A maximum-sized actual image still has an atomic reload boundary,
            # but no changed byte count in the delta journal.
            need(transferred and not reloaded and plan['final'][image] == MAXIMUM and seq[7] < at <= seq[8],
                 'generation resources reload interval')
            reloaded = True
        for value in row['removed']: state.pop(t.key(value))
        for value in row['added']: state[t.key(value)] = value
        match(); checks += 1
        for point, position in boundary.items():
            if position != at: continue
            index = p.POINTS.index(point)
            need((index < 1 or reserved and transferred) and (index < 8 or reloaded) and
                 (index < 9 or released == set(temporaries)), 'generation resources completed boundary handoff')
    need(seq[0] < seq[1] and seq[7] < seq[8] < seq[9] and reserved and transferred and reloaded and
         released == set(temporaries), 'generation resources complete publication handoff')
    return checks+1


def replay(transactions, traces, boundaries):
    required = plans(transactions, boundaries); grouped = {}
    for plan in required: grouped.setdefault(plan['node'], []).append(plan)
    checks = 0
    for node, work in grouped.items():
        need(node in traces, 'generation resources missing original owner')
        trace = traces[node]; t.replay(trace); changes = trace['changes']; starts = {}
        for plan in work:
            need(plan['sequences'][-1] < len(changes), 'generation resources boundary outside journal')
            # The native wrapper also checks every event. This conditional
            # reader verifies its own complete publication usage binding.
            for boundary in plan['boundaries']:
                t.same_usage(boundary['usage'], changes[boundary['sequence']]['usage'])
            starts[plan['sequences'][0]] = plan
        state = {}
        for row in changes:
            for value in row['removed']: state.pop(t.key(value))
            for value in row['added']: state[t.key(value)] = value
            if row['sequence'] in starts:
                checks += bind(starts[row['sequence']], changes, state)
    return dict(status='PASS', scope='admitted-publication-generation-custody', publications=len(required),
                physicalBoundaries=len(required)*len(p.POINTS), mutationStates=checks,
                generationIdentitiesDerived=True, completionTransferDerived=True,
                wholeRuntimePhysicalCustodyQualified=False, physicalPeakQualified=False,
                finalSourceCohortQualified=False, phase3Complete=False)
