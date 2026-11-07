"""Synthetic source-bound entry tests; real segmented pressure remains separate."""
import copy
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import queue_completion_run as m
from . import test_queue_completion_run as legacy
from . import test_wire_archive as archive_fixture


def result():
    value=legacy.replay()
    value['original'].update(wireLayout=m.gate.history.wire_archive.SEGMENTED,
                             bootstrapSource=m.gate.history.wire_archive.source.BACKUP)
    value['negatives']=[dict(case=n,status='REJECTED',reason=r) for n,r in m.gate.negative_cases(**m.options(m.SEGMENTED_PROFILE)).items()]
    return value


class SegmentedQueueRunTest(unittest.TestCase):
    def setUp(self):
        self.legacy=legacy.QueueCompletionRunTest();self.legacy.setUp();self.addCleanup(self.legacy.doCleanups)
        self.path=self.legacy.path;self.pins=self.legacy.pins
        self.raw=m.locate(self.path/'workspace',m.PROFILE)
        # Only the test's newly generated fake original is converted here.
        (self.raw/'wire.json').unlink()
        fixture=archive_fixture.WireArchiveTest();fixture.root=self.raw
        fixture.original({'wire.json':[{'synthetic':True}]})
        self.reports=self.path/'workspace'/m.h.MODULE/'target/surefire-reports'
        p=next(self.reports.glob('TEST-*.xml'));xml=ET.parse(p);xml.getroot().find('testcase').set('name',m.SEGMENTED_METHOD);xml.write(p)
        collected=m.collect(self.raw,m.SEGMENTED_PROFILE);m.h.save(self.path/'collection.json',collected)
        receipt=m.read(self.path/'receipt.json');receipt.update(schema=m.SEGMENTED_SCHEMA,profile=m.SEGMENTED_PROFILE,
            command=['mvn',*m.command(m.SEGMENTED_PROFILE)],junit=m.junit(self.reports,m.SEGMENTED_PROFILE),
            collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        m.h.save(self.path/'receipt.json',receipt)

    def test_explicit_source_bound_entry_and_old_entry_are_distinct(self):
        self.assertIn('-Dtest='+m.CLASS+'#'+m.SEGMENTED_METHOD,m.command(m.SEGMENTED_PROFILE))
        self.assertIn('-Dtest='+m.CLASS+'#'+m.METHOD,m.command(m.PROFILE))
        self.assertEqual({},m.options(m.PROFILE));self.assertNotEqual(m.schema(m.PROFILE),m.schema(m.SEGMENTED_PROFILE))
        self.assertEqual(self.raw,m.member(self.path,m.SEGMENTED_PROFILE,self.pins)['raw'])
        with self.assertRaisesRegex(ValueError,'successful unretried producer'):m.member(self.path,m.PROFILE,self.pins)

    def test_legacy_and_rehearsal_methods_cannot_replace_the_segmented_pressure_method(self):
        report=next(self.reports.glob('TEST-*.xml'));original=report.read_bytes()
        for method in (m.METHOD,'segmentedImageRehearsesSameNativeCompletion'):
            xml=ET.fromstring(original);xml.find('testcase').set('name',method);ET.ElementTree(xml).write(report)
            with self.subTest(method=method),self.assertRaisesRegex(ValueError,'exact unretried passing test'):
                m.junit(self.reports,m.SEGMENTED_PROFILE)

    def test_schema_command_or_collection_cannot_be_relabelled_from_json(self):
        original=m.read(self.path/'receipt.json')
        for mode in ('schema','command','collection'):
            value=copy.deepcopy(original)
            if mode=='schema':value['schema']=m.SCHEMA
            elif mode=='command':value['command']=['mvn',*m.command(m.PROFILE)]
            else:value['collectionSha256']='0'*64
            m.h.save(self.path/'receipt.json',value)
            with self.subTest(mode=mode),self.assertRaises(ValueError):m.member(self.path,m.SEGMENTED_PROFILE,self.pins)

    def test_collection_validates_the_complete_segments_without_granting_runtime_acceptance(self):
        value=m.collect(self.raw,m.SEGMENTED_PROFILE)
        self.assertEqual('PARTIAL',value['status']);self.assertFalse(value['queuePressureQualified']);self.assertFalse(value['phase3Complete'])
        (self.raw/'wire.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError,'legacy conflict'):m.collect(self.raw,m.SEGMENTED_PROFILE)
        with self.assertRaisesRegex(ValueError,'unexpected segmented evidence'):m.collect(self.raw,m.PROFILE)
        (self.raw/'wire.json').unlink()
        path=next((self.raw/m.gate.history.wire_archive.DIRECTORY/'wire/segments').iterdir());path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(ValueError):m.collect(self.raw,m.SEGMENTED_PROFILE)

    def test_segmented_gate_requires_twelve_exact_negatives_and_its_bound_profile(self):
        value=result();m.check_result(value,m.SEGMENTED_PROFILE);self.assertEqual(17,len(value['negatives']))
        for mode in ('missing-negative','reason','source','layout'):
            changed=copy.deepcopy(value)
            if mode=='missing-negative':changed['negatives'].pop()
            elif mode=='reason':changed['negatives'][-1]['reason']='another rejection'
            elif mode=='source':changed['original']['bootstrapSource']='EMPTY'
            else:changed['original']['wireLayout']='JSON'
            with self.subTest(mode=mode),self.assertRaises(ValueError):m.check_result(changed,m.SEGMENTED_PROFILE)
        with self.assertRaises(ValueError):m.check_result(value,m.PROFILE)
        with self.assertRaises(ValueError):m.check_result(legacy.replay(),m.SEGMENTED_PROFILE)

    def test_portable_entry_pins_both_original_loading_and_negative_replay_to_segmentation(self):
        with patch.object(m.gate,'load',return_value='synthetic loaded original') as load,patch.object(m.gate,'qualify',return_value=result()) as replay:
            value=m.qualify(self.path,m.SEGMENTED_PROFILE,self.pins)
        load.assert_called_once_with(self.raw,**m.options(m.SEGMENTED_PROFILE))
        replay.assert_called_once_with('synthetic loaded original',**m.options(m.SEGMENTED_PROFILE))
        self.assertEqual(m.SEGMENTED_SCHEMA,value['schema']);self.assertEqual(m.SEGMENTED_PROFILE,value['profile'])
        self.assertFalse(value['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])

    def test_failed_segmented_replay_retains_its_own_failure_schema(self):
        output=self.legacy.root/'failed-verifier'
        with patch.object(m.gate,'load',return_value={}),patch.object(m.gate,'qualify',side_effect=ValueError('original physical failure')):
            with self.assertRaisesRegex(ValueError,'^original physical failure$'):
                m.verify(output,self.path,m.SEGMENTED_PROFILE,self.pins)
        value=m.read(output/'receipt.json')
        self.assertEqual(m.SEGMENTED_SCHEMA,value['schema']);self.assertEqual(m.SEGMENTED_PROFILE,value['profile'])
        self.assertEqual('FAIL',value['status']);self.assertEqual('original physical failure',value['failure']['message'])
        self.assertFalse(value['phase3Complete'])


if __name__=='__main__':unittest.main()
