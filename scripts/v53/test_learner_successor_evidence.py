import unittest
from unittest.mock import patch
from . import learner_successor_evidence as e


class LearnerSuccessorEvidenceTest(unittest.TestCase):
    def trace(self,resume):
        def write(prefix):
            return [prefix+x for x in (('_FORCED','_PARENT_FORCED') if resume else
                                      ('_CREATED','_PREFIX_WRITTEN','_WRITTEN','_FORCED','_PARENT_FORCED'))]
        rows=e.t.trace(resume)+write('LEARNER_PREPARED')+['LEARNER_PREPARED_BEFORE_SELECT','LEARNER_PREPARED_BEFORE_RETURN']
        if not resume:
            rows+=['LEARNER_SUCCESSOR_DIRECTORY_FORCED']+write('LEARNER_SUCCESSOR_PLAN')+['LEARNER_SUCCESSOR_CANDIDATE_FORCED',
                   'LEARNER_SUCCESSOR_CANDIDATE_PARENT_FORCED','LEARNER_SUCCESSOR_PLAN_RENAMED']
        rows+=['LEARNER_SUCCESSOR_ACTIVE_FORCED','LEARNER_SUCCESSOR_ACTIVE_PARENT_FORCED']
        if not resume:rows+=['LEARNER_SUCCESSOR_SOURCE_MOVED']
        return rows+['LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED']+write('LEARNER_SUCCESSOR_SELECT')+['LEARNER_SUCCESSOR_BEFORE_RETURN']

    def test_original_and_resume_require_every_selection_force(self):
        for resume in (False,True):
            rows=self.trace(resume);e.check_trace(rows,resume)
            for point in ('LEARNER_SUCCESSOR_ACTIVE_FORCED','LEARNER_SUCCESSOR_SOURCE_PARENTS_FORCED','LEARNER_SUCCESSOR_SELECT_FORCED','LEARNER_SUCCESSOR_SELECT_PARENT_FORCED'):
                changed=rows.copy();changed.remove(point)
                with self.assertRaisesRegex(ValueError,'successor exact force order'):e.check_trace(changed,resume)

    def test_original_selection_cannot_precede_the_original_source_move(self):
        rows=self.trace(False);rows.remove('LEARNER_SUCCESSOR_SELECT_CREATED')
        rows.insert(rows.index('LEARNER_SUCCESSOR_SOURCE_MOVED'),'LEARNER_SUCCESSOR_SELECT_CREATED')
        with self.assertRaisesRegex(ValueError,'successor exact force order'):e.check_trace(rows)

    def test_duplicate_or_wrong_mode_trace_fails(self):
        with self.assertRaisesRegex(ValueError,'force order'):e.check_trace(self.trace(True))
        with self.assertRaisesRegex(ValueError,'force order'):e.check_trace(self.trace(False)+['LEARNER_SUCCESSOR_SELECT_FORCED'])

    def test_original_failure_is_not_successful_negative_qualification(self):
        with patch.object(e,'validate',side_effect=ValueError('invalid original')) as validate, \
                patch.object(e.tempfile,'TemporaryDirectory') as temporary:
            with self.assertRaisesRegex(ValueError,'invalid original'):e.qualify('/absent')
            validate.assert_called_once();temporary.assert_not_called()


if __name__=='__main__':unittest.main()
