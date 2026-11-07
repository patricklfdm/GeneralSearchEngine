"""Independent bounded format checks, without treating a capture as qualification."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from . import segmented_evidence as s


class SegmentedEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'original';self.root.mkdir()
        (self.root/'segments').mkdir();(self.root/'cuts').mkdir()

    def save(self,path,value):path.write_bytes(s.f.canonical(value))

    def fixture(self,parts=None):
        parts=parts if parts is not None else [[{'event':'\nλ"'},{'nested':[True,4,None]}],[{'end':True}]]
        entries=[]
        for i,part in enumerate(parts):
            raw=b''.join(s.f.canonical(v)+b'\n' for v in part);path=f'segment-{i:04d}.jsonl'
            (self.root/'segments'/path).write_bytes(raw)
            entries.append(dict(path=path,bytes=len(raw),rows=len(part),sha256=hashlib.sha256(raw).hexdigest()))
        value=dict(schema=s.SCHEMA,rows=sum(v['rows'] for v in entries),bytes=sum(v['bytes'] for v in entries),segments=entries)
        self.save(self.root/'complete.json',value)
        first=entries[:1];prefix=dict(value,segments=first,rows=sum(v['rows'] for v in first),bytes=sum(v['bytes'] for v in first))
        self.save(self.root/'cuts/prefix.json',prefix)
        return value,parts

    def test_ordered_rows_and_exact_cut_without_materializing_whole_history(self):
        value,parts=self.fixture();reader=s.Reader(self.root)
        self.assertEqual(3,len(reader));self.assertEqual(sum(parts,[]),list(reader));self.assertEqual(parts[-1][-1],reader[-1])
        self.assertEqual(parts[0],list(s.Reader(self.root,cut='prefix')));reader.check_unchanged()
        with self.assertRaises(IndexError):reader[3]
        with self.assertRaisesRegex(ValueError,'integer index'):reader[:]
        self.assertEqual(value,reader.complete)

    def test_empty_complete_and_empty_cut_are_observations_only(self):
        self.fixture([]);self.assertEqual([],list(s.Reader(self.root,cut='prefix')))
        self.assertEqual(0,len(s.Reader(self.root,maximum=0)))

    def test_missing_final_index_cannot_promote_a_saved_cut(self):
        self.fixture();(self.root/'complete.json').unlink()
        with self.assertRaisesRegex(ValueError,'complete layout'):s.Reader(self.root,cut='prefix')

    def test_byte_policy_is_caller_selected_and_boolean_or_excess_limits_refused(self):
        value,_=self.fixture();self.assertEqual(3,len(s.Reader(self.root,maximum=value['bytes'])))
        with self.assertRaisesRegex(ValueError,'index'):s.Reader(self.root,maximum=value['bytes']-1)
        for maximum in (True,-1,s.MAXIMUM+1):
            with self.subTest(maximum=maximum),self.assertRaisesRegex(ValueError,'byte limit'):s.Reader(self.root,maximum=maximum)

    def test_index_binds_exact_shapes_totals_paths_counts_and_hashes(self):
        good,_=self.fixture()
        for mutation in ('schema','extra','bytes','rows','boolean','path','hash','segment-bytes','segment-rows'):
            bad=copy.deepcopy(good)
            if mutation=='schema':bad['schema']='old'
            elif mutation=='extra':bad['maximum']=s.MAXIMUM
            elif mutation in ('bytes','rows'):bad[mutation]+=1
            elif mutation=='boolean':bad['rows']=True
            elif mutation=='path':bad['segments'][0]['path']='../outside'
            elif mutation=='hash':bad['segments'][0]['sha256']='a'*64
            elif mutation=='segment-bytes':bad['segments'][0]['bytes']=s.SEGMENT_BYTES+1
            else:bad['segments'][0]['rows']=True
            self.save(self.root/'complete.json',bad)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):s.Reader(self.root)

    def test_modified_cut_cannot_rebind_to_different_segment_or_extent(self):
        value,_=self.fixture()
        for mutation in ('hash','path','bytes'):
            bad=copy.deepcopy(value);bad['segments']=bad['segments'][:1]
            part=bad['segments'][0]
            if mutation=='hash':part['sha256']='a'*64
            elif mutation=='path':part['path']='segment-0001.jsonl'
            else:part['bytes']+=1
            bad['rows']=part['rows'];bad['bytes']=part['bytes'];self.save(self.root/'cuts/prefix.json',bad)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):s.Reader(self.root,cut='prefix')

    def test_damaged_unselected_tail_is_checked_before_exposing_prefix(self):
        self.fixture();path=self.root/'segments/segment-0001.jsonl';path.write_bytes(b'{"bad":true}\n')
        with self.assertRaises(ValueError):s.Reader(self.root,cut='prefix')

    def test_noncanonical_duplicate_numeric_and_nonobject_rows_are_rejected(self):
        for raw in (b'{"a":1,"a":1}',b'{"a":1} ',b'[]',b'{"a":1.0}',b'{"a":NaN}',
                    b'{"bad-key":1}',b'{"a":9223372036854775808}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):s.canonical(raw)

    def test_parser_budget_precedes_object_allocation_and_handles_escaped_quotes(self):
        from unittest.mock import patch
        for raw in (b'{"a":'+b'['*17+b'0'+b']'*17+b'}',b'{"a":['+b'0,'*65536+b'0]}'):
            with self.subTest(size=len(raw)),patch.object(s.json,'loads') as decode:
                with self.assertRaisesRegex(ValueError,'parser budget'):s.canonical(raw)
                decode.assert_not_called()
        for body in ('escaped " quote', 'slashes \\\"', '\\'*20+'"'):
            value={'body':body};self.assertEqual(value,s.canonical(s.f.canonical(value)))

    def test_row_capacity_is_independent_of_complete_history_byte_allowance(self):
        with self.assertRaisesRegex(ValueError,'row capacity'):s.canonical(b'x'*(s.ROW_BYTES+1))

    def test_truncated_line_and_mismatched_row_count_even_with_resealed_hash(self):
        good,_=self.fixture()
        (self.root/'cuts/prefix.json').unlink()
        path=self.root/'segments/segment-0000.jsonl';original=path.read_bytes()
        for raw in (original[:-1],original.replace(b'\n',b'\n\n',1)):
            bad=copy.deepcopy(good);part=bad['segments'][0];part['bytes']=len(raw);part['sha256']=hashlib.sha256(raw).hexdigest()
            bad['bytes']=sum(v['bytes'] for v in bad['segments']);path.write_bytes(raw);self.save(self.root/'complete.json',bad)
            with self.subTest(raw=raw),self.assertRaises(ValueError):s.Reader(self.root)

    def test_links_extra_files_missing_files_and_unknown_cuts_are_refused(self):
        self.fixture();path=self.root/'segments/segment-0000.jsonl';original=path.read_bytes();retained=Path(self.temp.name)/'retained'
        retained.write_bytes(original)
        for link in ('symbolic','hard'):
            path.unlink()
            if link=='symbolic':path.symlink_to(retained)
            else:os.link(retained,path)
            with self.subTest(link=link),self.assertRaisesRegex(ValueError,'regular file'):s.Reader(self.root)
            path.unlink();path.write_bytes(original)
        extra=self.root/'segments/unknown';extra.write_bytes(b'')
        with self.assertRaisesRegex(ValueError,'segment inventory'):s.Reader(self.root)
        extra.unlink();path.unlink()
        with self.assertRaisesRegex(ValueError,'segment inventory'):s.Reader(self.root)
        path.write_bytes(original)
        with self.assertRaisesRegex(ValueError,'absent cut'):s.Reader(self.root,cut='absent')

    def test_directory_replacement_after_open_cannot_redirect_reader(self):
        self.fixture();reader=s.Reader(self.root);path=self.root/'segments';renamed=self.root/'retained';path.rename(renamed);path.mkdir()
        with self.assertRaisesRegex(ValueError,'directory changed'):reader[0]

    def test_same_extent_content_change_after_open_and_between_rows_is_detected(self):
        self.fixture();reader=s.Reader(self.root);stream=iter(reader);next(stream)
        path=self.root/'segments/segment-0001.jsonl';raw=path.read_bytes();path.write_bytes(raw.replace(b'true',b'null'))
        with self.assertRaisesRegex(ValueError,'file changed|row content'):list(stream)

    def test_complete_index_change_after_open_is_detected_on_direct_access(self):
        value,_=self.fixture();reader=s.Reader(self.root);value['schema']='altered';self.save(self.root/'complete.json',value)
        with self.assertRaisesRegex(ValueError,'file changed'):reader[0]

    def test_empty_cuts_directory_and_inventory_bounds_are_enforced(self):
        self.fixture();(self.root/'cuts/prefix.json').unlink();self.assertEqual(3,len(s.Reader(self.root)))
        for i in range(s.CUTS+1):(self.root/'cuts'/f'cut-{i}.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'inventory capacity'):s.Reader(self.root)


if __name__=='__main__':unittest.main()
