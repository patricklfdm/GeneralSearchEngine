"""Original-first corruption qualification for physical context fixtures."""
from pathlib import Path
import shutil
import tempfile

from . import context_evidence as e
from . import format_fixture as f
from .membership_model import need

CASES = ('missing-file', 'file-hash', 'duplicate-path', 'path-traversal', 'symlink',
         'size-overflow', 'missing-profile', 'runtime-relabel', 'missing-owned-proof',
         'parent-force-order', 'foreign-storage', 'wrong-parent', 'catalog-retirement',
         'catalog-identities', 'entry-origin', 'certificate-receipt', 'profile-relabel', 'missing-descriptor')


def put(root, manifest, name, data):
    (root/name).write_bytes(data)
    row = next(r for r in manifest['files'] if r['path'] == name)
    row.update(size=len(data), sha256=e.sha(data))
    for force in manifest['forces']:
        if force['path'] == name: force['sha256'] = e.sha(data)


def mutate(root, case):
    root = Path(root); manifest = e.parse((root/'manifest.json').read_bytes())
    name = '3-REPLACE/history.json'; history = e.parse((root/name).read_bytes())
    first = manifest['files'][0]['path']; owned = history['owned'][0]
    if case == 'missing-file': (root/first).unlink()
    elif case == 'file-hash': (root/first).write_bytes(b'corruption')
    elif case == 'duplicate-path': manifest['files'].append(manifest['files'][0])
    elif case == 'path-traversal': manifest['files'][0]['path'] = '../escape'
    elif case == 'symlink':
        (root/first).unlink(); (root/first).symlink_to(root/name)
    elif case == 'size-overflow': manifest['files'][0]['size'] = 2**63
    elif case == 'missing-profile':
        prefix = '5-REPLACE/'
        shutil.rmtree(root/'5-REPLACE')
        manifest['files'] = [r for r in manifest['files'] if not r['path'].startswith(prefix)]
        manifest['forces'] = [r for r in manifest['forces'] if not r['path'].startswith(prefix)]
        for i, row in enumerate(manifest['forces'], 1): row['sequence'] = i
    elif case == 'runtime-relabel': manifest['authorityEvidence'] = True
    elif case == 'missing-owned-proof':
        proof = history['steps'][0]['proof']
        history['owned'] = [r for r in history['owned'] if not r['record'].endswith(proof+'.bin')]
    elif case == 'parent-force-order':
        a = next(i for i, r in enumerate(manifest['forces']) if r['path'] == owned['parent'])
        b = next(i for i, r in enumerate(manifest['forces']) if r['path'] == owned['record'])
        manifest['forces'][a], manifest['forces'][b] = manifest['forces'][b], manifest['forces'][a]
        for i, row in enumerate(manifest['forces'], 1): row['sequence'] = i
    elif case == 'foreign-storage': owned['storage'] = '00000000-0000-0000-0000-000000000099'
    elif case == 'wrong-parent':
        value = e.parse((root/owned['parent']).read_bytes()); value['index'] += 1
        put(root, manifest, owned['parent'], f.canonical(value))
    elif case in ('catalog-retirement', 'catalog-identities', 'entry-origin', 'certificate-receipt'):
        key, kind = ('entry', 'ENTRY') if case == 'entry-origin' else ('certificate', 'CERTIFICATE') if case == 'certificate-receipt' else ('catalogAfter', 'CATALOG')
        step = history['steps'][-1]; old_hash = step[key]; path = '3-REPLACE/objects/'+old_hash+'.bin'
        value = f.decode((root/path).read_bytes(), 'records', kind)
        if case == 'catalog-retirement': value['retiredThrough'] = 0
        elif case == 'catalog-identities': value['identities'] = [r for r in value['identities'] if r['node'] != 'node-3']
        elif case == 'entry-origin': value['origin']['counter'] = 999
        else: value['proofs'][0]['receipt'] = 'ff'*32
        data = f.encode('records', kind, value); new_hash = e.sha(data); target = '3-REPLACE/objects/'+new_hash+'.bin'
        (root/path).unlink(); (root/target).write_bytes(data)
        row = next(r for r in manifest['files'] if r['path'] == path)
        row.update(path=target, sha256=new_hash, size=len(data)); step[key] = new_hash
    elif case == 'profile-relabel': history['profile'] = '3-ADD'
    elif case == 'missing-descriptor':
        entry = f.decode((root/('3-REPLACE/objects/'+history['steps'][5]['entry']+'.bin')).read_bytes(), 'records', 'ENTRY')
        sealed = e.parse((root/('3-REPLACE/objects/'+entry['payload']+'.bin')).read_bytes())['sealed']
        path = '3-REPLACE/objects/'+e.digest(sealed)+'.bin'; (root/path).unlink()
        manifest['files'] = [r for r in manifest['files'] if r['path'] != path]
    else: raise ValueError('unknown context negative')
    if case not in ('missing-profile', 'symlink'): put(root, manifest, name, f.canonical(history))
    (root/'manifest.json').write_bytes(f.canonical(manifest))


def run(original):
    original = Path(original).resolve()
    e.validate(original)  # A broken original can never qualify all negative cases.
    results = []
    with tempfile.TemporaryDirectory(prefix='v53-context-negatives-') as directory:
        relocated = Path(directory)/'relocated'; shutil.copytree(original, relocated)
        need(e.validate(relocated) == e.validate(original), 'portable context replay')
        for case in CASES:
            target = Path(directory)/case; shutil.copytree(original, target); mutate(target, case)
            try: e.validate(target)
            except ValueError as error: results.append(dict(case=case, status='REJECT', reason=str(error)))
            else: raise ValueError('accepted negative: '+case)
            shutil.rmtree(target)
    need(tuple(r['case'] for r in results) == CASES, 'context negative inventory')
    return results
