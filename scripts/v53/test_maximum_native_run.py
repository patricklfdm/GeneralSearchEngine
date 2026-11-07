"""Maximum entry guard tests with synthetic producers; no history qualification."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import required_four_resource_run as m
from . import maximum_transition_capacity as capacity
from . import phase3_resource_cohort as cohort
from . import test_maximum_native_evidence as fixture
from . import test_backup_resource_run as backup_fixture


def capacity_record(stage='execute'):
    return dict(schema=capacity.SCHEMA,status='PASS',stage=stage,workspace='/synthetic/producer',system='Linux',release='6.8-native',
                freeBytes=capacity.FREE_BY_STAGE[stage],minimumFreeBytes=capacity.FREE_BY_STAGE[stage],
                availableMemoryBytes=capacity.MINIMUM_AVAILABLE_MEMORY,minimumAvailableMemoryBytes=capacity.MINIMUM_AVAILABLE_MEMORY,
                runtimeBudgetsChanged=False,phase3Complete=False)


def maximum_result():
    return dict(schema=m.maximum_native.SCHEMA,status='PASS',profile=m.MAXIMUM_PROFILE,
                seed=m.maximum_native.binding('a'*64,42,'00000000-0000-0000-0000-000000000001','b'*64),resources=fixture.resources(),originalFirst=True,originalPreserved=True,
                simultaneousImageStorage=fixture.storage_fixture.result(),
                maximumNativeHistoryQualified=True,combinedResourcesQualified=False,wholeReaderMemoryQualified=False,
                finalSourceCohortQualified=False,phase3Complete=False)


class MaximumNativeRunTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def test_new_command_preserves_ordinary_and_small_backup_entries(self):
        ordinary=m.command(m.PROFILE);small=m.command(m.BACKUP_PROFILE);maximum=m.command(m.MAXIMUM_PROFILE)
        self.assertEqual({v for v in small if v.startswith('-Dv53.')},{v for v in maximum if v.startswith('-Dv53.')})
        self.assertIn('-Dtest='+m.MAXIMUM_CLASS+'#'+m.MAXIMUM_METHOD,maximum)
        self.assertIn('-Dtest='+m.CLASS+'#'+m.METHOD,ordinary)
        self.assertIn('-Dtest='+m.BACKUP_CLASS+'#'+m.BACKUP_METHOD,small)
        self.assertIn('-DargLine=-Xmx4g',maximum)
        self.assertFalse(any('retry' in v.lower() or 'skipTests' in v or 'timeout' in v.lower() for v in maximum))
        self.assertNotIn(m.MAXIMUM_PROFILE,[v[1] for v in cohort.MEMBERS.values()])

    def test_default_staging_receipts_cannot_be_relabelled_as_old_profiles(self):
        marked=m.marked({'status':'PARTIAL'},m.MAXIMUM_PROFILE);m.check_markers(marked,m.MAXIMUM_PROFILE)
        for other in (m.PROFILE,m.BACKUP_PROFILE):
            with self.assertRaises(ValueError):m.check_markers(marked,other)
            with self.assertRaises(ValueError):m.check_markers(m.marked({'status':'PARTIAL'},other),m.MAXIMUM_PROFILE)

    def test_capture_capacity_failure_precedes_source_copy_or_maven(self):
        output=self.root/'refused'
        with patch.object(capacity,'check',side_effect=ValueError('unqualified host')) as check, \
             patch.object(m.h,'source_copy') as copy,patch.object(m.h,'execute') as execute:
            with self.assertRaisesRegex(ValueError,'unqualified host'):m.capture(output,'mvn',m.MAXIMUM_PROFILE)
            check.assert_called_once_with(output);copy.assert_not_called();execute.assert_not_called()
        receipt=m.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertFalse(receipt['collectionComplete'])
        self.assertFalse((output/'workspace').exists())

    def test_verify_capacity_failure_precedes_producer_reads(self):
        with patch.object(capacity,'check',side_effect=ValueError('unqualified host')) as check,patch.object(m,'member') as member:
            with self.assertRaisesRegex(ValueError,'unqualified host'):m.qualify(self.root,m.MAXIMUM_PROFILE,{})
            check.assert_called_once_with(self.root,'verify');member.assert_not_called()

    def test_maximum_result_requires_its_own_wrapper_and150_default_negatives(self):
        result=maximum_result()
        m.check_result(result,m.MAXIMUM_PROFILE)
        with self.assertRaises(ValueError):m.check_result(result['resources'],m.MAXIMUM_PROFILE)
        with self.assertRaises(ValueError):m.check_result(result,m.BACKUP_PROFILE)

    def producer(self):
        helper=backup_fixture.BackupResourceRunTest();helper.setUp();self.addCleanup(helper.doCleanups)
        path=helper.path;work=path/'workspace';raw=m.locate(work,m.MAXIMUM_PROFILE)
        seed=raw/m.maximum_native.DIRECTORY;(seed/'source-backup').mkdir(parents=True)
        for name in ('calibration.image','source.image','source-backup/gse-backup-checkpoint','source-backup/gse-backup-manifest','source-backup/gse-backup-metadata'):
            (seed/name).write_bytes(b'synthetic, not maximum native evidence')
        (seed/'binding.json').write_bytes(m.h.snapshot.f.canonical(m.maximum_native.binding('a'*64,42,'00000000-0000-0000-0000-000000000001','b'*64)))
        report=work/m.h.MODULE/'target/surefire-reports/TEST-original.xml';tree=ET.parse(report);suite=tree.getroot()
        suite.set('name',m.PACKAGE+m.MAXIMUM_CLASS);suite.find('testcase').set('classname',m.PACKAGE+m.MAXIMUM_CLASS)
        suite.find('testcase').set('name',m.MAXIMUM_METHOD);tree.write(report)
        m.h.save(path/'collection.json',m.collect(raw,m.MAXIMUM_PROFILE));m.h.save(path/'capacity.json',capacity_record())
        value=m.read(path/'receipt.json');value.update(profile=m.MAXIMUM_PROFILE,command=['mvn',*m.command(m.MAXIMUM_PROFILE)],
            junit=m.junit(report.parent,m.MAXIMUM_PROFILE),collectionSha256=m.h.digest((path/'collection.json').read_bytes()),
            capacitySha256=m.h.digest((path/'capacity.json').read_bytes()))
        m.h.save(path/'receipt.json',m.marked(value,m.MAXIMUM_PROFILE))
        return helper,raw

    def test_collection_remains_partial_and_requires_complete_seed_members(self):
        _,raw=self.producer()
        with patch.object(m.maximum_native,'qualify',side_effect=AssertionError('collector cannot qualify')):
            result=m.collect(raw,m.MAXIMUM_PROFILE)
        self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['observedResourcesQualified'])
        m.check_markers(result,m.MAXIMUM_PROFILE)
        (raw/m.maximum_native.DIRECTORY/'source-backup/gse-backup-metadata').unlink()
        with self.assertRaisesRegex(ValueError,'missing seed observation'):m.collect(raw,m.MAXIMUM_PROFILE)

    def test_bound_maximum_producer_uses_only_its_full_reader(self):
        helper,raw=self.producer()
        before=m.member(helper.path,m.MAXIMUM_PROFILE,helper.pins)
        with patch.object(capacity,'check',return_value=capacity_record('verify')), \
             patch.object(m.maximum_native,'qualify',return_value=maximum_result()) as maximum, \
             patch.object(m.gate,'qualify_backup',side_effect=AssertionError('small reader reached')):
            result=m.qualify(helper.path,m.MAXIMUM_PROFILE,helper.pins)
        self.assertEqual(raw,maximum.call_args.args[0]);self.assertEqual(1,maximum.call_count)
        self.assertEqual('maximum-native-required-four-observed-ownership',result['scope'])
        self.assertEqual('verify',result['verificationCapacity']['stage']);m.check_markers(result,m.MAXIMUM_PROFILE)
        self.assertEqual(before,m.member(helper.path,m.MAXIMUM_PROFILE,helper.pins))
        self.assertEqual(150,sum(map(len,result['qualification']['resources']['negatives'].values())))

    def test_producer_capacity_is_required_and_content_bound(self):
        helper,_=self.producer();m.member(helper.path,m.MAXIMUM_PROFILE,helper.pins)
        m.h.save(helper.path/'capacity.json',dict(capacity_record(),release='different-native-version'))
        with self.assertRaisesRegex(ValueError,'capacity binding'):m.member(helper.path,m.MAXIMUM_PROFILE,helper.pins)
        value=capacity_record();capacity.validate(value)
        for key,changed in [('release','6.1-microsoft-standard-WSL2'),('stage','verify'),('freeBytes',0),('availableMemoryBytes',True),
                            ('minimumFreeBytes',1),('minimumAvailableMemoryBytes',1),('runtimeBudgetsChanged',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):capacity.validate(dict(value,**{key:changed}))

    def test_maximum_reader_failure_and_late_original_change_are_never_retried(self):
        helper,raw=self.producer()
        with patch.object(capacity,'check',return_value=capacity_record('verify')), \
             patch.object(m.maximum_native,'qualify',side_effect=ValueError('original rejected')) as maximum:
            with self.assertRaisesRegex(ValueError,'original rejected'):
                m.verify(self.root/'failed',helper.path,m.MAXIMUM_PROFILE,helper.pins)
            self.assertEqual(1,maximum.call_count)
        self.assertEqual('FAIL',m.read(self.root/'failed/receipt.json')['status'])
        def changed(*args):
            (raw/'synthetic.bin').write_bytes(b'changed after replay');return maximum_result()
        with patch.object(capacity,'check',return_value=capacity_record('verify')),patch.object(m.maximum_native,'qualify',side_effect=changed):
            with self.assertRaises(ValueError):m.qualify(helper.path,m.MAXIMUM_PROFILE,helper.pins)


if __name__=='__main__':unittest.main()
