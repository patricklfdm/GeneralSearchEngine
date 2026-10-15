"""The crossing promise must lie strictly within the observed hold interval."""
import unittest
from unittest.mock import patch
from . import public_read_protocol_evidence as p


class ProtocolReadEvidenceTest(unittest.TestCase):
    def promise(self,order):return dict(event='FORCE',kind='PROMISE',order=order,record='AA==')
    def test_real_higher_promise_inside_both_edges_is_required(self):
        with patch.object(p.e.physical.f,'inspect',return_value=dict(epoch=9)):
            row=self.promise(15);self.assertEqual([row],p.crossing([row],8,10,20))
            for at in (9,10,20,21):
                with self.subTest(at=at),self.assertRaisesRegex(ValueError,'crossing higher promise'):
                    p.crossing([self.promise(at)],8,10,20)

    def test_equal_or_lower_ballot_cannot_explain_fencing(self):
        for epoch in (7,8):
            with self.subTest(epoch=epoch),patch.object(p.e.physical.f,'inspect',return_value=dict(epoch=epoch)):
                with self.assertRaisesRegex(ValueError,'crossing higher promise'):p.crossing([self.promise(15)],8,10,20)

    def test_status_or_wire_claim_cannot_replace_durable_promise(self):
        for event,kind in (('REPLY','PROMISE'),('FORCE','PROOF'),('STATUS','PROMISE')):
            row=dict(self.promise(15),event=event,kind=kind)
            with self.subTest(event=event),patch.object(p.e.physical.f,'inspect') as parse:
                with self.assertRaisesRegex(ValueError,'crossing higher promise'):p.crossing([row],8,10,20)
                parse.assert_not_called()

    def test_unknown_schedule_never_qualifies(self):
        with self.assertRaisesRegex(ValueError,'unknown public read protocol schedule'):p.schedule(None,'anything',{},[],[])


if __name__=='__main__':unittest.main()
