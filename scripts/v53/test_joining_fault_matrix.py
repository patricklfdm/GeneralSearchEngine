"""Synthetic metadata tests never stand in for a native matrix execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from . import joining_fault_matrix as m


class JoiningFaultMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.paths={kind:self.root/kind for kind in m.KINDS}
        for kind,path in self.paths.items():self.producer(path,kind)
        first=self.paths[m.KINDS[0]]
        self.source=m.h.digest((first/'source.json').read_bytes());self.build=m.h.digest((first/'build.json').read_bytes())

    def producer(self,path,kind):
        work=path/'workspace';work.mkdir(parents=True);(work/'original.java').write_bytes(b'original source')
        source=dict(head='a'*40,files={'original.java':m.h.digest(b'original source')});m.h.save(path/'source.json',source)
        build={}
        for name in m.BUILDS:
            p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'original build');build[name]=m.h.inventory(p)
        m.h.save(path/'build.json',build);m.h.save(path/'toolchain.json',dict(exit=0,stdout='pinned unit fixture',stderr=''))
        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name=m.h.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=m.h.CLASS,name=m.h.METHOD))
        ET.ElementTree(suite).write(reports/'TEST-fixture.xml')
        raw=work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000001';raw.mkdir(parents=True)
        (raw/'original-plan.gsbp').write_bytes(kind.encode())
        collection=dict(status='PARTIAL',collectionComplete=True,nativeHistoryQualified=False,forceAndNetworkQualified=False,
                        phase3Complete=False,inventory=m.h.inventory(raw));m.h.save(path/'collection.json',collection)
        command=['mvn','-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+m.h.MODULE,'-am','-Dsurefire.failIfNoSpecifiedTests=false',
                 '-Dtest='+m.h.TEST,'-Dv53.joining.sourceFault='+kind,'test']
        receipt=dict(schema=m.h.SCHEMA,status='PARTIAL',executionStatus='PASS',sourceFault=kind,collectionComplete=True,
                     nativeHistoryQualified=False,phase3Complete=False,retries=0,execution=dict(exit=0),collectionExecution=dict(exit=0),
                     sourceSha256=m.h.digest((path/'source.json').read_bytes()),baseHead=source['head'],command=command,
                     junit=m.h.junit(reports),buildSha256=m.h.digest((path/'build.json').read_bytes()),
                     toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()),raw=raw.relative_to(path).as_posix(),
                     collectionSha256=m.h.digest((path/'collection.json').read_bytes()))
        m.h.save(path/'receipt.json',receipt)

    def receipt(self,kind='SOURCE_OFFER',**changes):
        path=self.paths[kind]/'receipt.json';value=m.read(path);value.update(changes);m.h.save(path,value)

    def run_matrix(self):return m.validate(self.paths,self.source,self.build)

    @staticmethod
    def replay(raw,progress):
        kind=raw.parents[4].name
        return dict(original=dict(status='PASS',sourceFault=kind,joiningSourceFaultQualified=True,lostReplies=1,
                                  recoveredLostReplies=1,phase3Complete=False),originalPreserved=True,
                    negatives=[dict(case=name,status='REJECTED',reason=reason) for name,reason in m.gate.NEGATIVES.items()])

    def test_complete_set_replays_all_originals_and_exact_negatives(self):
        with patch.object(m.gate,'qualify',side_effect=self.replay) as replay:
            result=self.run_matrix()
        self.assertEqual(3,replay.call_count);self.assertEqual(42,result['negativeCases']);self.assertFalse(result['phase3Complete'])
        self.assertEqual(list(m.KINDS),[v['case'] for v in result['cases']])

    def test_missing_extra_or_aliased_inputs_fail_before_replay(self):
        for paths,reason in [({k:v for k,v in self.paths.items() if k!='CHUNK'},'complete reply set'),
                             (dict(self.paths,UNKNOWN=self.root),'complete reply set'),
                             (dict(self.paths,CHUNK=self.paths['SOURCE_OFFER']),'distinct producer directories')]:
            with patch.object(m.gate,'qualify') as replay,self.assertRaisesRegex(ValueError,'^joining matrix '+reason+'$'):
                m.validate(paths,self.source,self.build)
            replay.assert_not_called()

    def test_pinned_source_and_build_are_required(self):
        for source,build in [('main',self.build),(self.source,'a'*40)]:
            with self.assertRaisesRegex(ValueError,'^joining matrix pinned source/build hashes$'):m.validate(self.paths,source,build)
        for source,build,reason in [('f'*64,self.build,'producer source'),(self.source,'f'*64,'build manifest')]:
            with self.assertRaisesRegex(ValueError,'^joining matrix exact '+reason+':'):m.validate(self.paths,source,build)

    def test_failed_partial_wrong_case_or_retried_native_receipt_cannot_pass(self):
        original=m.read(self.paths['SOURCE_OFFER']/'receipt.json')
        for changes in (dict(status='FAIL'),dict(executionStatus='FAIL'),dict(sourceFault='CHUNK'),dict(collectionComplete=False),
                        dict(nativeHistoryQualified=True),dict(phase3Complete=True),dict(retries=1),dict(retries=False)):
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,'^joining matrix successful whole member:'):self.run_matrix()

    def test_process_exit_and_exact_test_method_are_required(self):
        original=m.read(self.paths['SOURCE_OFFER']/'receipt.json')
        for changes,reason in [(dict(execution=dict(exit=1)),'successful processes'),(dict(collectionExecution=dict(exit=False)),'successful processes'),
                               (dict(command=['mvn','test']),'exact whole command'),(dict(junit={}), 'exact JUnit receipt')]:
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,'^joining matrix '+reason+':'):self.run_matrix()

    def test_changed_source_or_built_classes_fail_before_semantic_reader(self):
        path=self.paths['SOURCE_OFFER'];source=path/'workspace/original.java';source.write_bytes(b'changed')
        with patch.object(m.gate,'qualify') as replay,self.assertRaisesRegex(ValueError,'^recorded source changed:'):self.run_matrix()
        replay.assert_not_called();source.write_bytes(b'original source')
        (path/'workspace/target/classes/original.class').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'^joining matrix original built bytes:'):self.run_matrix()

    def test_raw_path_escape_extra_history_and_changed_original_are_rejected(self):
        path=self.paths['SOURCE_OFFER'];original=m.read(path/'receipt.json')
        self.receipt(raw='../original')
        with self.assertRaisesRegex(ValueError,'^joining matrix original history path:'):self.run_matrix()
        self.receipt(**original);raw=path/original['raw'];extra=raw.parent/'run-extra';extra.mkdir()
        with self.assertRaisesRegex(ValueError,'^joining matrix exact original history directory:'):self.run_matrix()
        extra.rmdir();(raw/'original-plan.gsbp').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'^joining matrix original collection:'):self.run_matrix()

    def test_mixed_toolchain_and_duplicate_original_plan_cannot_form_cohort(self):
        kind='CHUNK';path=self.paths[kind];original=(path/'toolchain.json').read_bytes()
        m.h.save(path/'toolchain.json',dict(exit=0,stdout='other Java',stderr=''));self.receipt(kind,toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'^joining matrix exact toolchain cohort$'):self.run_matrix()
        (path/'toolchain.json').write_bytes(original);self.receipt(kind,toolchainSha256=m.h.digest(original))
        receipt=m.read(path/'receipt.json');raw=path/receipt['raw'];(raw/'original-plan.gsbp').write_bytes(b'SOURCE_OFFER')
        collection=m.read(path/'collection.json');collection['inventory']=m.h.inventory(raw);m.h.save(path/'collection.json',collection)
        self.receipt(kind,collectionSha256=m.h.digest((path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'^joining matrix distinct original histories$'):self.run_matrix()

    def test_independent_replay_failure_is_not_replaced_by_native_pass(self):
        with patch.object(m.gate,'qualify',side_effect=ValueError('physical invalid')):
            with self.assertRaisesRegex(ValueError,'^physical invalid$'):self.run_matrix()

    def test_missing_or_changed_negative_results_fail(self):
        for mode in ('missing','wrong-reason','wrong-case','false-preservation'):
            def changed(raw,progress):
                value=self.replay(raw,progress)
                if mode=='missing':value['negatives'].pop()
                elif mode=='wrong-reason':value['negatives'][0]['reason']='unrelated failure'
                elif mode=='wrong-case':value['original']['sourceFault']='CHUNK'
                else:value['originalPreserved']=False
                return value
            with self.subTest(mode=mode),patch.object(m.gate,'qualify',side_effect=changed),self.assertRaisesRegex(ValueError,'^joining matrix complete replay result:'):self.run_matrix()

    def test_changes_during_replay_are_rejected(self):
        def changed(raw,progress):
            result=self.replay(raw,progress);(raw/'original-plan.gsbp').write_bytes(b'changed');return result
        with patch.object(m.gate,'qualify',side_effect=changed),self.assertRaisesRegex(ValueError,'^joining matrix original history changed:'):self.run_matrix()

    def test_source_or_receipt_changed_after_replay_is_rechecked(self):
        for mode in ('source','receipt'):
            with self.subTest(mode=mode):
                path=self.paths['SOURCE_OFFER'];before=(path/'workspace/original.java').read_bytes();receipt=m.read(path/'receipt.json')
                def changed(raw,progress):
                    result=self.replay(raw,progress)
                    if mode=='source':(path/'workspace/original.java').write_bytes(b'changed')
                    else:self.receipt(note='changed after original check')
                    return result
                reason='recorded source changed:' if mode=='source' else 'joining matrix producer changed during replay:'
                with patch.object(m.gate,'qualify',side_effect=changed),self.assertRaisesRegex(ValueError,'^'+reason):self.run_matrix()
                (path/'workspace/original.java').write_bytes(before);self.receipt(**receipt)

    def test_later_member_cannot_change_an_already_replayed_producer(self):
        def changed(raw,progress):
            result=self.replay(raw,progress)
            if result['original']['sourceFault']=='TRANSFER_COMMIT':self.receipt(note='late modification')
            return result
        with patch.object(m.gate,'qualify',side_effect=changed),self.assertRaisesRegex(ValueError,'^joining matrix producer changed before completion:'):
            self.run_matrix()

    def test_duplicate_metadata_and_linked_original_are_rejected(self):
        path=self.paths['SOURCE_OFFER'];receipt=path/'receipt.json';before=receipt.read_bytes()
        receipt.write_text('{"status":"PASS","status":"PARTIAL"}')
        with self.assertRaisesRegex(ValueError,'^joining matrix duplicate metadata key$'):self.run_matrix()
        receipt.write_bytes(before);raw=path/m.read(receipt)['raw'];moved=raw.with_name('saved');raw.rename(moved);raw.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(ValueError):self.run_matrix()


if __name__=='__main__':unittest.main()
