"""Independent frozen-source selection observer over original compacted byte fixtures.

No production selector import. Force observations describe one fixture producer,
not a root-wide grant/install chronology or distributed runtime acceptance.
"""
from pathlib import Path
import uuid
from . import capsule_evidence as caps
from . import context_evidence as c
from . import source_packet as p
from . import format_fixture as f
from .membership_model import need

CASES = ('heterogeneous', 'highest-tail', 'covered-tail', 'joint')


def decide(rows):
    """Only called after source identities, prefix compatibility and ownership checks."""
    longest = max(rows, key=lambda r: r['basis']['cut']['index'])
    end = longest['basis']['cut']['index']; remaining = [r for r in rows if r['accept'] and r['accept']['index'] > end]
    need(all(r['accept']['index'] == end+1 for r in remaining), 'tail skips next slot')
    carried = None
    if remaining:
        def order(r):
            b = r['accept']['ballot']; return b['counter'], b['proposer'], b['incarnation']
        highest = max(map(order, remaining)); eligible = [r for r in remaining if order(r) == highest]
        need(len({r['accept']['entry'] for r in eligible}) == 1, 'equal ballot conflicting tails')
        carried = eligible[0]['accept']['entry']
    return longest, carried


def validate_case(root, profile, case, original, baseline):
    root = Path(root); paths = list(root.rglob('*'))
    need(len(paths) <= 256 and all(not x.is_symlink() and (x.is_file() or x.is_dir()) for x in paths), 'selection file types/count')
    files = {}; expected = {'manifest.json', 'selected.bin'}
    def raw(name, maximum):
        if name not in files: files[name] = caps.file_bytes(root/name, maximum)
        need(len(files[name]) <= maximum, 'selection file capacity'); return files[name]
    manifest = c.parse(raw('manifest.json', 128*1024))
    c.exact(manifest, 'schema profile case runtimeEnabled authorityEvidence forces')
    need(manifest['schema'] == 'gse-v53-selection-fixture-v1' and manifest['profile'] == profile and manifest['case'] == case
         and manifest['runtimeEnabled'] is False and manifest['authorityEvidence'] is False, 'selection fixture scope')
    final = original['states'][6 if case == 'joint' else 9]; view = final['cut']['view']
    voters = sorted(set(view['old']+view['new'])); root_hash = final['root']; histories = original['history']['steps']
    selected = f.decode(raw('selected.bin', 65536), 'records', 'SELECTED', root_hash)
    forces = {}
    for i, event in enumerate(manifest['forces'], 1):
        c.exact(event, 'sequence path sha256')
        need(type(event['sequence']) is int and event['sequence'] == i and event['path'] not in forces, 'selection force sequence')
        forces[event['path']] = (i, event['sha256'])
    used_forces = set()
    def forced(name, maximum):
        # Names here are constructed locally from validated voters, never taken from manifest paths.
        expected.add(name); data = raw(name, maximum)
        need(name in forces and forces[name][1] == c.sha(data), 'missing/changed source force')
        used_forces.add(name); return data
    rows = []
    for i, voter in enumerate(voters):
        through = 6 if case == 'joint' else min(7+i,9) if case == 'heterogeneous' else 8 if case == 'covered-tail' and i == 0 else 9
        state = original['states'][through]; prefix = 'sources/'+voter+'/'
        expected.add(prefix+'packet.bin'); packet = p.decode(raw(prefix+'packet.bin', 32*c.MIB)); basis_bytes = forced(prefix+'basis.bin',16384)
        p.bind(packet, basis_bytes); basis = f.decode(basis_bytes, 'records', 'BASIS', root_hash)
        need(basis['voter'] == voter and basis['cut'] == state['cut'] and basis['ballot'] == selected['ballot'], 'source identity/cut/ballot')
        old = baseline[through]; capsule = packet['capsule']; objects = packet['objects']
        need({k:v for k,v in capsule.items() if k != 'inventory'} == {k:v for k,v in old['capsule'].items() if k != 'inventory'}
             and all(objects.get(h) == data for h,data in old['objects'].items()), 'changed original compacted authority')
        identity = next(r for r in state['identities'] if r['node'] == voter)
        catalog_hash = histories[through-1]['catalogAfter'] if through else histories[0]['catalogBefore']
        parent = c.parse(forced(prefix+'parent.json', 16384))
        need(parent == dict(root=root_hash,voter=voter,storage=identity['storage'],cut=state['cut'],catalog=catalog_hash,application=state['application']), 'wrong owned source parent')
        need(forces[prefix+'parent.json'][0] < forces[prefix+'basis.bin'][0], 'basis before owned parent')
        need(basis['basisId'] == str(uuid.UUID(int=(through << 64) + int(voter[5:]))), 'original frozen basis UUID')
        expected_data = 'tail-'+str(i) if case == 'highest-tail' and i < 2 else 'minority' if case == 'covered-tail' and i == 0 else None
        need((basis['accepted'] is None) == (expected_data is None), 'omitted/introduced frozen tail')
        extras = set(); accept = None
        if basis['accepted'] is not None:
            accept_bytes = forced(prefix+'accepted.bin', 16384)
            need(c.sha(accept_bytes) == basis['accepted'] and objects.get(basis['accepted']) == accept_bytes, 'unowned accepted tail')
            accept = f.decode(accept_bytes, 'records', 'ACCEPT', root_hash); entry = f.decode(objects[accept['entry']], 'records', 'ENTRY', root_hash)
            extras.update((basis['accepted'], accept['entry'], entry['payload']))
            need(entry['kind'] == 'DATA' and objects[entry['payload']] == expected_data.encode('ascii')
                 and accept['ballot']['counter'] == (8 if i == 1 else 2) and entry['origin']['counter'] == 1, 'original accepted fixture bytes')
            need(forces[prefix+'parent.json'][0] < forces[prefix+'accepted.bin'][0] < forces[prefix+'basis.bin'][0], 'frozen basis before tail force')
            for ballot in (basis['ballot'], accept['ballot'], entry['origin']):
                who = next((r for r in state['identities'] if r['node'] == ballot['proposer']),None)
                need(who is not None and who['storage'] == ballot['incarnation'] and who['node'] in voters, 'tail ballot identity')
        need(set(objects) == set(old['objects']) | extras, 'source metadata inventory')
        need(packet['images'] == old['images'], 'source separate images')
        for h,size in packet['images'].items():
            path = prefix+'images/'+h+'.bin'; expected.add(path); data = raw(path,64*c.MIB)
            need(len(data) == size and c.sha(data) == h, 'source image bytes')
        rows.append(dict(basis=basis,raw=basis_bytes,packet=packet,accept=accept,through=through))
    refs = [dict(voter=r['basis']['voter'],basisId=r['basis']['basisId'],basisDigest=c.sha(r['raw'])) for r in rows]
    need(selected['sources'] == refs and selected['ballot']['proposer'] in voters, 'original proposer-inclusive selected references')
    proposer = next(r for r in final['identities'] if r['node'] == selected['ballot']['proposer'])
    need(proposer['storage'] == selected['ballot']['incarnation'] and selected['ballot']['counter'] == 20, 'campaign identity')
    c.majority(view,voters); authority=c.sha(f.canonical(dict(root=root_hash,**view)))
    need(selected['view'] == authority and all(r['basis']['view'] == authority for r in rows), 'mixed source era')
    longest, carried = decide(rows); longest_packet = longest['packet']; anchors = {}
    for item in longest_packet['capsule']['items']:
        statement = f.decode(longest_packet['objects'][item['statement']],'records','CHECKPOINT',root_hash)
        anchors[statement['end']['index']] = (statement['end'],statement['catalogAfter'],statement['applicationAfter'])
    missing = []
    for row in rows:
        cap = row['packet']['capsule']; wanted=(cap['cut'],cap['catalog'],cap['application'])
        if anchors.get(cap['cut']['index']) != wanted: missing.append(wanted)
    if missing:
        need(len(missing) == 1 and case in ('heterogeneous','covered-tail'), 'unexpected missing ancestry fixture')
        path='bridge/statement.bin'; expected.add(path); statement_bytes=raw(path,16384); statement=f.decode(statement_bytes,'records','CHECKPOINT',root_hash)
        lower=missing[0]; upper=anchors.get(statement['end']['index'])
        need((statement['start'],statement['catalogBefore'],statement['applicationBefore']) == lower and upper is not None
             and (statement['end'],statement['catalogAfter'],statement['applicationAfter']) == upper
             and statement['scope'] == 'RANGE' and statement['start']['view'] == statement['end']['view'] == view
             and view['operation'] is None and statement['start']['index'] < statement['end']['index'], 'ancestry exact frozen endpoints')
        total=len(statement_bytes)
        for voter in voters:
            identity=next(r for r in final['identities'] if r['node']==voter); name='bridge/'+voter
            data=forced(name+'.bin',2048); total+=len(data); ack=f.decode(data,'records','CHECKPOINT_ACK',root_hash)
            applied=c.parse(forced(name+'.applied',16384))
            need(ack == dict(root=root_hash,voter=voter,incarnation=identity['storage'],cut=statement['end'],statement=c.sha(statement_bytes)), 'ancestry endorsement binding')
            need(applied == dict(root=root_hash,voter=voter,storage=identity['storage'],cut=statement['end'],catalog=statement['catalogAfter'],application=statement['applicationAfter'])
                 and forces[name+'.applied'][0] < forces[name+'.bin'][0], 'ancestry before applied end')
        need(total<=16384,'ancestry complete byte capacity')
    need(selected['cut'] == longest['basis']['cut'] and selected['nextEntry'] == carried, 'longest prefix/highest accepted selection')
    need(used_forces == set(forces), 'unused source force observation')
    need({x.relative_to(root).as_posix() for x in paths if x.is_file()} == expected, 'selection physical inventory')
    return dict(profile=profile,case=case,sources=len(rows),bridges=len(missing),carried=carried is not None)


def validate(root):
    root=Path(root); caps.validate(root/'baseline'); original=caps.source(root/'baseline/source'); results=[]
    need({x.name for x in (root/'selections').iterdir()} == set(c.PROFILES),'selection profiles')
    for profile in c.PROFILES:
        directory=root/'selections'/profile;need({x.name for x in directory.iterdir()} == set(CASES),'selection cases')
        baseline={i:p.decode(caps.file_bytes(root/'baseline/capsules'/profile/('cut-'+str(i))/'packet.bin',32*c.MIB)) for i in range(10)}
        results.extend(validate_case(directory/case,profile,case,original[profile],baseline) for case in CASES)
    return dict(status='PASS',execution='single-jvm-frozen-selection-fixtures',runtimeEnabled=False,authorityEvidence=False,
                cases=results,selections=len(results),sources=sum(r['sources'] for r in results))
