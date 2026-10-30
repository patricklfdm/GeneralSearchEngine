import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import automatic_restart_network as a


class AutomaticRestartNetworkTest(unittest.TestCase):
    def test_invalid_original_cannot_be_counted_as_a_successful_negative(self):
        with patch.object(a.p,'validate',side_effect=ValueError('bad original')), patch.object(a.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):a.qualify('unused')
            copied.assert_not_called()

    def test_link_is_rejected_before_network_interpretation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'real').write_bytes(b'original');(root/'linked').symlink_to('real')
            with patch.object(a.x,'exchanges') as exchanges:
                with self.assertRaisesRegex(ValueError,'^automatic restart regular inventory$'):a.validate(root)
                exchanges.assert_not_called()

    def test_identical_replies_allow_at_most_the_real_number_of_deliveries(self):
        raw=b'identical original response';digest=a.e.digest(raw)
        received=dict(node='node-1',event='NETWORK_RECEIVED',kind='ACCEPT_ACK',response=digest)
        entry=dict(offered=0,request=dict(sender=dict(node='node-1')),answer='ACCEPT_ACK',
            row=dict(response=base64.b64encode(raw).decode()))
        event=dict(node='node-2',event='WIRE_RESPONSE')
        a.deliveries([event,received],[entry])
        # An undelivered duplicate does not invent an extra receive callback.
        a.deliveries([event,event,received],[entry,dict(entry,offered=1)])
        with self.assertRaisesRegex(ValueError,'^restart network delivery without original response$'):
            a.deliveries([event,received,received],[entry])
        a.deliveries([event,event,received,received],[entry,dict(entry,offered=1)])

    def test_future_or_unknown_response_cannot_back_delivery(self):
        raw=b'later reply';digest=a.e.digest(raw)
        received=dict(node='node-1',event='NETWORK_RECEIVED',kind='ACCEPT_ACK',response=digest)
        entry=dict(offered=1,request=dict(sender=dict(node='node-1')),answer='ACCEPT_ACK',
            row=dict(response=base64.b64encode(raw).decode()))
        for events,entries in [([received,dict(event='WIRE_RESPONSE')],[entry]),([received],[])]:
            with self.subTest(events=events),self.assertRaisesRegex(ValueError,'^restart network delivery without original response$'):
                a.deliveries(events,entries)


if __name__=='__main__':unittest.main()
