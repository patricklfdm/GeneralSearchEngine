import gzip
import json
from pathlib import Path
import tempfile
import unittest
from . import composition_qualification as q
from . import composition_scenarios as s


class QualificationTest(unittest.TestCase):
    def test_force_cut_and_membership_labels_must_match_actual_trace(self):
        record=s.recover_tail(3,'ADD','proof')[0].evidence()
        case=next(c for c in q.cases() if c['name']=='3-add-proof');q.coverage(record,case)
        with self.assertRaisesRegex(ValueError,'force cut mislabeled'):q.coverage(record,dict(case,family='accepted'))
        with self.assertRaisesRegex(ValueError,'transition kind'):q.coverage(record,dict(case,kind='REPLACE'))

    def test_noncanonical_and_oversized_decoded_evidence_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace.gz';path.write_bytes(gzip.compress(b'{ "test": true }'))
            with self.assertRaisesRegex(ValueError,'noncanonical'):q.trace(path)
            path.write_bytes(gzip.compress(b' '*(q.MAX_TRACE+1)))
            with self.assertRaisesRegex(ValueError,'decoded model trace bound'):q.trace(path)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'receipt.json';marker.write_text('original')
            with self.assertRaises(FileExistsError):q.run(temp)
            self.assertEqual('original',marker.read_text())

    def test_missing_inventory_and_source_drift_reject_before_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp);receipt=dict(schema=q.SCHEMA,status='PASS',runtimeQualified=False,
                execution='deterministic-model-only',source={'head':'original'},files={})
            (path/'receipt.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError,'scope/source'):q.replay(path,{'head':'other'})
            with self.assertRaisesRegex(ValueError,'evidence inventory'):q.replay(path,receipt['source'])


if __name__=='__main__':unittest.main()
