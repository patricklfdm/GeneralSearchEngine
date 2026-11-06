import unittest
from unittest.mock import patch
from . import native_completion_files as m


class NativeCompletionFilesTest(unittest.TestCase):
    def initial(self):
        return {'root.gsr':b'root','selector.gsr':b'old selector','pending.accept':b'certificate',
                'generations':None,'generations/b':None,'generations/b/generation.gsr':b'old manifest',
                'peer-retention.gspr':b'old peers','future-retention.gsft':b'future acknowledgements'}

    def applied(self,**extra):
        end={k:k.encode() for k in ('plan.json','selector.gsr','certificate.gsr','catalog.gsr','statement.gsr','application.image','ack.gsr')}
        end.update(extra)
        return dict(self.initial(),**{'applied-end':None},**{'applied-end/'+k:v for k,v in end.items()})

    def publication(self):
        applied=self.applied();published={k:v for k,v in applied.items() if not k.startswith('applied-end')}
        published.update({'selector.gsr':b'new selector','generations/a':None,'generations/a/generation.gsr':b'new manifest',
                          'generations/a/application.image':b'image','pending.accept':m.EMPTY,
                          'peer-retention.gspr':b'promoted peers','future-retention.gsft':b'cleared future'})
        with patch.object(m.f,'decode',return_value=dict(generation='a')):steps=m.publication(applied,published)
        return applied,published,steps

    def test_image_is_complete_before_ack_and_all_other_replica_bytes_survive(self):
        initial=self.initial();applied=self.applied();steps=m.application(initial,applied)
        points=[p for _,p,_ in steps];self.assertEqual(33,len(steps))
        forced=next(s for _,p,s in steps if p=='APPLY_END_FORCED')
        self.assertNotIn('applied-end/ack.gsr',forced)
        self.assertEqual(m.physical(applied)['applied-end/application.image'],forced['applied-end/application.image'])
        self.assertLess(points.index('APPLY_END_FORCED'),points.index('APPLY_ACK_CREATED'))
        self.assertEqual(m.physical(applied),steps[-1][2]);self.assertEqual(initial,self.initial())
        for _,_,state in steps:
            for key in initial:self.assertEqual(m.physical(initial)[key],state[key])

    def test_parent_and_ancestor_acks_follow_all_statement_and_image_forces(self):
        end=self.applied(**{'parent-statement.gsr':b'parent','parent-ack.gsr':b'ack',
                           'ancestor-0-statement.gsr':b'ancestor','ancestor-0-ack.gsr':b'ancestor ack'})
        points=[p for _,p,_ in m.application(self.initial(),end)]
        expected=['APPLY_PARENT_STATEMENT_FORCED','APPLY_ANCESTOR_0_STATEMENT_FORCED','APPLY_IMAGE_FORCED',
                  'APPLY_ACK_FORCED','APPLY_PARENT_ACK_FORCED','APPLY_ANCESTOR_0_ACK_FORCED','APPLY_ACK_DIRECTORY_FORCED']
        self.assertEqual(expected,[p for p in points if p in expected])

    def test_nonvoting_end_has_no_ack_and_partial_original_is_not_fresh(self):
        end=self.applied();del end['applied-end/ack.gsr']
        points=[p for _,p,_ in m.application(self.initial(),end)]
        self.assertIn('APPLY_NONVOTING_DIRECTORY_FORCED',points);self.assertFalse(any(p.startswith('APPLY_ACK') for p in points))
        for initial in (end,dict(self.initial(),**{'applied-end':None})):
            with self.assertRaisesRegex(ValueError,'^completion fresh application end$'):m.application(initial,end)

    def test_missing_end_file_ancestor_gap_and_unrelated_change_reject(self):
        cases=[];end=self.applied();del end['applied-end/application.image'];cases.append(end)
        cases.append(self.applied(**{'ancestor-1-statement.gsr':b'gap','ancestor-1-ack.gsr':b'ack'}))
        cases.append(self.applied(**{'parent-statement.gsr':b'parent'}))
        cases.append(dict(self.applied(),**{'root.gsr':b'changed'}))
        for end in cases:
            with self.assertRaises(ValueError):m.application(self.initial(),end)

    def test_selector_remains_old_until_rename_and_plan_is_deleted_last(self):
        initial,published,steps=self.publication();states={p:s for _,p,s in steps}
        self.assertEqual(m.physical(initial)['selector.gsr'],states['INSTALL_SELECTOR_FORCED']['selector.gsr'])
        self.assertIn('selector.pending.gsr',states['INSTALL_SELECTOR_FORCED'])
        self.assertEqual(m.physical(published)['selector.gsr'],states['INSTALL_SELECTOR_RENAMED']['selector.gsr'])
        self.assertNotIn('selector.pending.gsr',states['INSTALL_SELECTOR_RENAMED'])
        deletions=[s for _,p,s in steps if p=='COVERED_END_FILE_DELETED']
        self.assertTrue(all('applied-end/plan.json' in s for s in deletions[:-1]))
        self.assertNotIn('applied-end/plan.json',deletions[-1]);self.assertIn('applied-end',deletions[-1])
        self.assertEqual(m.physical(published),steps[-1][2])

    def test_covered_vote_and_ledger_promotion_are_separate_boundaries(self):
        initial,published,steps=self.publication();states={p:s for _,p,s in steps}
        self.assertEqual(m.physical(initial)['pending.accept'],states['COVERED_VOTE_CANDIDATE_PARENT_FORCED']['pending.accept'])
        self.assertEqual(m.physical(published)['pending.accept'],states['COVERED_VOTE_RENAMED']['pending.accept'])
        self.assertNotIn('pending.accept.next',states['COVERED_VOTE_RENAMED'])
        for name in m.LEDGERS:
            self.assertEqual(m.physical(initial)[name],states['PUBLICATION_RETIRED'][name])
            self.assertEqual(m.physical(published)[name],states['PUBLICATION_BEFORE_RETURN'][name])

    def test_publication_cannot_absorb_unrelated_final_mutation_or_partial_candidate(self):
        initial,published,_=self.publication()
        with patch.object(m.f,'decode',return_value=dict(generation='a')):
            for changed in (dict(initial,**{'pending.accept.next':b'partial'}),dict(initial,**{'generations/a':None})):
                with self.assertRaisesRegex(ValueError,'^completion fresh publication$'):m.publication(changed,published)
            with self.assertRaisesRegex(ValueError,'^completion publication outside transaction$'):
                m.publication(initial,dict(published,**{'root.gsr':b'changed'}))

    def test_callback_binding_uses_same_owner_and_excludes_campaign_installation(self):
        events=[('node-1','INSTALL_RESERVED'),('node-1','CURRENT_VALIDATED'),('node-1','APPLY_VALIDATED'),
                ('node-2','APPLY_VALIDATED'),('node-1','APPLY_BEFORE_RETURN'),('node-1','PUBLICATION_VALIDATED'),
                ('node-2','CURRENT_VALIDATED'),('node-1','INSTALL_RESERVED'),('node-1','PUBLICATION_BEFORE_RETURN'),
                ('node-2','APPLY_BEFORE_RETURN'),('node-1','PUBLICATION_ACK_BEFORE_RETURN')]
        rows=[dict(node=n,event=p) for n,p in events];found=m.observed(rows)
        self.assertEqual([2,3,4,5,7,8,9],[v[0] for v in found])
        for index,_,row in found:self.assertIs(row,rows[index])
        for bad in ([dict(node='node-1',event='APPLY_VALIDATED')],
                    [dict(node='node-1',event='COVERED_END_VALIDATED')],rows[:4]+[rows[2]]):
            with self.assertRaises(ValueError):m.observed(bad)

    def test_declared_application_ack_stop_keeps_full_forced_end_without_return(self):
        initial=self.initial();end=self.applied(**{'parent-statement.gsr':b'parent','parent-ack.gsr':b'parent ack'})
        complete=m.application(initial,end)
        stopped=m.application(initial,end,stop='APPLY_ACK_DIRECTORY_FORCED')
        self.assertEqual(complete[:-1],stopped)
        self.assertEqual(('application','APPLY_ACK_DIRECTORY_FORCED'),stopped[-1][:2])
        self.assertEqual(m.physical(end),stopped[-1][2])
        self.assertFalse(any(p=='APPLY_BEFORE_RETURN' for _,p,_ in stopped))
        rows=[dict(node='node-1',event=point) for _,point,_ in stopped]
        with self.assertRaisesRegex(ValueError,'incomplete transaction'):m.observed(rows)
        observed=m.observed(rows,interrupted_application='node-1')
        self.assertEqual(list(range(len(rows))),[at for at,_,_ in observed])
        self.assertTrue(all(row is rows[at] for at,_,row in observed))

    def test_application_stop_cannot_admit_nonvoting_or_another_write_boundary(self):
        end=self.applied();del end['applied-end/ack.gsr']
        with self.assertRaisesRegex(ValueError,'requires ACK'):
            m.application(self.initial(),end,stop='APPLY_ACK_DIRECTORY_FORCED')
        for stop in ('APPLY_ACK_FORCED','APPLY_BEFORE_RETURN',False,''):
            with self.subTest(stop=stop),self.assertRaisesRegex(ValueError,'supported application stop'):
                m.application(self.initial(),self.applied(),stop=stop)

    def test_declared_stop_cannot_hide_later_or_other_owner_activity(self):
        rows=[dict(node='node-1',event=p) for _,p,_ in m.application(self.initial(),self.applied(),stop='APPLY_ACK_DIRECTORY_FORCED')]
        variants=[rows[:-1],rows+[dict(node='node-1',event='APPLY_BEFORE_RETURN')],
                  rows+[dict(node='node-2',event='WIRE_RESPONSE')],
                  [dict(node='node-2',event='APPLY_VALIDATED')]+rows]
        for variant in variants:
            with self.subTest(variant=variant[-1]),self.assertRaisesRegex(ValueError,'exact interrupted application boundary'):
                m.observed(variant,interrupted_application='node-1')
        with self.assertRaisesRegex(ValueError,'exact interrupted application boundary'):
            m.observed(rows,interrupted_application='node-2')
        for owner in (False,True,'',0):
            with self.assertRaisesRegex(ValueError,'interrupted application owner'):m.observed(rows,interrupted_application=owner)


if __name__=='__main__':unittest.main()
