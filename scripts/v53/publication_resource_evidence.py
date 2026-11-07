"""Independently derive observed publication storage from complete native histories.

Writer observations never supply expected bytes or authority. The original
physical/network reader runs first; intermediate inventories then follow its
derived pre/post states. Completion reservations remain maximum-sized until the
specified handoff/reload/cleanup boundary. CONTROL/WAITER are bounded observations,
not independently derived network charges in this reader.
"""
import argparse
import json
from pathlib import Path
import re

from . import bootstrap_replay_contract as source_policy
from . import joining_grant_captures as grants
from . import native_dispatch_evidence as native
from . import joining_history_run as history

f, need, sha, disk = grants.f, grants.need, grants.sha, grants.disk
MIB = grants.MIB
DIRECTORY = 'publication-resource-captures'
POINTS = ('PUBLICATION_VALIDATED', 'INSTALL_RESERVED', 'INSTALL_PARENT_FORCED',
          'CURRENT_VALIDATED', 'CURRENT_FILES_FORCED', 'CURRENT_GENERATION_FORCED',
          'CURRENT_SELECTOR_FORCED', 'CURRENT_DIRECTORY_FORCED', 'PUBLICATION_SELECTOR_FORCED',
          'PUBLICATION_RETIRED', 'PUBLICATION_BEFORE_RETURN')
COUNTS = dict(GENERATION=2, SOURCE=6, LEARNER=1, JOURNAL=1, CATALOG=1, MISC=1,
              APPLICATION=7, CONTROL=256, WAITER=64)


def events(root):
    return history.read_json(root,'events.json',history.EVENT_BYTES)


def usage(value):
    need(type(value) is dict and set(value) == {'metadata','staging','queued','leases','counts'} and
         all(type(value[k]) is int and value[k] >= 0 for k in ('metadata','staging','queued','leases')) and
         type(value['counts']) is dict, 'publication resources usage shape')
    counts = value['counts']
    need(all(k in COUNTS and type(v) is int and 0 < v <= COUNTS[k] for k,v in counts.items()) and
         value['leases'] == sum(counts.values()) and value['metadata'] <= 384*MIB and
         value['staging'] <= 7*64*MIB+7*32*MIB and value['queued'] <= 64*MIB,
         'publication resources observed limits')
    storage = {k:v for k,v in counts.items() if k not in ('CONTROL','WAITER')}
    return dict(metadata=value['metadata'], staging=value['staging'], counts=storage, leases=sum(storage.values()))


def collect(root, events):
    need(type(events) is list and 0 < len(events) <= 65536 and all(type(v) is dict for v in events),
         'publication resources event collection')
    root = Path(root)/DIRECTORY
    need(root.is_dir() and not root.is_symlink(), 'publication resources collection missing')
    objects = root/'objects'
    need(objects.is_dir() and not objects.is_symlink(), 'publication resources object directory')
    payloads = {}; used = set(); total = 0
    for path in objects.iterdir():
        need(re.fullmatch('[0-9a-f]{64}', path.name) is not None and len(payloads) < 8192,
             'publication resources object name/count')
        raw = grants.snapshot.s.regular(path,64*MIB); total += len(raw)
        need(total <= grants.MAXIMUM_BYTES and sha(raw) == path.name, 'publication resources object identity/capacity')
        payloads[path.name] = raw
    _, index = grants.json_file(root/'index.json')
    need(type(index) is dict and set(index) == {'schema','complete','captures'} and
         index['schema'] == 'gse-v53-publication-resource-index-v1' and index['complete'] is True and
         type(index['captures']) is list and 0 < len(index['captures']) <= 1024,
         'publication resources complete index')
    observed = {}; names = []
    for ordinal, ref in enumerate(index['captures']):
        name = f'capture-{ordinal:04d}.json'; names.append(name)
        need(type(ref) is dict and set(ref) == {'path','sha256'} and ref['path'] == name,
             'publication resources ordered index')
        raw, row = grants.json_file(root/name)
        need(sha(raw) == ref['sha256'], 'publication resources capture digest')
        need(type(row) is dict and set(row) == {'schema','node','scope','point','eventIndex','usageBefore','usageAfter','files'} and
             row['schema'] == 'gse-v53-publication-resource-capture-v1' and
             type(row['eventIndex']) is int and 0 <= row['eventIndex'] < len(events) and
             row['eventIndex'] not in observed and type(row['node']) is str and type(row['scope']) is str,
             'publication resources metadata binding')
        event = events[row['eventIndex']]
        need(row['point'] in POINTS and event == dict(node=row['node'],event=row['point'],
             **({'scope':row['scope']} if row['scope'] else {})), 'publication resources exact event')
        before, after = usage(row['usageBefore']), usage(row['usageAfter'])
        need(before == after, 'publication resources storage changed during observation')
        entries = row['files']; files = {}; previous = None
        need(type(entries) is list and 0 < len(entries) <= grants.MAXIMUM_FILES, 'publication resources file count')
        for entry in entries:
            need(type(entry) is dict and set(entry) == {'name','identity'}, 'publication resources file shape')
            name = entry['name']; grants.snapshot.relative(name)
            need(previous is None or previous < name, 'publication resources ordered unique member'); previous = name
            identity = entry['identity']; need(type(identity) is dict, 'publication resources member identity')
            if identity == {'directory':True}:
                need(type(identity['directory']) is bool, 'publication resources directory type'); files[name] = None
            else:
                need(set(identity) == {'size','sha256'} and type(identity['size']) is int and identity['size'] >= 0 and
                     type(identity['sha256']) is str and identity['sha256'] in payloads,
                     'publication resources missing object/size')
                digest = identity['sha256']; data = payloads[digest]
                need(len(data) == identity['size'], 'publication resources file size'); used.add(digest); files[name] = data
            parent = str(Path(name).parent)
            need(parent == '.' or parent in files and files[parent] is None, 'publication resources parent directory')
        observed[row['eventIndex']] = dict(row, files=files, storage=before)
    need({p.name for p in root.iterdir()} == {'objects','index.json',*names}, 'publication resources unobserved metadata')
    need(used == payloads.keys(), 'publication resources unobserved object')
    transactions = []; active = {}; seen = set()
    for at, event in enumerate(events):
        node, point, scope = event.get('node'), event.get('event'), event.get('scope','')
        key = node, scope
        if point == POINTS[0]:
            need(key not in active, 'publication resources overlapping transaction')
            active[key] = []
        if key not in active or point not in POINTS: continue
        rows = active[key]
        need(len(rows) < len(POINTS) and point == POINTS[len(rows)] and at in observed,
             'publication resources complete boundary order')
        rows.append(observed[at]); seen.add(at)
        if point == POINTS[-1]: transactions.append(active.pop(key))
    need(transactions and not active and seen == observed.keys(), 'publication resources incomplete transaction')
    return transactions


