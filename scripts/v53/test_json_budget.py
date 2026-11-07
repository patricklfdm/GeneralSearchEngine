"""Lexical limits survive long strings without regex-sized memory overhead."""
import json
import re
import subprocess
import sys
import unittest
from . import format_fixture as f
from . import segmented_evidence as segmented


def previous(raw):
    depth = nodes = 0
    for match in re.finditer(rb'"(?:\\.|[^"\\])*"|[{}\[\],:]|[^\s{}\[\],:"]+', raw):
        token = match.group()
        if token in (b'{', b'['):depth += 1
        if token in (b'}', b']'):depth -= 1
        if token not in (b'}', b']', b',', b':'):nodes += 1
        if not (0 <= depth <= 16 and nodes <= 65536):raise ValueError('parser depth/node budget')
    if depth:raise ValueError('unbalanced JSON')


class JsonBudgetTest(unittest.TestCase):
    def outcome(self, read, raw):
        try:read(raw)
        except ValueError as error:return str(error)
        return 'PASS'

    def test_valid_json_matches_previous_scanner_including_escaped_strings(self):
        values = [None, True, False, 0, -1, 1.25, {}, [], {'values':[None, True, False, 12]}]
        for slashes in range(12):
            values += ['x'+'\\'*slashes+'"{}[],:'+ '\n', {'a':'\\'*slashes, 'b':['"', '\u263a']}]
        for value in values:
            for raw in (f.canonical(value), json.dumps(value, indent=2, ensure_ascii=True).encode()):
                with self.subTest(value=value):
                    self.assertEqual('PASS', self.outcome(previous, raw))
                    self.assertEqual('PASS', self.outcome(f.parse_budget, raw))
                    self.assertEqual('PASS', self.outcome(segmented.parse_budget, raw))

    def test_exact_depth_and_node_edges_match_previous_scanner(self):
        samples = [b'['*d+b'0'+b']'*d for d in (15, 16, 17)]
        samples += [b'['+b','.join([b'0']*n)+b']' for n in (65534, 65535, 65536)]
        samples += [b'{"a":'+b'['*d+b'0'+b']'*d+b'}' for d in (15,16)]
        for raw in samples:
            self.assertEqual(self.outcome(previous,raw), self.outcome(f.parse_budget,raw))
            self.assertEqual(self.outcome(previous,raw)=='PASS', self.outcome(segmented.parse_budget,raw)=='PASS')

    def test_unclosed_strings_and_unbalanced_containers_are_rejected(self):
        for raw in (b'"', b'{"a":"x\\"', b'[', b']', b'{}]'):
            for read in (f.parse_budget, segmented.parse_budget):
                with self.subTest(raw=raw,read=read), self.assertRaises(ValueError):read(raw)

    def test_budget_does_not_replace_json_syntax_validation(self):
        for raw in (b'{"a":}', b'{"a":1,"a":2}', b'{"a":01}', b'{"a":"\\q"}', b'{"a":\v0}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):segmented.canonical(raw)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux address-space bound')
    def test_full_four_mib_chunk_decodes_under_bounded_address_space(self):
        code = '''
import base64,hashlib,resource
from scripts.v53 import format_fixture as f
resource.setrlimit(resource.RLIMIT_AS,(128*1024**2,128*1024**2))
c=f.catalog();value=f.sample(c['wire']['CHUNK']['schema'],c['types']);raw=b'x'*(4*1024**2)
value['payload'].update(action='DATA',offset=0,digest=hashlib.sha256(raw).hexdigest(),bytes=base64.b64encode(raw).decode())
frame=f.encode('wire','CHUNK',value)
if f.decode(frame,'wire','CHUNK')!=value:raise ValueError('maximum CHUNK decode changed')
print('PASS')
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=f.ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual('PASS', result.stdout.strip())


if __name__ == '__main__':unittest.main()
