"""Complete-backup orchestration guards; synthetic producers earn no native credit."""
import copy
from pathlib import Path
import re
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import required_four_resource_run as m
from . import test_required_four_resource_run as old
from . import test_wire_archive as archive
from . import phase3_resource_cohort as cohort
from .test_process_toolchain import record


def replay():
    value=old.replay();value.update(schema=m.gate.BACKUP_SCHEMA,profile=m.gate.BACKUP_PROFILE)
    value['original']=m.marked(value['original'],m.BACKUP_PROFILE)
    value['negatives']['bootstrap-source']=[dict(m.gate.SOURCE_NEGATIVE)]
    value['negatives']['wire-layout']=[dict(m.gate.LAYOUT_NEGATIVE)]
    return m.marked(value,m.BACKUP_PROFILE)


class BackupResourceRunTest(unittest.TestCase):
    def setUp(self):
        self.helper=old.RequiredFourResourceRunTest();self.helper.setUp();self.addCleanup(self.helper.doCleanups)
        self.root=self.helper.root;self.path=self.helper.path;self.pins=self.helper.pins
        self.convert_generated(self.path/'workspace')
        receipt=m.read(self.path/'receipt.json');raw=m.locate(self.path/'workspace',m.BACKUP_PROFILE)
        m.h.save(self.path/'collection.json',m.collect(raw,m.BACKUP_PROFILE))
        receipt.update(profile=m.BACKUP_PROFILE,command=['mvn',*m.command(m.BACKUP_PROFILE)],
                       junit=m.junit(self.path/'workspace'/m.h.MODULE/'target/surefire-reports',m.BACKUP_PROFILE),
                       collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        m.h.save(self.path/'receipt.json',m.marked(receipt,m.BACKUP_PROFILE))

    def convert_generated(self,work):
        raw=m.locate(work,m.BACKUP_PROFILE);(raw/'wire.json').unlink()
        fixture=archive.WireArchiveTest();fixture.root=raw;fixture.original()
        path=work/m.h.MODULE/'target/surefire-reports/TEST-original.xml'
        tree=ET.parse(path);suite=tree.getroot();cls=m.PACKAGE+m.BACKUP_CLASS
        suite.set('name',cls);suite.find('testcase').set('classname',cls);suite.find('testcase').set('name',m.BACKUP_METHOD)
        tree.write(path)

    def test_explicit_backup_command_keeps_all_observations_and_ordinary_cohort(self):
        normal=m.command(m.PROFILE);backup=m.command(m.BACKUP_PROFILE)
        flags={s for s in normal if s.startswith('-Dv53.')}
        self.assertEqual(flags,{s for s in backup if s.startswith('-Dv53.')})
        java=(m.h.ROOT/m.h.MODULE/'src/test/java/io/github/patricklfdm/generalsearch/replication/V53BackupJoiningQualification.java').read_text()
        observations=set(re.findall(r'"(v53\.[a-zA-Z.]+)"',java)) - {'v53.joining.sourceFault'}
        self.assertEqual({'-D'+v+'=true' for v in observations},flags)
        self.assertIn('-Dtest='+m.BACKUP_CLASS+'#'+m.BACKUP_METHOD,backup)
        self.assertIn('-DargLine=-Xmx4g',backup)
        self.assertFalse(any('retry' in v.lower() or 'skipTests' in v or 'timeout' in v.lower() for v in backup))
        self.assertEqual(m.PROFILE,cohort.MEMBERS['required-four'][1])
        self.assertNotIn(m.BACKUP_PROFILE,[v[1] for v in cohort.MEMBERS.values()])

    def test_collection_only_marks_partial_and_checks_original_segment_bytes(self):
        raw=m.locate(self.path/'workspace',m.BACKUP_PROFILE)
        with patch.object(m.gate,'qualify_backup',side_effect=AssertionError('collection cannot qualify')):
            value=m.collect(raw,m.BACKUP_PROFILE)
        self.assertEqual(('PARTIAL',False,False),(value['status'],value['observedResourcesQualified'],value['phase3Complete']))
        m.check_markers(value,m.BACKUP_PROFILE)
        segment=next((raw/'segmented-wire/wire/segments').iterdir());segment.write_bytes(b'changed')
        with self.assertRaises(ValueError):m.collect(raw,m.BACKUP_PROFILE)

    def test_backup_producer_cannot_be_admitted_as_the_empty_supplement(self):
        m.member(self.path,m.BACKUP_PROFILE,self.pins)
        with self.assertRaisesRegex(ValueError,'successful unretried producer'):m.member(self.path,m.PROFILE,self.pins)
        for marker in ('bootstrapSource','wireLayout'):
            receipt=m.read(self.path/'receipt.json');changed=copy.deepcopy(receipt);changed.pop(marker)
            m.h.save(self.path/'receipt.json',changed)
            try:
                with self.assertRaisesRegex(ValueError,'receipt'):m.member(self.path,m.BACKUP_PROFILE,self.pins)
            finally:m.h.save(self.path/'receipt.json',receipt)

    def test_exact_class_method_command_and_unretried_report_are_required(self):
        receipt=m.read(self.path/'receipt.json')
        for mutation in ('command','retries','junit'):
            changed=copy.deepcopy(receipt)
            if mutation=='command':changed['command']=['mvn',*m.command(m.PROFILE)]
            elif mutation=='retries':changed['retries']=1
            else:changed['junit']['method']=m.METHOD
            m.h.save(self.path/'receipt.json',changed)
            try:
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):m.member(self.path,m.BACKUP_PROFILE,self.pins)
            finally:m.h.save(self.path/'receipt.json',receipt)
        reports=self.path/'workspace'/m.h.MODULE/'target/surefire-reports';path=reports/'TEST-original.xml'
        tree=ET.parse(path);ET.SubElement(tree.getroot().find('testcase'),'rerunFailure');tree.write(path)
        with self.assertRaisesRegex(ValueError,'unretried passing test'):m.junit(reports,m.BACKUP_PROFILE)

    def test_complete_backup_gate_and_all_149_negatives_are_required(self):
        with patch.object(m.gate,'qualify',side_effect=AssertionError('EMPTY gate reached')), \
             patch.object(m.gate,'qualify_backup',return_value=replay()) as gate:
            value=m.qualify(self.path,m.BACKUP_PROFILE,self.pins)
        self.assertEqual(m.source_policy.SEGMENTED,gate.call_args.kwargs['wire_layout'])
        self.assertEqual('required-four-backup-observed-ownership',value['scope']);m.check_markers(value,m.BACKUP_PROFILE)
        self.assertEqual(149,sum(map(len,value['qualification']['negatives'].values())))
        self.assertFalse(value['combinedResourcesQualified']);self.assertFalse(value['phase3Complete'])
        for field in ('bootstrap-source','wire-layout',*m.gate.NEGATIVES):
            bad=replay();bad['negatives'][field].pop()
            with patch.object(m.gate,'qualify_backup',return_value=bad),self.assertRaises(ValueError):
                m.qualify(self.path,m.BACKUP_PROFILE,self.pins)
        with self.assertRaises(ValueError):m.check_result(replay(),m.PROFILE)

    def test_source_or_original_failure_is_retained_and_never_retried(self):
        output=self.root/'failed-verifier'
        with patch.object(m.gate,'qualify_backup',side_effect=ValueError('original rejected')) as gate:
            with self.assertRaisesRegex(ValueError,'original rejected'):m.verify(output,self.path,m.BACKUP_PROFILE,self.pins)
            self.assertEqual(1,gate.call_count)
        failed=m.read(output/'receipt.json');self.assertEqual('FAIL',failed['status']);m.check_markers(failed,m.BACKUP_PROFILE)
        raw=m.locate(self.path/'workspace',m.BACKUP_PROFILE)
        def changed(*args,**kwargs):
            (raw/'synthetic.bin').write_bytes(b'changed');return replay()
        with patch.object(m.gate,'qualify_backup',side_effect=changed),self.assertRaisesRegex(ValueError,'original collection'):
            m.qualify(self.path,m.BACKUP_PROFILE,self.pins)

    def test_capture_uses_one_complete_native_test_then_the_exact_source_collector(self):
        output=self.root/'capture';commands=[]
        def execute(args,work,log,**kwargs):
            commands.append(args);log.write_text('synthetic execution only')
            if len(commands)==1:self.helper.generated(work);self.convert_generated(work)
            else:m.h.save(output/'collection.json',m.collect(m.locate(work,m.BACKUP_PROFILE),m.BACKUP_PROFILE))
            return dict(exit=0)
        with patch.object(m.h,'source_copy',side_effect=self.helper.source),patch.object(m.tc,'capture',return_value=record()), \
             patch.object(m.h,'execute',side_effect=execute):
            value=m.capture(output,'mvn',m.BACKUP_PROFILE)
        self.assertEqual('PARTIAL',value['status']);self.assertEqual(2,len(commands))
        self.assertEqual(['mvn',*m.command(m.BACKUP_PROFILE)],commands[0])
        self.assertIn(m.BACKUP_PROFILE,commands[1]);m.check_markers(value,m.BACKUP_PROFILE)
        m.member(output,m.BACKUP_PROFILE,m.read(output/'pins.json'))

    def test_failed_native_capture_preserves_failure_and_has_no_second_attempt(self):
        output=self.root/'failed-capture'
        with patch.object(m.h,'source_copy',side_effect=self.helper.source),patch.object(m.tc,'capture',return_value=record()), \
             patch.object(m.h,'execute',return_value={'exit':1}) as execute:
            with self.assertRaisesRegex(ValueError,'Maven failed'):m.capture(output,'mvn',m.BACKUP_PROFILE)
            self.assertEqual(1,execute.call_count)
        receipt=m.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
        m.check_markers(receipt,m.BACKUP_PROFILE)


if __name__=='__main__':unittest.main()
