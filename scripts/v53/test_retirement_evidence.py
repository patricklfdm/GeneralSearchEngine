import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import retirement_evidence as e
from . import retirement_negatives as n
from . import retirement_qualification as q


class RetirementEvidenceTest(unittest.TestCase):
    def test_each_authority_and_crash_boundary_has_halt_and_kill(self):
        rows=e.cases();self.assertEqual(549,len(rows));self.assertEqual(549,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (0,6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})
        self.assertEqual(18,sum(r['mode'].startswith('repeat-') for r in rows))

    def fixture(self):
        original={'generation.gsr':b'm','source.gscp':b's','promise.gsr':b'p','00.image':b'i'}
        initial={'generations/a':dict(directory=True),'selector.gsr':e.entry(b'selector'),'floor-copies/floor.gsr':e.entry(b'floor')}
        initial.update({'generations/a/'+n:e.entry(raw) for n,raw in original.items()})
        return initial,original,b'authority'

    def test_full_saved_inventory_and_authority_force_precede_every_original_deletion(self):
        initial,original,record=self.fixture();steps,returned=e.transaction(initial,original,record);events=[name for name,_ in steps]
        first=events.index('RETIREMENT_FILE_DELETED')
        self.assertLess(events.index('RETIREMENT_SOURCE_FORCED'),events.index('RETIREMENT_AUTHORITY_WRITTEN'))
        self.assertLess(events.index('RETIREMENT_AUTHORITY_FORCED'),first)
        self.assertEqual({n:e.entry(raw) for n,raw in original.items()},
                         {n.removeprefix('retirement/source/'):v for n,v in steps[first][1].items() if n.startswith('retirement/source/')})
        self.assertEqual(e.c.sha(record),returned)
        self.assertLess(events.index('RETIREMENT_DIRECTORY_DELETED'),events.index('RETIREMENT_SAVED_FILE_DELETED'))
        self.assertLess(events.index('RETIREMENT_SAVED_DIRECTORY_DELETED'),events.index('RETIREMENT_AUTHORITY_CLEARED'))

    def test_every_interrupted_state_converges_without_changing_protected_authority(self):
        initial,original,record=self.fixture();steps,_=e.transaction(initial,original,record);final=steps[-1][1]
        for _,state in steps:
            resumed,_=e.transaction(state,original,record)
            self.assertEqual(final,resumed[-1][1] if resumed else state)
            self.assertEqual(initial['selector.gsr'],state['selector.gsr'])
            self.assertEqual(initial['floor-copies/floor.gsr'],state['floor-copies/floor.gsr'])
        self.assertEqual(([],None),e.transaction(final,original,record))

    def test_repeated_recovery_never_recreates_deleted_original_files(self):
        initial,original,record=self.fixture();steps,_=e.transaction(initial,original,record)
        crash=steps[e.cut_position(steps,'RETIREMENT_FILE_DELETED@2')][1]
        resumed,_=e.transaction(crash,original,record)
        self.assertEqual(('RETIREMENT_AUTHORITY_RESEALED',crash),resumed[0])
        self.assertEqual(2,sum(name=='RETIREMENT_FILE_DELETED' for name,_ in resumed))
        self.assertEqual(resumed,e.transaction(resumed[0][1],original,record)[0])

    def test_missing_occurrence_cannot_silently_select_another_cut(self):
        with self.assertRaisesRegex(ValueError,'absent crash cut'):e.cut_position([('EVENT',{})],'EVENT@2')

    def test_invalid_original_is_not_counted_as_rejected_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copied.assert_not_called()

    def test_unrelated_negative_failure_is_rejected(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated retirement negative'):n.run('absent')

    def test_output_collision_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
