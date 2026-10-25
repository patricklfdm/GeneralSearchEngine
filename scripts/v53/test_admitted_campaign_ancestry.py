"""Retain the exact previously checked bridge; do not invent installation authority."""
import copy
import unittest
from unittest.mock import patch
from . import admitted_cross_view_evidence as q
from . import admitted_campaign_evidence as campaign


def fixture():
    f=q.e.f;catalog=f.catalog();types=catalog['types']
    statement=f.sample(catalog['records']['CHECKPOINT']['schema'],types)
    statement['scope']='RANGE'
    statement['start']['index']=0;statement['end']['index']=2
    raw=f.encode('records','CHECKPOINT',statement)
    packet=dict(capsule=dict(cut=statement['end'],items=[dict(statement=q.e.digest(raw))]),objects={q.e.digest(raw):raw})
    hidden=copy.deepcopy(statement['start']);hidden['index']=1;hidden['entry']='cd'*32
    bridge=f.encode('records','CHECKPOINT',dict(statement,start=hidden))
    ack=f.sample(catalog['records']['CHECKPOINT_ACK']['schema'],types)
    ack.update(cut=statement['end'],statement=q.e.digest(bridge))
    encoded=bridge+f.encode('records','CHECKPOINT_ACK',ack)
    return packet,hidden,encoded


class AdmittedCampaignAncestryTest(unittest.TestCase):
    def test_invalid_original_cannot_be_reported_as_successful_mutation(self):
        with patch.object(campaign,'validate',side_effect=ValueError('invalid original')),patch.object(campaign.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'invalid original'):campaign.qualify('missing')
            copied.assert_not_called()

    def test_retains_hidden_original_including_its_exact_ack(self):
        packet,hidden,raw=fixture()
        self.assertEqual(raw,q.retained_campaign_ancestry({'ancestry.gsr':raw},packet,hidden))

    def test_direct_original_does_not_import_unused_ancestry(self):
        packet,_,raw=fixture()
        self.assertEqual(b'',q.retained_campaign_ancestry({'ancestry.gsr':raw},packet,packet['capsule']['cut']))

    def test_absent_wrong_duplicate_and_partial_bridges_are_rejected(self):
        packet,hidden,raw=fixture()
        wrong=copy.deepcopy(hidden);wrong['entry']='ef'*32
        for members,prior in (({},hidden),({'ancestry.gsr':raw},wrong),({'ancestry.gsr':raw+raw},hidden),({'ancestry.gsr':raw[:-1]},hidden)):
            with self.subTest(members=len(members.get('ancestry.gsr',b'')),prior=prior):
                with self.assertRaises(ValueError):q.retained_campaign_ancestry(members,packet,prior)


if __name__=='__main__':unittest.main()
