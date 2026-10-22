from copy import deepcopy
import unittest
from .format_qualification import validate_java
from .format_fixture import generate


class JavaByteQualificationTest(unittest.TestCase):
    def test_exact_inventory_and_bytes_cannot_be_relabelled(self):
        rows=[{k:r[k] for k in ('family','name','hex','sha256')} for r in generate()['fixtures']]
        original=dict(schema='gse-v53-java-format-output-v1',fixtures=rows)
        self.assertEqual(45,validate_java(original)['syntaxFixtures'])
        for mutation in (lambda r:r['fixtures'].pop(),lambda r:r['fixtures'].append(r['fixtures'][0]),
                         lambda r:r['fixtures'][0].update(hex='00'),lambda r:r['fixtures'][0].update(sha256='0'*64),
                         lambda r:r['fixtures'][0].update(name='FAKE'),lambda r:r['fixtures'][0].update(extra=True)):
            value=deepcopy(original);mutation(value)
            with self.assertRaises(ValueError):validate_java(value)


if __name__=='__main__':unittest.main()
