import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import journal_rotation_evidence as e
from . import journal_rotation_negatives as n
from . import journal_rotation_qualification as q


class JournalRotationEvidenceTest(unittest.TestCase):
    def test_complete_authority_and_recovery_cut_inventory(self):
        rows=e.cases();self.assertEqual(135,len(rows));self.assertEqual(135,len({r['name'] for r in rows}))
        for size in (3,4,5):
            for through in (0,6,7):
                for mode in ('halt','kill'):
                    self.assertEqual(set(e.CUTS),{r['cut'] for r in rows if (r['size'],r['through'],r['mode'])==(size,through,mode)})
        self.assertEqual(18,sum(r['mode'].startswith('repeat-') for r in rows))

    def test_compact_file_is_forced_before_replacing_the_original(self):
        original={'grants.gsr':e.r.entry(b'original'),'selector.gsr':e.r.entry(b'selector')};steps=e.transaction(original,b'compact')
        self.assertEqual(list(e.CUTS),[name for name,_ in steps]);renamed=list(e.CUTS).index('JOURNAL_ROTATION_RENAMED')
        for i,(_,state) in enumerate(steps):
            self.assertEqual(original['selector.gsr'],state['selector.gsr'])
            self.assertEqual(original['grants.gsr'] if i<renamed else e.r.entry(b'compact'),state['grants.gsr'])
            self.assertEqual(i<renamed,e.PENDING in state)
        self.assertEqual(e.r.entry(b''),steps[0][1][e.PENDING])
        self.assertEqual(e.r.entry(b'compact'),steps[1][1][e.PENDING])

    def test_each_interruption_converges_to_exact_compact_journal(self):
        initial={'grants.gsr':e.r.entry(b'original')};steps=e.transaction(initial,b'compact');final=steps[-1][1]
        for _,state in steps:
            resumed=e.transaction(state,b'compact');self.assertEqual(final,resumed[-1][1] if resumed else state)
            if e.PENDING in state:self.assertEqual('JOURNAL_ROTATION_WRITTEN',resumed[0][0])
        self.assertEqual([],e.transaction(final,b'compact'))

    def test_returned_promise_and_network_scope_are_bound(self):
        value=dict(journal=e.c.sha(b'compact'),promise='11'*32,networkAck=False);e.result([value],b'compact','11'*32)
        for changed in (dict(promise='22'*32),dict(networkAck=True),dict(journal='33'*32)):
            with self.assertRaisesRegex(ValueError,'rotation returned binding'):e.result([dict(value,**changed)],b'compact','11'*32)

    def test_invalid_original_is_not_counted_as_rejected_mutations(self):
        with patch.object(e,'validate',side_effect=ValueError('original')),patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original'):n.run('absent')
            copied.assert_not_called()

    def test_unrelated_negative_failure_is_rejected(self):
        with patch.object(e,'validate'),patch.object(n.shutil,'copytree'),patch.object(n,'mutate'),patch.object(e,'validate_case',side_effect=ValueError('unrelated')):
            with self.assertRaisesRegex(ValueError,'unrelated rotation negative'):n.run('absent')

    def test_output_collision_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'keep';path.write_text('old')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('old',path.read_text())


if __name__=='__main__':unittest.main()
