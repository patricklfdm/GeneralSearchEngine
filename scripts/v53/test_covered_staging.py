import struct
import unittest
from unittest.mock import patch
from . import covered_staging_evidence as q


class CoveredStagingTest(unittest.TestCase):
    def original(self):
        files={'pending.accept':b'original vote','selector.gsr':b'original selector','applied-end':None,
               'applied-end/plan.json':b'plan','applied-end/ack.gsr':b'ack','applied-end/application.image':b'image'}
        body=q.e.f.canonical(dict(authority={'mode':'covered-prefix','coveringGeneration':'a'*64},
            files=[dict(path=k.removeprefix('applied-end/'),type='file',**q.e.info(v)) for k,v in sorted(files.items()) if k.startswith('applied-end/')]))
        header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));return files,header+bytes.fromhex(q.e.digest(header+body))+body

    def test_retirement_force_precedes_every_delete_and_preserves_original_vote(self):
        before,marker=self.original();after,events=q.cleanup(before,marker)
        self.assertEqual(q.without_staging(before),after);self.assertLess(events.index('SUPERSEDED_END_AUTHORITY_FORCED'),events.index('SUPERSEDED_END_BEFORE_DELETE'))
        self.assertNotIn('applied-end/retirement.gsat',before)

    def test_every_retirement_cut_can_resume_without_changing_originals(self):
        before,marker=self.original()
        for cut in q.CUTS:
            with self.subTest(cut=cut):
                interrupted,_=q.cleanup(before,marker,cut);after,_=q.cleanup(interrupted,marker)
                self.assertEqual(q.without_staging(before),after)

    def test_empty_directory_after_marker_removal_has_an_empty_new_inventory(self):
        before,marker=self.original();state,_=q.cleanup(before,marker,'SUPERSEDED_END_RETIREMENT_DELETED')
        state,_=q.cleanup(state,marker,'SUPERSEDED_END_AUTHORITY_FORCED');active=state['applied-end/retirement.gsat']
        self.assertEqual([],q.e.parse(active[48:])['files']);self.assertEqual(q.e.parse(marker[48:])['authority'],q.e.parse(active[48:])['authority'])
        self.assertEqual(q.without_staging(before),q.cleanup(state,marker)[0])

    def test_different_marker_cannot_authorize_cleanup(self):
        before,marker=self.original();state,_=q.cleanup(before,marker,'SUPERSEDED_END_AUTHORITY_FORCED');state['applied-end/retirement.gsat']=marker[:-1]+b'x'
        with self.assertRaisesRegex(ValueError,'exact retained authority'):q.cleanup(state,marker)

    def test_different_partial_candidate_cannot_authorize_cleanup(self):
        before,marker=self.original();state,_=q.cleanup(before,marker,'SUPERSEDED_END_RETIREMENT_PREFIX_WRITTEN');state['applied-end/retirement.gsat.next']=b'x'
        with self.assertRaisesRegex(ValueError,'exact retirement prefix'):q.cleanup(state,marker)

    def test_old_ack_events_are_refused(self):
        for event in ('APPLY_ACK_FORCED','APPLY_BEFORE_RETURN'):
            with self.assertRaisesRegex(ValueError,'old ACK'):q.no_ack(['STAGED_RETIREMENT_BEFORE_RETURN',event])

    def test_invalid_original_cannot_count_as_negative_rejections(self):
        with patch.object(q,'validate',side_effect=ValueError('invalid original')),patch.object(q.shutil,'copytree') as copytree:
            with self.assertRaisesRegex(ValueError,'invalid original'):q.qualify('profiles','interruptions')
            copytree.assert_not_called()

    def test_cut_and_negative_inventory_is_unique(self):
        self.assertEqual(18,len(q.CUTS));self.assertEqual(len(q.CUTS),len(set(q.CUTS)));self.assertEqual(17,len(q.VARIANTS))


if __name__=='__main__':unittest.main()
