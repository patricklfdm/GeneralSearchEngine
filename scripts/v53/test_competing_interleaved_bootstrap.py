"""Reader dispatch, claimed authority, and prerequisite guards (not native evidence)."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import competing_interleaved_bootstrap as m
from . import competing_campaign_prefix as prefix
from . import competing_campaign_maintenance as maintenance
from . import competing_campaign_publication as publication
from . import competing_export_evidence as exports
from . import automatic_history_replay as replay
from .test_automatic_history_replay import original


class InterleavedBootstrapTest(unittest.TestCase):
    def test_late_capture_dispatch_requires_continuation_not_a_weaker_prefix(self):
        r=SimpleNamespace(events=[dict(event='INSTALL_RESERVED')],by_basis={'basis':dict(capturedEvent=1)})
        self.assertTrue(m.needed(r))
        with self.assertRaisesRegex(ValueError,'later grant needs continuation replay'):prefix.Replay.physical_prefix(r)
        with patch.object(m,'run',return_value='continued') as continuation,patch.object(prefix.Replay,'run') as old:
            self.assertEqual('continued',maintenance.Replay.run(r));continuation.assert_called_once_with(r);old.assert_not_called()

    def test_existing_prefix_stays_on_its_original_reader(self):
        r=SimpleNamespace(events=[dict(event='before'),dict(event='INSTALL_RESERVED')],by_basis={'basis':dict(capturedEvent=0)})
        self.assertFalse(m.needed(r))

    def test_new_shape_needs_its_complete_original_chain_and_exact_counts(self):
        value=original('competition','interleaved')['exports']
        self.assertEqual('interleaved',replay.competition_branch(value))
        for change in ('sources','partial','loss','responses','marker'):
            changed=deepcopy(value)
            if change=='sources':changed['sourceWindows']=4
            elif change=='partial':changed['incompleteTransfers']=1
            elif change=='loss':changed['precondition']['pregrantLosses']=[{}]
            elif change=='responses':changed['precondition']['undeliveredOriginalResponses']=1
            else:changed['precondition'].pop('interleavedBootstrap')
            with self.subTest(change=change),self.assertRaises(ValueError):replay.competition_branch(changed)

    def test_failed_original_cannot_earn_new_negative_credit(self):
        with patch.object(prefix.collection.h,'inventory',return_value={}),patch.object(exports,'Replay') as reader,patch.object(m,'activation') as negative:
            reader.return_value.run.side_effect=ValueError('invalid original')
            with self.assertRaisesRegex(ValueError,'^invalid original$'):m.qualify(Path('/original'))
            negative.assert_not_called()

    def test_partial_install_cannot_name_an_unselected_owner_or_install_twice(self):
        selected=dict(ballot=dict(proposer='one'),sources=[dict(voter='one'),dict(voter='two')])
        for owners in ((),('three',),('one','one')):
            with self.subTest(owners=owners),patch.object(publication.f,'decode',return_value=selected),\
                    self.assertRaisesRegex(ValueError,'owner subset'):
                publication.selected_install({'one':{},'two':{},'three':{}},b'choice',owners=owners)


if __name__=='__main__':unittest.main()
