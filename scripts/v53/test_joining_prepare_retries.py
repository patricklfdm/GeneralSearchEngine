"""Exact PREPARE retries reuse one forced grant, never another quorum vote."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from . import joining_network_evidence as n
from .test_joining_grant_write_chain import fixture as grant_events
from .test_joining_same_view_network import fixture as installation_fixture


def fixture():
    events=grant_events(0);own_end=len(events)-2
    sent=len(events);events.append(dict(event='SEND'))
    received=len(events);events.append(dict(event='RECEIVE'))
    start=len(events);events.extend(dict(v,node='node-2') for v in grant_events(0))
    peer_end=len(events)-2
    first=dict(kind='PREPARE',answer='PROMISE',sent=sent,received=received,
        offered=len(events)+2,delivered=None,
        request=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'),root='root',
                     ballot=dict(counter=1,proposer='node-1',incarnation='original'),
                     view='view',trace='original',sequence=1,payload=dict(promise=n.sha(b'node-1-promise'))),
        response=dict(payload=dict(basis=n.sha(b'node-2-basis'))))
    retry=copy.deepcopy(first);retry.update(sent=len(events),received=len(events)+1,
                                          offered=len(events)+3,delivered=len(events)+4)
    captures=[dict(node=node,scope='network-owner',capture='grant-captures/'+node,root='root',
                   returnEvent=end,capturedEvent=end+1,basisId=node,basisSha256=n.sha((node+'-basis').encode()),
                   ballot=first['request']['ballot']) for node,end in [('node-1',own_end),('node-2',peer_end)]]
    return events,captures,[first,retry],start


class JoiningPrepareRetryTest(unittest.TestCase):
    def check(self,data,**options):
        events,captures,rows,_=data
        def inventory(path):
            node=path.parent.name
            return {'grants.gsr':node.encode(),'sources/'+node+'/source.gscp':b'packet'}
        def journal(raw,*args):
            return [('PROMISE',raw+b'-promise',{}),('BASIS',raw+b'-basis',dict(view='view'))]
        with patch.object(n.p.captures,'collect',return_value=captures),patch.object(n.disk,'inventory',side_effect=inventory), \
             patch.object(n.disk,'journal',side_effect=journal),patch.object(n.disk.p,'decode',return_value=dict(images={})):
            return n.grants(Path('/conditional'),events,rows,**options)[0]

    def unanswered(self):
        data=fixture();first=data[2][0];data[0][first['sent']]['bytes']='original'
        failure=dict(kind='PREPARE',sent=first['sent'],received=first['received'],
                     serverFailed=first['offered'],finished=first['offered']+1,
                     responseOffered=False,clientReason='IO',serverReason='PROTOCOL')
        data[2].clear()
        return data,first,failure

    def test_received_prepare_can_force_grant_without_offering_any_vote(self):
        data,first,failure=self.unanswered()
        with patch.object(n,'wire',return_value=('PREPARE',first['request'])):
            counts=self.check(data,failed=[failure])
        self.assertEqual(2,counts['forcedGrants']);self.assertEqual(0,counts['boundPromiseReplies'])
        self.assertEqual(1,counts['responseLessPreparedGrants'])
        self.assertEqual([],n.delivered_promises(data[2],'node-1','unused',999))

    def test_failed_original_trigger_and_later_offered_retry_remain_one_grant(self):
        data,first,failure=self.unanswered();reply=copy.deepcopy(first)
        reply.update(sent=len(data[0]),received=len(data[0])+1,offered=first['offered']+3,delivered=first['offered']+4)
        data[2].append(reply)
        with patch.object(n,'wire',return_value=('PREPARE',first['request'])):counts=self.check(data,failed=[failure])
        self.assertEqual(dict(forcedGrants=2,boundPromiseReplies=1),counts)

    def test_unreceived_retry_cannot_replace_or_invalidate_the_real_trigger(self):
        data=fixture();first=data[2][0];sent=len(data[0]);data[0].append(dict(event='SEND',bytes='original'))
        failure=dict(kind='PREPARE',sent=sent,received=None,serverFailed=None,responseOffered=False)
        with patch.object(n,'wire',return_value=('PREPARE',first['request'])):
            self.assertEqual(dict(forcedGrants=2,boundPromiseReplies=1),self.check(data,failed=[failure]))

    def test_unanswered_prepare_requires_original_trigger_authority_and_terminal(self):
        for change in ('no-read','late-read','early-failure','promise','view','response-offered','no-terminal','wrong-root'):
            data,first,failure=self.unanswered()
            if change=='no-read':failure['received']=None
            elif change=='late-read':failure['received']=data[3]+1
            elif change=='early-failure':failure['serverFailed']=data[1][1]['capturedEvent']
            elif change=='promise':first['request']['payload']['promise']='foreign'
            elif change=='view':first['request']['view']='foreign'
            elif change=='wrong-root':first['request']['root']='foreign'
            elif change=='response-offered':failure['responseOffered']=True
            else:failure['serverFailed']=None
            with self.subTest(change=change),patch.object(n,'wire',return_value=('PREPARE',first['request'])),self.assertRaises(ValueError):
                self.check(data,failed=[failure])

    def test_failed_delivery_then_exact_retry_share_one_original_force_chain(self):
        result=self.check(fixture())
        self.assertEqual(dict(forcedGrants=2,boundPromiseReplies=1),result)

    def test_response_offer_order_does_not_select_a_different_trigger(self):
        data=fixture();a,b=data[2];a['offered'],b['offered']=b['offered'],a['offered']
        data[2].reverse()
        self.assertEqual(1,self.check(data)['boundPromiseReplies'])

    def test_multiple_deliveries_still_bind_one_peer_grant(self):
        data=fixture();data[2][0]['delivered']=data[2][0]['offered']+1
        self.assertEqual(1,self.check(data)['boundPromiseReplies'])

    def test_retry_without_original_trigger_cannot_borrow_a_prior_capture(self):
        data=fixture();data[2].pop(0)
        with self.assertRaisesRegex(ValueError,'^joining network force before promise reply$'):self.check(data)

    def test_each_reply_needs_original_force_and_each_send_needs_local_capture(self):
        for field,value in [('offered',fixture()[1][1]['capturedEvent']),('sent',0)]:
            data=fixture();data[2][1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'^joining network force before promise reply$'):self.check(data)

    def test_changed_context_or_authority_cannot_be_an_exact_retry(self):
        for field,value in [('trace','changed'),('sequence',2),('root','other'),('view','other'),
                            ('payload',dict(promise='f'*64)),('sender',dict(node='foreign')),
                            ('recipient',dict(node='foreign')),('ballot',dict(counter=2,proposer='node-1',incarnation='original'))]:
            data=fixture();data[2][1]['request'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.check(data)
        data=fixture();data[2][1]['response']['payload']['basis']='f'*64
        with self.assertRaises(ValueError):self.check(data)

    def test_missing_or_duplicate_original_force_still_rejects(self):
        for change in ('missing','duplicate'):
            data=fixture();events=data[0];at=next(i for i in range(data[3],len(events)) if events[i]['event']=='PROMISE_FORCED')
            events[at]['event']='PROMISE_WRITTEN' if change=='missing' else 'BASIS_FORCED'
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'^joining network durable grant order$'):self.check(data)

    def install(self,data):
        events,rows,replay,bases,raw,members=data
        with patch.object(n.disk,'inventory',side_effect=lambda p:p),patch.object(n.disk,'current',return_value=('',members,{})):
            return n.installations('/conditional',events,rows,replay,bases,recovery=raw)

    def test_selected_grant_uses_delivery_not_failed_or_later_duplicate(self):
        data=installation_fixture();reply=data[1][0]
        data[1].insert(0,dict(reply,delivered=None))
        data[1].append(dict(reply,delivered=len(data[0])-1))
        self.assertEqual(2,self.install(data)['forcedSelections'])

    def test_only_failed_or_late_deliveries_cannot_authorize_selection(self):
        for delivered in (None,True,'1',len(installation_fixture()[0])-1):
            data=installation_fixture();data[1][0]['delivered']=delivered
            with self.subTest(delivered=delivered),self.assertRaisesRegex(ValueError,'^joining network selection before delivered promises$'):
                self.install(data)


if __name__=='__main__':unittest.main()
