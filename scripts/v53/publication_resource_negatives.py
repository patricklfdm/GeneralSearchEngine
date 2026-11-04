"""Original-first, capture-only rejection qualification; no new native execution."""
import json
from pathlib import Path
import shutil
import tempfile
from . import publication_resource_evidence as r

NEGATIVES = {
    'incomplete-index':'complete index', 'index-path':'ordered index', 'capture-digest':'capture digest',
    'boolean-event-index':'metadata binding', 'duplicate-event':'metadata binding', 'foreign-scope':'exact event',
    'missing-object':'missing object/size', 'altered-object':'object identity/capacity',
    'extra-object':'unobserved object', 'extra-metadata':'unobserved metadata',
    'boolean-directory':'directory type', 'missing-parent':'parent directory',
    'missing-boundary':'complete boundary order', 'changed-storage':'storage changed during observation',
    'boolean-charge':'usage shape', 'incorrect-lease-count':'observed limits',
    'lost-old-generation-charge':'exact charges: CURRENT_VALIDATED',
    'premature-candidate-shrink':'exact charges: CURRENT_DIRECTORY_FORCED',
    'late-candidate-shrink':'exact charges: PUBLICATION_SELECTOR_FORCED',
    'lost-completion-reserve':'exact charges: PUBLICATION_VALIDATED',
    'leaked-completion-reserve':'exact charges: PUBLICATION_RETIRED',
    'extra-file':'exact inventory: PUBLICATION_VALIDATED',
    'changed-original-file':'exact inventory: PUBLICATION_VALIDATED',
    'early-selector':'exact inventory: INSTALL_RESERVED',
    'early-vote-cleanup':'exact inventory: PUBLICATION_SELECTOR_FORCED',
    'lost-old-generation':'exact inventory: CURRENT_VALIDATED',
}


