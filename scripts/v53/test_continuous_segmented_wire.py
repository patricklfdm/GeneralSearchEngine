"""Explicit segmented transport guards; no synthetic native qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import continuous_transition_evidence as h
from . import queue_completion_evidence as q
from . import test_wire_archive as archive_fixture
from . import test_queue_completion_evidence as queue_fixture
from .test_queue_completion_run import replay as formal_result
from . import queue_completion_run as formal


class ContinuousSegmentedWireTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.fixture=archive_fixture.WireArchiveTest();self.fixture.root=self.root

    def create(self):
        self.fixture.original({'wire.json':[{'order':1},{'order':2}]})

    def read(self,**changes):
        options=dict(backup=True,wire_layout=h.wire_archive.SEGMENTED,maximum_bytes=8*1024*h.e.MIB,wire_bytes=256*h.e.MIB)
        options.update(changes);return h.wire_history(self.root,**options)

    def test_checked_reader_preserves_all_rows_without_materializing_the_array(self):
        self.create();wire,archive=self.read()
        self.assertIs(type(wire),h.wire_archive.segmented.Reader)
        self.assertEqual([{'order':1},{'order':2}],list(wire));self.assertIs(archive.read('wire.json'),wire)
        archive.check_unchanged()

    def test_json_default_never_discovers_or_silently_accepts_segments(self):
        self.create()
        with self.assertRaisesRegex(ValueError,'^continuous unexpected segmented wire$'):
            self.read(wire_layout=h.wire_archive.JSON)
        with self.assertRaisesRegex(ValueError,'^joining segmented wire requires backup$'):
            self.read(backup=False)
        for layout in ('auto',True,None):
            with self.subTest(layout=layout),self.assertRaisesRegex(ValueError,'explicit wire layout'):self.read(wire_layout=layout)

    def test_larger_transport_must_not_change_the_callers_shared_byte_limit(self):
        self.create();total=sum(p.stat().st_size for p in (self.root/h.wire_archive.DIRECTORY).rglob('*') if p.is_file())
        self.read(maximum_bytes=total)
        with self.assertRaisesRegex(ValueError,'shared byte capacity'):self.read(maximum_bytes=total-1)

    def test_only_the_main_continuous_history_is_admitted(self):
        self.fixture.original({'wire.json':[{'order':1}],'joining-intent-wire.json':[{'unrelated':True}]})
        with self.assertRaisesRegex(ValueError,'^continuous exact segmented histories$'):self.read()

    def test_corrupt_tail_and_missing_complete_index_cannot_expose_a_prefix(self):
        self.create();part=next((self.root/h.wire_archive.DIRECTORY/'wire/segments').iterdir())
        part.write_bytes(part.read_bytes().replace(b'"order":2',b'"order":3'))
        with self.assertRaises(ValueError):self.read()
        (self.root/h.wire_archive.DIRECTORY/'wire/complete.json').unlink()
        with self.assertRaises(OSError):self.read()

    def test_archive_remains_bound_after_initial_parse(self):
        self.create();wire,archive=self.read()
        path=self.root/h.wire_archive.DIRECTORY/'index.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'changed'):archive.check_unchanged()

    def test_empty_backup_is_rejected_before_physical_replay_or_file_reads(self):
        with patch.object(h.a,'prelude') as physical,patch.object(h.b.selection,'layout') as layout:
            with self.assertRaisesRegex(ValueError,'^joining segmented wire requires backup$'):
                h.history(self.root,'continuous-result.json',wire_layout=h.wire_archive.SEGMENTED)
            physical.assert_not_called();layout.assert_not_called()

    def test_declared_segmentation_changes_expected_inventory_not_history_or_publication(self):
        with patch.object(h.b.selection,'layout') as layout,patch.object(h,'wire_history',side_effect=ValueError('stop before physical')) as wire:
            with self.assertRaisesRegex(ValueError,'^stop before physical$'):
                h.history(self.root,'continuous-result.json',backup=True,wire_layout=h.wire_archive.SEGMENTED)
            expected=layout.call_args.args[1]
            self.assertIn(h.wire_archive.DIRECTORY,expected);self.assertNotIn('wire.json',expected)
            self.assertEqual(512*h.e.MIB,wire.call_args.kwargs['maximum_bytes'])

    def test_original_physical_failure_precedes_queue_receipt_and_resource_loading(self):
        (self.root/'continuous-result.json').write_text(json.dumps(dict(status='PASS',kind='REMOVE',activations=3,publicReady=False,automaticLifecycle=False)))
        with patch.object(h,'history',side_effect=ValueError('physical failure')) as physical,patch.object(q.t,'read') as resource:
            with self.assertRaisesRegex(ValueError,'^physical failure$'):
                q.load(self.root,wire_layout=h.wire_archive.SEGMENTED)
            self.assertEqual(h.wire_archive.SEGMENTED,physical.call_args.kwargs['wire_layout'])
            resource.assert_not_called()

    def test_queue_scope_cannot_be_promoted_between_explicit_layouts(self):
        value=queue_fixture.QueueCompletionEvidenceTest().value()
        with self.assertRaisesRegex(ValueError,'^queue completion scope$'):q.replay(value,wire_layout=h.wire_archive.SEGMENTED)
        value['receipt'].update(schema='gse-v53-segmented-queue-completion-v2',wireLayout=h.wire_archive.SEGMENTED,
                                bootstrapSource=h.wire_archive.source.BACKUP)
        with self.assertRaisesRegex(ValueError,'^queue completion scope$'):q.replay(value)
        for key,wrong in (('bootstrapSource','EMPTY'),('wireLayout','JSON')):
            original=value['receipt'][key];value['receipt'][key]=wrong
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^queue completion original wire profile$'):
                q.replay(value,wire_layout=h.wire_archive.SEGMENTED)
            value['receipt'][key]=original

    def test_segmented_result_cannot_fill_the_existing_json_resource_slot(self):
        value=formal_result();value['original'].update(wireLayout=h.wire_archive.SEGMENTED,bootstrapSource=h.wire_archive.source.BACKUP)
        with self.assertRaisesRegex(ValueError,'^queue-completion admission original pressure and native completion$'):
            formal.check_result(value,formal.PROFILE)

    def test_segmented_negative_replay_still_requires_a_passing_original_first(self):
        with patch.object(q,'replay',side_effect=ValueError('bad original')) as replay,patch.object(q.copy,'deepcopy') as mutate:
            with self.assertRaisesRegex(ValueError,'^bad original$'):q.qualify({},wire_layout=h.wire_archive.SEGMENTED)
            replay.assert_called_once_with({},wire_layout=h.wire_archive.SEGMENTED);mutate.assert_not_called()


if __name__=='__main__':unittest.main()
