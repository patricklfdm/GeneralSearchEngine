"""Synthetic provenance and orchestration tests; not native qualification."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import node_rename_matrix as m
from .test_process_toolchain import record


def history(raw,case):
    raw.mkdir(parents=True);(raw/'history').mkdir();(raw/'process').mkdir()
    expected=m.run.selected(case);cut,mode=expected['cut'],expected['mode']
    save=lambda p,v:p.write_bytes(m.gate.f.canonical(v))
    save(raw/'process/spec.json',{})  # Deliberately not a physical plan.
    children=[];events=[]
    for life in (1,2):
        start=dict(life=life,pid=100+life,mode=mode)
        child=dict(life=life,pid=100+life,started=start,exit=(73 if mode=='halt' else 137) if life==1 else 0)
        child.update(dict(lockHeldBeforeDeath=True,lockReleasedAfterDeath=True) if life==1 else dict(drained=True));children.append(child)
        opened=dict(node='node-1',incarnation=life,event='NODE_OPEN');events.append(opened)
        rows=[dict(action='started',value=start),dict(action='event',value=opened),dict(action='opened',value=life)]
        def installed(number):
            data=('synthetic installation '+str(number)).encode();(raw/'history'/f'selected-{number}.gsr').write_bytes(data)
            rows.append(dict(action='installed',value=dict(number=number,bytes=base64.b64encode(data).decode())))
        installed(life)
        snapshots=['applied-1','published-1','first-ready'] if life==1 else ['applied-2','published-2','applied-3','published-3','second-ready']
        rows.extend(dict(action='snapshot',value=v) for v in snapshots)
        if life==1:
            event=dict(node='node-1',incarnation=1,event=cut);events.append(event);rows.append(dict(action='event',value=event))
            rows.append(dict(action='cut',value=dict(name=cut,mode=mode,pid=101)))
            events.append(dict(node='node-1',event='NODE_CRASH'))
        else:
            installed(3)
            rows.extend(dict(action='snapshot',value=v) for v in ('applied-4','published-4','applied-5','published-5'))
            rows.append(dict(action='closed',value=2))
        (raw/'process'/f'life-{life}.jsonl').write_bytes(b'\n'.join(m.gate.f.canonical(v) for v in rows)+b'\n')
        (raw/'process'/f'life-{life}.stderr').write_bytes(b'')
    save(raw/'history/events.json',events);save(raw/'history/wire.json',[])
    (raw/'history/original-plan.gsbp').write_bytes(case.encode())
    save(raw/'process/result.json',dict(**expected,children=children,status='PARTIAL',powerLoss=False,phase3Complete=False))


class NodeRenameMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.reader=dict(files={'reader.py':m.h.digest(b'synthetic reader')},sha256='f'*64)
        self.reader_patch=patch.object(m,'reader_manifest',return_value=self.reader);self.reader_patch.start();self.addCleanup(self.reader_patch.stop)
        self.paths={case:self.root/m.slug(case) for case in m.KINDS}
        for case,path in self.paths.items():self.producer(path,case)
        self.case=m.KINDS[0];self.path=self.paths[self.case]
        self.pins=[m.h.digest((self.path/name).read_bytes()) for name in ('source.json','build.json')]+[
            m.process_toolchain.pin((self.path/'toolchain.json').read_bytes()),self.reader['sha256']]

    def producer(self,path,case):
        work=path/'workspace';work.mkdir(parents=True);(work/'reader.py').write_bytes(b'synthetic reader')
        m.h.save(path/'source.json',dict(head='a'*40,files=self.reader['files']))
        for name in m.BUILDS:
            directory=work/name;directory.mkdir(parents=True);(directory/'original.class').write_bytes(b'synthetic classes')
        m.h.save(path/'build.json',{name:m.h.inventory(work/name) for name in m.BUILDS})
        m.h.save(path/'toolchain.json',record());reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name=m.run.CLASS,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=m.run.CLASS,name=m.run.METHODS[case]));ET.ElementTree(suite).write(reports/'TEST-original.xml')
        raw=work/m.h.MODULE/'target/v53-node-process/run-00000000-0000-0000-0000-000000000001';history(raw,case)
        m.h.save(path/'collection.json',m.run.collect(raw,case));m.h.save(path/'execution.json',dict(exit=0))
        m.h.save(path/'receipt.json',dict(schema=m.run.SCHEMA,status='PARTIAL',executionStatus='PASS',case=case,
            collectionComplete=True,physicalHistoryQualified=False,processDeathQualified=False,phase3Complete=False,retries=0,
            execution=dict(exit=0),baseHead='a'*40,command=['mvn',*m.run.command(case)],junit=m.run.junit(reports,case),
            raw=raw.relative_to(path).as_posix(),**{key+'Sha256':m.h.digest((path/file).read_bytes()) for key,file in
            (('source','source.json'),('build','build.json'),('toolchain','toolchain.json'),('collection','collection.json'))}))

    def receipt(self,**changes):
        value=m.read(self.path/'receipt.json');value.update(changes);m.h.save(self.path/'receipt.json',value)

    def raw(self):return self.path/m.read(self.path/'receipt.json')['raw']
    def member(self):return m.member(self.path,self.case,*self.pins)

    @staticmethod
    def replay(raw):
        case=(raw/'history/original-plan.gsbp').read_text();expected=m.run.selected(case)
        original=dict(status='PASS',scope='current-node-rename-recovery',**expected,originalFirst=True,physicalReplay=True,
            processRestart=True,carriedOriginalEntry=True,interruptedClientSuccess=False,powerLoss=False,publicRuntime=False,
            phase3Complete=False,campaigns=3,publishedSlots=5,freshLeaderJvms=2,network={})
        negatives=m.gate.p.negative_cases(expected['cut'])|m.gate.EXTRA_NEGATIVES
        return dict(original=original,negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in negatives.items()])

    def matrix(self,paths=None,workers=2):
        with patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths,*self.pins,workers=workers)

    def test_four_cases_exactly_match_native_methods(self):
        source=(m.h.ROOT/m.h.MODULE/'src/test/java/io/github/patricklfdm/generalsearch/replication/V53NodeRenameProcessTest.java').read_text()
        self.assertEqual(4,len(m.KINDS));self.assertEqual(4,len({m.slug(v) for v in m.KINDS}))
        for case,method in m.run.METHODS.items():
            cut,mode=case.split(',');self.assertIn(f'{method}()throws Exception{{run("{cut}","{mode}");}}',source)

    def test_collect_never_claims_physical_qualification(self):
        result=m.run.collect(self.raw(),self.case);self.assertEqual('PARTIAL',result['status'])
        for key in ('physicalHistoryQualified','processDeathQualified','phase3Complete'):self.assertFalse(result[key])
        with self.assertRaises(ValueError):m.gate.validate(self.raw())

    def test_complete_cohort_replays_all_originals_and_keeps_scope(self):
        with patch.object(m.gate,'qualify',side_effect=self.replay) as replay:result=self.matrix()
        self.assertEqual(4,replay.call_count);self.assertEqual('PASS',result['status']);self.assertEqual(136,result['negativeCases'])
        self.assertTrue(result['declaredNodeRenameMatrixQualified']);self.assertFalse(result['phase3Complete'])

    def test_junit_retries_failures_and_wrong_case_reject(self):
        report=self.path/'workspace'/m.h.MODULE/'target/surefire-reports/TEST-original.xml';original=report.read_bytes()
        for tag in ('failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'):
            suite=ET.fromstring(original);ET.SubElement(suite[0],tag);ET.ElementTree(suite).write(report)
            with self.subTest(tag=tag),self.assertRaisesRegex(ValueError,'unretried test'):self.member()
        report.write_bytes(original)
        with self.assertRaisesRegex(ValueError,'unretried test'):m.run.junit(report.parent,m.KINDS[1])

    def test_forged_success_command_and_execution_reject(self):
        original=m.read(self.path/'receipt.json')
        for change in (dict(status='PASS'),dict(retries=1),dict(retries=False),dict(case=m.KINDS[1]),dict(phase3Complete=True),
                       dict(processDeathQualified=True),dict(execution=dict(exit=False)),dict(command=['mvn','test']),dict(junit={})):
            self.receipt(**dict(original,**change))
            with self.subTest(change=change),self.assertRaises(ValueError):self.member()

    def test_source_build_tools_and_reader_drift_reject(self):
        for path in (self.path/'workspace/reader.py',self.path/'workspace/target/classes/original.class',self.path/'toolchain.json'):
            original=path.read_bytes();path.write_bytes(b'changed')
            with self.subTest(path=path),self.assertRaises(ValueError):self.member()
            path.write_bytes(original)
        self.reader['files']['reader.py']='0'*64
        with self.assertRaisesRegex(ValueError,'reader belongs to producer source'):self.member()

    def test_changed_process_is_recollected_even_with_updated_hash(self):
        raw=self.raw();value=m.read(raw/'process/result.json');value['children'][1]['pid']=101
        m.h.save(raw/'process/result.json',value);collection=m.read(self.path/'collection.json');collection['inventory']=m.h.inventory(raw)
        m.h.save(self.path/'collection.json',collection);self.receipt(collectionSha256=m.h.digest((self.path/'collection.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'fresh child identities'):self.member()

    def test_invalid_case_duplicate_metadata_and_escaping_path_reject(self):
        with self.assertRaisesRegex(ValueError,'exact case'):m.run.selected('ACCEPT_RENAMED,retry')
        self.receipt(raw='../escape')
        with self.assertRaisesRegex(ValueError,'original history path'):self.member()
        (self.path/'receipt.json').write_text('{"status":"PASS","status":"PARTIAL"}')
        with self.assertRaisesRegex(ValueError,'duplicate metadata'):self.member()

    def test_linked_history_rejects(self):
        raw=self.raw();other=self.root/'saved';raw.rename(other);raw.symlink_to(other,target_is_directory=True)
        with self.assertRaises(ValueError):self.member()

    def test_missing_extra_aliased_or_copied_history_cannot_fill_matrix(self):
        for paths in ({k:v for k,v in self.paths.items() if k!=self.case},dict(self.paths,extra=self.root),
                      dict(self.paths,**{m.KINDS[1]:self.path})):
            with patch.object(m.gate,'qualify') as replay,self.assertRaises(ValueError):self.matrix(paths)
            replay.assert_not_called()
        other=self.paths[m.KINDS[1]];raw=other/m.read(other/'receipt.json')['raw']
        (raw/'history/original-plan.gsbp').write_bytes((self.raw()/'history/original-plan.gsbp').read_bytes())
        m.h.save(other/'collection.json',m.run.collect(raw,m.KINDS[1]));receipt=m.read(other/'receipt.json')
        receipt['collectionSha256']=m.h.digest((other/'collection.json').read_bytes());m.h.save(other/'receipt.json',receipt)
        with self.assertRaisesRegex(ValueError,'distinct original histories'):self.matrix()

    def test_one_failed_replay_preserved_without_retry_or_skipping_other_members(self):
        def replay(raw):
            if raw==self.raw():raise ValueError('original physical failure')
            return self.replay(raw)
        with patch.object(m.gate,'qualify',side_effect=replay) as called:result=self.matrix()
        self.assertEqual(4,called.call_count);self.assertEqual('FAIL',result['status'])
        self.assertEqual('original physical failure',result['cases'][0]['failure']['message'])
        self.assertEqual(3,sum(v['status']=='PASS' for v in result['cases']))

    def test_replay_cannot_change_already_verified_member(self):
        calls=[]
        def replay(raw):
            calls.append(raw)
            if len(calls)==4:self.receipt(note='changed')
            return self.replay(raw)
        with patch.object(m.gate,'qualify',side_effect=replay),self.assertRaisesRegex(ValueError,'changed before completion'):
            self.matrix(workers=1)

    def test_negative_list_and_conditional_late_reply_negatives_must_be_exact(self):
        from . import node_late_prepare
        original=self.replay(self.raw())
        for kind in ('missing','reason','scope','late'):
            result=copy.deepcopy(original)
            if kind=='missing':result['negatives'].pop()
            elif kind=='reason':result['negatives'][0]['reason']='unrelated'
            elif kind=='scope':result['original']['interruptedClientSuccess']=True
            else:result['original']['network']['lateUnusedPrepares']=[dict(authority=False)]
            with self.subTest(kind=kind),self.assertRaises(ValueError):m.check_result(result,self.case)
        result=copy.deepcopy(original);result['original']['network']['lateUnusedPrepares']=[dict(authority=False)]
        result['negatives'] += [dict(case=k,status='REJECTED',reason=v) for k,v in node_late_prepare.NEGATIVES.items()]
        m.check_result(result,self.case)

    def test_invalid_pins_and_parallelism_reject(self):
        for i in range(4):
            pins=list(self.pins);pins[i]='master'
            with self.assertRaisesRegex(ValueError,'pinned hashes'):m.check_pins(*pins)
        for workers in (0,5,True,1.5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.matrix(workers=workers)

    def test_failed_native_runs_once_and_retains_diagnostics(self):
        def source(repo,dest):
            dest.mkdir();return dict(head='a'*40,files={})
        output=self.root/'failed'
        with patch.object(m.h,'source_copy',side_effect=source),patch.object(m.run.process_toolchain,'capture',return_value=record()),\
             patch.object(m.h,'execute',return_value=dict(exit=1)) as execute,redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'Maven failed; original retained'):m.run.run(output,'mvn',self.case)
        execute.assert_called_once();self.assertEqual(['mvn',*m.run.command(self.case)],execute.call_args.args[0])
        receipt=m.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
        self.assertTrue((output/'execution.json').is_file());self.assertFalse(receipt['phase3Complete'])


if __name__=='__main__':unittest.main()
