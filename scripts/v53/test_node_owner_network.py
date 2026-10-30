import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import node_owner_network as n


class NodeOwnerNetworkTest(unittest.TestCase):
    def test_bad_physical_original_cannot_be_used_as_negative_success(self):
        with patch.object(n.p,'validate',side_effect=ValueError('bad original')),patch.object(n.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'^bad original$'):n.qualify('unused')
            copied.assert_not_called()

    def test_link_is_rejected_before_network_interpretation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'original').write_bytes(b'original');(root/'link').symlink_to('original')
            with patch.object(n.a.x,'exchanges') as exchanges:
                with self.assertRaisesRegex(ValueError,'regular inventory'):n.validate(root)
                exchanges.assert_not_called()

    def fixture(self):
        catalog=n.f.catalog();request=n.f.sample(catalog['wire']['STATUS_PROBE']['schema'],catalog['types'])
        request['recipient']=n.f.sample(catalog['types']['identity'],catalog['types'],2)
        raw=n.f.encode('wire','STATUS_PROBE',request);digest=n.e.digest(raw)
        identities={v['node']:v for v in (request['sender'],request['recipient'])}
        send=dict(node=request['sender']['node'],event='NETWORK_SEND',kind='STATUS_PROBE',request=digest,bytes=base64.b64encode(raw).decode())
        received=dict(node=request['recipient']['node'],event='NETWORK_REQUEST',kind='STATUS_PROBE',request=digest)
        entry=dict(offered=2,row=dict(request=base64.b64encode(raw).decode()))
        return request,identities,send,received,entry

    def test_silent_write_is_not_a_response_and_duplicate_response_needs_another_receipt(self):
        request,identities,send,received,entry=self.fixture()
        def run(events,entries):return n.request_attempts(events,entries,identities,request['root'],request['view'])
        values=run([send],[]);self.assertIsNone(next(iter(values.values()))[0]['response'])
        run([send,received,dict(event='WIRE_RESPONSE')],[entry])
        with self.assertRaisesRegex(ValueError,'response without original receipt'):
            run([send,received,dict(event='WIRE_RESPONSE'),dict(event='WIRE_RESPONSE')],[entry,dict(entry,offered=3)])

    def test_four_identical_sends_and_receive_before_send_are_rejected(self):
        request,identities,send,received,entry=self.fixture()
        for events,reason in [([send]*4,'bounded identical writes'),([received,send],'received request without write')]:
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):
                n.request_attempts(events,[],identities,request['root'],request['view'])

    def test_response_cannot_cross_an_already_completed_phase(self):
        rows={'original':[dict(at=1,received=3,response=4,request=dict(sender=dict(node='node-2')))]}
        with self.assertRaisesRegex(ValueError,'crosses completed phase'):
            n.request_phases(rows,[(-1,2),(2,5)],[{}]*5)


if __name__=='__main__':unittest.main()
