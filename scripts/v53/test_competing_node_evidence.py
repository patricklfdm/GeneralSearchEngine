"""Whole-history boundaries and raw send/receive conservation."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import competing_node_evidence as p
from . import competing_node_network as n
from . import competing_node_negatives as negatives


def conversation():
    identities={name:dict(node=name,storage='00000000-0000-0000-0000-00000000000'+str(i),host='127.0.0.1',port=9000+i)
                for i,name in enumerate(('node-1','node-2','node-3'),1)}
    root='a'*64;view='b'*64;leader=identities['node-1'];peer=identities['node-2']
    cut=dict(index=0,entry='c'*64,view=dict(generation=0,old=list(identities),new=list(identities),operation=None))
    request=dict(root=root,view=view,ballot=dict(counter=2,proposer='node-1',incarnation=leader['storage']),sender=leader,recipient=peer,
        trace='00000000-0000-0000-0000-000000000004',sequence=1,payload=dict(cut=cut,activated=True))
    response=dict(request,sender=peer,recipient=leader,payload=dict(cut=cut))
    q=p.f.encode('wire','HEARTBEAT',request);r=p.f.encode('wire','HEARTBEAT_ACK',response)
    events=[dict(node='node-1',event='NETWORK_SEND',kind='HEARTBEAT',request=p.e.digest(q),bytes=base64.b64encode(q).decode()),
        dict(node='node-2',event='NETWORK_REQUEST',kind='HEARTBEAT',request=p.e.digest(q)),
        dict(node='node-2',event='WIRE_RESPONSE',request=p.e.digest(q),response=p.e.digest(r)),
        dict(node='node-1',event='NETWORK_RECEIVED',kind='HEARTBEAT_ACK',response=p.e.digest(r))]
    entry=dict(kind='HEARTBEAT',request=request,answer='HEARTBEAT_ACK',response=response,offered=2,deliveries=[3],
        row=dict(request=base64.b64encode(q).decode(),response=base64.b64encode(r).decode()))
    return events,[entry],identities,dict(root=root,view=view)


class CompetingNodeEvidenceTest(unittest.TestCase):
    def test_original_failure_stops_before_any_negative_copy(self):
        with patch.object(p,'validate',side_effect=ValueError('invalid original')) as validate,patch.object(p.shutil,'copytree') as copy:
            with self.assertRaisesRegex(ValueError,'^invalid original$'):p.qualify('/original')
            validate.assert_called_once_with(Path('/original'));copy.assert_not_called()

    def test_linked_or_incomplete_history_cannot_use_producer_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'result.json').write_text('{"status":"PASS"}')
            with patch.object(p,'physical') as physical:
                with self.assertRaises(ValueError):p.validate(root)
                (root/'link').symlink_to('/missing')
                with self.assertRaisesRegex(ValueError,'regular inventory'):p.validate(root)
                physical.assert_not_called()

    def test_unrelated_rejection_cannot_count_as_expected_negative(self):
        original=dict(proposer='node-1',selected=['node-1','node-2'])
        with patch.object(p,'validate',side_effect=[original,ValueError('unrelated failure')]),patch.object(p.shutil,'copytree'),patch.object(negatives,'mutate'):
            with self.assertRaisesRegex(ValueError,'^competing unrelated negative initial-image: unrelated failure$'):p.qualify('/original')

    def test_delivery_requires_a_prior_original_send_request_and_response(self):
        events,entries,ids,selection=conversation();result=n.raw_sends(events,entries,ids,selection)
        self.assertFalse(result[2])
        for position,reason in ((0,'request without original send'),(1,'response without original request'),(2,'delivery without original response')):
            changed=events[:position]+events[position+1:]
            # Removing a response also removes its independent wire-row binding.
            current=[] if position==2 else [dict(entries[0],offered=1,deliveries=[2])]
            with self.subTest(position=position),self.assertRaisesRegex(ValueError,reason):n.raw_sends(changed,current,ids,selection)

    def test_duplicate_delivery_never_invents_another_response(self):
        events,entries,ids,selection=conversation()
        with self.assertRaisesRegex(ValueError,'delivery without original response'):n.raw_sends([*events,events[-1]],entries,ids,selection)

    def test_failed_send_remains_unanswered_without_granting_delivery(self):
        events,_,ids,selection=conversation();by_hash,sends,unanswered=n.raw_sends(events[:1],[],ids,selection)
        self.assertEqual(set(by_hash),unanswered);self.assertEqual([0],next(iter(sends.values())))

    def test_retries_remain_byte_identical_and_bounded(self):
        events,_,ids,selection=conversation();n.raw_sends([events[0]]*3,[],ids,selection)
        with self.assertRaisesRegex(ValueError,'bounded send attempts'):n.raw_sends([events[0]]*4,[],ids,selection)
        changed=copy.deepcopy(events[0]);changed['request']='d'*64
        with self.assertRaisesRegex(ValueError,'original send binding'):n.raw_sends([changed],[],ids,selection)

    def test_sender_identity_cannot_be_relabelled(self):
        events,entries,ids,selection=conversation();events[0]['node']='node-2'
        with self.assertRaisesRegex(ValueError,'original send binding'):n.raw_sends(events,entries,ids,selection)

    def test_clock_order_is_checked_before_reconstruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'events.json').write_text('[{"event":"NODE_OPEN","node":"node-1","nanoTime":1}, {"event":"NODE_OPEN","node":"node-2","nanoTime":0}]')
            with self.assertRaisesRegex(ValueError,'monotonic owned events'):p.trace(root)

    def test_unknown_owner_work_cannot_be_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'events.json').write_text('[{"event":"UNACCOUNTED_WRITE","node":"node-1","nanoTime":1}]')
            with self.assertRaisesRegex(ValueError,'^competing unknown owner event$'):p.trace(root)


if __name__=='__main__':unittest.main()
