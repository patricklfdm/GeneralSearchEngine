import hashlib
import json
from pathlib import Path
import unittest
from . import token

FIXTURES = Path(__file__).resolve().parents[2]/'docs/v5x/v5.2/fixtures'


class TokenTest(unittest.TestCase):
    def test_frozen_independent_bytes(self):
        file=FIXTURES/'read-tokens-v1.json'
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),(FIXTURES/'read-tokens-v1.sha256').read_text().split()[0])
        for case in json.loads(file.read_text())['cases']:
            self.assertEqual(bytes.fromhex(case['hex']),token.encode(case['value']))
            self.assertEqual(case['value'],token.decode(bytes.fromhex(case['hex'])))

    def test_corruption_unknown_version_and_recomputed_semantic_failures(self):
        raw=bytes.fromhex(json.loads((FIXTURES/'read-tokens-v1.json').read_text())['cases'][0]['hex'])
        for size in (0,1,79,80,111,113):
            with self.assertRaisesRegex(ValueError,'INVALID_TOKEN'):token.decode((raw+b'x')[:size])
        for offset in range(112):
            bad=bytearray(raw);bad[offset]^=1
            with self.assertRaises(ValueError):token.decode(bad)
        for offset,expected in ((4,'UNSUPPORTED_TOKEN_VERSION'),(5,'INVALID_TOKEN'),(72,'INVALID_TOKEN')):
            bad=bytearray(raw);bad[offset]=255;bad[80:]=hashlib.sha256(token.DOMAIN+bad[:80]).digest()
            with self.assertRaisesRegex(ValueError,expected):token.decode(bad)
