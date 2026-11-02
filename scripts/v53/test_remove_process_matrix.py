"""Synthetic metadata proves matrix guards, never execution of the native cohort."""
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import remove_process_matrix as m


class RemoveProcessMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cases=m.KINDS[:3];self.paths={case:self.root/m.slug(case) for case in self.cases}
        for case,path in self.paths.items():self.producer(path,case)
        first=self.paths[self.cases[0]]
        self.pins=[m.h.digest((first/name).read_bytes()) for name in ('source.json','build.json','toolchain.json')]+['f'*64]

    def producer(self,path,case):
        work=path/'workspace';work.mkdir(parents=True);(work/'original.java').write_bytes(b'original source')
        source=dict(head='a'*40,files={'original.java':m.h.digest(b'original source')});m.h.save(path/'source.json',source)
        build={}
        for name in m.BUILDS:
            p=work/name;p.mkdir(parents=True);(p/'original.class').write_bytes(b'original build');build[name]=m.h.inventory(p)
        m.h.save(path/'build.json',build);m.h.save(path/'toolchain.json',dict(exit=0,stdout='synthetic pinned tools',stderr=''))
        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name=m.run.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=m.run.CLASS,name=m.run.METHOD));ET.ElementTree(suite).write(reports/'TEST-fixture.xml')
        raw=work/m.h.MODULE/'target/v53-remove-retirement-process/run-00000000-0000-0000-0000-000000000001';raw.mkdir(parents=True)
        profile=m.run.selected(case);mode=profile['mode'];(raw/'profile.json').write_bytes(m.gate.f.canonical(profile))
        m.h.save(raw/'process.json',dict(parentPid=1,childPid=2,resumePid=3,mode=mode,index=5,point=profile['point'],
                                      exit=23 if mode=='halt' else 137,resumeExit=0,publicReady=False,liveLockRefused=mode=='kill'))
        for name,worker in ((mode,'interrupted-worker'),('resume','resumed-worker')):
            (raw/worker).mkdir();(raw/'history'/f'{name}-opened-0').mkdir(parents=True);(raw/worker/'stderr').write_text('')
        (raw/'history/process-trace.jsonl').write_text('collection fixture only\n')
        (raw/'history/original-plan.gsbp').write_bytes(case.encode())
        (raw/'interrupted-worker/stdout').write_text('SNAPSHOT '+mode+'-opened-0\nCUT '+json.dumps(dict(index=5,event=profile['point']),sort_keys=True,separators=(',',':'))+'\n')
        (raw/'resumed-worker/stdout').write_text('SNAPSHOT resume-opened-0\nREADY resume\nCLOSED resume\n')
        m.h.save(raw/'resumed-worker/ready.json',dict(state='READY',cut=dict(index=7,view=dict(operation=None)),operation=dict(phase='COMPLETED'),publicReady=False))
        (raw/'resumed-worker/ready.gsrp').write_bytes(b'not physical evidence')
        m.h.save(path/'collection.json',m.run.collect(raw,case));m.h.save(path/'execution.json',dict(exit=0))
        command=['mvn','-o','-B','-ntp','-f','reactor/pom.xml','-pl','../'+m.h.MODULE,'-am','-Dsurefire.failIfNoSpecifiedTests=false',
                 '-Dtest='+m.run.CLASS.rsplit('.',1)[-1]+'#'+m.run.METHOD,'-Dv53.remove.retirement.process='+case,'test']
        receipt=dict(schema='gse-v53-remove-process-execution-v1',status='PARTIAL',executionStatus='PASS',case=case,collectionComplete=True,
                     physicalHistoryQualified=False,processDeathQualified=False,phase3Complete=False,retries=0,execution=dict(exit=0),
                     sourceSha256=m.h.digest((path/'source.json').read_bytes()),baseHead=source['head'],command=command,
                     junit=m.run.junit(reports),buildSha256=m.h.digest((path/'build.json').read_bytes()),
                     toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()),raw=raw.relative_to(path).as_posix(),
                     collectionSha256=m.h.digest((path/'collection.json').read_bytes()))
        m.h.save(path/'receipt.json',receipt)

    def receipt(self,case=None,**changes):
        path=self.paths[case or self.cases[0]]/'receipt.json';value=m.read(path);value.update(changes);m.h.save(path,value)

    def member(self):return m.member(self.paths[self.cases[0]],self.cases[0],*self.pins[:3])

    @staticmethod
    def replay(raw,*,workers):
        return dict(original=dict(status='PARTIAL',ballotForceCompositionQualified=True,phase3Complete=False,
                                  precondition=dict(retirementRetentionCompositionQualified=True)),mutatedFullPrerequisiteReplayed=False,
                    negatives=sorted([dict(case=name,status='REJECTED',reason=reason,retirementReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)
                                      for name,reason in m.gate.NEGATIVES.items()],key=lambda v:v['case']))

    def matrix(self,paths=None,workers=2):
        with patch.object(m,'KINDS',self.cases),patch.object(m,'reader_manifest',return_value=dict(sha256=self.pins[-1])),\
             patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths,*self.pins,workers=workers)

    def test_catalogue_is_complete_unique_and_whole_history_only(self):
        self.assertEqual(52,len(m.KINDS));self.assertEqual(52,len({m.slug(v) for v in m.KINDS}))
        self.assertEqual(set(m.run.CASES),set(m.KINDS))
        self.assertEqual({(p,c,k) for p in ('4-REMOVE','5-REMOVE') for c in m.run.POINTS for k in ('halt','kill')},
                         {tuple(v.split(',')) for v in m.KINDS})

    def test_all_originals_are_replayed_and_nested_negatives_are_exact(self):
        with patch.object(m.gate,'qualify',side_effect=self.replay) as replay:result=self.matrix()
        self.assertEqual(3,replay.call_count);self.assertEqual('PASS',result['status']);self.assertEqual(54,result['negativeCases'])
        self.assertEqual(list(self.cases),[v['case'] for v in result['cases']]);self.assertFalse(result['phase3Complete'])
        self.assertFalse(result['allMembershipProfilesQualified'])

    def test_all_52_synthetic_members_keep_the_exact_catalogue_and_scope(self):
        paths=dict(self.paths)
        for case in m.KINDS:
            if case not in paths:
                paths[case]=self.root/m.slug(case);self.producer(paths[case],case)
        with patch.object(m,'reader_manifest',return_value=dict(sha256=self.pins[-1])),\
             patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor),patch.object(m.gate,'qualify',side_effect=self.replay) as replay:
            result=m.validate(paths,*self.pins,workers=4)
        self.assertEqual(52,replay.call_count);self.assertEqual(936,result['negativeCases'])
        self.assertEqual(list(m.KINDS),[v['case'] for v in result['cases']]);self.assertFalse(result['phase3Complete'])

    def test_later_member_cannot_change_already_checked_receipt(self):
        calls=[]
        def change(raw,**kwargs):
            calls.append(raw);result=self.replay(raw,**kwargs)
            if len(calls)==3:self.receipt(note='changed by later member')
            return result
        with patch.object(m.gate,'qualify',side_effect=change),self.assertRaisesRegex(ValueError,'producer changed before completion'):
            self.matrix(workers=1)

    def test_missing_extra_and_aliased_members_fail_before_replay(self):
        variants=[{k:v for k,v in self.paths.items() if k!=self.cases[0]},dict(self.paths,extra=self.root),
                  dict(self.paths,**{self.cases[1]:self.paths[self.cases[0]]})]
        for paths in variants:
            with patch.object(m.gate,'qualify') as replay,self.assertRaises(ValueError):self.matrix(paths)
            replay.assert_not_called()

    def test_invalid_hashes_reader_drift_and_worker_bounds_refuse(self):
        for pin in range(4):
            changed=list(self.pins);changed[pin]='master'
            with self.assertRaisesRegex(ValueError,'pinned hashes'):m.check_pins(*changed)
        with patch.object(m,'reader_manifest',return_value=dict(sha256='e'*64)),self.assertRaisesRegex(ValueError,'pinned reader'):m.check_pins(*self.pins)
        for workers in (0,5,True,1.5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.matrix(workers=workers)

    def test_failed_wrong_case_retried_or_claimed_native_qualification_refuses(self):
        original=m.read(self.paths[self.cases[0]]/'receipt.json')
        for changes in (dict(status='FAIL'),dict(executionStatus='FAIL'),dict(case=self.cases[1]),dict(retries=1),dict(retries=False),
                        dict(collectionComplete=False),dict(physicalHistoryQualified=True),dict(processDeathQualified=True),dict(phase3Complete=True)):
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,'successful whole member'):self.member()

    def test_exact_execution_command_and_unretried_junit_required(self):
        original=m.read(self.paths[self.cases[0]]/'receipt.json')
        for changes,reason in ((dict(execution=dict(exit=False)),'successful processes'),(dict(execution=dict(exit=0,note='different')),'execution receipt'),
                               (dict(command=['mvn','test']),'exact whole command'),(dict(junit={}), 'exact JUnit receipt')):
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,reason):self.member()
        self.receipt(**original);reports=self.paths[self.cases[0]]/'workspace'/m.h.MODULE/'target/surefire-reports'
        suite=m.run.ET.parse(reports/'TEST-fixture.xml');m.run.ET.SubElement(suite.getroot()[0],'flakyFailure');suite.write(reports/'TEST-fixture.xml')
        with self.assertRaisesRegex(ValueError,'unretried test'):self.member()

    def test_changed_source_classes_and_toolchain_refuse(self):
        path=self.paths[self.cases[0]];source=path/'workspace/original.java';source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'recorded source changed'):self.member()
        source.write_bytes(b'original source');compiled=path/'workspace/target/classes/original.class';compiled.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'original built bytes'):self.member()
        compiled.write_bytes(b'original build');m.h.save(path/'toolchain.json',dict(exit=0,stdout='new',stderr=''))
        self.receipt(toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'toolchain receipt'):self.member()

    def test_path_escape_links_and_duplicate_metadata_refuse(self):
        path=self.paths[self.cases[0]];receipt=m.read(path/'receipt.json');self.receipt(raw='../elsewhere')
        with self.assertRaisesRegex(ValueError,'original history path'):self.member()
        self.receipt(**receipt);raw=path/receipt['raw'];moved=raw.with_name('saved');raw.rename(moved);raw.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(ValueError):self.member()
        (path/'receipt.json').write_text('{"status":"PASS","status":"PARTIAL"}')
        with self.assertRaisesRegex(ValueError,'duplicate metadata'):self.member()

    def test_collection_status_is_rechecked_from_actual_process_observations(self):
        path=self.paths[self.cases[0]];raw=path/m.read(path/'receipt.json')['raw'];process=m.read(raw/'process.json');process['resumePid']=process['childPid']
        m.h.save(raw/'process.json',process)
        collection=m.read(path/'collection.json');collection['inventory']=m.h.inventory(raw);m.h.save(path/'collection.json',collection)
        self.receipt(collectionSha256=m.h.digest((path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'distinct original workers'):self.member()

    def test_copied_original_histories_cannot_fill_different_slots(self):
        first=self.paths[self.cases[0]];path=self.paths[self.cases[1]];raw=path/m.read(path/'receipt.json')['raw']
        original=(first/m.read(first/'receipt.json')['raw']/'history/original-plan.gsbp').read_bytes()
        (raw/'history/original-plan.gsbp').write_bytes(original);m.h.save(path/'collection.json',m.run.collect(raw,self.cases[1]))
        self.receipt(self.cases[1],collectionSha256=m.h.digest((path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'distinct original histories'):self.matrix()

    def test_replay_failures_are_retained_and_other_members_still_finish(self):
        def fail(raw,**kwargs):
            if raw.parents[4].name==m.slug(self.cases[0]):raise ValueError('physical failure')
            return self.replay(raw,**kwargs)
        with patch.object(m.gate,'qualify',side_effect=fail):result=self.matrix()
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['declaredRemoveProcessMatrixQualified'])
        self.assertEqual(2,sum(v['status']=='PASS' for v in result['cases']))
        self.assertEqual('physical failure',result['cases'][0]['failure']['message'])

    def test_bad_composition_or_negative_reason_is_not_acceptance(self):
        for kind in ('scope','missing','reason','prior'):
            result=self.replay(None,workers=1)
            if kind=='scope':result['original']['ballotForceCompositionQualified']=False
            elif kind=='missing':result['negatives'].pop()
            elif kind=='reason':result['negatives'][0]['reason']='unrelated failure'
            else:result['original']['precondition']['retirementRetentionCompositionQualified']=False
            with self.subTest(kind=kind),self.assertRaises(ValueError):m.check_result(result,self.cases[0])

    def test_source_changes_during_replay_and_reader_changes_at_end_refuse(self):
        path=self.paths[self.cases[0]]
        def change(raw,**kwargs):
            result=self.replay(raw,**kwargs);(path/'workspace/original.java').write_bytes(b'changed');return result
        with patch.object(m,'reader_manifest',return_value=dict(sha256=self.pins[-1])),patch.object(m.gate,'qualify',side_effect=change):
            with self.assertRaisesRegex(ValueError,'recorded source changed'):m.qualify_member(path,self.cases[0],*self.pins)
        (path/'workspace/original.java').write_bytes(b'original source')
        with patch.object(m,'reader_manifest',side_effect=[dict(sha256=self.pins[-1]),dict(sha256='e'*64)]),patch.object(m.gate,'qualify',side_effect=self.replay):
            with self.assertRaisesRegex(ValueError,'pinned reader'):m.qualify_member(path,self.cases[0],*self.pins)


if __name__=='__main__':unittest.main()
