"""Keep phased original inventory and recovery phase discrimination strict."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from . import covered_phased_vote_evidence as p


class CoveredPhasedVoteEvidenceTest(unittest.TestCase):
    def test_invalid_original_is_never_counted_as_evidence_rejection(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'invalid original'):p.qualify('profiles','proof','certificate')
            validate.assert_called_once();copy.assert_not_called()

    def test_missing_matrix_refuses_before_any_case_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(p,'clean') as clean,self.assertRaisesRegex(ValueError,'inventory'):p.validate(tmp,'proof','certificate')
            clean.assert_not_called()

    def test_profile_types_and_unknown_phases_are_not_coerced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for profile in (dict(size=True,backup=False,phase='PROOF'),dict(size=3,backup=0,phase='PROOF'),dict(size=3,backup=False,phase='ACCEPT')):
                (root/'profile.json').write_bytes(p.e.f.canonical(profile))
                with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'exact profile'):p.profile(root)

    def test_original_phase_is_forced_before_an_interrupted_install(self):
        for phase in ('PROOF','CERTIFICATE'):
            before={'selector.gsr':b'old','pending.accept':b'original'};after={'selector.gsr':b'new'}
            state,events=p.model.transaction(before,after,phase+'_ACTIVE_FORCED',phase=phase)
            self.assertEqual(before,state);self.assertEqual(p.model.OPEN+[phase+'_ACTIVE_FORCED'],events)
        with self.assertRaisesRegex(ValueError,'opening vote phase'):p.model.transaction({}, {}, phase='UNKNOWN')

    def test_completed_empty_vote_reopens_as_accept_not_old_certificate(self):
        before={'selector.gsr':b'new','pending.accept':p.c.EMPTY};after=dict(before)
        state,events=p.model.transaction(before,after,'ACCEPT_ACTIVE_FORCED',phase='CERTIFICATE')
        self.assertEqual(before,state);self.assertEqual(p.model.OPEN+['ACCEPT_ACTIVE_FORCED'],events)

    def test_capture_preserves_every_requested_original_phase(self):
        frames=dict(ENTRY=b'entry',ACCEPT=b'accept',PAYLOAD=b'payload',PROOF=b'proof',CERTIFICATE=b'certificate')
        values={'ACCEPT':dict(ballot=dict(counter=2))};packet=dict(objects={},capsule={},images={})
        files={'pending.accept':b'vote','g/generation.gsr':b'manifest'}
        for phases in [('PROOF',),('PROOF','CERTIFICATE')]:
            with patch.object(p.c,'current',return_value=('g/',{},packet)),patch.object(p.c,'pending',return_value=(frames,values)) as pending,patch.object(p.e.f,'decode',return_value={'ownedTail':None}),patch.object(p.e,'packet_bytes',return_value=b'source') as encode:
                source,tail=p.d.captured(files,phases)
                pending.assert_called_once_with(b'vote',phases);self.assertEqual(b'source',source);self.assertEqual(p.e.digest(b'accept'),tail)
                self.assertEqual({p.e.digest(frames[k]):frames[k] for k in ('ENTRY','ACCEPT','PAYLOAD',*phases)},encode.call_args.args[1])


if __name__=='__main__':unittest.main()
