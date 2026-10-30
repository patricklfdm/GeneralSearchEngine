"""Conditional byte/plan checks; physical authority requires original replay."""
import base64
import copy
import tempfile
import unittest
from pathlib import Path
from . import peer_confirmation_evidence as e


def fixture():
    identity = lambda n: dict(node=f'node-{n}', storage=f'00000000-0000-0000-0000-{n:012d}', host='127.0.0.1', port=9000+n)
    view = dict(generation=0, old=[f'node-{n}' for n in (1, 2, 3)], new=[f'node-{n}' for n in (1, 2, 3)], operation=None)
    point = lambda n: dict(cut=dict(index=n, entry='b'*64, view=view), catalog='c'*64, application='d'*64)
    generation = e.f.encode('records', 'GENERATION', dict(root='a'*64, node='node-3', generation='a', **point(2),
        capsule='e'*64, promise='f'*64, basis=None, selection=None, ownedTail=None,
        files=[dict(path='source.gscp', size=1, sha256='e'*64)]))
    plan = dict(root='a'*64, view=view, peers=[dict(identity=identity(n), possible=[point(0)]) for n in (1, 2, 3)])
    plan['peers'][2] = dict(identity=identity(3), possible=[point(2)], renewals=[point(0), point(1)], confirmation=base64.b64encode(generation).decode())
    return dict(root='a'*64, owner=identity(2), revision=1, previous='b'*64, plan=plan), generation


class PeerConfirmationEvidenceTest(unittest.TestCase):
    def test_binding_roundtrip_and_only_original_copy_discharge(self):
        value, generation = fixture(); raw = e.r.frame(value)
        self.assertEqual(value, e.r.decode(raw))
        with self.assertRaisesRegex(ValueError, 'original provenance replay'): e.e.merged(raw, [raw])
        result = e.r.decode(e._confirmed_merge(raw, [raw], generation))
        self.assertEqual([2], [a['cut']['index'] for a in result['plan']['peers'][2]['possible']])
        self.assertNotIn('renewals', result['plan']['peers'][2])
        self.assertEqual(2, result['revision'])

    def test_binding_and_renewal_mutations_are_rejected(self):
        for field in ('root', 'node', 'catalog', 'base64', 'unknown', 'empty', 'duplicate', 'future', 'capacity'):
            value, generation = fixture(); row = value['plan']['peers'][2]
            if field in ('root', 'node', 'catalog'):
                record = e.f.decode(generation, 'records', 'GENERATION'); record[field] = 'node-2' if field == 'node' else 'f'*64
                row['confirmation'] = base64.b64encode(e.f.encode('records', 'GENERATION', record)).decode()
            elif field == 'base64': row['confirmation'] += '\n'
            elif field == 'unknown': row['trusted'] = True
            elif field == 'empty': row['renewals'] = []
            elif field == 'future': row['renewals'] = row['possible']
            else: row['renewals'] = [row['renewals'][0]] * (3 if field == 'capacity' else 2)
            with self.subTest(field=field), self.assertRaises(ValueError): e.r.decode(e.r.frame(value))

    def test_same_index_conflict_is_checked_before_discharge(self):
        value, generation = fixture(); bad = copy.deepcopy(value); bad['plan']['peers'][2]['renewals'][1]['catalog'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'conflicting original endpoint'):
            e._confirmed_merge(e.r.frame(value), [e.r.frame(bad)], generation)

    def test_later_unconfirmed_point_survives_and_wrong_original_refuses(self):
        value, generation = fixture(); point = copy.deepcopy(value['plan']['peers'][2]['possible'][0]); point['cut']['index'] = 3
        value['plan']['peers'][2]['possible'].append(point); raw = e.r.frame(value)
        result = e.r.decode(e._confirmed_merge(raw, [raw], generation))
        self.assertEqual([2, 3], [a['cut']['index'] for a in result['plan']['peers'][2]['possible']])
        changed = e.f.decode(generation, 'records', 'GENERATION'); changed['generation'] = 'b'
        with self.assertRaisesRegex(ValueError, 'exact observed generation'):
            e._confirmed_merge(raw, [raw], e.f.encode('records', 'GENERATION', changed))

    def test_six_peer_manifests_fit_normal_bounds_but_oversize_refuses(self):
        value, generation = fixture(); p = value['plan']; old = [f'node-{n}' for n in range(1, 6)]; new = [*old[:-1], 'node-6']
        p['view'] = dict(generation=256, old=old, new=new, operation='e'*64)
        p['peers'] = []
        for n in range(1, 7):
            row = copy.deepcopy(value['owner']); row['node'] = f'node-{n}'; row['storage'] = f'00000000-0000-0000-0000-{n:012d}'
            record = e.f.decode(generation, 'records', 'GENERATION'); record['node'] = row['node']; record['cut']['view'] = p['view']
            point = {k: record[k] for k in ('cut', 'catalog', 'application')}
            p['peers'].append(dict(identity=row, possible=[point], confirmation=base64.b64encode(e.f.encode('records', 'GENERATION', record)).decode()))
        self.assertEqual(p, e.plan(p))
        for row in p['peers']:
            record = e.f.decode(base64.b64decode(row['confirmation']), 'records', 'GENERATION')
            record['files'] = [dict(path='file'+str(i)+'x'*200, size=2**63-2, sha256='f'*64) for i in range(32)]
            row['confirmation'] = base64.b64encode(e.f.encode('records', 'GENERATION', record)).decode()
        with self.assertRaisesRegex(ValueError, 'plan capacity'): e.plan(p)

    def test_invalid_original_cannot_count_as_negative_acceptance(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises((ValueError, FileNotFoundError)): e.qualify(Path(temp))


if __name__ == '__main__': unittest.main()
