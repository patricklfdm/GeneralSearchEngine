"""Additive runtime wire fixtures, independent rejection and unchanged Phase 1 bytes."""
import base64
import hashlib
import json
import unittest
from . import format_encoder as e,format_inspector as f


class RuntimeWireTest(unittest.TestCase):
    def test_frozen_extension_and_original_catalog_projection(self):
        root=e.CATALOG.parent
        for line in (root/'runtime-wire-fixtures.sha256').read_text().splitlines():
            digest,name=line.split('  ');self.assertEqual(digest,hashlib.sha256((root/name).read_bytes()).hexdigest())
        manifest=json.loads((root/'format-fixtures.json').read_text())['manifest']
        fixture=json.loads((root/'runtime-wire-fixtures.json').read_text())
        for name in ('request','response'):
            raw=base64.b64decode(fixture[name]);message=f.wire(raw,manifest);payload=message.pop('payload');kind=message.pop('type')
            self.assertEqual(raw,e.wire(kind,message,payload))
        original=e.catalog();runtime=e.runtime_catalog()
        self.assertEqual(original['wire'],{k:v for k,v in runtime['wire'].items() if k in original['wire']})

    def test_changed_basis_and_ballot_reject_even_with_recomputed_checksum(self):
        root=e.CATALOG.parent;manifest=json.loads((root/'format-fixtures.json').read_text())['manifest']
        fixture=json.loads((root/'runtime-wire-fixtures.json').read_text())
        for mutation in ('swapped','duplicate','ballot','direction'):
            message=json.loads(base64.b64decode(fixture['request'])[48:]);payload=message['payload']
            if mutation=='swapped':payload['bases'].reverse()
            elif mutation=='duplicate':payload['bases'][1]=payload['bases'][0]
            elif mutation=='ballot':message['incarnationId']='22222222-2222-2222-2222-222222222222'
            else:message['sender'],message['recipient']=message['recipient'],message['sender']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):f.wire(e.frame(24,e.canonical(message),b'GSRP'),manifest)
