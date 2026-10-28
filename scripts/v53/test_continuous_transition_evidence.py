import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import continuous_transition_evidence as e


class ContinuousTransitionEvidenceTest(unittest.TestCase):
    def test_broken_original_is_not_a_successful_negative(self):
        with patch.object(e,'validate',side_effect=ValueError('broken original')) as validate,patch.object(e.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^broken original$'):e.qualify(Path('/original'))
        validate.assert_called_once_with(Path('/original'));copied.assert_not_called()

    def test_explicit_history_cannot_claim_automatic_or_public_service(self):
        original=dict(status='PASS',kind='REMOVE',activations=3,publicReady=False,automaticLifecycle=False)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for changed in ({'publicReady':True},{'automaticLifecycle':True},{'activations':2},{'kind':'REPLACE'},{'phase3Complete':True}):
                (root/'continuous-result.json').write_text(json.dumps(dict(original,**changed)))
                with self.assertRaisesRegex(ValueError,'^continuous scope$'):e.validate(root)

    def test_reconciliation_cannot_infer_a_missing_learner_identity(self):
        state=dict(revision=4,previous='unused',plan=dict(view={'old':['node-1'],'new':['node-1']},
            peers=[dict(identity=dict(node='node-1'),possible=['original'])]))
        current=dict(old=['node-1','node-2'],new=['node-1','node-2'])
        with patch.object(e.d.s.r,'decode',return_value=state),patch.object(e.c,'current',return_value=(None,None,dict(capsule=dict(cut=dict(view=current))))):
            with self.assertRaisesRegex(ValueError,'^continuous actual joining identity required$'):
                e.reconcile({'node-1':{e.d.s.FILE:b'original'}},('node-1',))

    def test_known_removal_preserves_remaining_peer_possibilities(self):
        state=dict(revision=4,previous='unused',plan=dict(view={'old':['node-1','node-2'],'new':['node-1','node-2']},
            peers=[dict(identity=dict(node='node-1'),possible=['old','pending']),dict(identity=dict(node='node-2'),possible=['removed'])]))
        current=dict(old=['node-1'],new=['node-1']);encoded=[]
        with patch.object(e.d.s.r,'decode',return_value=state),patch.object(e.c,'current',return_value=(None,None,dict(capsule=dict(cut=dict(view=current))))),\
                patch.object(e.d.s.r,'frame',side_effect=lambda value:encoded.append(value) or b'reconciled'):
            group={'node-1':{e.d.s.FILE:b'original'}};result=e.reconcile(group,('node-1',))
        self.assertEqual(b'original',group['node-1'][e.d.s.FILE])
        self.assertEqual(b'reconciled',result['node-1'][e.d.s.FILE])
        self.assertEqual(5,encoded[0]['revision']);self.assertEqual(e.e.digest(b'original'),encoded[0]['previous'])
        self.assertEqual([state['plan']['peers'][0]],encoded[0]['plan']['peers'])


if __name__=='__main__':unittest.main()