def mutate(root, name):
    root = Path(root)/r.DIRECTORY
    index = json.loads((root/'index.json').read_bytes())
    rows = [json.loads((root/ref['path']).read_bytes()) for ref in index['captures']]
    objects = root/'objects'
    def point(label): return next(row for row in rows if row['point'] == label)
    def identity(row, name): return next(v['identity'] for v in row['files'] if v['name'] == name)
    def amounts(row, metadata=0, staging=0, application=0, generation=0):
        for key in ('usageBefore','usageAfter'):
            use = row[key]; use['metadata'] += metadata; use['staging'] += staging
            use['counts']['APPLICATION'] += application; use['counts']['GENERATION'] += generation
            use['leases'] += application+generation
    if name == 'incomplete-index': index['complete'] = False
    elif name == 'index-path': index['captures'][0]['path'] = '../outside'
    elif name == 'capture-digest': index['captures'][0]['sha256'] = '0'*64
    elif name == 'boolean-event-index': rows[0]['eventIndex'] = True
    elif name == 'duplicate-event': rows[1]['eventIndex'] = rows[0]['eventIndex']
    elif name == 'foreign-scope': rows[0]['scope'] = 'foreign'
    elif name in ('missing-object','altered-object'):
        path = objects/identity(rows[0],'root.gsr')['sha256']
        if name == 'missing-object': path.unlink()
        else: path.write_bytes(b'changed')
    elif name == 'extra-object':
        raw = b'unobserved'; (objects/r.sha(raw)).write_bytes(raw)
    elif name == 'extra-metadata': (root/'unreferenced.json').write_bytes(b'{}')
    elif name == 'boolean-directory': next(v for v in rows[0]['files'] if 'directory' in v['identity'])['identity']['directory'] = 1
    elif name == 'missing-parent': rows[0]['files'] = [v for v in rows[0]['files'] if v['name'] != 'applied-end']
    elif name == 'missing-boundary':
        rows.remove(point('INSTALL_RESERVED')); (root/index['captures'][-1]['path']).unlink(); index['captures'].pop()
    elif name == 'changed-storage': rows[0]['usageAfter']['staging'] -= 1
    elif name == 'boolean-charge': rows[0]['usageBefore']['staging'] = True
    elif name == 'incorrect-lease-count': rows[0]['usageBefore']['leases'] -= 1
    elif name == 'lost-old-generation-charge':
        first = rows[0]; old = next(v['name'] for v in first['files'] if v['name'].startswith('generations/') and 'directory' in v['identity'])
        members = [v for v in first['files'] if v['name'].startswith(old+'/')]
        meta = sum(v['identity']['size'] for v in members if not v['name'].endswith('.image'))
        image = sum(v['identity']['size'] for v in members if v['name'].endswith('.image'))
        amounts(point('CURRENT_VALIDATED'),metadata=-meta,staging=-image,application=-1,generation=-1)
    elif name in ('premature-candidate-shrink','late-candidate-shrink'):
        image = identity(rows[0],'applied-end/application.image')['size']; difference = 64*r.MIB-image
        amounts(point('CURRENT_DIRECTORY_FORCED' if name == 'premature-candidate-shrink' else 'PUBLICATION_SELECTOR_FORCED'),
                staging=-difference if name == 'premature-candidate-shrink' else difference)
    elif name == 'lost-completion-reserve': amounts(rows[0],staging=-64*r.MIB,application=-1)
    elif name == 'leaked-completion-reserve': amounts(point('PUBLICATION_RETIRED'),staging=64*r.MIB,application=1)
    elif name == 'extra-file':
        rows[0]['files'].append(dict(name='unreferenced.bin',identity=identity(rows[0],'root.gsr')))
        rows[0]['files'].sort(key=lambda v:v['name'])
    elif name == 'changed-original-file':
        next(v for v in rows[0]['files'] if v['name'] == 'root.gsr')['identity'] = identity(rows[0],'node.gsr')
    elif name in ('early-selector','early-vote-cleanup'):
        target = point('INSTALL_RESERVED' if name == 'early-selector' else 'PUBLICATION_SELECTOR_FORCED')
        field = 'selector.gsr' if name == 'early-selector' else 'pending.accept'
        next(v for v in target['files'] if v['name'] == field)['identity'] = identity(point('PUBLICATION_RETIRED'),field)
    elif name == 'lost-old-generation':
        old = next(v['name'] for v in rows[0]['files'] if v['name'].startswith('generations/') and 'directory' in v['identity'])
        row = point('CURRENT_VALIDATED'); row['files'] = [v for v in row['files'] if v['name'] != old and not v['name'].startswith(old+'/')]
    else: raise ValueError('unknown publication resources mutation')
    if name not in ('index-path','capture-digest'):
        for ref,row in zip(index['captures'],rows):
            raw = r.f.canonical(row); (root/ref['path']).write_bytes(raw); ref['sha256'] = r.sha(raw)
    (root/'index.json').write_bytes(r.f.canonical(index))


def qualify(directory, profile='stable', progress=None):
    from .joining_history_run import inventory
    root = Path(directory); before = inventory(root)
    precondition,plans = r.original(root,profile,progress)
    events = r.events(root)
    original = r.compare(r.collect(root,events),plans)
    results = []
    for name, suffix in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-publication-resource-negative-') as tmp:
            target = Path(tmp); shutil.copytree(root/r.DIRECTORY,target/r.DIRECTORY); mutate(target,name)
            reason = 'publication resources '+suffix
            try: r.compare(r.collect(target,events),plans)
            except ValueError as error: r.need(str(error) == reason, 'unrelated publication resources negative: '+name+': '+str(error))
            else: raise ValueError('publication resources mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    r.need(inventory(root) == before, 'publication resources original changed')
    return dict(status='PASS',profile=profile,precondition=precondition,original=original,negatives=results,
                publicationStorageDerived=True,controlChargesDerived=False,wholeRuntimePeakQualified=False,phase3Complete=False)
