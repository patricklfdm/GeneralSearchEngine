"""Whole-stream ownership and exact causal intervals for the append reader."""
import unittest
from . import selection_journal_evidence as e


def fixture():
    points=['BOUNDARY','SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN','BOUNDARY']
    events=[dict(node='node-1',event=p) for p in points]
    bound=dict(node='node-1',scope=None,selection='a'*64,forced=3,lower=0,upper=5)
    return events,[bound]


class SelectionJournalEvidenceTest(unittest.TestCase):
    def test_complete_interleaved_original_owners(self):
        events,bounds=fixture();other=[dict(row,node='node-2',scope='owner-2') for row in events]
        interleaved=[row for pair in zip(events,other) for row in pair]
        bounds[0].update(forced=6,lower=0,upper=10)
        bounds.append(dict(node='node-2',scope='owner-2',selection='b'*64,forced=7,lower=1,upper=11))
        self.assertEqual(dict(selections=2,callbacks=8),e.validate(interleaved,bounds))

    def test_all_four_boundaries_are_required(self):
        for index in range(1,5):
            events,bounds=fixture();events[index]['event']='OMITTED'
            reason='incomplete transaction' if index==4 else 'complete write order'
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,'^selection journal '+reason+'$'):e.validate(events,bounds)

    def test_binding_and_original_selection_cannot_be_reused(self):
        events,bounds=fixture();bounds.append(dict(bounds[0]))
        with self.assertRaisesRegex(ValueError,'^selection journal reused original selection$'):e.validate(events,bounds)
        events,bounds=fixture();events+=events[1:5]
        with self.assertRaisesRegex(ValueError,'^selection journal unbound original selection$'):e.validate(events,bounds)

    def test_each_bound_requires_its_exact_owner_and_valid_interval(self):
        for change in ({'scope':'other'},{'selection':'claimed'},{'lower':1},{'upper':4},{'lower':True},{'upper':99}):
            events,bounds=fixture();bounds[0].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^selection journal original authority interval$'):e.validate(events,bounds)

    def test_malformed_or_foreign_rows_cannot_claim_an_original_write(self):
        for change in ({'node':'foreign'},{'node':[]},{'scope':None},{'scope':4},{'written':True},{'event':True}):
            events,bounds=fixture();events[2].update(change)
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^selection journal callback shape$'):e.validate(events,bounds)

    def test_only_exact_known_retention_callbacks_are_outside_this_family(self):
        events,bounds=fixture()
        for point in ('SELECTED_RETENTION_COMPLETED','SELECTED_LEARNER_RETENTION_COMPLETED'):
            events.append(dict(node='node-1',event=point))
        self.assertEqual(dict(selections=1,callbacks=4),e.validate(events,bounds))
        events.append(dict(node='node-1',event='SELECTED_RETENTION_UNKNOWN'))
        with self.assertRaisesRegex(ValueError,'^selection journal unsupported callback$'):e.validate(events,bounds)

    def test_early_write_mutation_uses_original_and_normalized_transport_kinds(self):
        for role in ('proposer','remote','recovery'):
            for raw in (False,True):
                node={'proposer':'node-1','remote':'node-2','recovery':'node-4'}[role]
                authority=dict(node=node,event=('AFTER_REQUEST_READ' if raw else 'NETWORK_REQUEST') if role=='remote' else
                    ('AFTER_RESPONSE_READ' if raw else 'NETWORK_RECEIVED'),kind='SELECTED' if role=='remote' else
                    ('PREPARE' if raw else 'PROMISE'))
                if raw and role!='remote':authority['responseKind']='PROMISE'
                unrelated=dict(node=node,event='AFTER_RESPONSE_READ',kind='CHUNK',responseKind='CHUNK')
                writes=[dict(node=node,event=point,**({'scope':'continuation-owner'} if role=='recovery' else {})) for point in
                        ('SELECTED_BEFORE_WRITE','SELECTED_WRITTEN','SELECTED_FORCED','SELECTED_BEFORE_RETURN')]
                events=[authority,unrelated,*writes]
                with self.subTest(role=role,raw=raw):
                    e.mutate(events,'selection-'+role+'-writes-before-authority')
                    self.assertEqual([writes[0],writes[1],authority,unrelated,writes[2],writes[3]],events)


if __name__=='__main__':unittest.main()
