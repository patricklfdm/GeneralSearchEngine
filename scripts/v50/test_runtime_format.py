"""Cross-check the runtime inspector using independently frozen Step A authority bytes."""
import json
from pathlib import Path
import tempfile
import unittest
from . import runtime_format as runtime, admission_format as f

FIXTURE = Path(__file__).resolve().parents[2] / 'general-search-engine-replication/src/test/resources/replication/v50-admission-fixtures-v2.json'


class RuntimeFormatTest(unittest.TestCase):
    def test_all_frozen_genesis_bases_and_tampered_seals(self):
        for files in json.loads(FIXTURE.read_text())['bases'].values():
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                for name, value in files.items():
                    if name.startswith('node-1/'):
                        (root / name[7:]).write_bytes(bytes.fromhex(value))
                report = runtime.inspect(root)
                expected = f.genesis(bytes.fromhex(files['genesis.gsr']))['base']
                self.assertEqual((report['sequence'], report['committed'], report['lastIndex']), (expected, 0, 0))
                seal = root / 'bootstrap-seal.gsr'; raw = bytearray(seal.read_bytes()); raw[-1] ^= 1; seal.write_bytes(raw)
                with self.assertRaises(ValueError): runtime.inspect(root)

    def test_runtime_rejects_legacy_header_even_with_recomputed_checksum(self):
        files = next(iter(json.loads(FIXTURE.read_text())['bases'].values()))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, value in files.items():
                if name.startswith('node-1/'): (root / name[7:]).write_bytes(bytes.fromhex(value))
            raw = (root / 'manifest.gsr').read_bytes()
            (root / 'manifest.gsr').write_bytes(f.framed(1, raw[48:], minor=0))
            with self.assertRaises(ValueError): runtime.inspect(root)


if __name__ == '__main__': unittest.main()
