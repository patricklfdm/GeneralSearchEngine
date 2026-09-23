"""Boundary tests for the local measurement oracle and safe evidence container."""
import copy
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from . import performance_plan as plan, performance_model as model, performance_evidence as evidence, performance_bundle as bundle


class MeasurementTest(unittest.TestCase):
    def rows(self):
        return [dict({k:v for k,v in row.items() if k not in ('applicationSha256','indexCount','documentCount')},
                     outcome='SUCCESS',opId=str(row['ordinal']),apiStartNanos=row['ordinal']*100,
                     apiEndNanos=row['ordinal']*100+row['ordinal']) for row in model.expected(plan.load())['rows']]

    def test_full_program_and_nearest_rank_use_eight_samples(self):
        rows=self.rows();evidence.calls(rows,plan.load())
        self.assertEqual(evidence.summary(rows)['ADD'],dict(samples=8,p50Nanos=41,p95Nanos=81,p99Nanos=81))

    def test_zero_duration_is_retained(self):
        rows=self.rows()
        for row in rows:row['apiEndNanos']=row['apiStartNanos']
        evidence.calls(rows,plan.load())
        self.assertEqual(evidence.summary(rows)['QUERY']['p99Nanos'],0)

    def test_changed_operation_order_is_rejected(self):
        rows=self.rows();rows[1],rows[2]=rows[2],rows[1]
        with self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_missing_or_extra_calls_are_rejected(self):
        for rows in (self.rows()[:-1],self.rows()+[self.rows()[-1]]):
            with self.subTest(size=len(rows)),self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_hidden_failures_and_uncertain_outcomes_are_rejected(self):
        for outcome in plan.load()['observations']['outcomes']:
            if outcome=='SUCCESS':continue
            rows=self.rows();rows[12]['outcome']=outcome
            with self.subTest(outcome=outcome),self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_read_and_payload_hash_resealing_does_not_repair_semantics(self):
        for key,value in [('answer','forged'),('keys',[100]),('payloadSha256','a'*64),('afterSequence',900)]:
            rows=self.rows();row=rows[8];row[key]=value;row['answerSha256']=model.sha(model.canonical(row['answer']))
            with self.subTest(key=key),self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_replayed_operation_id_is_rejected(self):
        rows=self.rows();rows[1]['opId']=rows[0]['opId']
        with self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_reversed_and_noninteger_api_timestamps_are_rejected(self):
        for value in (-1,1.5,True):
            rows=self.rows();rows[0]['apiEndNanos']=value
            with self.subTest(value=value),self.assertRaises(ValueError):evidence.calls(rows,plan.load())

    def test_warmup_is_never_used_to_pad_missing_measured_samples(self):
        rows=[r for r in self.rows() if r['ordinal']!=11]
        with self.assertRaises(ValueError):evidence.summary(rows)

    def test_incomplete_and_duplicate_key_jsonl_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'trace'
            for raw in (b'{"a":1}',b'{"a":1,"a":2}\n'):
                p.write_bytes(raw)
                with self.assertRaises(ValueError):evidence.lines(p)


class BundleTest(unittest.TestCase):
    def test_round_trip_binds_all_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();(raw/'data').write_bytes(b'raw evidence')
            expected=bundle.pack(raw,root/'bundle.tar.gz')
            extracted=bundle.unpack(root/'bundle.tar.gz',root/'extracted')
            self.assertEqual(expected,bundle.members(extracted))

    def archive(self,path,entries):
        with tarfile.open(path,'w:gz') as tar:
            for name,data,kind in entries:
                item=tarfile.TarInfo(name);item.type=kind
                if kind==tarfile.REGTYPE:item.size=len(data)
                if kind in (tarfile.SYMTYPE,tarfile.LNKTYPE):item.linkname='/tmp/escape'
                tar.addfile(item,io.BytesIO(data) if item.isfile() else None)

    def test_path_traversal_absolute_links_and_duplicates_are_rejected(self):
        for entries in [
            [('../escape',b'x',tarfile.REGTYPE)],[('/escape',b'x',tarfile.REGTYPE)],
            [('a/../../escape',b'x',tarfile.REGTYPE)],[('a\\b',b'x',tarfile.REGTYPE)],
            [('link',b'',tarfile.SYMTYPE)],[('link',b'',tarfile.LNKTYPE)],
            [('fifo',b'',tarfile.FIFOTYPE)],[('same',b'x',tarfile.REGTYPE),('same',b'y',tarfile.REGTYPE)]]:
            with self.subTest(entries=entries),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);self.archive(root/'bad.tgz',entries)
                with self.assertRaises(ValueError):bundle.unpack(root/'bad.tgz',root/'extracted')

    def test_missing_inventory_or_resealed_wrong_member_hash_is_rejected(self):
        for index in (None,b'{"data":{"bytes":1,"sha256":"wrong"}}\n'):
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);entries=[('data',b'x',tarfile.REGTYPE)]
                if index is not None:entries.append(('bundle-members.json',index,tarfile.REGTYPE))
                self.archive(root/'bad.tgz',entries)
                with self.assertRaises(ValueError):bundle.unpack(root/'bad.tgz',root/'extracted')

    def test_source_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();(root/'real').write_text('data');(raw/'link').symlink_to(root/'real')
            with self.assertRaises(ValueError):bundle.pack(raw,root/'out.tgz')

    def test_each_size_and_count_ceiling_is_enforced(self):
        for name,value in [('files',1),('expanded',3),('member',3),('traces',3)]:
            with self.subTest(limit=name),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);raw=root/'raw';raw.mkdir();(raw/'trace.jsonl').write_bytes(b'four')
                with patch.dict(bundle.LIMITS,{name:value}),self.assertRaises(ValueError):bundle.pack(raw,root/'out.tgz')

    def test_json_histories_and_mutated_trace_arrays_share_the_trace_ceiling(self):
        for name in ('history.json','calls.json','node-1-process.json','negative-inputs/missing-proof.json'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);raw=root/'raw';raw.mkdir();member=raw/name
                member.parent.mkdir(parents=True,exist_ok=True);member.write_bytes(b'four')
                with patch.dict(bundle.LIMITS,traces=3),self.assertRaises(ValueError):bundle.pack(raw,root/'out.tgz')

    def test_compressed_input_limit_and_existing_destination_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();(raw/'data').write_text('data');bundle.pack(raw,root/'ok.tgz')
            with patch.dict(bundle.LIMITS,compressed=1),self.assertRaises(ValueError):bundle.unpack(root/'ok.tgz',root/'output')
            with self.assertRaises(ValueError):bundle.unpack(root/'ok.tgz',raw)

    def test_truncated_archive_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);raw=root/'raw';raw.mkdir();(raw/'data').write_bytes(b'x'*1000);bundle.pack(raw,root/'ok.tgz')
            data=(root/'ok.tgz').read_bytes();(root/'bad.tgz').write_bytes(data[:len(data)//2])
            with self.assertRaises((ValueError,tarfile.TarError,EOFError,OSError)):bundle.unpack(root/'bad.tgz',root/'output')


if __name__=='__main__':unittest.main()
