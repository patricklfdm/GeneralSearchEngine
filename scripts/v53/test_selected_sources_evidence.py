import copy
import json
import tempfile
from pathlib import Path
import unittest
from . import selected_sources_evidence as e


def fixture():
    c = e.f.catalog()
    def sample(kind): return e.f.sample(c['records'][kind]['schema'], c['types'])
    selected = sample('SELECTED'); selected['view'] = e.authority(selected['root'], selected['cut']['view'])
    frames = []
    for i, ref in enumerate(selected['sources']):
        basis = sample('BASIS')
        basis.update({k: selected[k] for k in ('root', 'view', 'ballot')})
        basis.update(voter=ref['voter'], basisId=ref['basisId'], cut=dict(selected['cut'], index=i))
        frames.append(e.f.encode('records', 'BASIS', basis)); ref['basisDigest'] = e.digest(frames[-1])
    selected['cut']['index'] = 1; raw = b''.join(frames)
    generation = sample('GENERATION'); sr = e.f.encode('records', 'SELECTED', selected)
    generation.update(selection=e.digest(sr), files=[dict(path=e.FILE, size=len(raw), sha256=e.digest(raw))])
    gr = e.f.encode('records', 'GENERATION', generation); selector = sample('SELECTOR'); selector['digest'] = e.digest(gr)
    original = {'selector.gsr': e.f.encode('records', 'SELECTOR', selector), 'generations/a/generation.gsr': gr,
                'generations/a/selected.gsr': sr, 'generations/a/'+e.FILE: raw}
    return original, selected, frames


class SelectedSourcesEvidenceTest(unittest.TestCase):
    def test_only_explicit_boolean_enables_new_receipt_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'case.json'
            for value, expected in (({}, False), ({'selectedSourceFrames': False}, False), ({'selectedSourceFrames': True}, True)):
                path.write_text(json.dumps(value)); self.assertEqual(expected, e.recorded_mode(tmp))
            for value in (1, 'true', None):
                path.write_text(json.dumps(dict(selectedSourceFrames=value)))
                with self.assertRaises(ValueError): e.recorded_mode(tmp)

    def test_original_set_preserves_distinct_source_cuts(self):
        original, selected, frames = fixture()
        self.assertEqual([0, 1], [c['index'] for c in e.cuts(b''.join(frames), selected)])
        self.assertEqual({e.FILE: b''.join(frames)}, e.retained(original, 'generations/a/'))

    def test_missing_partial_changed_reordered_duplicate_and_oversized_frames_reject(self):
        _, selected, frames = fixture(); raw = b''.join(frames)
        for bad in (b'', raw[:-1], raw+b'x', raw[:-1]+bytes([raw[-1]^1]), b''.join(reversed(frames)), frames[0]*2, bytes(e.MAXIMUM+1)):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError): e.cuts(bad, selected)

    def test_changed_decision_quorum_or_longest_cut_rejects(self):
        _, selected, frames = fixture()
        for change in ('ballot', 'view', 'root', 'longest', 'order', 'duplicate'):
            s = copy.deepcopy(selected)
            if change == 'ballot': s['ballot']['counter'] += 1
            elif change in ('root', 'view'): s[change] = 'f'*64
            elif change == 'longest': s['cut']['index'] = 2
            elif change == 'order': s['sources'].reverse()
            else: s['sources'][1] = s['sources'][0]
            with self.subTest(change=change), self.assertRaises(ValueError): e.cuts(b''.join(frames), s)

    def test_missing_recorded_original_cannot_downgrade_to_legacy(self):
        original, _, _ = fixture(); del original['generations/a/'+e.FILE]
        with self.assertRaises(KeyError): e.retained(original, 'generations/a/')

    def test_original_selector_and_manifest_bind_bytes_before_projection(self):
        original, _, _ = fixture()
        for path in ('selector.gsr', 'generations/a/generation.gsr', 'generations/a/selected.gsr', 'generations/a/'+e.FILE):
            bad = dict(original); raw = bad[path]; bad[path] = raw[:-1]+bytes([raw[-1]^1])
            with self.subTest(path=path), self.assertRaises(ValueError): e.retained(bad, 'generations/a/')
        with self.assertRaises((KeyError, ValueError)): e.retained(original, 'generations/b/')

    def test_explicit_original_legacy_manifest_remains_readable(self):
        original, _, _ = fixture(); gr = e.f.decode(original['generations/a/generation.gsr'], 'records', 'GENERATION')
        gr['files'] = [dict(path='selected.gsr', size=len(original['generations/a/selected.gsr']), sha256=gr['selection'])]
        raw = e.f.encode('records', 'GENERATION', gr); original['generations/a/generation.gsr'] = raw
        sr = e.f.decode(original['selector.gsr'], 'records', 'SELECTOR'); sr['digest'] = e.digest(raw)
        original['selector.gsr'] = e.f.encode('records', 'SELECTOR', sr)
        with self.assertRaisesRegex(ValueError, 'unlisted'): e.retained(original, 'generations/a/')
        del original['generations/a/'+e.FILE]
        self.assertEqual({}, e.retained(original, 'generations/a/'))


if __name__ == '__main__': unittest.main()
