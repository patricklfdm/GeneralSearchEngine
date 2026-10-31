"""Narrow carried-round retirement projection over already replayed originals.

Only the empty-tail predecessor of this two-campaign history is eligible. The
enclosing reader must prove both original campaigns, publication, exact-current
majority copies and the complete retirement/rotation force sequence. This is not
a generic source eligibility test or an interrupted-retirement qualification.
"""
import json
import shutil
from . import slot_endpoint_evidence as slot
from . import source_release_evidence as release

c, e, f, need = slot.c, slot.e, slot.f, slot.need


def retire_predecessor(group, voters):
    result = dict(group); events = {}
    for node in voters:
        files = group[node]; prefix, _, packet = c.current(files); cap = packet['capsule']
        manifest = f.decode(files[prefix+'generation.gsr'], 'records', 'GENERATION')
        rows = c.journal(files['grants.gsr'], cap['root'], node)
        need([v[0] for v in rows] == ['PROMISE','BASIS','SELECTED']*2,
             'native source retirement original campaigns')
        prior, basis, selected, highest, current_basis, _ = [v[2] for v in rows]
        identifier = prior['basisId']; source = 'sources/'+identifier
        need([v['ballot']['counter'] for v in (prior, highest)] == [2,3]
             and basis['accepted'] is None and basis['basisId'] == identifier
             and cap['cut']['index'] == 1 and e.authority(cap['root'], cap['cut']['view']) == selected['view']
             and manifest['promise'] == e.digest(rows[3][1])
             and manifest['basis'] == e.digest(rows[4][1])
             and current_basis['basisId'] != identifier,
             'native source retirement covered empty predecessor')
        original = e.p.decode(files[source+'/source.gscp']); e.p.bind(original, rows[1][1])
        old = original['capsule']
        need(old['root'] == cap['root'] and old['cut']['index'] == 0
             and old['cut']['view'] == cap['cut']['view'], 'native source retirement original root/cut')
        # The enclosing original publication replay derives this exact range
        # from the completed carried entry, not from a claimed retirement ACK.
        statements = [f.decode(packet['objects'][item['statement']], 'records', 'CHECKPOINT')
                      for item in cap['items']]
        need(any(v == dict(root=cap['root'], scope='RANGE', start=old['cut'], end=cap['cut'],
                           catalogBefore=old['catalog'], catalogAfter=cap['catalog'],
                           applicationBefore=old['application'], applicationAfter=cap['application'])
                 for v in statements), 'native source retirement original ancestry')
        expected = {source: None, source+'/source.gscp': files[source+'/source.gscp']}
        for digest, metadata in original['images'].items():
            raw = files[source+'/'+digest+'.image']
            need(len(raw) == metadata and e.digest(raw) == digest, 'native source retirement original image')
            expected[source+'/'+digest+'.image'] = raw
        need({k:v for k,v in files.items() if k == source or k.startswith(source+'/')} == expected,
             'native source retirement exact source inventory')
        result[node] = {k:v for k,v in files.items() if k not in expected}
        result[node]['grants.gsr'] = b''.join(v[1] for v in rows[3:])
        # Reuse the already qualified transaction's clean force order, with
        # exact deletion multiplicity from the original source inventory.
        events[node] = list(release.CUTS[:10]) + ['SOURCE_RETIREMENT_FILE_DELETED']*(len(expected)-1) + list(release.CUTS[12:])
    return result, events


NEGATIVES = {
    'retirement-kept-predecessor': 'admitted exact applied-2: node-1',
    'retirement-current-source-deleted': 'admitted exact applied-2: node-1',
    'retirement-compact-journal': 'admitted exact applied-2: node-1',
    'retirement-missing-force': 'native dispatch exact source retirement',
    'retirement-early-journal': 'native dispatch exact source retirement',
    'retirement-unexpected-first-slot': 'native dispatch exact source retirement',
    'retirement-before-generation': 'selected retention force order: native source retirement after generation before floor release',
}


def mutate(root, name):
    if name in ('retirement-kept-predecessor', 'retirement-current-source-deleted'):
        before = c.inventory(root/'published-1/node-1'); cap = c.current(before)[2]['capsule']
        rows = c.journal(before['grants.gsr'], cap['root'], 'node-1')
        identifier = rows[0 if name == 'retirement-kept-predecessor' else 3][2]['basisId']
        path = root/'applied-2/node-1/sources'/identifier
        if name == 'retirement-kept-predecessor': shutil.copytree(root/'published-1/node-1/sources'/identifier, path)
        else: shutil.rmtree(path)
        return
    if name == 'retirement-compact-journal':
        (root/'applied-2/node-1/grants.gsr').write_bytes(b'changed'); return
    path = root/'events.json'; rows = json.loads(path.read_text())
    own = [v for v in rows if v['node'] == 'node-1']
    def event(kind): return next(v for v in own if v['event'] == kind)
    if name == 'retirement-missing-force': rows.remove(event('SOURCE_RETIREMENT_FORCED'))
    elif name == 'retirement-early-journal':
        a, b = rows.index(event('SOURCE_RETIREMENT_PARENT_FORCED')), rows.index(event('JOURNAL_ROTATION_CREATED'))
        rows[a], rows[b] = rows[b], rows[a]
    elif name == 'retirement-unexpected-first-slot':
        rows.insert(rows.index(event('FLOOR_BEFORE_RETURN'))+1, dict(node='node-1',event='JOURNAL_ROTATION_CREATED'))
    elif name == 'retirement-before-generation':
        moving = [v for v in own if v['event'].startswith(('SOURCE_RETIREMENT_', 'JOURNAL_ROTATION_'))]
        for row in moving: rows.remove(row)
        start = next(i for i,v in enumerate(rows) if v['event'] == 'SLOT_BEGIN' and v['index'] == 2)
        at = next(i for i in range(start, len(rows)) if rows[i]['node'] == 'node-1' and rows[i]['event'] == 'RETIREMENT_BEFORE_RETURN')
        rows[at:at] = moving
    else: raise ValueError('unknown source retirement mutation')
    path.write_text(json.dumps(rows))
