"""Byte-level negative fixtures for the independent atomic-bulk command inspector."""
import struct
import unittest
from .runtime_evidence import documents_command, command


def item(key, value):
    document = struct.pack('>i', key) + value.encode()
    return struct.pack('>iii', 4, key, len(document)) + document


class PublicCommandInspectorTest(unittest.TestCase):
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
