import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import floor_release_evidence as e
from . import floor_release_negatives as n
from . import floor_release_qualification as q


class FloorReleaseEvidenceTest(unittest.TestCase):
    def state(self):
        return {'grants.gsr':e.r.entry(b'journal'),'selector.gsr':e.r.entry(b'selector'),'floor-copies':dict(directory=True),
                'floor-copies/floor.gsr':e.r.entry(b'floor'),'floor-copies/proposal.gsr':e.r.entry(b'floor'),
                'floor-copies/copy':dict(directory=True),'floor-copies/copy/source.gscp':e.r.entry(b'packet')}

    def test_complete_profiles_and_repeated_recovery_inventory(self):
        rows=e.cases();self.assertEqual(261,len(rows));self.assertEqual(261,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (0,6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})
        self.assertEqual(18,sum(r['mode'].startswith('repeat-') for r in rows))

    def test_release_record_is_forced_before_any_floor_or_copy_delete(self):
        initial=self.state();steps=e.transaction(initial,b'record');names=[name for name,_ in steps]
        self.assertLess(names.index('FLOOR_RELEASE_AUTHORITY_FORCED'),names.index('FLOOR_RELEASE_RELINQUISHED'))
        self.assertLess(names.index('FLOOR_RELEASE_PARENT_FORCED'),names.index('FLOOR_RELEASE_RELINQUISHED'))
        self.assertLess(names.index('FLOOR_RELEASE_RELINQUISHED'),names.index('FLOOR_RELEASE_FILE_DELETED'))
        self.assertLess(names.index('FLOOR_RELEASE_COPY_DELETED'),names.index('FLOOR_RELEASE_AUTHORITY_CLEARED'))
        for _,state in steps:
            for name in ('grants.gsr','selector.gsr'):self.assertEqual(initial[name],state[name])
        self.assertEqual(e.r.entry(b''),steps[0][1][e.RELEASE])

    def test_each_interrupted_state_converges_without_new_floor_authority(self):
        steps=e.transaction(self.state(),b'record');final=steps[-1][1]
        for _,state in steps:
            resumed=e.transaction(state,b'record');self.assertEqual(final,resumed[-1][1] if resumed else state)
            if 'floor-copies/floor.gsr' not in state:
                self.assertTrue(all('floor-copies/floor.gsr' not in v for _,v in resumed))
        self.assertEqual([],e.transaction(final,b'record'))

    def test_returned_authority_must_be_absent_and_bind_original_journal_selector(self):
        initial=self.state();row=dict(journal=initial['grants.gsr']['sha256'],selector=e.c.sha(b'selector'),floor=None,networkAck=False)
        e.result([row],initial,b'selector')
        for changed in (dict(journal='11'*32),dict(selector='22'*32),dict(floor='33'*32),dict(networkAck=True)):
            with self.assertRaisesRegex(ValueError,'floor release returned binding'):e.result([dict(row,**changed)],initial,b'selector')

    def test_invalid_original_is_not_counted_as_mutation_rejections(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copy.assert_not_called()

    def test_unrelated_negative_failure_is_rejected(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated floor release negative'):n.run('absent')

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