def baseline(files):
    """Exact extents in independently derived owner files, plus fixed journal/root owners."""
    metadata, staging = 34*MIB, 0
    counts = dict(JOURNAL=1,MISC=1)
    for directory, unit in (('generations','GENERATION'),('sources','SOURCE'),('floor-copies','SOURCE')):
        groups = [n for n,v in files.items() if v is None and n.startswith(directory+'/') and n.count('/') == 1]
        for group in groups:
            members = {n:v for n,v in files.items() if n.startswith(group+'/') and v is not None}
            images = {n:v for n,v in members.items() if n.endswith('.image')}
            size = sum(len(v) for n,v in members.items() if n not in images)
            need(0 < size <= 32*MIB and images and all(0 < len(v) <= 64*MIB for v in images.values()),
                 'publication resources derived owner extent')
            counts[unit] = counts.get(unit,0)+1
            counts['APPLICATION'] = counts.get('APPLICATION',0)+len(images)
            metadata += size; staging += sum(map(len,images.values()))+(size if unit == 'SOURCE' else 0)
    return dict(metadata=metadata,staging=staging,counts=counts,leases=sum(counts.values()))


def membership_edge(files):
    """Only an independently admitted exact certificate can omit replay output."""
    frames,_=native.c.pending(files['pending.accept'],('PROOF','CERTIFICATE'))
    entry=f.decode(frames['ENTRY'],'records','ENTRY')
    cert=f.decode(frames['CERTIFICATE'],'records','CERTIFICATE')
    need(cert['entry']==sha(frames['ENTRY']) and frames['CERTIFICATE']==files['applied-end/certificate.gsr'],
         'publication resources completion original certificate')
    return entry['kind'] in ('INTENT','FINAL')


def output_reserved(before,after,observed):
    # Preserve historical conservative two-slot evidence. The reduced form
    # additionally requires exact original membership bytes, never a label.
    full=next(derived(before,after))[2]
    if observed==full:return True
    reduced=dict(full,staging=full['staging']-64*MIB,leases=full['leases']-1,
                 counts=dict(full['counts'],APPLICATION=full['counts']['APPLICATION']-1))
    need(observed==reduced,'publication resources exact charges: '+POINTS[0])
    try:edge=membership_edge(before)
    except ValueError as error:raise ValueError('publication resources exact charges: '+POINTS[0]) from error
    need(edge,'publication resources exact charges: '+POINTS[0])
    need(observed==next(derived(before,after,output=False))[2],'publication resources exact charges: '+POINTS[0])
    return False


