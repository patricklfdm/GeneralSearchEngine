"""Independent backup parser against actual published V4.4 bytes, including repaired CRC mutations."""
import base64
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from . import public_read_import_evidence as e


class ReadImportEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        value=json.loads((Path(__file__).parent/'fixtures/published-v44-read-backup.json').read_text())
        self.assertEqual('0219af2998e1f6f782443097b8b4b8d792e45da56535b0c45b1c9fff77dd50e5',value['controlJarSha256'])
        self.original={name:base64.b64decode(raw,validate=True) for name,raw in value['members'].items()};self.write(self.original)
    def write(self,values):
        for name,raw in values.items():(self.root/name).write_bytes(raw)
    def repair(self,name,change):
        values=copy.deepcopy(self.original);body=bytearray(values[name][:-4]);change(body)
        values[name]=body+struct.pack('>I',e.b.crc32c(body));self.write(values)

    def test_real_published_backup_documents_sequence_and_content(self):
        result=e.backup_report(self.root)
        self.assertEqual(4,result['sequence']);self.assertEqual(3,result['memberCount'])
        self.assertEqual([1,3,7,5],[v['id'] for v in result['documents']]);self.assertEqual('java search',result['documents'][0]['value'])
        self.assertEqual(sum(map(len,self.original.values())),result['totalBytes'])

    def test_corrupt_truncated_and_trailing_members_are_not_restorable_evidence(self):
        for name,raw in self.original.items():
            for changed in (raw[:-1],raw+b'x',bytes([raw[0]^1])+raw[1:]):
                with self.subTest(name=name),self.assertRaises(ValueError):
                    self.write({**self.original,name:changed});e.backup_report(self.root)
        self.write(self.original);(self.root/'unexpected').write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'member set'):e.backup_report(self.root)

    def test_recomputed_crc_cannot_hide_foreign_codec_or_document_identity(self):
        def codec(body):
            pos=body.index(b'v52-read-codec');body[pos:pos+14]=b'v52-fake-codec'
        self.repair('gse-backup-metadata',codec)
        with self.assertRaisesRegex(ValueError,'codec identity'):e.backup_report(self.root)
        self.write(self.original)
        def key(body):
            pos=body.index(struct.pack('>i',1)+b'java search');body[pos:pos+4]=struct.pack('>i',999)
        self.repair('gse-backup-checkpoint',key)
        with self.assertRaisesRegex(ValueError,'document identity'):e.backup_report(self.root)

    def test_recomputed_crc_cannot_hide_checkpoint_live_count(self):
        self.repair('gse-backup-checkpoint',lambda body:body.__setitem__(slice(72,76),struct.pack('>i',100)))
        with self.assertRaisesRegex(ValueError,'live count'):e.backup_report(self.root)


if __name__=='__main__':unittest.main()
