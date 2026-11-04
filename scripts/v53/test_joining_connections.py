"""Connection integration keeps all failures and original physical event positions."""
import copy
import unittest
from . import joining_connections as e
from . import joining_phase_evidence as phase
from . import joining_transcript as transcript
from . import test_connection_transcript as fixture


def joined(old_receiver=False):
    events,wires,ids,root=fixture.overlap()
    for row in events:
        old=row['node']=='node-1' or old_receiver
        if not old:continue
        row.pop('scope')
        if row['event']==e.t.SEND:row['event']='NETWORK_SEND'
        elif row['event']==e.t.READ:row['event']='NETWORK_REQUEST'
        elif row['event']==e.t.OFFER:
            row['event']='WIRE_RESPONSE';row.pop('kind');row.pop('responseKind')
        elif row['event']==e.t.DELIVER:
            row['event']='NETWORK_RECEIVED';row['kind']=row.pop('responseKind');row.pop('request')
    events.insert(2,dict(node='node-2',event='ACTUAL_STORAGE_FORCE'))
    events.insert(0,dict(node='node-1',event='CURRENT_VALIDATED'))
    return events,wires,ids,root


class JoiningConnectionsTest(unittest.TestCase):
    def test_old_and_scoped_callbacks_bind_without_renumbering_physical_events(self):
        for old in (False,True):
            events,wires,ids,root=joined(old);result=e.replay(events,wires,ids,root)
            lost,good=result['rows'];failed=result['failed'][0]
            self.assertEqual((1,2,7,None),tuple(lost[k] for k in ('sent','received','offered','delivered')))
            self.assertEqual((5,6,9,10),tuple(good[k] for k in ('sent','received','offered','delivered')))
            self.assertEqual((4,8,8),tuple(failed[k] for k in ('clientFailed','serverFailed','finished')))
            self.assertEqual(events[8]['connection']['id'],failed['serverConnection'])

    def test_phase_reader_and_whole_transcript_share_exact_attempt_binding(self):
        for old in (False,True):
            values=joined(old);failed=[];rows=transcript.causal(*values,failed=failed)
            self.assertEqual(phase.exchanges(*values),rows);self.assertEqual(1,len(failed))
            self.assertTrue(failed[0]['responseOffered']);self.assertIsNone(rows[0]['delivered']);self.assertEqual(10,rows[1]['delivered'])
            self.assertEqual([],transcript.causal(*values,transfer_only=True))

    def test_metadata_cannot_be_partially_stripped_or_fall_back_to_fifo(self):
        for where in ('send','receiver','offer','delivered','wire'):
            events,wires,ids,root=joined(True)
            row=wires[0] if where=='wire' else events[dict(send=1,receiver=2,offer=7,delivered=10)[where]]
            del row['connection']
            with self.subTest(where=where),self.assertRaisesRegex(ValueError,'complete .* metadata'):
                transcript.causal(events,wires,ids,root)

    def test_connection_format_rejects_legacy_extra_fields(self):
        for at in (1,2,7,10):
            events,wires,ids,root=joined(True);events[at]['success']=True
            with self.subTest(at=at),self.assertRaisesRegex(ValueError,'old .* shape'):e.replay(events,wires,ids,root)

    def test_unknown_delivery_connection_cannot_borrow_a_request_digest(self):
        events,wires,ids,root=joined();events[-1]['connection']['id']='00000000-0000-0000-0000-000000000099'
        with self.assertRaisesRegex(ValueError,'old delivery shape'):e.replay(events,wires,ids,root)

    def test_failed_delivery_is_not_a_declared_transfer_loss(self):
        events,wires,ids,root=joined();kind,q=e.t.wire(wires[0]['request'])
        for row in wires:row['withheld']=True
        with self.assertRaisesRegex(ValueError,'original response shape'):e.replay(events,wires,ids,root)

    def test_explicit_event_positions_must_be_complete_ordered_and_unique(self):
        events,wires,ids,root=fixture.trace()
        for positions in ([0,1,2],[0,2,1,3],[0,1,1,3],[0,1,2,True]):
            with self.subTest(positions=positions),self.assertRaisesRegex(ValueError,'original event positions'):
                e.t.replay(events,wires,ids,root,positions=positions)
        result=e.t.replay(events,wires,ids,root,positions=[10,20,30,40]);self.assertEqual(40,result['rows'][0]['delivered'])

    def test_same_uuid_on_other_owner_or_changed_packet_still_refuses(self):
        events,wires,ids,root=joined();events[8]['node']='node-3'
        with self.assertRaisesRegex(ValueError,'invocation changed'):phase.exchanges(events,wires,ids,root)
        events,wires,ids,root=joined();wires[0]['response']=wires[0]['request']
        with self.assertRaisesRegex(ValueError,'original response binding'):phase.exchanges(events,wires,ids,root)


if __name__=='__main__':unittest.main()
