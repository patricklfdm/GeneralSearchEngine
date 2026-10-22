"""Disabled process evidence cannot claim runtime acceptance or omit a size case."""
from copy import deepcopy
import unittest
from . import foundation as f


class FoundationTest(unittest.TestCase):
    def original(self):
        return dict(schema=f.SCHEMA, status='PASS', runtimeEnabled=False, physicalMembershipEvidence=False,
                    source=dict(source='a'*40, checkoutSha256='b'*64),
                    jars=[dict(path=p, sha256='c'*64, size=100) for p in f.JARS],
                    cases=[dict(members=n, exitCode=0, createdFiles=[], result=dict(status='PASS',
                        execution='disabled-public-declarations', protocol='gse-replication/1.3', members=n,
                        runtimeEnabled=False)) for n in (3, 4, 5)])

    def test_rejects_runtime_promotion_and_incomplete_process_inventory(self):
        original=self.original(); self.assertEqual('PASS', f.validate(original)['status'])
        mutations=(lambda r:r.update(runtimeEnabled=True), lambda r:r.update(physicalMembershipEvidence=True),
                   lambda r:r['cases'].pop(), lambda r:r['cases'].reverse(),
                   lambda r:r['cases'][0].update(exitCode=1), lambda r:r['cases'][0].update(createdFiles=['ROOT']),
                   lambda r:r['cases'][0]['result'].update(runtimeEnabled=True),
                   lambda r:r['cases'][0]['result'].update(protocol='gse-replication/1.2'),
                   lambda r:r['jars'].reverse(), lambda r:r.update(status='FAIL'))
        for mutate in mutations:
            case=deepcopy(original); mutate(case)
            with self.assertRaises(ValueError): f.validate(case)
        self.assertEqual(original, self.original())


if __name__ == '__main__': unittest.main()
