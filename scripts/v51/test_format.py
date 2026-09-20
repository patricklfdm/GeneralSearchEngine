import base64
from copy import deepcopy
import hashlib
import json
import struct
import unittest
from . import fixtures, format_encoder as encoder, format_inspector as inspector


def reframe(raw, *, minor=None, kind=None, flags=None, body=None):
    prefix=bytearray(raw[:16])
    if minor is not None:struct.pack_into('>H',prefix,6,minor)
    if kind is not None:struct.pack_into('>H',prefix,8,kind)
    if flags is not None:struct.pack_into('>H',prefix,10,flags)
    data=raw[48:] if body is None else body
    struct.pack_into('>i',prefix,12,len(data))
    return bytes(prefix)+hashlib.sha256(prefix+data).digest()+data


class FormatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=json.loads((fixtures.ROOT/'format-fixtures.json').read_text())

    def test_frozen_positive_inventory_and_independent_encoder_agree(self):
        result=fixtures.validate();self.assertEqual((25,19),(result['storageRecords'],result['wireMessages']))

    def test_all_storage_kinds_reject_unknown_old_versions_flags_and_trailing_bytes(self):
        for name,encoded in self.fixture['storage'].items():
            raw=base64.b64decode(encoded)
            for bad in (reframe(raw,minor=0),reframe(raw,minor=1),reframe(raw,minor=3),
                        reframe(raw,kind=23),reframe(raw,flags=1),raw+b'\0',raw[:-1]):
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):inspector.inspect(bad,name)

    def test_wire_mismatch_reserved_kind_foreign_actor_and_recomputed_checksum_negatives(self):
        for name,encoded in self.fixture['wire'].items():
            raw=base64.b64decode(encoded)
            for bad in (reframe(raw,minor=1),reframe(raw,minor=3),reframe(raw,kind=13),reframe(raw,flags=1)):
                with self.assertRaises(ValueError):inspector.wire(bad,self.fixture['manifest'])
            message=json.loads(raw[48:])
            for field,value in [('protocol','gse-replication/1.1'),('manifestDigest','ff'*32),
                                ('proposer','node-2'),('sender','foreign'),('extra',1)]:
                altered=dict(message,**{field:value})
                with self.assertRaises(ValueError):inspector.wire(reframe(raw,body=encoder.canonical(altered)),self.fixture['manifest'])

    def test_changed_payload_receipts_origin_and_snapshot_sequence_reject(self):
        cases=[('ENTRY','payloadDigest','00'*32),('ENTRY','operation',255),
               ('ACCEPT','epoch',1),('ACCEPT','entryDigest','00'*32),
               ('SNAPSHOT','applicationSequence',99),('SELECTED','sourceBallot',None)]
        for name,field,value in cases:
            raw=base64.b64decode(self.fixture['storage'][name]);decoded=inspector.inspect(raw,name);decoded[field]=value
            with self.subTest(name=name,field=field):
                with self.assertRaises(ValueError):inspector.inspect(encoder.encode(name,decoded),name)
        p=inspector.inspect(base64.b64decode(self.fixture['storage']['PROOF']),'PROOF')
        for receipts in ([p['receipts'][0],p['receipts'][0]],list(reversed(p['receipts'])),
                         [dict(p['receipts'][0],digest='00'*32),p['receipts'][1]]):
            bad=dict(p,receipts=receipts)
            with self.assertRaises(ValueError):inspector.inspect(encoder.encode('PROOF',bad),'PROOF')

    def test_unknown_duplicate_fields_bool_as_integer_and_invalid_optional_reject(self):
        raw=base64.b64decode(self.fixture['storage']['MANIFEST'])
        for value in (dict(self.fixture['manifest'],extra=0),dict(self.fixture['manifest'],baseSequence=True)):
            value.pop('digest',None)
            with self.assertRaises(ValueError):inspector.inspect(encoder.encode('MANIFEST',value),'MANIFEST')
        with self.assertRaises(ValueError):inspector.inspect(reframe(raw,body=b'{"mode":"AUTOMATIC","mode":"AUTOMATIC"}'),'MANIFEST')
        raw=base64.b64decode(self.fixture['storage']['PROMISE']);body=bytearray(raw[48:]);body[40]=2
        with self.assertRaises(ValueError):inspector.inspect(reframe(raw,body=bytes(body)),'PROMISE')

    def test_bootstrap_receipt_and_two_source_floor_are_bound(self):
        for name,key in [('RECEIPT','preparations'),('FLOOR','sources')]:
            value=inspector.inspect(base64.b64decode(self.fixture['storage'][name]),name)
            value[key][-1]=value[key][0]
            with self.assertRaises(ValueError):inspector.inspect(encoder.encode(name,value),name)
        plan=inspector.inspect(base64.b64decode(self.fixture['storage']['PLAN']),'PLAN')
        for field,value in [('maxFrameBytes',1024),('maxInFlightPerPeer',1),('requestTimeoutMillis',300001)]:
            changed=deepcopy(plan);changed['targets'][0]['bounds'][field]=value
            with self.assertRaises(ValueError):inspector.inspect(encoder.encode('PLAN',changed),'PLAN')

    def test_valid_nested_checksum_cannot_change_wire_manifest_or_quorum_members(self):
        raw=base64.b64decode(self.fixture['wire']['ACCEPT']);message=json.loads(raw[48:])
        acceptance=inspector.inspect(base64.b64decode(message['payload']['acceptance']),'ACCEPT')
        entry=inspector.inspect(base64.b64decode(acceptance['entry']),'ENTRY')
        entry['manifestDigest']='ff'*32;new_entry=encoder.encode('ENTRY',entry)
        acceptance.update(manifestDigest='ff'*32,entry=fixtures.B64(new_entry),entryDigest=new_entry[16:48].hex())
        message['payload']['acceptance']=fixtures.B64(encoder.encode('ACCEPT',acceptance))
        with self.assertRaisesRegex(ValueError,'manifest identity'):
            inspector.wire(reframe(raw,body=encoder.canonical(message)),self.fixture['manifest'])
        proof=inspector.inspect(base64.b64decode(self.fixture['storage']['PROOF']),'PROOF')
        proof['receipts']=[dict(voter=n,digest=inspector.receipt('ACCEPT_ACK',proof['manifestDigest'],n,
            proof['epoch'],proof['proposer'],proof['incarnation'],proof['index'],proof['entryDigest'])) for n in ('foreign','node-1')]
        with self.assertRaisesRegex(ValueError,'voter membership'):
            inspector.contextual_frame(encoder.encode('PROOF',proof),'PROOF',self.fixture['manifest'])

if __name__=='__main__':unittest.main()
