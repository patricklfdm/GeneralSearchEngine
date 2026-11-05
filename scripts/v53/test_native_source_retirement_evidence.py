import copy
import unittest
from unittest.mock import patch
from . import native_source_retirement_evidence as r
from .test_source_packet import fixture, frame


class NativeSourceRetirementEvidenceTest(unittest.TestCase):
    def fixture(self):
        capsule, index, objects = fixture()
        original = r.e.p.decode(frame(capsule, r.f.canonical(index), objects))
        cap = original['capsule']; catalog = r.f.catalog()
        def sample(kind): return r.f.sample(catalog['records'][kind]['schema'], catalog['types'])
        rows = []
        for counter in (2, 3):
            promise = sample('PROMISE')
            promise.update(root=cap['root'], view=r.e.authority(cap['root'], cap['cut']['view']),
                           basisId='00000000-0000-0000-0000-'+str(counter).zfill(12))
            promise['ballot']['counter'] = counter
            basis = dict(sample('BASIS'), **promise, cut=cap['cut'], capsule=r.e.digest(capsule),
                         inventory=r.e.digest(original['indexBytes']))
            selected = dict(sample('SELECTED'), root=cap['root'], view=promise['view'],
                            cut=cap['cut'], ballot=promise['ballot'])
            for kind, value in (('PROMISE', promise), ('BASIS', basis), ('SELECTED', selected)):
                rows.append((kind, r.f.encode('records', kind, value), value))
        entry = dict(root=cap['root'], authority=rows[-1][2]['view'], index=1,
                     previous=cap['cut']['entry'], origin=rows[0][2]['ballot'], kind='BARRIER', payload=r.e.digest(b''))
        entry_raw = r.f.encode('records', 'ENTRY', entry)
        chosen = dict(rows[-1][2], nextEntry=r.e.digest(entry_raw))
        packet = dict(original, objects=dict(objects, **{r.e.digest(entry_raw):entry_raw}))
        manifest = dict(sample('GENERATION'), promise=r.e.digest(rows[3][1]), basis=r.e.digest(rows[4][1]))
        source = 'sources/'+rows[0][2]['basisId']
        files = {'grants.gsr':b''.join(row[1] for row in rows), source:None,
                 source+'/source.gscp':frame(capsule, r.f.canonical(index), objects),
                 source+'/'+cap['application']+'.image':b'independent image',
                 'current/generation.gsr':r.f.encode('records', 'GENERATION', manifest),
                 'pending.accept':b'transferred vote checked by enclosing history reader'}
        return files, rows, packet, chosen

    def project(self, files, rows, packet, chosen):
        current = ('current/', {'selected.gsr':r.f.encode('records', 'SELECTED', chosen)}, packet)
        # The enclosing history reader owns installation/vote validation. This
        # component still decodes and binds the real original source packet.
        with patch.object(r.c, 'current', return_value=current), patch.object(r.c, 'journal', return_value=rows):
            return r.retire_predecessor({'node-1':files}, ('node-1',))

    def test_exact_empty_predecessor_retires_without_removing_carried_vote(self):
        files, rows, packet, chosen = self.fixture(); before = copy.deepcopy(files)
        result, events = self.project(files, rows, packet, chosen)
        self.assertEqual(before, files)
        self.assertEqual(files['pending.accept'], result['node-1']['pending.accept'])
        self.assertFalse(any(k.startswith('sources/') for k in result['node-1']))
        self.assertEqual(b''.join(row[1] for row in rows[3:]), result['node-1']['grants.gsr'])
        self.assertLess(events['node-1'].index('SOURCE_RETIREMENT_PARENT_FORCED'),
                        events['node-1'].index('JOURNAL_ROTATION_CREATED'))

    def test_changed_same_cut_application_or_catalog_is_not_ancestry(self):
        for field in ('application', 'catalog'):
            files, rows, packet, chosen = self.fixture()
            packet = copy.deepcopy(packet); packet['capsule'][field] = 'ab'*32
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'same-cut original ancestry'):
                self.project(files, rows, packet, chosen)

    def test_missing_carried_entry_or_wrong_ballot_cannot_authorize_retirement(self):
        for change in ('missing', 'ballot'):
            files, rows, packet, chosen = self.fixture(); chosen = copy.deepcopy(chosen)
            if change == 'missing': chosen['nextEntry'] = None
            else: chosen['ballot']['counter'] += 1
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'carried selection'):
                self.project(files, rows, packet, chosen)

    def test_changed_payload_and_nonempty_predecessor_refuse(self):
        files, rows, packet, chosen = self.fixture(); packet['objects'][r.e.digest(b'')] = b'changed'
        with self.assertRaisesRegex(ValueError, 'retained carried bytes'):
            self.project(files, rows, packet, chosen)
        files, rows, packet, chosen = self.fixture(); rows[1][2]['accepted'] = 'ab'*32
        with self.assertRaisesRegex(ValueError, 'covered empty predecessor'):
            self.project(files, rows, packet, chosen)


if __name__ == '__main__': unittest.main()
