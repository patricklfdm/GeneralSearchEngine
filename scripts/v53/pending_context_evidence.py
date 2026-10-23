"""Independent original-byte replay of the pure detached pending-context codec.

GSPC reconstructs an old packet and vote from one exact local frozen source.
This checks byte provenance, framing and retained metadata; it creates no force
observations and makes no image-semantic, retirement or runtime-readiness claim.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import tempfile

from . import format_fixture as f
from . import source_packet as p
from .applied_end_evidence import digest
from .context_evidence import parse, exact, identities, majority, authority
from .generation_install_evidence import packet_bytes
from .membership_model import need
from .pending_accept_evidence import container
from .round_storage_evidence import current, votes
from .selected_sources_evidence import cuts

MIB = 1024 * 1024
HEADER = 48
META_LIMITS = {'generation.gsr': 65536, 'promise.gsr': 8192, 'basis.gsr': 16384,
               'selected.gsr': 65536, 'owned-tail.gsr': 8192, 'ancestry.gsr': 96*1024,
               'selected-sources.gsr': 6*16384, 'selected-coverage.json': 4096,
               'adopted-certificate.gsr': 16384}
METADATA_MAXIMUM = sum(META_LIMITS.values())
MAXIMUM = HEADER+5*4+4+8192+4096+8192+16384+MIB+METADATA_MAXIMUM+len(META_LIMITS)*40
VOTE_MAXIMUM = 12+4+4096+8192+65536+16384+8192+8*MIB+2*16384
BINDING_FIELDS = 'schema root node storage backingPacket vote entry accept payload proof certificate'
TOP_LIMITS = {'context.gspc': MAXIMUM, 'old-selector.gsr': 4096, 'pending.accept': VOTE_MAXIMUM,
              'root.gsr': 65536, 'backing-promise.gsr': 8192, 'backing-basis.gsr': 16384,
              'backing-source.gscp': 32*MIB, 'receipt.json': 16384}


def info(raw):
    return dict(bytes=len(raw), sha256=digest(raw))


def framed(magic, body):
    prefix = struct.pack('>4sHHHHI', magic, 1, 3, 0, 0, len(body))
    return prefix+bytes.fromhex(digest(prefix+body))+body


def part(data, position, maximum):
    need(len(data)-position >= 4, 'context truncated segment length')
    size = int.from_bytes(data[position:position+4], 'big'); position += 4
    need(0 < size <= maximum and size <= len(data)-position, 'context segment length')
    return data[position:position+size], position+size


def decode(raw):
    need(type(raw) is bytes and HEADER <= len(raw) <= MAXIMUM, 'context complete capacity')
    need(struct.unpack('>4sHHHHI', raw[:16]) == (b'GSPC', 1, 3, 0, 0, len(raw)-HEADER), 'context header')
    need(raw[16:HEADER] == bytes.fromhex(digest(raw[:16]+raw[HEADER:])), 'context checksum')
    position = HEADER; segments = []
    for limit in (8192, 4096, 8192, 16384, MIB-HEADER):
        value, position = part(raw, position, limit); segments.append(value)
    need(len(raw)-position >= 4, 'context member count missing')
    count = int.from_bytes(raw[position:position+4], 'big'); position += 4
    need(0 < count <= len(META_LIMITS), 'context member count')
    metadata = {}; previous = ''
    for _ in range(count):
        name, position = part(raw, position, 32)
        try: name = name.decode('ascii')
        except UnicodeError as error: raise ValueError('context member ASCII name') from error
        need(name in META_LIMITS and previous < name, 'context member name/order'); previous = name
        metadata[name], position = part(raw, position, META_LIMITS[name])
    need(position == len(raw), 'context trailing bytes')
    need(sum(map(len, metadata.values())) <= METADATA_MAXIMUM, 'context metadata capacity')
    binding = parse(segments[0]); exact(binding, BINDING_FIELDS)
    need(binding['schema'] == 'gse-v53-pending-context/1.3', 'context binding schema')
    for name in ('root', 'entry', 'accept', 'payload'): f.check_type(binding[name], 'hash', {})
    for name in ('proof', 'certificate'):
        if binding[name] is not None: f.check_type(binding[name], 'hash', {})
    need(binding['certificate'] is None or binding['proof'] is not None, 'context certificate without proof')
    f.check_type(binding['node'], 'node', {}); f.check_type(binding['storage'], 'uuid', {})
    for name, low, high in (('backingPacket', 56, 32*MIB), ('vote', 12, VOTE_MAXIMUM)):
        exact(binding[name], 'bytes sha256'); value = binding[name]
        need(type(value['bytes']) is int and low <= value['bytes'] <= high, 'context bound identity size')
        f.check_type(value['sha256'], 'hash', {})
    return segments, metadata, binding


def encode(segments, metadata):
    body = b''.join(struct.pack('>I', len(v))+v for v in segments)+struct.pack('>I', len(metadata))
    for name, value in sorted(metadata.items()):
        label = name.encode('ascii'); body += struct.pack('>I', len(label))+label+struct.pack('>I', len(value))+value
    return framed(b'GSPC', body)


def reconstruct(envelope, backing):
    need(8 <= len(envelope) <= MIB-HEADER, 'context envelope capacity')
    capsule_raw, position = part(envelope, 0, MIB-56)
    capsule = f.decode(capsule_raw, 'records', 'CAPSULE')
    index_raw, position = part(envelope, position, MIB-56-len(capsule_raw))
    need(position == len(envelope), 'context envelope trailing bytes')
    index = parse(index_raw); exact(index, 'schema objects images')
    need(index['schema'] == 'gse-membership-source-index/1.3', 'context envelope index schema')
    sizes = p.rows(index['objects'], 65536, 8*MIB, 0); images = p.rows(index['images'], 7, 64*MIB, 1)
    need(sum(sizes.values())+HEADER+len(envelope) <= 32*MIB, 'context rebuilt packet capacity')
    need(capsule['inventory'] == digest(index_raw), 'context old capsule/index binding')
    objects = {}
    for key, size in sizes.items():
        need(key in backing['objects'], 'context missing borrowed object')
        raw = backing['objects'][key]
        need(len(raw) == size and digest(raw) == key, 'context borrowed object hash/size'); objects[key] = raw
    need(all(backing['images'].get(key) == size for key, size in images.items()), 'context borrowed image identity')
    raw = framed(b'GSCP', envelope+b''.join(objects.values()))
    packet = p.decode(raw)
    need(packet['capsuleBytes'] == capsule_raw and packet['indexBytes'] == index_raw, 'context reconstructed exact envelope')
    return raw, packet


def physical(root):
    root = Path(root); need(root.is_dir() and not root.is_symlink(), 'context evidence directory')
    paths = list(root.rglob('*'))
    need(len(paths) <= 64 and all(not path.is_symlink() and (path.is_dir() or path.is_file()) for path in paths), 'context physical inventory type/count')
    need({path.name for path in root.iterdir()} == set(TOP_LIMITS) | {'original-generation', 'backing-images'}, 'context root inventory')
    need({path.relative_to(root).as_posix() for path in paths if path.is_dir()} == {'original-generation', 'backing-images'}, 'context directory inventory')
    files = {}; total = 0
    for path in paths:
        if path.is_dir(): continue
        name = path.relative_to(root).as_posix()
        if '/' not in name: limit = TOP_LIMITS[name]
        elif name.startswith('original-generation/'):
            leaf = path.name; need(leaf in META_LIMITS or leaf == 'source.gscp', 'context unexpected original member')
            limit = 32*MIB if leaf == 'source.gscp' else META_LIMITS[leaf]
        else:
            need(re.fullmatch(r'backing-images/[0-9a-f]{64}\.image', name) is not None, 'context image path')
            limit = 64*MIB
        length = path.stat().st_size; need(0 < length <= limit, 'context physical member capacity')
        total += length; need(total <= 512*MIB, 'context total evidence capacity')
        files[name] = path.read_bytes(); need(len(files[name]) == length, 'context changing physical member')
    return files


def certificate_links(packet, cert_raw, parent, registry):
    """Check encoded receipt links, without treating their names/hashes as force observations."""
    cert = f.decode(cert_raw, 'records', 'CERTIFICATE', packet['capsule']['root'])
    objects = packet['objects']; entry_raw = objects[cert['entry']]; entry = f.decode(entry_raw, 'records', 'ENTRY', cert['root'])
    accept = {key: value for key, value in cert.items() if key not in ('accepts', 'proofs')}
    proof = {key: value for key, value in cert.items() if key != 'proofs'}
    raw_accept = f.encode('records', 'ACCEPT', accept); raw_proof = f.encode('records', 'PROOF', proof)
    need(objects.get(digest(raw_accept)) == raw_accept and objects.get(digest(raw_proof)) == raw_proof, 'context certificate original phase objects')
    need(accept['index'] == entry['index'] == parent['index']+1 and entry['previous'] == parent['entry']
         and accept['authority'] == entry['authority'] == authority(cert['root'], parent['view'])
         and digest(objects[entry['payload']]) == entry['payload'], 'context certificate parent/ENTRY/payload')
    for label, phase, raw in (('accepts', 'ACCEPT', raw_accept), ('proofs', 'PROOF', raw_proof)):
        names = [row['voter'] for row in cert[label]]; majority(parent['view'], names)
        expected = [dict(voter=node, incarnation=registry[node]['storage'], receipt=digest(f.canonical(dict(root=cert['root'], voter=node,
                    incarnation=registry[node]['storage'], phase=phase, record=digest(raw))))) for node in names]
        need(cert[label] == expected, 'context encoded witness identity/receipt')
    return entry, cert


def original_generation(files, selector_raw, packet, root_record, registry):
    selector = f.decode(selector_raw, 'records', 'SELECTOR'); cap = packet['capsule']
    members = {name.removeprefix('original-generation/'): raw for name, raw in files.items() if name.startswith('original-generation/')}
    members.update({key+'.image': files['backing-images/'+key+'.image'] for key in packet['images']})
    prefix = 'generations/'+selector['generation']+'/'
    _, admitted, verified = current({'selector.gsr': selector_raw, **{prefix+key: raw for key, raw in members.items()}})
    need(verified == packet, 'context original materialization packet')
    manifest = f.decode(members['generation.gsr'], 'records', 'GENERATION')
    promise = f.decode(members['promise.gsr'], 'records', 'PROMISE'); basis = f.decode(members['basis.gsr'], 'records', 'BASIS')
    selected = f.decode(members['selected.gsr'], 'records', 'SELECTED')
    need(set(admitted) == {'source.gscp', 'promise.gsr', 'basis.gsr', 'selected.gsr', 'selected-sources.gsr', 'selected-coverage.json'}
         | {key+'.image' for key in packet['images']}, 'context fixture exact original selected inventory')
    need(manifest['promise'] == digest(members['promise.gsr']) and manifest['basis'] == digest(members['basis.gsr'])
         and manifest['selection'] == digest(members['selected.gsr']) and manifest['ownedTail'] is None, 'context original materialization grant digests')
    need(all(promise[key] == basis[key] == selected[key] for key in ('root', 'view', 'ballot')) and promise['basisId'] == basis['basisId']
         and basis['voter'] == selector['node'], 'context original promise/basis/selection')
    need(selected['ballot']['counter'] == 20 and selected['cut']['index'] == 0 and cap['cut']['index'] == 1 and selected['nextEntry'] is None,
         'context fixture continued-round boundary')
    need(cuts(members['selected-sources.gsr'], selected) == [selected['cut']]*3, 'context original selected-source parents')
    need(next(row for row in selected['sources'] if row['voter'] == selector['node']) == dict(voter=selector['node'], basisId=basis['basisId'],
         basisDigest=digest(members['basis.gsr'])), 'context selected exact local basis')
    need(selected['view'] == authority(selected['root'], selected['cut']['view']) == authority(cap['root'], cap['cut']['view']), 'context original stable governing view')
    for ballot in (promise['ballot'], selected['ballot']):
        need(registry[ballot['proposer']]['storage'] == ballot['incarnation'], 'context original ballot incarnation')
    coverage = parse(members['selected-coverage.json']); exact(coverage, 'schema selection parent certificate')
    need(coverage['schema'] == 'gse-v53-selected-coverage/1.3' and coverage['selection'] == digest(members['selected.gsr'])
         and coverage['parent']['cut'] == selected['cut'], 'context exact original selected coverage')
    objects = packet['objects']; genesis = f.decode(objects[root_record['genesis']], 'records', 'GENESIS')
    need(cap['initial'] == root_record['genesis'] and all(root_record[key] == genesis[key] for key in ('groupId', 'historyId', 'baseSequence', 'schema', 'indexes'))
         and genesis['source'] == 'EMPTY' and genesis['sourceDigest'] is None, 'context exact original ROOT/genesis binding')
    initial = dict(root=cap['root'], active=None, application=genesis['application'], applicationSequence=genesis['baseSequence'], cut=selected['cut'],
                   identities=root_record['initial'], lastDataIndex=0, nextOperation=1, results=[], retiredThrough=0)
    need(coverage['parent'] == dict(cut=selected['cut'], catalog=digest(f.encode('records', 'CATALOG', initial)), application=genesis['application']),
         'context exact genesis coverage parent')
    entry, cert = certificate_links(packet, objects[coverage['certificate']], selected['cut'], registry)
    need(cert['ballot'] == selected['ballot'] == entry['origin'] and cert['entry'] == cap['cut']['entry'] and entry['kind'] == 'DATA', 'context retained first certificate')
    catalog = f.decode(objects[cap['catalog']], 'records', 'CATALOG')
    need(catalog == dict(initial, cut=cap['cut'], application=cap['application'], applicationSequence=42, lastDataIndex=1), 'context fixture first-slot catalog')
    need(len(cap['items']) == 1, 'context exact original range count'); item = cap['items'][0]
    need(item['kind'] == 'RANGE' and item['certificate'] is None and item['descriptor'] is None, 'context original range item')
    statement = dict(root=cap['root'], scope='RANGE', start=selected['cut'], end=cap['cut'], catalogBefore=coverage['parent']['catalog'],
                     applicationBefore=coverage['parent']['application'], catalogAfter=cap['catalog'], applicationAfter=cap['application'])
    need(objects[item['statement']] == f.encode('records', 'CHECKPOINT', statement), 'context exact original range statement')
    acknowledgements = [f.decode(objects[key], 'records', 'CHECKPOINT_ACK') for key in item['endorsements']]
    names = [row['voter'] for row in acknowledgements]; majority(cap['cut']['view'], names)
    need(acknowledgements == [dict(root=cap['root'], voter=node, incarnation=registry[node]['storage'], cut=cap['cut'], statement=item['statement']) for node in names],
         'context encoded range endorsements')
    return members, selected


def validate(root):
    files = physical(root); segments, metadata, binding = decode(files['context.gspc'])
    need(encode(segments, metadata) == files['context.gspc'], 'context exact canonical re-encoding')
    root_record = f.decode(files['root.gsr'], 'records', 'ROOT'); root_hash = files['root.gsr'][16:48].hex()
    registry = identities(root_record['initial'])
    need(root_record['limits'] == digest(f.canonical(f.catalog()['resources'])) and binding['root'] == root_hash
         and binding['node'] == 'node-1' and registry[binding['node']]['storage'] == binding['storage'], 'context root/owner identity')
    selector_raw, promise_raw, basis_raw, envelope = segments[1:]
    need(selector_raw == files['old-selector.gsr'] and promise_raw == files['backing-promise.gsr'] and basis_raw == files['backing-basis.gsr'],
         'context exact supplied selector/backing grant')
    backing_raw = files['backing-source.gscp']; backing = p.decode(backing_raw); p.bind(backing, basis_raw)
    need(info(backing_raw) == binding['backingPacket'], 'context exact backing packet identity')
    need(backing['objects'].get(digest(files['root.gsr'])) == files['root.gsr'] and backing['capsule']['root'] == root_hash,
         'context exact backing ROOT bytes')
    need({name.removeprefix('backing-images/') for name in files if name.startswith('backing-images/')} == {key+'.image' for key in backing['images']},
         'context exact backing image inventory')
    for key, length in backing['images'].items():
        raw = files['backing-images/'+key+'.image']; need(info(raw) == dict(bytes=length, sha256=key), 'context backing image bytes')
    old_raw, old = reconstruct(envelope, backing)
    need(old_raw == files['original-generation/source.gscp'], 'context rebuilt original packet bytes')
    need(old['objects'].get(digest(files['root.gsr'])) == files['root.gsr'], 'context original packet ROOT bytes')
    members, selected = original_generation(files, selector_raw, old, root_record, registry)
    need(metadata == {name: raw for name, raw in members.items() if name != 'source.gscp' and not name.endswith('.image')},
         'context exact original metadata inventory/bytes')
    need(all(backing['capsule'][key] == old['capsule'][key] for key in ('root', 'cut', 'catalog', 'application', 'initial', 'items')),
         'context old/backing exact parent anchor')
    promise = f.decode(promise_raw, 'records', 'PROMISE'); basis = f.decode(basis_raw, 'records', 'BASIS')
    need(all(promise[key] == basis[key] for key in ('root', 'view', 'ballot', 'basisId')) and basis['voter'] == binding['node']
         and promise['ballot']['counter'] == 21 and promise['ballot']['proposer'] == 'node-3'
         and registry['node-3']['storage'] == promise['ballot']['incarnation'], 'context higher local source ballot/grant')
    frames, values = votes(files['pending.accept'], old['capsule']['cut'])
    need(info(files['pending.accept']) == binding['vote'] and frames['SELECTOR'] == selector_raw and frames['PROMISE'] == members['promise.gsr']
         and frames['SELECTED'] == members['selected.gsr'], 'context old original pending identity')
    for field, kind in (('entry', 'ENTRY'), ('accept', 'ACCEPT'), ('payload', 'PAYLOAD'), ('proof', 'PROOF'), ('certificate', 'CERTIFICATE')):
        need(binding[field] == digest(frames[kind]) and backing['objects'].get(binding[field]) == frames[kind], 'context exact borrowed original '+field)
    first = container([selector_raw, members['promise.gsr'], members['selected.gsr'], backing['objects'][binding['entry']], backing['objects'][binding['accept']]],
                      backing['objects'][binding['payload']])
    body = first[12:]+backing['objects'][binding['proof']]+backing['objects'][binding['certificate']]
    reconstructed_vote = struct.pack('>4sHHI', b'GSPV', 1, 3, len(body)+12)+body
    need(reconstructed_vote == files['pending.accept'], 'context reconstructed original vote bytes')
    need(basis['accepted'] == binding['accept'] and values['ENTRY']['kind'] == 'DATA' and values['ENTRY']['origin']['counter'] == 20
         and selected['ballot'] == values['ACCEPT']['ballot'], 'context old entry/accept not relabelled')
    certificate_links(backing, frames['CERTIFICATE'], old['capsule']['cut'], registry)
    need(frames['PAYLOAD'] not in files['context.gspc'] and all(files['backing-images/'+key+'.image'] not in files['context.gspc'] for key in backing['images']),
         'context no embedded payload/application image')
    receipt = parse(files['receipt.json'])
    expected = dict(schema='gse-v53-pending-context-codec-v1', status='PASS', execution='pure-context-codec-reconstruction', contextForced=False,
                    retirementAuthorized=False, freshProcesses=False, runtimeEnabled=False, imageSemanticClaim=False, historicalBootstrap='conditional-fixture',
                    contextSha256=digest(files['context.gspc']), contextBytes=len(files['context.gspc']), entry=binding['entry'], oldVoteSha256=digest(reconstructed_vote),
                    backingPacketSha256=digest(backing_raw), origin=20, backingBallot=21)
    need(receipt == expected and all(type(receipt[key]) is type(value) for key, value in expected.items()), 'context receipt exact scope/physical bindings')
    return dict(status='PASS', execution='pure-context-codec-reconstruction', originalFirst=True, contextBytes=len(files['context.gspc']), maximumContextBytes=MAXIMUM,
                originalMetadataMembers=len(metadata), borrowedObjects=len(old['objects']), borrowedImages=len(old['images']), originalVotePhase='CERTIFICATE',
                selectedCut=0, originalParentCut=1, pendingIndex=2, origin=20, backingBallot=21, physicalBytes=True, contextForced=False,
                retirementAuthorized=False, remoteOwnershipVerified=False, imageSemanticClaim=False, freshProcesses=False, runtimeEnabled=False,
                maximumPayloadIndependentlyReplayed=False, historicalBootstrap='conditional-fixture')


def qualify(root):
    root = Path(root); result = validate(root); negatives = []
    variants = ('context-checksum', 'context-truncated', 'context-version', 'context-flags', 'context-oversize', 'segment-overflow', 'trailing-context',
                'missing-metadata', 'changed-metadata', 'context-entry-binding', 'context-vote-identity', 'envelope-inventory', 'backing-missing-certificate',
                'changed-original-source', 'changed-original-vote', 'missing-backing-image', 'changed-backing-image', 'changed-backing-promise',
                'changed-root', 'extra-member', 'linked-member', 'false-retirement-authority')
    for variant in variants:
        with tempfile.TemporaryDirectory(prefix='v53-pending-context-negative-') as temporary:
            case = Path(temporary)/'evidence'; shutil.copytree(root, case)
            path = case/'context.gspc'; raw = path.read_bytes(); segments, metadata, binding = decode(raw)
            if variant == 'context-checksum': path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            elif variant == 'context-truncated': path.write_bytes(raw[:HEADER+5])
            elif variant in ('context-version', 'context-flags'):
                changed = bytearray(raw); changed[7 if variant == 'context-version' else 11] ^= 1
                changed[16:48] = bytes.fromhex(digest(changed[:16]+changed[48:])); path.write_bytes(changed)
            elif variant == 'context-oversize': path.write_bytes(raw+b'X'*(MAXIMUM+1-len(raw)))
            elif variant == 'segment-overflow': path.write_bytes(framed(b'GSPC', b'\xff\xff\xff\xff'+raw[52:]))
            elif variant == 'trailing-context': path.write_bytes(framed(b'GSPC', raw[48:]+b'X'))
            elif variant == 'missing-metadata':
                metadata.pop('selected-coverage.json'); path.write_bytes(encode(segments, metadata))
            elif variant == 'changed-metadata':
                metadata['selected-coverage.json'] = b'{}'; path.write_bytes(encode(segments, metadata))
            elif variant in ('context-entry-binding', 'context-vote-identity'):
                if variant == 'context-entry-binding': binding['entry'] = '0'*64
                else: binding['vote']['bytes'] += 1
                segments[0] = f.canonical(binding); path.write_bytes(encode(segments, metadata))
            elif variant == 'envelope-inventory':
                envelope = segments[4]; cap, at = part(envelope, 0, MIB); index, _ = part(envelope, at, MIB)
                value = parse(index); value['objects'][0]['bytes'] += 1; index = f.canonical(value)
                segments[4] = struct.pack('>I', len(cap))+cap+struct.pack('>I', len(index))+index; path.write_bytes(encode(segments, metadata))
            elif variant == 'backing-missing-certificate':
                packet = p.decode((case/'backing-source.gscp').read_bytes()); objects = dict(packet['objects']); objects.pop(binding['certificate'])
                changed = packet_bytes(packet['capsule'], objects, packet['images']); (case/'backing-source.gscp').write_bytes(changed)
                binding['backingPacket'] = info(changed); segments[0] = f.canonical(binding)
                cap = p.decode(changed); basis_path = case/'backing-basis.gsr'; basis = f.decode(basis_path.read_bytes(), 'records', 'BASIS')
                basis.update(capsule=digest(cap['capsuleBytes']), inventory=digest(cap['indexBytes']))
                segments[3] = f.encode('records', 'BASIS', basis); basis_path.write_bytes(segments[3]); path.write_bytes(encode(segments, metadata))
            elif variant == 'changed-original-source':
                file = case/'original-generation/source.gscp'; value = file.read_bytes(); file.write_bytes(value[:-1]+bytes([value[-1]^1]))
            elif variant == 'changed-original-vote':
                file = case/'pending.accept'; value = file.read_bytes(); file.write_bytes(value[:-1]+bytes([value[-1]^1]))
            elif variant in ('missing-backing-image', 'changed-backing-image'):
                file = next((case/'backing-images').iterdir())
                if variant == 'missing-backing-image': file.unlink()
                else:
                    value = file.read_bytes(); file.write_bytes(bytes([value[0]^1])+value[1:])
            elif variant == 'changed-backing-promise': (case/'backing-promise.gsr').write_bytes((case/'original-generation/promise.gsr').read_bytes())
            elif variant == 'changed-root':
                file = case/'root.gsr'; value = f.decode(file.read_bytes(), 'records', 'ROOT'); value['historyId'] = '33333333-2222-3333-4444-555555555555'
                file.write_bytes(f.encode('records', 'ROOT', value))
            elif variant == 'extra-member': (case/'original-generation/unlisted.gsr').write_bytes(b'X')
            elif variant == 'linked-member':
                file = case/'backing-source.gscp'; file.unlink(); file.symlink_to((root/'backing-source.gscp').resolve())
            else:
                file = case/'receipt.json'; value = parse(file.read_bytes()); value['retirementAuthorized'] = True; file.write_bytes(f.canonical(value))
            try: validate(case)
            except (ValueError, OSError, KeyError, TypeError): negatives.append(variant)
            else: raise ValueError('accepted pending context mutation: '+variant)
    with tempfile.TemporaryDirectory(prefix='v53-pending-context-portable-') as temporary:
        case = Path(temporary)/'evidence'; shutil.copytree(root, case)
        need(validate(case) == result, 'context portable replay')
    return dict(result, negatives=negatives, portableReplay='PASS')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('root'); args = parser.parse_args()
    print(json.dumps(qualify(args.root), sort_keys=True))
