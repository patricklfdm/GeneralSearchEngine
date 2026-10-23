"""Independent initial layout replay; offline commit and image semantics stay unclaimed."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile
from . import pending_context_evidence as e
from .journal_context_evidence import read_snapshot


def initial(path, size, node):
    files, directories = read_snapshot(path)
    e.need(directories == {'generations', 'generations/a', 'sources'}, 'seed initial directories')
    root = e.f.decode(files['root.gsr'], 'records', 'ROOT'); root_hash = files['root.gsr'][16:48].hex()
    genesis = e.f.decode(files['genesis.gsr'], 'records', 'GENESIS'); members = root['initial']; registry = e.identities(members)
    e.need(len(members) == size and node in registry and root['limits'] == e.digest(e.f.canonical(e.f.catalog()['resources'])), 'seed original root resources/size')
    e.need(all(root[key] == genesis[key] for key in ('groupId','historyId','baseSequence','schema','indexes'))
           and root['genesis'] == e.digest(files['genesis.gsr']) and genesis['source'] == 'EMPTY'
           and genesis['sourceDigest'] is None and genesis['baseSequence'] == 0, 'seed exact empty genesis')
    identity = registry[node]; expected_node = e.f.encode('records', 'NODE', dict(root=root_hash, identity=identity))
    e.need(files['node.gsr'] == expected_node and files['replica.lock'] == b'', 'seed original local identity')
    allocator = e.f.encode('records', 'ALLOCATOR', dict(root=root_hash, node=node, counter=1))
    e.need(files['allocator.gsr'] == allocator and files['pending.accept'] == struct.pack('>4sHHI',b'GSPV',1,3,12), 'seed empty vote and reserved counter')
    view = dict(generation=0, old=list(registry), new=list(registry), operation=None)
    cut = dict(entry=root['genesis'], index=0, view=view)
    catalog = dict(root=root_hash, application=genesis['application'], applicationSequence=0, cut=cut, identities=members,
                   active=None, lastDataIndex=0, nextOperation=1, results=[], retiredThrough=0)
    catalog_raw = e.f.encode('records', 'CATALOG', catalog)
    promise = e.f.encode('records', 'PROMISE', dict(root=root_hash, view=e.authority(root_hash,view),
        ballot=dict(counter=1,proposer=node,incarnation=identity['storage']),basisId=None))
    e.need(files['grants.gsr'] == promise and files['generations/a/promise.gsr'] == promise, 'seed fence only, no original vote')
    packet = e.p.decode(files['generations/a/source.gscp'])
    objects = {e.digest(files['root.gsr']):files['root.gsr'],root['genesis']:files['genesis.gsr'],e.digest(catalog_raw):catalog_raw}
    e.need(packet['objects'] == objects and packet['capsule'] == dict(root=root_hash,application=genesis['application'],catalog=e.digest(catalog_raw),
        cut=cut,initial=root['genesis'],inventory=packet['capsule']['inventory'],items=[]), 'seed exact zero-cut capsule')
    image_name = genesis['application']+'.image'; image = files['generations/a/'+image_name]
    e.need(packet['images'] == {genesis['application']:len(image)} and e.digest(image) == genesis['application'], 'seed initial image identity')
    # Exact image hashing, not a second implementation of the typed durable decoder.
    generation = {'source.gscp':files['generations/a/source.gscp'],'promise.gsr':promise,image_name:image}
    manifest = e.f.encode('records', 'GENERATION', dict(root=root_hash,node=node,generation='a',cut=cut,application=genesis['application'],catalog=e.digest(catalog_raw),
        capsule=e.digest(packet['capsuleBytes']),promise=e.digest(promise),basis=None,selection=None,ownedTail=None,
        files=[dict(path=name,size=len(raw),sha256=e.digest(raw)) for name,raw in sorted(generation.items())]))
    selector = e.f.encode('records','SELECTOR',dict(root=root_hash,node=node,generation='a',digest=e.digest(manifest)))
    e.need(files['generations/a/generation.gsr'] == manifest and files['selector.gsr'] == selector, 'seed exact selector and generation')
    e.need(set(files) == {'replica.lock','root.gsr','genesis.gsr','node.gsr','allocator.gsr','grants.gsr','pending.accept','selector.gsr','generations/a/generation.gsr'}
           | {'generations/a/'+name for name in generation}, 'seed original file inventory')
    return root_hash, files['root.gsr'], files['genesis.gsr'], files['generations/a/source.gscp'], image


def validate(root):
    root=Path(root);e.need(root.is_dir() and not root.is_symlink() and {p.name for p in root.iterdir()} == {'size-3','size-4','size-5','receipt.json'},'seed evidence case inventory')
    rows=[]
    for size in (3,4,5):
        case=root/('size-'+str(size));e.need(case.is_dir() and not case.is_symlink(),'seed case directory')
        names=['node-'+str(n) for n in range(1,size+1)]
        e.need({p.name for p in case.iterdir()} == set(names)|{'initial-'+n for n in names}|{'scratch'},'seed cohort inventory')
        originals=[initial(case/('initial-'+node),size,node) for node in names]
        e.need(all(row==originals[0] for row in originals),'seed cohort original agreement')
        rows.append(dict(size=size,accepts=size,proofs=size,acks=size,root=originals[0][0],status='PASS'))
    receipt_path=root/'receipt.json';e.need(receipt_path.is_file() and not receipt_path.is_symlink() and receipt_path.stat().st_size<=65536,'seed receipt type/capacity')
    receipt=e.parse(receipt_path.read_bytes());expected=dict(schema='gse-v53-bootstrap-seed-v1',status='PASS',cases=rows,offlineCommit=False,syntheticObservations=False)
    e.need(e.f.canonical(receipt)==e.f.canonical(expected),'seed producer receipt scope')
    return dict(status='PASS',sizes=[3,4,5],initialOwners=12,scope='initial-projected-byte-layout',offlineCommit=False,
                imageSemanticsIndependentlyVerified=False,subsequentVoteTraceIndependentlyVerified=False)


def qualify(root):
    root=Path(root);result=validate(root);negatives=[]
    variants={'missing-size':'seed evidence case inventory','extra-node':'seed cohort inventory','initial-counter':'seed empty vote and reserved counter',
        'initial-vote':'seed empty vote and reserved counter','extra-grant':'seed fence only, no original vote','swapped-node':'seed original local identity',
        'changed-image':'seed initial image identity','extra-file':'seed original file inventory','new-directory':'seed initial directories',
        'false-commit':'seed producer receipt scope','linked-image':'owner context linked/nonregular member'}
    for name,reason in variants.items():
        with tempfile.TemporaryDirectory(prefix='v53-seed-negative-') as tmp:
            moved=Path(tmp)/'evidence';shutil.copytree(root,moved);node=moved/'size-3/initial-node-1'
            if name=='missing-size':shutil.rmtree(moved/'size-5')
            elif name=='extra-node':(moved/'size-3/unplanned').mkdir()
            elif name=='initial-counter':
                p=node/'allocator.gsr';value=e.f.decode(p.read_bytes(),'records','ALLOCATOR');value['counter']=0;p.write_bytes(e.f.encode('records','ALLOCATOR',value))
            elif name=='initial-vote':(node/'pending.accept').write_bytes(b'fake')
            elif name=='extra-grant':
                p=node/'grants.gsr';p.write_bytes(p.read_bytes()+p.read_bytes())
            elif name=='swapped-node':(node/'node.gsr').write_bytes((moved/'size-3/initial-node-2/node.gsr').read_bytes())
            elif name=='changed-image':next((node/'generations/a').glob('*.image')).write_bytes(b'changed')
            elif name=='extra-file':(node/'extra').write_bytes(b'unplanned')
            elif name=='new-directory':(node/'generations/b').mkdir()
            elif name=='false-commit':
                p=moved/'receipt.json';value=e.parse(p.read_bytes());value['offlineCommit']=True;p.write_bytes(e.f.canonical(value))
            else:
                p=next((node/'generations/a').glob('*.image'));original=root/'size-3/initial-node-1/generations/a'/p.name;p.unlink();p.symlink_to(original.resolve())
            try:validate(moved)
            except ValueError as error:
                e.need(str(error)==reason,'wrong seed negative reason: '+name+': '+str(error));negatives.append(dict(case=name,reason=reason))
            else:raise ValueError('accepted seed mutation: '+name)
    with tempfile.TemporaryDirectory(prefix='v53-seed-portable-') as tmp:
        moved=Path(tmp)/'evidence';shutil.copytree(root,moved);e.need(validate(moved)==result,'seed portable replay')
    return dict(result,negatives=negatives,portableReplay='PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(qualify(args.root),sort_keys=True))
