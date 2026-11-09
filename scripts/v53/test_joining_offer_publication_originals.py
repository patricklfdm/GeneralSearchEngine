"""Retained original components; not a whole native history qualification."""
import base64
import gzip
import json
from pathlib import Path
import unittest
from . import joining_aborted_prefix as prefix
from . import joining_abandoned_offer as offers
from . import joining_phase_evidence as phase
from . import joining_transcript as transfer


def fixture():
    def decode(value):
        if isinstance(value,dict):
            if set(value)=={'$bytes'}:return base64.b64decode(value['$bytes'],validate=True)
            if set(value)=={'$tuple'}:return tuple(decode(v) for v in value['$tuple'])
            return {k:decode(v) for k,v in value.items()}
        if isinstance(value,list):return [decode(v) for v in value]
        return value
    return decode(json.loads(gzip.decompress((Path(__file__).parent/'fixtures/profile-offer-publication.json.gz').read_bytes())))


class JoiningOfferPublicationOriginalTest(unittest.TestCase):
    def test_original_first_publish_response_does_not_precede_the_retry_send(self):
        data=fixture()['publication'];rows=data['rows']
        self.assertEqual([23203,23397],phase.publication_sends(data['events'],rows,0))
        self.assertIsNone(rows[0]['delivered']);self.assertEqual(23401,rows[1]['delivered'])
        self.assertLess(rows[0]['offered'],rows[1]['sent'])

    def test_original_revoked_manifest_offer_has_zero_content_and_three_terminals(self):
        data=fixture()['offer'];prefix.bind(data['events'],data['result']);contents=[]
        counts=transfer.transfers(data['result']['rows'],contents=contents)
        self.assertEqual([],contents);self.assertEqual(0,counts['committedTransfers'])
        receipt=offers.authorize(data['result']['rows'],data['windows'])
        self.assertEqual(1,len(receipt));self.assertEqual(3,receipt[0]['terminalAttempts'])
        self.assertEqual(30637,receipt[0]['selector']);self.assertEqual(0,receipt[0]['receivedBytes'])

    def test_original_projection_cannot_drop_failure_or_forge_selector_and_manifest(self):
        for change in ('terminal','selector','manifest','continued'):
            data=fixture()['offer'];result=data['result']
            if change=='terminal':result['failed'][0]['serverFailed']=None
            elif change=='selector':data['events'][30637]['node']='node-3'
            elif change=='manifest':data['windows'][0]['manifest']=b'foreign'
            else:data['events'].append(dict(data['events'][result['failed'][-1]['sent']]))
            with self.subTest(change=change),self.assertRaises(ValueError):
                prefix.bind(data['events'],result);transfer.transfers(result['rows'])
                offers.authorize(result['rows'],data['windows'])


if __name__=='__main__':unittest.main()