def derived(before, after, *, output=True):
    """Eleven observed boundaries of one new publication; no installed/idempotent shortcut."""
    selector = f.decode(after['selector.gsr'],'records','SELECTOR')
    slot = 'generations/'+selector['generation']
    need(slot not in before and slot in after, 'publication resources fresh inactive slot')
    generation = {n:v for n,v in after.items() if n == slot or n.startswith(slot+'/')}
    image = [v for n,v in generation.items() if n.endswith('.image')]
    need(len(image) == 1, 'publication resources single published image')
    installed = dict(before, **generation, **{'selector.gsr':after['selector.gsr']})
    retired = {n:v for n,v in installed.items() if n != 'applied-end' and not n.startswith('applied-end/')}
    retired['pending.accept'] = disk.EMPTY
    need(type(output) is bool and (output or membership_edge(before)), 'publication resources output demand')
    for at, point in enumerate(POINTS):
        files = before if at <= 1 else installed if at <= 8 else retired if at == 9 else after
        charged = baseline(before if at == 0 else installed)
        maximum = (3+int(output)) if at == 0 else (2+int(output)) if at <= 8 else 0
        if 1 <= at <= 7: charged['staging'] += 64*MIB-len(image[0])
        charged['staging'] += maximum*64*MIB
        charged['counts']['APPLICATION'] += maximum
        charged['leases'] += maximum
        yield point,files,charged


def compare(transactions, plans):
    need(len(transactions) == len(plans), 'publication resources exact transaction count')
    pending = dict(plans); maxima = dict(metadata=0,staging=0,applications=0,sources=0)
    for rows in transactions:
        need(len(rows) == len(POINTS), 'publication resources exact boundary count')
        first = rows[0]; files = first['files']
        need(type(files.get('applied-end/certificate.gsr')) is bytes, 'publication resources original certificate')
        cert = f.decode(files['applied-end/certificate.gsr'],'records','CERTIFICATE')
        key = first['node'],cert['index']
        need(key in pending, 'publication resources unique derived publication')
        before,after = pending.pop(key)
        output=output_reserved(before,after,rows[0]['storage'])
        for row,(point,expected,charges) in zip(rows,derived(before,after,output=output)):
            need(row['point'] == point and row['files'] == expected, 'publication resources exact inventory: '+point)
            need(row['storage'] == charges, 'publication resources exact charges: '+point)
            maxima['metadata'] = max(maxima['metadata'],charges['metadata'])
            maxima['staging'] = max(maxima['staging'],charges['staging'])
            for name,unit in (('applications','APPLICATION'),('sources','SOURCE')):
                maxima[name] = max(maxima[name],charges['counts'].get(unit,0))
    need(not pending, 'publication resources missing derived publication')
    return dict(publications=len(transactions),observedBoundaries=sum(map(len,transactions)),maximumObservedStorage=maxima)


def original(root, profile, progress=None, *, resource_transitions=False, control_closes=False, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    need(bootstrap_source==source_policy.EMPTY or profile=='5-REPLACE-required-four', 'publication resources bootstrap source profile')
    plans = {}
    if profile == 'stable':
        receipt = native.validate(root,confirmed_retention=True,publication_resources=True,resource_transitions=resource_transitions,control_closes=control_closes)
        _,rounds,_,_ = native.physical(root,confirmed_retention=True)
        for row in rounds:
            for node in native.VOTERS: plans[node,row['index']] = row['recorded'][node],row['published'][node]
    elif profile in ('5-REPLACE','5-REPLACE-required-four'):
        def observer(node,index,before,after):
            need((node,index) not in plans, 'publication resources duplicate derivation')
            plans[node,index] = before,after
        if profile == '5-REPLACE':
            from . import joint_ledger_evidence as joint
            receipt = joint.validate(root,progress,publication_observer=observer)
        else:
            from . import required_four_physical as required_four
            receipt = required_four.validate(root,publication_observer=observer,**source_args)
            need(len(plans)==34,'publication resources required-four complete publications')
    else: raise ValueError('publication resources unknown profile')
    return receipt,plans


def validate(directory, profile='stable', progress=None, *, resource_transitions=False, control_closes=False, bootstrap_source='EMPTY', wire_layout='JSON'):
    source_args = source_policy.options(bootstrap_source,wire_layout)
    need(bootstrap_source==source_policy.EMPTY or profile=='5-REPLACE-required-four', 'publication resources bootstrap source profile')
    root = Path(directory); before = source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout)
    receipt,plans = original(root,profile,progress,resource_transitions=resource_transitions,control_closes=control_closes,**source_args)
    transactions = collect(root,events(root))
    result = compare(transactions,plans)
    need(source_policy.inventory(root, bootstrap_source=bootstrap_source, wire_layout=wire_layout) == before, 'publication resources original changed')
    return source_policy.receipt(dict(status='PASS',scope='native-publication-storage-boundaries',profile=profile,precondition=receipt,**result,
                publicationStorageDerived=True,controlChargesDerived=False,wholeRuntimePeakQualified=False,
                processDeathQualified=False,phase3Complete=False),bootstrap_source,wire_layout)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); parser.add_argument('--profile',choices=('stable','5-REPLACE','5-REPLACE-required-four'),default='stable')
    parser.add_argument('--qualify',action='store_true')
    args = parser.parse_args()
    if args.qualify:
        from .publication_resource_negatives import qualify
        run = qualify
    else: run = validate
    print(json.dumps(run(args.root,args.profile,lambda v: print(json.dumps(v),flush=True)),sort_keys=True))
