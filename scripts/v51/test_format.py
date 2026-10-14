import base64
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
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

class CatalogReuseTest(unittest.TestCase):
    def setUp(self):
        original=inspector.CATALOG.parent
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name)
        for name in ('format-catalog.json','bootstrap-catalog.json','runtime-wire-extension.json','rejoin-wire-extension.json'):
            (self.root/name).write_bytes((original/name).read_bytes())
        for name,value in (('CATALOG',self.root/'format-catalog.json'),('WIRE_EXTENSIONS',tuple(self.root/n for n in ('runtime-wire-extension.json','rejoin-wire-extension.json')))):
            override=patch.object(inspector,name,value);override.start();self.addCleanup(override.stop)
        for cache in (inspector._records,inspector._bootstrap_records,inspector._wire_catalog):
            cache.cache_clear();self.addCleanup(cache.cache_clear)
        fixture=json.loads((original/'format-fixtures.json').read_bytes());self.manifest=fixture['manifest']
        self.genesis=base64.b64decode(fixture['storage']['GENESIS'])
        self.bootstrap=encoder.frame(28,encoder.canonical({'descriptor':''}))
        self.runtime=base64.b64decode(json.loads((original/'runtime-wire-fixtures.json').read_bytes())['request'])
        self.rejoin=base64.b64decode(json.loads((original/'rejoin-wire-fixtures.json').read_bytes())['SOURCE_OFFER-request'])

    def cases(self):
        return (
            ('format-catalog.json',lambda:inspector.inspect(self.genesis,'GENESIS')),
            ('bootstrap-catalog.json',lambda:inspector.inspect(self.bootstrap,'BOOTSTRAP_BINDING')),
            ('runtime-wire-extension.json',lambda:inspector.wire(self.runtime,self.manifest)),
            ('rejoin-wire-extension.json',lambda:inspector.wire(self.rejoin,self.manifest)),
        )

    def test_warm_catalogs_still_reject_missing_and_corrupt_files(self):
        for name,decode in self.cases():
            with self.subTest(name=name):
                path=self.root/name;data=path.read_bytes();expected=decode()
                try:
                    path.unlink()
                    with self.assertRaises(FileNotFoundError):decode()
                    path.write_bytes(b'{')
                    with self.assertRaises(ValueError):decode()
                    path.write_bytes(data)
                    self.assertEqual(expected,decode())
                finally:path.write_bytes(data)

    def test_same_size_same_mtime_catalog_changes_are_not_stale(self):
        for name,decode in self.cases():
            with self.subTest(name=name):
                path=self.root/name;original=path.read_bytes();expected=decode()
                value=json.loads(original)
                if name=='format-catalog.json':spec=value['records']['GENESIS']
                elif name=='bootstrap-catalog.json':spec=value['BOOTSTRAP_BINDING']
                else:spec=value['wire']['SELECTED_OFFER' if name.startswith('runtime') else 'SOURCE_OFFER']
                spec['id']+=100
                changed=json.dumps(value).encode();size=max(len(original),len(changed))
                data=original.ljust(size);changed=changed.ljust(size)
                try:
                    path.write_bytes(data);stamp=path.stat();self.assertEqual(expected,decode())
                    path.write_bytes(changed);os.utime(path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
                    self.assertEqual((size,stamp.st_mtime_ns),(path.stat().st_size,path.stat().st_mtime_ns))
                    with self.assertRaises(ValueError):decode()
                    path.write_bytes(data);self.assertEqual(expected,decode())
                finally:path.write_bytes(original)

    def test_public_catalog_and_results_remain_independent_mutable_objects(self):
        original=inspector.load();altered=inspector.load()
        altered['records']['GENESIS']['maximum']=0
        self.assertEqual(original,inspector.load())
        for _,decode in self.cases():
            expected=decode();changed=decode();changed.clear()
            self.assertEqual(expected,decode())

    def test_warm_schema_does_not_cache_evidence_or_a_positive_verdict(self):
        for raw,name in ((self.genesis,'GENESIS'),(self.bootstrap,'BOOTSTRAP_BINDING')):
            inspector.inspect(raw,name)
            for bad in (raw[:-1],raw+b'\0',reframe(raw,flags=1)):
                with self.assertRaises(ValueError):inspector.inspect(bad,name)
        for raw in (self.runtime,self.rejoin):
            inspector.wire(raw,self.manifest)
            for bad in (raw[:-1],reframe(raw,flags=1),reframe(raw,body=raw[48:-1]+b'!')):
                with self.assertRaises(ValueError):inspector.wire(bad,self.manifest)

    def test_repeated_validation_reuses_parsing_but_rereads_catalog_bytes(self):
        data=inspector.CATALOG.read_bytes()
        with patch.object(inspector.json,'loads',wraps=json.loads) as parse:
            for _ in range(5):inspector.inspect(self.genesis,'GENESIS')
        self.assertEqual(1,sum(call.args[0]==data for call in parse.call_args_list))
        # A fresh read after warming the parser must still observe removal.
        inspector.CATALOG.unlink()
        with self.assertRaises(FileNotFoundError):inspector.inspect(self.genesis,'GENESIS')


if __name__=='__main__':unittest.main()
