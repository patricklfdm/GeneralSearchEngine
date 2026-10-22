"""Independent GSCP transport inventory reader. Capsule authority is a later gate."""
import struct
from pathlib import Path

from . import format_fixture as f
from .context_evidence import parse, sha, exact, MIB
from .membership_model import need


def rows(value, limit, maximum, minimum):
    need(type(value) is list and 0 < len(value) <= limit, 'packet index count')
    previous = None; result = {}
    for row in value:
        exact(row, 'sha256 bytes'); h = row['sha256']; f.check_type(h, 'hash', {})
        need(type(row['bytes']) is int and minimum <= row['bytes'] <= maximum, 'packet member size')
        need(previous is None or previous < h, 'duplicate/unordered packet member')
        previous = h; result[h] = row['bytes']
    return result


def decode(data):
    need(type(data) is bytes and 56 <= len(data) <= 32*MIB, 'packet size')
    magic, major, minor, kind, flags, length = struct.unpack('>4sHHHHI', data[:16])
    need((magic, major, minor, kind, flags) == (b'GSCP', 1, 3, 0, 0) and length == len(data)-48, 'packet header')
    need(bytes.fromhex(sha(data[:16]+data[48:])) == data[16:48], 'packet checksum')
    position = 48
    def part(maximum):
        nonlocal position
        need(len(data)-position >= 4, 'packet truncated length')
        size = int.from_bytes(data[position:position+4], 'big'); position += 4
        need(0 < size <= maximum and size <= len(data)-position, 'packet part length')
        raw = data[position:position+size]; position += size; return raw
    capsule_bytes = part(MIB-56); capsule = f.decode(capsule_bytes, 'records', 'CAPSULE')
    index_bytes = part(MIB-56-len(capsule_bytes)); index = parse(index_bytes)
    exact(index, 'schema objects images'); need(index['schema'] == 'gse-membership-source-index/1.3', 'packet index schema')
    sizes = rows(index['objects'], 65536, 8*MIB, 0); images = rows(index['images'], 7, 64*MIB, 1)
    need(sum(sizes.values()) == len(data)-position, 'packet trailing/missing bytes')
    objects = {}
    for h, size in sizes.items():
        raw = data[position:position+size]; position += size
        need(sha(raw) == h, 'packet member hash'); objects[h] = raw
    need(capsule['inventory'] == sha(index_bytes), 'capsule index binding')
    need(capsule['initial'] in objects and capsule['catalog'] in objects and capsule['application'] in images, 'missing capsule root objects')
    f.decode(objects[capsule['initial']], 'records', 'GENESIS')
    catalog = f.decode(objects[capsule['catalog']], 'records', 'CATALOG', capsule['root'])
    need(catalog['cut'] == capsule['cut'] and catalog['application'] == capsule['application'], 'capsule terminal catalog')
    return dict(capsule=capsule, capsuleBytes=capsule_bytes, indexBytes=index_bytes, objects=objects, images=images)


def bind(packet, basis_bytes):
    basis = f.decode(basis_bytes, 'records', 'BASIS'); capsule = packet['capsule']
    need(basis['root'] == capsule['root'] and basis['cut'] == capsule['cut']
         and basis['capsule'] == sha(packet['capsuleBytes']) and basis['inventory'] == sha(packet['indexBytes'])
         and basis['view'] == sha(f.canonical(dict(root=basis['root'], **basis['cut']['view']))), 'packet original basis binding')
    need(basis['accepted'] is None or basis['accepted'] in packet['objects'], 'missing frozen accepted body')
    if basis['accepted'] is not None:
        objects = packet['objects']; accept = f.decode(objects[basis['accepted']], 'records', 'ACCEPT', basis['root'])
        need(accept['entry'] in objects, 'missing frozen entry')
        entry = f.decode(objects[accept['entry']], 'records', 'ENTRY', basis['root'])
        need(basis['cut']['index'] < 2**63-2 and accept['index'] == entry['index'] == basis['cut']['index']+1
             and entry['previous'] == basis['cut']['entry'] and accept['authority'] == entry['authority'] == basis['view'], 'frozen tail parent/root/view')
        def ballot(b): return b['counter'], b['proposer'], b['incarnation']
        need(ballot(entry['origin']) <= ballot(accept['ballot']) <= ballot(basis['ballot']), 'frozen tail ballot order')
        need(entry['payload'] in objects, 'missing frozen payload')
        payload = objects[entry['payload']]
        if entry['kind'] == 'BARRIER': need(payload == b'', 'frozen barrier payload')
        elif entry['kind'] != 'DATA': f.check_type(parse(payload), {'object': f.catalog()['commands'][entry['kind']]}, f.catalog()['types'])


def validate(root):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'packet evidence directory')
    paths = list(root.rglob('*'))
    need(not any(p.is_symlink() for p in paths) and all(p.is_file() or p.is_dir() for p in paths), 'linked/nonregular packet evidence')
    need((root/'packet.bin').stat().st_size <= 32*MIB and (root/'basis.bin').stat().st_size <= 16384, 'packet evidence capacity')
    packet = decode((root/'packet.bin').read_bytes()); bind(packet, (root/'basis.bin').read_bytes())
    expected = {'packet.bin', 'basis.bin'} | {'images/'+h+'.bin' for h in packet['images']}
    need({p.relative_to(root).as_posix() for p in paths if p.is_file()} == expected, 'packet evidence inventory')
    for h, size in packet['images'].items():
        image = root/'images'/(h+'.bin')
        need(image.stat().st_size == size, 'application materialization length')
        need(sha(image.read_bytes()) == h, 'application materialization hash')
    return dict(status='PASS', packetBytes=(root/'packet.bin').stat().st_size, objects=len(packet['objects']), images=len(packet['images']),
                originalBasisBinding=True, runtimeEnabled=False, capsuleAuthorityVerified=False)
