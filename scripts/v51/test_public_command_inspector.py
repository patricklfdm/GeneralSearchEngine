"""Byte-level negative fixtures for the independent atomic-bulk command inspector."""
import struct
import base64
import json
import unittest
from .runtime_evidence import documents_command, command, application_command, project_application


def item(key, value):
    document = struct.pack('>i', key) + value.encode()
    return struct.pack('>iii', 4, key, len(document)) + document


class PublicCommandInspectorTest(unittest.TestCase):
    def keys(self,*keys):return b'\0\1'+struct.pack('>i',len(keys))+b''.join(struct.pack('>ii',4,k) for k in keys)
    def text(self,value):
        data=value.encode();return b'\0\1'+struct.pack('>i',len(data))+data
    def descriptor(self,field='id',kind='equality',analyzer=''):
        return json.dumps(dict(field=field,kind=kind,analyzer=analyzer),sort_keys=True,separators=(',',':'))

    def test_single_and_bulk_keep_document_order(self):
        self.assertEqual(command(b'\x00\x01' + struct.pack('>i', 1) + item(9, 'a')), (9, 'a'))
        raw = b'\x00\x01' + struct.pack('>i', 2) + item(9, 'a') + item(2, 'b')
        self.assertEqual(documents_command(raw), [(9, 'a'), (2, 'b')])
        with self.assertRaisesRegex(ValueError, 'single command count'): command(raw)

    def test_partial_duplicate_and_malformed_items_rejected(self):
        raw = b'\x00\x01' + struct.pack('>i', 2) + item(9, 'a') + item(2, 'b')
        invalid = [raw[:-1], raw + b'x', raw[:6] + item(9, 'a'), raw[:6] + item(9, 'a') * 2,
                   b'\x00\x01' + struct.pack('>i', 101), raw[:6] + struct.pack('>i', 8) + raw[10:],
                   raw[:6] + struct.pack('>iii', 4, 9, -1) + raw[18:]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError): documents_command(value)

    def test_delete_keys_keep_order_and_reject_aliases_truncation_and_extra_bytes(self):
        self.assertEqual([7,2],application_command(6,self.keys(7,2))['keys'])
        self.assertEqual([7],application_command(3,self.keys(7))['keys'])
        raw=self.keys(7,2)
        for operation,value in ((3,raw),(6,self.keys()),(6,self.keys(7,7)),(6,raw[:-1]),(6,raw+b'x'),
                                (6,raw[:6]+struct.pack('>i',8)+raw[10:]),(6,b'\0\1'+struct.pack('>i',101))):
            with self.subTest(operation=operation,value=value),self.assertRaises(ValueError):application_command(operation,value)

    def test_index_descriptor_is_canonical_complete_and_has_exact_analyzer(self):
        valid=self.descriptor()
        self.assertEqual(dict(field='id',kind='equality',analyzer=''),application_command(7,self.text(valid))['index'])
        self.assertEqual('id',application_command(8,self.text('id'))['field'])
        for value in (valid+' ',valid.replace('"id"','"id","field":"id"'),self.descriptor(kind='unknown'),
                      self.descriptor(analyzer='gse-simple-v1'),self.descriptor(kind='text'),self.descriptor(field=''),
                      self.descriptor(field='x'*1025),'[]','{"field":"id"}'):
            with self.subTest(value=value),self.assertRaises(ValueError):application_command(7,self.text(value))
        for operation,data in ((7,self.text(valid)[:-1]),(7,self.text(valid)+b'x'),(8,self.text('id')+b'x'),
                               (8,self.text('')), (8,self.text('x'*1025)),(9,b'\0'),(10,b'')):
            with self.subTest(operation=operation),self.assertRaises(ValueError):application_command(operation,data)

    def test_all_application_operations_preserve_history_and_canonical_index_order(self):
        def entry(op,data):return dict(operation=op,payload=base64.b64encode(data).decode())
        def docs(*pairs):return b'\0\1'+struct.pack('>i',len(pairs))+b''.join(item(*p) for p in pairs)
        seed=[dict(field='value',kind='text',analyzer='gse-simple-v1')]
        changes=[entry(1,docs((3,'added'))),entry(2,docs((1,'updated'))),entry(3,self.keys(2)),
                 entry(4,docs((4,'bulk'),(5,'bulk'))),entry(5,docs((3,'new'),(4,'new'))),entry(6,self.keys(4,5)),
                 entry(7,self.text(self.descriptor())),entry(9,b''),entry(8,self.text('id'))]
        indexes,documents,sequence,commands=project_application(changes[:-1],seed,{1:'old',2:'deleted'},41)
        self.assertEqual(['id','value'],[v['field'] for v in indexes]);self.assertEqual([(1,'updated'),(3,'new')],list(documents.items()))
        self.assertEqual(48,sequence);self.assertEqual([1,2,3,4,5,6,7,9],[v['operation'] for v in commands])
        self.assertEqual((seed,documents,49),project_application(changes,seed,{1:'old',2:'deleted'},41)[:3])
        for invalid in ([entry(3,self.keys(9))],[entry(8,self.text('id'))],
                        [entry(7,self.text(self.descriptor('value','text','gse-simple-v1')))]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):project_application(invalid,seed,{1:'old'},0)
