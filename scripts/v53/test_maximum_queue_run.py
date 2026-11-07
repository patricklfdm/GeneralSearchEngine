"""Maximum queue orchestration guards; synthetic members grant no native credit."""
import copy
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import queue_completion_run as m
from . import maximum_transition_capacity as capacity
from . import test_segmented_queue_run as segmented
from . import test_maximum_native_run as native


def result():
    value=segmented.result();value['original']=m.gate.maximum.resources.receipt(value['original'],m.gate.maximum.resources.DEFAULT)
    value['original'].update(scope='maximum-image-joint-queue-component-only',maximumImageQueueQualified=True,
                             maximumSeed=native.maximum_result()['seed'],
                             pressureStorage=segmented.legacy.pressure_storage(m.gate.maximum.maximum.NATIVE_MAXIMUM))
    value['negatives']=[dict(case=n,status='REJECTED',reason=r) for n,r in m.gate.negative_cases(**m.options(m.MAXIMUM_PROFILE)).items()]
    return value


class MaximumQueueRunTest(unittest.TestCase):
    def setUp(self):
        self.fixture=segmented.SegmentedQueueRunTest();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.path=self.fixture.path;self.pins=self.fixture.pins
        old=m.locate(self.path/'workspace',m.SEGMENTED_PROFILE)
        target=old.parent.parent/'v53-maximum-queue';target.mkdir();self.raw=target/old.name;old.rename(self.raw)
        directory=self.raw/m.gate.maximum.DIRECTORY;directory.mkdir();(directory/'source-backup').mkdir()
        for name in ('calibration.image','source.image',*('source-backup/'+v for v in ('gse-backup-checkpoint','gse-backup-manifest','gse-backup-metadata'))):
            (directory/name).write_bytes(b'synthetic, not native maximum evidence')
        m.h.save(directory/'binding.json',result()['original']['maximumSeed'])
        cls,method,_=m.selected(m.MAXIMUM_PROFILE);cls=m.PACKAGE+cls
        report=next(self.fixture.reports.glob('TEST-*.xml'));suite=ET.parse(report)
        suite.getroot().set('name',cls);case=suite.getroot().find('testcase');case.set('classname',cls);case.set('name',method);suite.write(report)
        m.h.save(self.path/'capacity.json',native.capacity_record())
        m.h.save(self.path/'collection.json',m.collect(self.raw,m.MAXIMUM_PROFILE))
        receipt=m.read(self.path/'receipt.json');receipt.update(schema=m.MAXIMUM_SCHEMA,profile=m.MAXIMUM_PROFILE,
            raw=self.raw.relative_to(self.path).as_posix(),command=['mvn',*m.command(m.MAXIMUM_PROFILE)],
            junit=m.junit(self.fixture.reports,m.MAXIMUM_PROFILE),
            capacitySha256=m.h.digest((self.path/'capacity.json').read_bytes()),
            collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        m.h.save(self.path/'receipt.json',receipt)

    def test_distinct_exact_method_schema_and_larger_caller_bound_archive(self):
        self.assertEqual(self.raw,m.member(self.path,m.MAXIMUM_PROFILE,self.pins)['raw'])
        self.assertEqual(128*1024**3,m.raw_bytes(m.MAXIMUM_PROFILE));self.assertEqual(8*1024**3,m.raw_bytes(m.SEGMENTED_PROFILE))
        self.assertIn('-DargLine=-Xmx4g',m.command(m.MAXIMUM_PROFILE))
        self.assertEqual(dict(wire_layout=m.gate.history.wire_archive.SEGMENTED,maximum_image=True),m.options(m.MAXIMUM_PROFILE))
        for profile in (m.PROFILE,m.SEGMENTED_PROFILE):
            with self.subTest(profile=profile),self.assertRaises(ValueError):m.member(self.path,profile,self.pins)

    def test_missing_seed_member_prevents_complete_collection(self):
        path=self.raw/m.gate.maximum.DIRECTORY/'source-backup/gse-backup-checkpoint';path.unlink()
        with self.assertRaisesRegex(ValueError,'complete seed members'):m.collect(self.raw,m.MAXIMUM_PROFILE)

    def test_capacity_receipt_is_bound_and_cannot_be_lowered(self):
        value=m.read(self.path/'capacity.json');value['minimumFreeBytes']-=1;m.h.save(self.path/'capacity.json',value)
        with self.assertRaisesRegex(ValueError,'capacity receipt limits'):m.member(self.path,m.MAXIMUM_PROFILE,self.pins)
        value=native.capacity_record();value['workspace']='/different';m.h.save(self.path/'capacity.json',value)
        with self.assertRaisesRegex(ValueError,'producer capacity binding'):m.member(self.path,m.MAXIMUM_PROFILE,self.pins)

    def test_host_rejection_precedes_source_copy_build_and_replay(self):
        output=self.fixture.legacy.root/'blocked-producer'
        with patch.object(capacity,'check',side_effect=ValueError('unqualified host')),patch.object(m.h,'source_copy') as copy_source,patch.object(m.h,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'^unqualified host$'):m.capture(output,'mvn',m.MAXIMUM_PROFILE)
            copy_source.assert_not_called();execute.assert_not_called()
        receipt=m.read(output/'receipt.json');self.assertEqual(m.MAXIMUM_SCHEMA,receipt['schema']);self.assertEqual('FAIL',receipt['status'])
        with patch.object(capacity,'check',side_effect=ValueError('unqualified verifier')),patch.object(m,'member') as member:
            with self.assertRaisesRegex(ValueError,'^unqualified verifier$'):m.qualify(self.path,m.MAXIMUM_PROFILE,self.pins)
            member.assert_not_called()

    def test_complete_gate_requires_maximum_seed_default_limits_and_all_twenty_negatives(self):
        value=result();m.check_result(value,m.MAXIMUM_PROFILE);self.assertEqual(20,len(value['negatives']))
        for mode in ('seed','staging','scope','negative','reason'):
            changed=copy.deepcopy(value)
            if mode=='seed':changed['original']['maximumSeed']['bootstrapHistory']=m.gate.maximum.maximum.HISTORY
            elif mode=='staging':changed['original']['stagingLimit']=512*1024**2
            elif mode=='scope':changed['original']['combinedMaximumQualified']=True
            elif mode=='negative':changed['negatives'].pop()
            else:changed['negatives'][7]['reason']='unrelated'
            with self.subTest(mode=mode),self.assertRaises(ValueError):m.check_result(changed,m.MAXIMUM_PROFILE)
        with self.assertRaises(ValueError):m.check_result(value,m.SEGMENTED_PROFILE)
        with self.assertRaises(ValueError):m.check_result(segmented.result(),m.MAXIMUM_PROFILE)

    def test_verification_binds_maximum_options_and_preserves_false_closure_flags(self):
        with patch.object(capacity,'check',return_value=native.capacity_record('verify')) as host, \
             patch.object(m.gate,'load',return_value='checked original') as load,patch.object(m.gate,'qualify',return_value=result()) as replay:
            receipt=m.qualify(self.path,m.MAXIMUM_PROFILE,self.pins)
        host.assert_called_once_with(self.path,'verify');load.assert_called_once_with(self.raw,**m.options(m.MAXIMUM_PROFILE))
        replay.assert_called_once_with('checked original',**m.options(m.MAXIMUM_PROFILE))
        self.assertEqual(m.MAXIMUM_SCHEMA,receipt['schema']);self.assertEqual('maximum-image-joint-queue-component-only',receipt['scope'])
        self.assertFalse(receipt['combinedResourcesQualified']);self.assertFalse(receipt['phase3Complete'])


if __name__=='__main__':unittest.main()
