import copy
import struct
import unittest

from . import source_packet as p
from . import format_fixture as f
from .context_evidence import parse, sha


def frame(capsule, index, objects):
    body = len(capsule).to_bytes(4, 'big')+capsule+len(index).to_bytes(4, 'big')+index+b''.join(objects[k] for k in sorted(objects))
    prefix = struct.pack('>4sHHHHI', b'GSCP', 1, 3, 0, 0, len(body))
    return prefix+bytes.fromhex(sha(prefix+body))+body


def fixture():
    c = f.catalog(); image = b'independent image'; app = sha(image)
    def sample(kind): return f.sample(c['records'][kind]['schema'], c['types'])
    genesis = sample('GENESIS'); genesis['application'] = app
    genesis_bytes = f.encode('records', 'GENESIS', genesis)
    catalog = sample('CATALOG'); catalog.update(application=app)
    catalog['cut']['entry'] = sha(genesis_bytes)
    catalog_bytes = f.encode('records', 'CATALOG', catalog)
    objects = {sha(genesis_bytes): genesis_bytes, sha(catalog_bytes): catalog_bytes, sha(b''): b''}
    index = dict(schema='gse-membership-source-index/1.3', objects=[dict(sha256=k, bytes=len(v)) for k,v in sorted(objects.items())],
                 images=[dict(sha256=app, bytes=len(image))])
    capsule = sample('CAPSULE'); capsule.update(application=app, catalog=sha(catalog_bytes), cut=catalog['cut'],
                                               initial=sha(genesis_bytes), inventory=sha(f.canonical(index)), items=[])
    return f.encode('records', 'CAPSULE', capsule), index, objects


class SourcePacketTest(unittest.TestCase):
    def test_complete_index_is_deterministic_and_images_are_separate(self):
        capsule, index, objects = fixture(); raw = frame(capsule, f.canonical(index), objects); packet = p.decode(raw)
        self.assertEqual(objects, packet['objects']); self.assertEqual(f.canonical(index), packet['indexBytes'])
        self.assertEqual(frame(packet['capsuleBytes'], packet['indexBytes'], packet['objects']), raw)

    def test_oversized_or_malformed_header_and_inner_lengths_fail(self):
        capsule, index, objects = fixture(); original = frame(capsule, f.canonical(index), objects)
        for position in (0, 4, 6, 8, 10, 12, 48, 52+len(capsule)):
            bad = bytearray(original); bad[position] ^= 128; bad[16:48] = bytes.fromhex(sha(bad[:16]+bad[48:]))
            with self.assertRaises(ValueError, msg=str(position)): p.decode(bytes(bad))
        with self.assertRaises(ValueError): p.decode(original[:-1])
        with self.assertRaises(ValueError): p.decode(original+b'X')

    def test_duplicate_unordered_unknown_and_invalid_index_entries_reject(self):
        capsule, index, objects = fixture()
        for case in ('duplicate', 'order', 'negative', 'overflow', 'unknown', 'boolean', 'digest-type'):
            bad = copy.deepcopy(index)
            if case == 'duplicate': bad['objects'].append(bad['objects'][0])
            elif case == 'order': bad['objects'].reverse()
            elif case == 'negative': bad['objects'][0]['bytes'] = -1
            elif case == 'overflow': bad['objects'][0]['bytes'] = 2**63
            elif case == 'unknown': bad['paths'] = ['../outside']
            elif case == 'boolean': bad['objects'][0]['bytes'] = True
            else: bad['objects'][0]['sha256'] = 1
            with self.assertRaises(ValueError, msg=case): p.decode(frame(capsule, f.canonical(bad), objects))

    def test_member_bytes_and_total_are_checked_even_with_valid_outer_checksum(self):
        capsule, index, objects = fixture()
        for body in (b'bad', b'', b'0'*64):
            bad = dict(objects); bad[next(iter(objects))] = body
            with self.assertRaises(ValueError): p.decode(frame(capsule, f.canonical(index), bad))

    def test_original_basis_binding_is_distinct_from_capsule_authority(self):
        capsule, index, objects = fixture(); packet = p.decode(frame(capsule, f.canonical(index), objects)); c = f.catalog()
        basis = f.sample(c['records']['BASIS']['schema'], c['types'])
        basis.update(root=packet['capsule']['root'], cut=packet['capsule']['cut'], capsule=sha(capsule), inventory=sha(f.canonical(index)))
        basis['view'] = sha(f.canonical(dict(root=basis['root'], **basis['cut']['view'])))
        p.bind(packet, f.encode('records', 'BASIS', basis))
        for field in ('root', 'capsule', 'inventory', 'accepted', 'cut'):
            bad = copy.deepcopy(basis)
            if field == 'cut': bad['cut']['index'] += 1
            else: bad[field] = 'ff'*32
            with self.assertRaises(ValueError): p.bind(packet, f.encode('records', 'BASIS', bad))

    def test_complete_owned_tail_must_match_parent_ballots_and_payload(self):
        capsule, index, originals = fixture(); c = f.catalog(); cap = f.decode(capsule, 'records', 'CAPSULE')
        ballot = f.sample('ballot', c['types']); view = sha(f.canonical(dict(root=cap['root'], **cap['cut']['view'])))
        def make(change=None):
            objects = dict(originals); entry = dict(root=cap['root'], authority=view, origin=copy.deepcopy(ballot), kind='BARRIER',
                index=cap['cut']['index']+1, previous=cap['cut']['entry'], payload=sha(b''))
            if change == 'parent': entry['previous'] = 'ff'*32
            if change == 'origin': entry['origin']['counter'] += 1
            if change == 'payload': objects[sha(b'x')] = b'x'; entry['payload'] = sha(b'x')
            if change == 'missing': del objects[sha(b'')]
            raw = f.encode('records', 'ENTRY', entry); objects[sha(raw)] = raw
            accept = dict(root=cap['root'], authority=view, ballot=copy.deepcopy(ballot), entry=sha(raw), index=entry['index'])
            if change == 'accept': accept['ballot']['counter'] += 1
            raw = f.encode('records', 'ACCEPT', accept); accepted = sha(raw); objects[accepted] = raw
            inventory = copy.deepcopy(index); inventory['objects'] = [dict(sha256=h, bytes=len(b)) for h,b in sorted(objects.items())]
            value = dict(cap, inventory=sha(f.canonical(inventory))); raw = f.encode('records', 'CAPSULE', value)
            packet = p.decode(frame(raw, f.canonical(inventory), objects))
            basis = f.sample(c['records']['BASIS']['schema'], c['types']); basis.update(root=cap['root'], cut=cap['cut'],
                view=view, ballot=ballot, accepted=accepted, capsule=sha(raw), inventory=value['inventory'])
            return packet, f.encode('records', 'BASIS', basis)
        p.bind(*make())
        for change in ('parent', 'origin', 'payload', 'missing', 'accept'):
            with self.assertRaises(ValueError, msg=change): p.bind(*make(change))


if __name__ == '__main__': unittest.main()
