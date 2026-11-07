"""Writer-held retirement prefixes and independent exact transaction comparison.

Collection binds original observations; it is not authority to retire a source.
The comparison API requires a separately derived initial state/decision/journal.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from . import joining_grant_captures as grants
from . import source_release_evidence as release
from . import capture_objects
from . import bootstrap_replay_contract as policy

f, need, sha = grants.f, grants.need, grants.sha
DIRECTORY, EVENT = 'source-retirement-captures', 'SOURCE_RETIREMENT_CAPTURED'
SCHEMA = 'gse-v53-source-retirement-capture-v1'
MAXIMUM_CAPTURES = 512


def collect(root, events, *, bootstrap_source=policy.EMPTY, wire_layout=policy.JSON):
    source_args=policy.options(bootstrap_source,wire_layout)
    need(type(events) is list and 0 < len(events) <= 65536 and all(type(row) is dict for row in events),
         'retirement capture event collection')
    root = Path(root)/DIRECTORY
    need(root.is_dir() and not root.is_symlink(), 'retirement capture collection missing')
    objects = root/'objects'
    need(objects.is_dir() and not objects.is_symlink(), 'retirement capture object directory')
    streamed=wire_layout==policy.SEGMENTED
    payloads = capture_objects.Pool(objects,label='retirement capture',**source_args) if streamed else {}
    used = set(); total = 0
    for path in (() if streamed else objects.iterdir()):
        need(re.fullmatch('[0-9a-f]{64}', path.name) is not None and len(payloads) < 8192, 'retirement capture object name/count')
        raw = grants.snapshot.s.regular(path,64*grants.MIB); total += len(raw)
        need(total <= grants.MAXIMUM_BYTES and sha(raw) == path.name, 'retirement capture object identity/capacity')
        payloads[path.name] = raw
    transactions = []; active = {}; pending = {}; names = []; identities = {}; roots = set()
    for position, event in enumerate(events):
        kind = event.get('event'); node = event.get('node'); scope = event.get('scope', 'network-owner')
        if kind == EVENT:
            need(node in pending and node in active and len(names) < MAXIMUM_CAPTURES, 'retirement capture orphan/capacity')
            at, point = pending.pop(node); transaction = active[node]
            need(scope == transaction['scope'] and event.get('point') == point, 'retirement capture event point/scope')
            name = f'capture-{len(names)+1:04d}.json'
            need(event.get('capture') == DIRECTORY+'/'+name, 'retirement capture ordered unique path')
            raw, metadata = grants.json_file(root/name)
            need(set(event) == {'node','scope','event','point','capture','sha256'} and sha(raw) == event['sha256'],
                 'retirement capture event digest')
            need(type(metadata) is dict and set(metadata) == {'schema','node','scope','point','files'} and
                 metadata['schema'] == SCHEMA and all(metadata[k] == event[k] for k in ('node','scope','point')),
                 'retirement capture metadata binding')
            entries = metadata['files']; files = {}; previous = None
            need(type(entries) is list and 0 < len(entries) <= grants.MAXIMUM_FILES, 'retirement capture file count')
            for entry in entries:
                need(type(entry) is dict and set(entry) == {'name','identity'}, 'retirement capture file shape')
                path = entry['name']; grants.snapshot.relative(path)
                need(previous is None or previous < path, 'retirement capture ordered unique member'); previous = path
                identity = entry['identity']
                need(type(identity) is dict, 'retirement capture member identity')
                if identity == {'directory':True}:
                    need(type(identity['directory']) is bool, 'retirement capture directory type'); files[path] = None
                else:
                    need(set(identity) == {'size','sha256'} and type(identity['size']) is int and identity['size'] >= 0
                         and type(identity['sha256']) is str and identity['sha256'] in payloads,
                         'retirement capture missing object/size')
                    digest = identity['sha256']
                    size=payloads.size(digest) if streamed else len(payloads[digest])
                    need(size == identity['size'], 'retirement capture file size'); used.add(digest)
                    files[path] = digest if streamed else payloads[digest]
                parent = str(Path(path).parent)
                need(parent == '.' or parent in files and files[parent] is None, 'retirement capture parent directory')
            if streamed:files=payloads.view(files)
            need(type(files.get('root.gsr')) is bytes and type(files.get('node.gsr')) is bytes,
                 'retirement capture owner records')
            f.decode(files['root.gsr'],'records','ROOT'); root_id = files['root.gsr'][16:48].hex()
            owner = f.decode(files['node.gsr'],'records','NODE',root_id)['identity']
            need(owner['node'] == node and (node not in identities or identities[node] == owner), 'retirement capture original owner')
            identities[node] = owner; roots.add(root_id); need(len(roots) == 1, 'retirement capture mixed roots')
            transaction['steps'].append(dict(point=point,files=files,event=at,capturedEvent=position))
            names.append(name)
            if point == 'SOURCE_RETIREMENT_BEFORE_RETURN': transactions.append(active.pop(node))
            continue
        if kind == 'SOURCE_RETIREMENT_CREATED':
            need(type(node) is str and type(scope) is str and node not in active, 'retirement capture overlapping start')
            active[node] = dict(node=node,scope=scope,steps=[])
        relevant = type(kind) is str and (kind.startswith('SOURCE_RETIREMENT_') or
                   kind.startswith('JOURNAL_ROTATION_') and node in active)
        if relevant:
            need(node in active and node not in pending and scope == active[node]['scope'], 'retirement capture missing copy/start')
            pending[node] = position,kind
    need(transactions and not active and not pending, 'retirement capture incomplete transaction')
    need({path.name for path in root.iterdir()} == {'objects',*names}, 'retirement capture unobserved metadata')
    need(used == payloads.keys(), 'retirement capture unobserved object')
    if streamed:payloads.check_unchanged()
    return transactions


def compare(transaction, initial, authority, compact, identifier):
    """All expected bytes must come from the preceding independent derivation."""
    expected = release.transaction(initial,authority,compact,identifier)
    rows = transaction['steps']
    need(len(rows) == len(expected), 'retirement capture exact prefix count')
    for row, (point, state) in zip(rows,expected):
        need(row['point'] == point, 'retirement capture original force order')
        files=row['files']
        if type(files) is capture_objects.Files:
            observed={name:identity if 'directory' in identity else dict(bytes=identity['size'],sha256=identity['sha256'])
                      for name,identity in files.identities().items()}
        else:observed = {name:dict(directory=True) if value is None else release.r.entry(value) for name,value in files.items()}
        need(observed == state, 'retirement capture exact prefix: '+point)
    return len(expected)


def validate(root, events=None, *, bootstrap_source=policy.EMPTY, wire_layout=policy.JSON):
    source_args=policy.options(bootstrap_source,wire_layout)
    root = Path(root)
    if events is None:
        from .joining_history_run import read_json, EVENT_BYTES
        events = read_json(root,'events.json',EVENT_BYTES)
    transactions = collect(root,events,**source_args)
    return policy.receipt(dict(status='PARTIAL',scope='original-source-retirement-prefix-collection',transactions=len(transactions),
                capturedPrefixes=sum(len(v['steps']) for v in transactions),
                independentlyDerived=False,forceAndNetworkQualified=False,phase3Complete=False),bootstrap_source,wire_layout)


def component(root):
    """Small real writer exercise; old/joint/new floor fixture remains explicit."""
    root = Path(root); before = grants.inventory(root)[1]
    initial,authority,compact,identifier = release.plan(root,dict(size=3,through=0))
    transactions = collect(root,json.loads((root/'events.json').read_bytes()))
    need(len(transactions) == 1 and transactions[0]['node'] == 'node-1', 'retirement capture component transaction')
    prefixes = compare(transactions[0],initial,authority,compact,identifier)
    release.r.snapshot(root/'final',release.transaction(initial,authority,compact,identifier)[-1][1])
    need(grants.inventory(root)[1] == before,'retirement original changed during replay')
    return dict(status='PASS',scope='source-retirement-component-prefixes',transactions=1,capturedPrefixes=prefixes,
                independentInitialFixture=True,wholeJoiningHistory=False,processDeathQualified=False,phase3Complete=False)


NEGATIVES = {
    'missing-copy':'retirement capture missing copy/start',
    'wrong-event-digest':'retirement capture event digest',
    'missing-object':'retirement capture missing object/size',
    'altered-object':'retirement capture object identity/capacity',
    'extra-object':'retirement capture unobserved object',
    'wrong-floor':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-source-file':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'premature-journal-pruning':'retirement capture exact prefix: SOURCE_RETIREMENT_WRITTEN',
    'wrong-deletion':'retirement capture exact prefix: SOURCE_RETIREMENT_FILE_DELETED',
    'extra-preserved-file':'retirement capture exact prefix: SOURCE_RETIREMENT_BEFORE_RETURN',
    'lost-force':'retirement capture exact prefix count',
    'foreign-scope':'retirement capture event point/scope',
}


def mutate(root,name):
    events=json.loads((root/'events.json').read_bytes()); copies=[row for row in events if row.get('event') == EVENT]
    if name == 'missing-copy': events.remove(copies[0])
    elif name == 'wrong-event-digest': copies[0]['sha256']='0'*64
    elif name == 'foreign-scope': copies[0]['scope']='foreign'
    elif name == 'lost-force':
        events=[row for row in events if row.get('event') != 'SOURCE_RETIREMENT_FORCED' and row.get('point') != 'SOURCE_RETIREMENT_FORCED']
        # Renumber retained metadata in the event sequence and keep the removed
        # force's objects only if another captured state still refers to them.
        for index,row in enumerate((v for v in events if v.get('event') == EVENT),1):
            old=root/row['capture']; dest=root/DIRECTORY/f'capture-{index:04d}.json'
            if old != dest: old.rename(dest); row['capture']=dest.relative_to(root).as_posix()
    elif name in ('missing-object','altered-object','extra-object'):
        if name == 'extra-object':
            raw=b'unobserved';(root/DIRECTORY/'objects'/sha(raw)).write_bytes(raw)
        else:
            metadata=json.loads((root/copies[0]['capture']).read_bytes())
            digest=next(row['identity']['sha256'] for row in metadata['files'] if row['name']=='root.gsr')
            path=root/DIRECTORY/'objects'/digest
            if name == 'missing-object':path.unlink()
            else:path.write_bytes(b'altered')
    else:
        point = 'SOURCE_RETIREMENT_FILE_DELETED' if name=='wrong-deletion' else 'SOURCE_RETIREMENT_BEFORE_RETURN' if name=='extra-preserved-file' else 'SOURCE_RETIREMENT_WRITTEN'
        event=next(v for v in copies if v['point']==point);path=root/event['capture'];metadata=json.loads(path.read_bytes())
        files={row['name']:row['identity'] for row in metadata['files']};objects=root/DIRECTORY/'objects'
        def value(n):return (objects/files[n]['sha256']).read_bytes()
        def store(n,raw):
            (objects/sha(raw)).write_bytes(raw);files[n]=dict(size=len(raw),sha256=sha(raw))
        if name in ('wrong-floor','wrong-source-file'):
            raw=value(release.AUTHORITY);size=48+int.from_bytes(raw[12:16],'big');record=f.decode(raw[:size],'records','RETIREMENT')
            if name=='wrong-floor':record['floor']='0'*64
            else:record['files'][0]['sha256']='0'*64
            store(release.AUTHORITY,f.encode('records','RETIREMENT',record)+raw[size:])
        elif name=='premature-journal-pruning':
            _,_,compact,_=release.plan(root,dict(size=3,through=0));store('grants.gsr',compact)
        elif name=='wrong-deletion':
            initial=json.loads((root/copies[0]['capture']).read_bytes());old={row['name']:row['identity'] for row in initial['files']}
            removed=next(n for n in old if n.startswith('sources/') and n not in files)
            files[removed]=old[removed]
        else:store('unexpected.bin',b'not derived')
        metadata['files']=[dict(name=n,identity=files[n]) for n in sorted(files)]
        raw=f.canonical(metadata);path.write_bytes(raw);event['sha256']=sha(raw)
    (root/'events.json').write_bytes(f.canonical(events))


def qualify_component(root):
    root=Path(root); original=component(root);results=[]
    for name,reason in NEGATIVES.items():
        with tempfile.TemporaryDirectory(prefix='v53-retirement-capture-negative-') as tmp:
            target=Path(tmp)/'raw';shutil.copytree(root,target);mutate(target,name)
            try:component(target)
            except ValueError as error:need(str(error)==reason,'unrelated retirement capture negative: '+name+': '+str(error))
            else:raise ValueError('retirement capture mutation accepted: '+name)
        results.append(dict(case=name,status='REJECTED',reason=reason))
    return dict(original=original,negatives=results)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('--component',action='store_true');parser.add_argument('--qualify',action='store_true');args=parser.parse_args()
    print(json.dumps(qualify_component(args.root) if args.qualify else component(args.root) if args.component else validate(args.root),sort_keys=True))
