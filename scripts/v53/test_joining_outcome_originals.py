"""Small original projections; whole-history acceptance requires the full reader."""
import base64
import gzip
import json
from pathlib import Path
import unittest
from . import joining_aborted_prefix as aborted
from . import joining_connections as connection
from . import joining_network_evidence as network
from . import joining_export_evidence as exports


def fixture():
    def decode(value):
        if isinstance(value,dict):
            if set(value)=={'$bytes'}:return base64.b64decode(value['$bytes'],validate=True)
            if set(value)=={'$tuple'}:return tuple(decode(v) for v in value['$tuple'])
            return {k:decode(v) for k,v in value.items()}
        if isinstance(value,list):return [decode(v) for v in value]
        return value
    return decode(json.loads(gzip.decompress((Path(__file__).parent/'fixtures/profile-outcome-boundaries.json.gz').read_bytes())))


class JoiningOutcomeOriginalTest(unittest.TestCase):
    def offered(self):
        data=fixture()['offered'];aborted.bind(data['events'],data['result']);contents=[]
        counts=network.transfers(data['result']['rows'],contents=contents)
        return data,contents,counts

    def test_original_two_commits_and_third_offer_preserve_exact_received_prefix(self):
        data,contents,counts=self.offered()
        self.assertEqual(2,counts['committedTransfers']);self.assertEqual(2,len(contents))
        claim=contents[0]['offer']['abortedPrefix'];self.assertTrue(claim['offerPending'])
        self.assertEqual(30705,claim['selector']);self.assertEqual(b'',claim['uncommittedObject']['raw'])
        self.assertEqual('current-generation',exports.authorize_generation(contents,data['windows']))
        self.assertEqual(3,len(data['result']['failed']))

    def test_original_pending_offer_cannot_change_member_extent_digest_or_lifetime(self):
        for change in ('bytes','digest','kind','window','received','prefix'):
            data,contents,_=self.offered();claim=contents[0]['offer']['abortedPrefix'];pending=claim['uncommittedObject']
            if change=='bytes':pending['offer']['response']['payload']['bytes']+=1
            elif change in ('digest','kind'):pending['offer']['response']['payload'][change]='foreign'
            elif change=='window':claim['selector']+=1
            elif change=='received':pending['raw']=b'invented'
            else:contents[1]['raw']=b'foreign'
            with self.subTest(change=change),self.assertRaises(ValueError):exports.authorize_generation(contents,data['windows'])

    def test_original_unread_promise_has_one_failure_and_no_delivered_vote(self):
        data=fixture()['asymmetric'];result=connection.replay(**data)
        self.assertEqual(1,len(result['failed']));self.assertEqual(1,len(result['rows']))
        fail=result['failed'][0];row=result['rows'][0]
        self.assertEqual(30291,fail['clientFailed']);self.assertIsNone(fail['serverFailed'])
        self.assertEqual(30946,row['offered']);self.assertIsNone(row['delivered'])
        self.assertEqual([],network.delivered_promises(result['rows'],'node-1',row['response']['payload']['basis'],len(data['events'])))

    def test_original_failed_socket_needs_its_actual_offered_frame_and_pair(self):
        for change in ('wire-missing','offer-missing','scope','route'):
            data=fixture()['asymmetric']
            if change=='wire-missing':data['wires'].clear()
            elif change=='offer-missing':data['events'][30946]=dict(event='OMITTED_FROM_COMPONENT_FIXTURE')
            elif change=='scope':data['events'][30946]['scope']='foreign-lifetime'
            else:data['wires'][0]['connection']['remote']['port']+=1
            with self.subTest(change=change),self.assertRaises(ValueError):connection.replay(**data)


if __name__=='__main__':unittest.main()
