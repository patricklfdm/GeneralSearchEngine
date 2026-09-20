"""Frozen recovery exchange vectors and independently rejected malformed packets."""
import base64
import hashlib
import json
import unittest
from . import format_encoder as e,format_inspector as f,rejoin_evidence


class RejoinFormatTest(unittest.TestCase):
    def test_vectors_and_checksums(self):
        root=e.CATALOG.parent;manifest=json.loads((root/'format-fixtures.json').read_text())['manifest']
        for line in (root/'rejoin-wire-fixtures.sha256').read_text().splitlines():
            digest,name=line.split('  ');self.assertEqual(digest,hashlib.sha256((root/name).read_bytes()).hexdigest())
        for name,encoded in json.loads((root/'rejoin-wire-fixtures.json').read_text()).items():
            raw=base64.b64decode(encoded);message=f.wire(raw,manifest);payload=message.pop('payload');kind=message.pop('type')
            with self.subTest(name=name):self.assertEqual(raw,e.wire(kind,message,payload))

    def test_changed_chunk_and_install_direction_reject(self):
        root=e.CATALOG.parent;manifest=json.loads((root/'format-fixtures.json').read_text())['manifest'];vectors=json.loads((root/'rejoin-wire-fixtures.json').read_text())
        for name in ('SOURCE_CHUNK-response','REJOIN_INSTALL-request'):
            message=json.loads(base64.b64decode(vectors[name])[48:])
            if name.startswith('SOURCE'):message['payload']['chunk']=base64.b64encode(b'forged').decode()
            else:message['sender'],message['recipient']=message['recipient'],message['sender']
            with self.assertRaises(ValueError):f.wire(e.frame(e.runtime_catalog()['wire'][message['type']]['id'],e.canonical(message),b'GSRP'),manifest)

    def test_source_inventory_cannot_escape_or_duplicate(self):
        for names in (['../current.gsr']*5,['current.gsr']*5):
            with self.assertRaises(ValueError):rejoin_evidence.packet({'files':[dict(name=n,bytes='') for n in names]}, {})


if __name__=='__main__':unittest.main()
