"""Bound discovery claims; these are not new native experiment receipts."""
import copy
import unittest
from . import competing_discovery_evidence as e


def fixture():
    ballot=dict(counter=1,proposer='node-1',incarnation='original')
    cut=dict(index=0)
    q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),ballot=ballot,sequence=1,payload=dict(nonce='original'))
    row=dict(sent=20,received=21,offered=22,delivered=23,request=q,answer='STATUS',
             response=dict(payload=dict(cut=cut,nonce='original',ready=False)))
    return dict(node='node-1',prior=copy.deepcopy(ballot),begin=10,closed=100,grant=30,stop=50,
                peers=['node-2','node-3'],cuts={'node-2':cut,'node-3':cut},rows=[row])


class CompetingDiscoveryEvidenceTest(unittest.TestCase):
    def test_delivery_binds_to_first_round_before_higher_grant_without_voting(self):
        value=fixture();before=copy.deepcopy(value)
        self.assertEqual(dict(node='node-1',probes=1,peers=['node-2'],localReservationCreated=False,localGrantCreated=False),e.bind(value))
        self.assertEqual(before,value)

    def test_each_negative_hits_its_specific_guard(self):
        for name,reason in e.NEGATIVES.items():
            value=fixture();e.mutate(value,name)
            with self.subTest(case=name),self.assertRaisesRegex(ValueError,reason):e.bind(value)

    def test_unknown_response_or_extra_attempt_cannot_supply_discovery(self):
        for mode in ('cut','ballot','sequence','answer','attempts','missing-delivery','closed'):
            value=fixture();row=value['rows'][0]
            if mode=='cut':row['response']['payload']['cut']={'index':1}
            elif mode=='ballot':row['request']['ballot']['proposer']='other'
            elif mode=='sequence':row['request']['sequence']=2
            elif mode=='answer':row['answer']='PROMISE'
            elif mode=='attempts':value['rows']*=4
            elif mode=='closed':value['closed']=value['stop']-1
            else:row['delivered']=None
            with self.subTest(mode=mode),self.assertRaises(ValueError):e.bind(value)


if __name__=='__main__':unittest.main()
