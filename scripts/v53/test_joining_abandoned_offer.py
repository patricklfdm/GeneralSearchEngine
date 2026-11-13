"""An original offer remains an offer, including when no byte was received."""
import unittest
from . import joining_abandoned_offer as a
from . import test_joining_export_evidence as fixture


class JoiningAbandonedOfferTest(unittest.TestCase):
    def data(self):
        windows,q=fixture.JoiningExportEvidenceTest().inputs();own=windows[1]
        reference,raw,kind=a.e.native.maintenance_generations(own['manifest'],own['members'],own['packet'])[1][0]
        offer=dict(id='object',digest=a.e.sha(raw),bytes=len(raw),kind=kind)
        payload=dict(id='object',action='REQUEST',offset=0,digest=reference,bytes='')
        row=dict(answer='SOURCE_OFFER',received=10,offered=11,request=dict(q,sequence=1,payload=payload),
                 response=dict(payload=offer),abortedPrefix=dict(offerOnly=True,selector=100,attempts=3,
                    request=dict(payload=dict(payload,digest=offer['digest']))))
        return [row],windows

    def test_offer_authenticates_manifest_without_claiming_bytes_or_copy(self):
        rows,windows=self.data();result=a.authorize(rows,windows)
        self.assertEqual(1,len(result));self.assertEqual(0,result[0]['receivedBytes'])
        self.assertEqual(0,result[0]['committedObjects']);self.assertFalse(result[0]['generationCopy'])
        self.assertNotIn('raw',result[0])

    def test_revoked_packet_offer_authenticates_packet_without_claiming_receipt(self):
        rows,windows=self.data();own=windows[1];row=rows[0];cap=own['packet']['capsule']
        row['request']['payload']['digest']=a.e.native.current_reference(cap,'retained-current-packet')
        raw=own['members']['source.gscp'];offer=row['response']['payload']
        offer.update(digest=a.e.sha(raw),bytes=len(raw),kind='CAPSULE')
        row['abortedPrefix']['request']['payload']['digest']=offer['digest']
        result=a.authorize(rows,windows)
        self.assertEqual(0,result[0]['receivedBytes']);self.assertFalse(result[0]['generationCopy'])
        self.assertEqual(a.e.sha(raw),result[0]['contentSha256']);self.assertEqual('CAPSULE',result[0]['contentKind'])
        for change in ('bytes','kind','packet','selector'):
            import copy
            changed=copy.deepcopy(rows);copies=copy.deepcopy(windows)
            if change=='bytes':changed[0]['response']['payload']['bytes']+=1
            elif change=='kind':changed[0]['response']['payload']['kind']='RECORD'
            elif change=='packet':copies[1]['members']['source.gscp']=b'wrong packet'
            else:changed[0]['abortedPrefix']['selector']+=1
            with self.subTest(change=change),self.assertRaises(ValueError):a.authorize(changed,copies)

    def test_offer_cannot_authenticate_itself_by_its_own_digest(self):
        for change in ('alias','digest','bytes','kind','selector','manifest','owner','sender','root','view','proposer','early','late','chunk'):
            rows,windows=self.data();r=rows[0];q=r['request'];offer=r['response']['payload']
            if change=='alias':q['payload']['digest']='foreign'
            elif change=='digest':offer['digest']='foreign';r['abortedPrefix']['request']['payload']['digest']='foreign'
            elif change=='bytes':offer['bytes']+=1
            elif change=='kind':offer['kind']='CAPSULE'
            elif change=='selector':r['abortedPrefix']['selector']+=1
            elif change=='manifest':windows[1]['manifest']=b'foreign'
            elif change=='owner':q['recipient']=dict(q['recipient'],storage='foreign')
            elif change=='sender':q['sender']=dict(q['sender'],storage='foreign')
            elif change in ('root','view'):q[change]='foreign'
            elif change=='proposer':q['ballot']['incarnation']='foreign'
            elif change=='early':r['received']=0
            elif change=='late':r['offered']=100
            else:r['abortedPrefix']['request']['payload']['offset']=1
            with self.subTest(change=change),self.assertRaises(ValueError):a.authorize(rows,windows)

    def test_only_physically_authenticated_offers_can_leave_content_accounting(self):
        rows,windows=self.data();offers=a.authorize(rows,windows)
        counts=dict(transferSessions=5,rejectedTransferAttempts=1,abandonedOfferSessions=1)
        self.assertEqual(3,a.content_sessions(counts,dict(abandonedGenerationOffers=offers)))
        for declared in ([],offers*2):
            with self.assertRaisesRegex(ValueError,'joining abandoned offer complete accounting'):
                a.content_sessions(counts,dict(abandonedGenerationOffers=declared))
        with self.assertRaisesRegex(ValueError,'joining abandoned offer complete accounting'):
            a.content_sessions(dict(counts,abandonedOfferSessions=0),dict(abandonedGenerationOffers=offers))


if __name__=='__main__':unittest.main()
