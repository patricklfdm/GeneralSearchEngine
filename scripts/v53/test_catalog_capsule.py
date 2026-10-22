from copy import deepcopy
import unittest

from . import catalog_capsule as c
from . import catalog_capsule_oracle as o
from . import integrated_model as g
from .test_integrated_model import prepared,finish


def fixture(size=3,kind='ADD'):
    group=g.Group(size);group.commit();prepared(group,kind);finish(group)
    group.commit(dict(kind='RETIRE',through=1));group.commit(dict(kind='DATA',value='after'))
    return c.Source(group.evidence())


class CapsuleTest(unittest.TestCase):
    def test_every_profile_incrementally_preserves_catalog_after_result_retirement(self):
        for size,kind in ((3,'ADD'),(4,'ADD'),(4,'REMOVE'),(5,'REMOVE'),(3,'REPLACE'),(4,'REPLACE'),(5,'REPLACE')):
            with self.subTest(size=size,kind=kind):
                s=fixture(size,kind);previous=None
                for cut in sorted(s.certs):previous=s.build(cut,previous)
                self.assertEqual({},previous['catalog']['results']);self.assertEqual(1,previous['catalog']['retiredThrough'])
                edges=[i for i in previous['items'] if i['kind']=='membership']
                self.assertEqual(2,len(edges));self.assertIn('request',edges[0]['descriptor'])
                self.assertEqual(len(s.certs),o.check(s.evidence())['capsules'])

    def test_no_future_unforced_or_crashed_endorsement(self):
        s=fixture();statement=s.statement(0,1);n=s.input['old'][0]
        s.through=s.applies[n,1]-1
        with self.assertRaisesRegex(ValueError,'forced catalog'):s.stage(n,statement)
        s.through=len(s.input['events']);s.stage(n,statement);s.crash(n)
        with self.assertRaisesRegex(ValueError,'stage'):s.force(n)
        o.check(s.evidence())

    def test_extension_requires_new_endorsement_for_changed_range(self):
        s=fixture();packet=s.build(1);later=s.build(2,packet);s.endorsed.clear()
        with self.assertRaisesRegex(ValueError,'quorum'):s.verify(later)
        changed=deepcopy(s.evidence());changed['events']=[e for e in changed['events'] if
             not (e['event']=='force' and e['statement']['after']['index']==3)]
        with self.assertRaises(ValueError):o.check(changed)

    def test_modified_catalog_identity_or_descriptor_is_rejected(self):
        s=fixture();packet=s.build(max(s.certs));o.check(s.evidence())
        for kind in ('catalog','identity','descriptor','proof'):
            changed=deepcopy(packet)
            if kind=='catalog':changed['catalog']['nextOperation']=1
            elif kind=='identity':changed['catalog']['identities'].pop()
            else:
                edge=next(i for i in changed['items'] if i['kind']=='membership')
                if kind=='descriptor':edge['descriptor']['request']['target'][0]['storage']='different'
                else:edge['certificate']['proofs']=[]
            with self.subTest(kind=kind),self.assertRaises(ValueError):s.verify(changed)
            record=deepcopy(s.evidence());record['events'][-1]['packet']=changed
            with self.subTest(oracle=kind),self.assertRaises(ValueError):o.check(record)

    def test_cannot_hide_membership_inside_attested_range(self):
        s=fixture();packet=s.build(max(s.certs));changed=deepcopy(packet)
        edge=next(i for i in changed['items'] if i['kind']=='membership')
        del edge['certificate'];del edge['descriptor'];edge['kind']='range'
        with self.assertRaisesRegex(ValueError,'authority'):s.verify(changed)
        record=deepcopy(s.evidence());record['events'][-1]['packet']=changed
        with self.assertRaisesRegex(ValueError,'boundary'):o.check(record)

    def test_cancelled_identity_survives_control_range_and_retirement(self):
        group=g.Group();group.commit();prepared(group);group.commit(dict(kind='CANCEL',number=1))
        group.commit(dict(kind='RETIRE',through=1));s=c.Source(group.evidence());packet=s.build(max(s.certs))
        self.assertEqual(1,len(packet['items']));self.assertEqual(4,len(packet['catalog']['identities']))
        self.assertEqual({},packet['catalog']['results']);o.check(s.evidence())

    def test_original_invalid_input_never_counts_as_capsule_rejection(self):
        s=fixture();record=deepcopy(s.input);record['events']=[e for e in record['events'] if e['event']!='receipt-force']
        with self.assertRaises(ValueError):c.Source(record)


if __name__=='__main__':unittest.main()
