import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import source_release_evidence as e
from . import source_release_negatives as n
from . import source_release_qualification as q


class SourceReleaseEvidenceTest(unittest.TestCase):
    def test_complete_profiles_and_repeated_recovery_inventory(self):
        rows=e.cases();self.assertEqual(297,len(rows));self.assertEqual(297,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (0,6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})
        self.assertEqual(18,sum(r['mode'].startswith('repeat-') for r in rows))

    def state(self):
        return {'sources':dict(directory=True),'sources/id':dict(directory=True),
                'sources/id/aa.image':e.r.entry(b'image'),'sources/id/source.gscp':e.r.entry(b'packet'),
                'grants.gsr':e.r.entry(b'original'),'selector.gsr':e.r.entry(b'selector'),'floor-copies/floor.gsr':e.r.entry(b'floor')}

    def test_authority_and_journal_are_forced_before_deletion_and_authority_clears_last(self):
        initial=self.state();steps=e.transaction(initial,b'authority',b'compact','id');names=[name for name,_ in steps]
        self.assertLess(names.index('SOURCE_RETIREMENT_FORCED'),names.index('JOURNAL_ROTATION_RENAMED'))
        self.assertLess(names.index('SOURCE_RETIREMENT_PARENT_FORCED'),names.index('JOURNAL_ROTATION_RENAMED'))
        self.assertLess(names.index('JOURNAL_ROTATION_PARENT_FORCED'),names.index('SOURCE_RETIREMENT_FILE_DELETED'))
        self.assertLess(names.index('SOURCE_RETIREMENT_DIRECTORY_DELETED'),names.index('SOURCE_RETIREMENT_CLEARED'))
        for _,state in steps:
            for name in ('selector.gsr','floor-copies/floor.gsr'):self.assertEqual(initial[name],state[name])

    def test_every_interrupted_state_converges_without_recreating_deleted_files(self):
        initial=self.state();steps=e.transaction(initial,b'authority',b'compact','id');final=steps[-1][1]
        for _,state in steps:
            again=e.transaction(state,b'authority',b'compact','id');self.assertEqual(final,again[-1][1] if again else state)
            missing={n for n in initial if n.startswith('sources/id') and n not in state}
            self.assertTrue(all(not missing.intersection(v) for _,v in again))
        self.assertEqual([],e.transaction(final,b'authority',b'compact','id'))

    def test_returned_result_requires_exact_journal_floor_selector_and_completed_cleanup(self):
        initial=self.state();row=dict(retired=True,journal=e.c.sha(b'compact'),selector=initial['selector.gsr']['sha256'],floor=initial['floor-copies/floor.gsr']['sha256'],networkAck=False)
        e.result([row],initial,b'compact')
        for changed in (dict(retired=False),dict(journal='00'*32),dict(floor='00'*32),dict(selector='00'*32),dict(networkAck=True)):
            with self.assertRaisesRegex(ValueError,'source release returned binding'):e.result([dict(row,**changed)],initial,b'compact')

    def test_invalid_original_is_not_counted_as_mutation_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_negative_failure_is_rejected(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated source release negative'):n.run('absent')

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
