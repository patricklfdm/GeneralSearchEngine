import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import deferred_grant_process_evidence as e


class DeferredGrantProcessEvidenceTest(unittest.TestCase):
    def test_exact_seven_boundaries_and_both_death_modes(self):
        rows=e.cases();self.assertEqual(14,len(rows));self.assertEqual(14,len({v['case'] for v in rows}))
        for mode in ('halt','kill'):self.assertEqual(set(e.CUTS),{v['cut'] for v in rows if v['mode']==mode})
        self.assertEqual({'CAPTURE_INTENT_FORCED','SOURCE_PACKET_PREFIX_WRITTEN','BASIS_FORCED'},e.CAPTURED)

    def test_original_failure_prevents_copy_and_mutation(self):
        with patch.object(e,'history_inventory',return_value={}),patch.object(e,'validate',side_effect=ValueError('original rejected')),patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original rejected'):e.qualify('absent')
            copied.assert_not_called()

    def test_unrelated_failure_is_not_an_accepted_negative(self):
        with (patch.object(e,'history_inventory',return_value={}),patch.object(e,'validate',side_effect=[{},ValueError('unrelated')]),patch.object(e.shutil,'copytree'),patch.object(e,'mutate')):
            with self.assertRaisesRegex(ValueError,'deferred process unrelated negative'):e.qualify('absent')

    @staticmethod
    def fixture(path):
        row=dict(case='halt-PROMISE_FORCED',cut='PROMISE_FORCED',mode='halt',status='PASS',processes=[])
        derived=dict(captureResumed=False,basis31='a'*64)
        for pid,action in enumerate(('fault','resume','inspect'),1):
            death=action=='fault';row['processes'].append(dict(pid=pid,action=action,exit=73 if death else 0,lockProbe=False))
            rows=[dict(event='STARTED',pid=pid,action=action)]
            if death:rows.extend([dict(event='PROMISE_FORCED'),dict(event='CUT',cut='PROMISE_FORCED',pid=pid)])
            else:
                if action=='resume':rows.append(dict(event='RESUMED',captured=False,basis=derived['basis31']))
                rows.append(dict(status='PASS',action=action,pid=pid,peakSources=6,peakImages=7,nativeHistory=False))
            (path/(action+'.stdout')).write_bytes(b''.join(e.f.canonical(v)+b'\n' for v in rows));(path/(action+'.stderr')).write_bytes(b'')
        return row,derived

    def test_fresh_process_binding_rejects_reused_pid_or_false_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);row,derived=self.fixture(path);self.assertEqual(3,e.processes(path,row,derived))
            for mode in ('pid','exit','boolean'):
                changed=copy.deepcopy(row)
                if mode=='pid':changed['processes'][1]['pid']=changed['processes'][0]['pid']
                elif mode=='exit':changed['processes'][0]['exit']=0
                else:changed['processes'][0]['lockProbe']=0
                with self.subTest(mode=mode),self.assertRaises(ValueError):e.processes(path,changed,derived)

    def test_death_and_recovered_return_bind_to_original_cut_and_basis(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);row,derived=self.fixture(path)
            changed=dict(derived,basis31='b'*64)
            with self.assertRaisesRegex(ValueError,'recovered original result'):e.processes(path,row,changed)
            changed=dict(row,cut='FLOOR_BEFORE_RETURN')
            with self.assertRaisesRegex(ValueError,'death handshake'):e.processes(path,changed,derived)

    def test_missing_original_directory_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'original directory'):e.validate(temp)

    def test_mutating_original_during_qualification_is_rejected(self):
        with (patch.object(e,'history_inventory',side_effect=[{},dict(changed=True)]),
              patch.object(e,'validate',side_effect=[{}]+[ValueError(v) for v in e.NEGATIVES.values()]),
              patch.object(e.shutil,'copytree'),patch.object(e,'mutate')):
            with self.assertRaisesRegex(ValueError,'original changed'):e.qualify('absent')

    def test_history_inventory_rejects_links_and_hashes_original_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);(path/'original').write_bytes(b'original');first=e.history_inventory(path)
            (path/'original').write_bytes(b'changed');self.assertNotEqual(first,e.history_inventory(path))
            (path/'alias').symlink_to('original')
            with self.assertRaisesRegex(ValueError,'history bound/type'):e.history_inventory(path)


if __name__=='__main__':unittest.main()
