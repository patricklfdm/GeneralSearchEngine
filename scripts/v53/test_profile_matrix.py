"""Synthetic matrix guards; no test here claims execution of a native cohort."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack,redirect_stdout
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import profile_matrix as m


class ProfileMatrixTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.reader=dict(files={'scripts/v53/pinned.py':m.h.digest(b'pinned reader')},sha256='f'*64)
        self.paths={p:self.root/m.slug(p) for p in m.PROFILES}
        for p,path in self.paths.items():self.producer(path,p)
        first=self.paths[m.PROFILES[0]]
        self.pins=[m.h.digest((first/n).read_bytes()) for n in ('source.json','build.json','toolchain.json')]+[self.reader['sha256']]
        self.patch=patch.object(m,'reader_manifest',return_value=self.reader);self.patch.start();self.addCleanup(self.patch.stop)

    def producer(self,path,profile):
        remove=profile in m.removal.PROFILES
        work=path/'workspace';(work/'scripts/v53').mkdir(parents=True);(work/'scripts/v53/pinned.py').write_bytes(b'pinned reader')
        source=dict(head='a'*40,files=self.reader['files']);m.h.save(path/'source.json',source)
        build={}
        for name in m.BUILDS:
            d=work/name;d.mkdir(parents=True);(d/'original.class').write_bytes(b'pinned compiled bytes');build[name]=m.h.inventory(d)
        m.h.save(path/'build.json',build);m.h.save(path/'toolchain.json',dict(exit=0,stdout='synthetic tools',stderr=''))
        cls=m.remove_run.CLASS if remove else m.h.CLASS;method=m.remove_run.METHOD if remove else m.joining_run.COMPLETE_METHOD
        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
        suite=ET.Element('testsuite',dict(name=cls,tests='1',failures='0',errors='0',skipped='0'))
        ET.SubElement(suite,'testcase',dict(classname=cls,name=method));ET.ElementTree(suite).write(reports/'TEST-original.xml')
        raw=work/m.h.MODULE/'target/v53-native-dispatch/run-00000000-0000-0000-0000-000000000001';raw.mkdir(parents=True)
        (raw/'original-plan.gsbp').write_bytes(profile.encode());(raw/'events.json').write_bytes(m.removal.f.canonical([dict(node='node-1',event='RETIREMENT_OPEN')]))
        original=dict(status='PASS',profile=profile,phase3Complete=False)
        if remove:original.update(automaticOperationCompletion=True,publicReady=False)
        else:original.update(semanticFinalAndColdQualified=True,finalAndColdReopenQualified=False)
        negatives=m.remove_run.reader.negative_cases(profile) if remove else m.joining_run.complete_reader.NEGATIVES
        semantic=dict(original=original,negatives=[dict(case=k,status='REJECTED',reason=v) for k,v in negatives.items()])
        m.h.save(path/'replay.json',semantic);m.h.save(path/'execution.json',dict(exit=0))
        receipt=dict(schema=m.remove_run.SCHEMA if remove else 'gse-v53-joining-profile-completion-v1',status='PARTIAL',profile=profile,
                     executionStatus='PASS',retries=0,phase3Complete=False,execution=dict(exit=0),replayExecution=dict(exit=0),
                     sourceSha256=m.h.digest((path/'source.json').read_bytes()),baseHead=source['head'],command=['mvn',*m.command(profile)],
                     junit=m.remove_run.junit(reports) if remove else m.joining_run.junit(reports,method),
                     buildSha256=m.h.digest((path/'build.json').read_bytes()),toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()),
                     raw=raw.relative_to(path).as_posix(),replaySha256=m.h.digest((path/'replay.json').read_bytes()),negativeCases=len(negatives))
        if remove:
            receipt.update(retirementCapturesRequested=True,transientRetirementBytesQualified=True,continuousOriginalQualified=True,
                           automaticOperationCompletion=True,publicRuntimeQualified=False,completeNetworkQualified=False,processDeathQualified=False)
            captures=raw.with_name('retirement-captures-'+raw.name);(captures/'objects').mkdir(parents=True)
            m.h.save(raw/'transition-round-result.json',dict(profile=profile))
            entries=[];total=0
            for name,data in (('node.gsr',b'synthetic node'),('root.gsr',b'synthetic root')):
                owner=raw/'before-network/node-1';owner.mkdir(parents=True,exist_ok=True);(owner/name).write_bytes(data)
                digest=m.h.digest(data);(captures/'objects'/digest).write_bytes(data);total+=len(data)
                entries.append(dict(name=name,identity=dict(size=len(data),sha256=digest)))
            capture=captures/'capture-0001.json'
            capture.write_bytes(m.removal.f.canonical(dict(schema=m.removal.prior.SCHEMA,node='node-1',kind='generation',point='RETIREMENT_OPEN',eventIndex=0,files=entries)))
            (captures/'collection.json').write_bytes(m.removal.f.canonical(dict(schema=m.removal.prior.SCHEMA,profile=profile,
                eventsSha256=m.h.digest((raw/'events.json').read_bytes()),resultSha256=m.h.digest((raw/'transition-round-result.json').read_bytes()),
                captures=1,storedBytes=total+capture.stat().st_size)))
            copies,inventory=m.removal.prior.collect(raw,captures,profile);self.assertEqual(1,len(copies))
            m.h.save(path/'inventory.json',m.h.inventory(raw));m.h.save(path/'capture-inventory.json',inventory)
            prefix=dict(status='PARTIAL',profile=profile,transientRetirementBytesQualified=True,processDeathQualified=False,phase3Complete=False,capturedPrefixes=1)
            m.h.save(path/'retirement-prefixes.json',prefix)
            receipt.update(prefixExecution=dict(exit=0),capturedPrefixes=1,captures=captures.relative_to(path).as_posix(),
                           prefixReplaySha256=m.h.digest((path/'retirement-prefixes.json').read_bytes()))
        else:receipt.update(completeExecutionRequested=True,semanticChainQualified=True,semanticFinalAndColdQualified=True,
                            finalAndColdReopenQualified=False,forceAndNetworkQualified=False)
        m.h.save(path/'inventory.json',m.h.inventory(raw));m.h.save(path/'receipt.json',receipt)

    def receipt(self,profile='3-ADD',**changes):
        path=self.paths[profile]/'receipt.json';value=m.read(path);value.update(changes);m.h.save(path,value)

    def member(self,profile='3-ADD'):return m.member(self.paths[profile],profile,*self.pins)

    @staticmethod
    def result(profile):
        original=dict(status='PARTIAL',profile=profile,phase3Complete=False,processDeathQualified=False,
                      allMembershipProfilesQualified=False,currentSourceNativeCohortQualified=False)
        if profile in m.removal.PROFILES:
            original.update(ballotForceCompositionQualified=True,precondition=dict(transientRetirementBytesQualified=True))
            result=dict(original=original,mutatedFullPrerequisiteReplayed=False,
                        negatives=[dict(case=k,status='REJECTED',reason=v,retirementReplay='PASS',physicalWireAndOtherObservationsUnchanged=True)
                                   for k,v in m.removal.NEGATIVES.items()])
        else:
            adoption=[] if profile.endswith('ADD') else [dict(promiseAppended=True)]
            original.update(ballotCompositionQualified=True,adoptionFences=adoption,precondition=dict(peerLedgerCompositionQualified=True,
                            futureLedgerCompositionQualified=True,learnerLedgerCompositionQualified=True))
            negatives=[]
            for k,v in m.joining.NEGATIVES.items():
                if not adoption and k in m.joining.EXTRA:
                    reason='no original adoption transaction' if k=='adoption-fence-missing' else 'no original adoption promise append'
                    negatives.append(dict(case=k,status='NOT_APPLICABLE',reason=reason))
                else:negatives.append(dict(case=k,status='REJECTED',reason=v,mutationScope='allocator-promise-and-adoption-boundaries'))
            result=dict(original=original,negatives=negatives,mutatedPrerequisiteReplayed=False)
        result['negatives'].sort(key=lambda v:v['case']);return result

    def matrix(self,paths=None,workers=3,progress=None):
        with patch('concurrent.futures.ProcessPoolExecutor',ThreadPoolExecutor):
            return m.validate(self.paths if paths is None else paths,*self.pins,workers=workers,progress=progress)

    def readers(self):
        stack=ExitStack();stack.enter_context(patch.object(m.joining,'qualify',side_effect=lambda raw,p,**kw:self.result(p)))
        stack.enter_context(patch.object(m.removal,'qualify',side_effect=lambda raw,c,p,**kw:self.result(p)))
        return stack

    def test_catalogue_matches_frozen_seven_profiles_and_whole_commands(self):
        self.assertEqual(m.PROFILES,m.catalogue());self.assertEqual(7,len(set(m.PROFILES)))
        for p in m.PROFILES:
            args=m.command(p);self.assertEqual('test',args[-1]);self.assertNotIn('-DskipTests',args)
            self.assertEqual(p.endswith('REMOVE'),'-Dv53.remove.retirement.captures=true' in args)

    def test_all_seven_synthetic_producers_replay_once_without_phase_completion(self):
        rows=[]
        with self.readers():result=self.matrix(progress=rows.append)
        self.assertEqual('PASS',result['status']);self.assertEqual(7,result['wholeHistories']);self.assertTrue(result['declaredMembershipProfileMatrixQualified'])
        self.assertEqual(list(m.PROFILES),[v['profile'] for v in result['cases']]);self.assertEqual(7,len(rows))
        self.assertEqual(5*len(m.joining.NEGATIVES)+2*len(m.removal.NEGATIVES),result['negativeCases'])
        for k in ('phase3Complete','processDeathQualified','originalObservationCoverageComplete'):self.assertFalse(result[k])

    def test_missing_extra_and_aliased_members_refuse_before_replay(self):
        for paths in ({k:v for k,v in self.paths.items() if k!='3-ADD'},dict(self.paths,extra=self.root),dict(self.paths,**{'4-ADD':self.paths['3-ADD']})):
            with patch.object(m.joining,'qualify') as replay,self.assertRaises(ValueError):self.matrix(paths)
            replay.assert_not_called()

    def test_hash_reader_and_worker_bounds_are_enforced(self):
        for i in range(4):
            pins=list(self.pins);pins[i]='master'
            with self.assertRaisesRegex(ValueError,'pinned hashes'):m.check_pins(*pins)
        with patch.object(m,'reader_manifest',return_value=dict(sha256='e'*64)),self.assertRaisesRegex(ValueError,'pinned reader'):self.member()
        for workers in (0,5,True,1.5):
            with self.assertRaisesRegex(ValueError,'replay workers'):self.matrix(workers=workers)

    def test_failed_retried_wrong_profile_or_overclaimed_member_refuses(self):
        original=m.read(self.paths['3-ADD']/'receipt.json')
        for changes in (dict(status='FAIL'),dict(executionStatus='FAIL'),dict(profile='4-ADD'),dict(retries=1),dict(retries=False),dict(phase3Complete=True)):
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,'successful whole member'):self.member()

    def test_prefix_same_view_and_uncaptured_remove_are_ineligible(self):
        for changes in (dict(completeExecutionRequested=False),dict(sameViewRecoveryRequested=False)):
            self.receipt(**changes)
            with self.assertRaisesRegex(ValueError,'ordinary complete joining'):self.member()
        self.receipt('4-REMOVE',retirementCapturesRequested=False)
        with self.assertRaisesRegex(ValueError,'captured ordinary REMOVE'):self.member('4-REMOVE')

    def test_producer_must_contain_the_exact_current_reader(self):
        self.reader['files']['scripts/v53/new.py']='d'*64
        with self.assertRaisesRegex(ValueError,'readers belong to producer source'):self.member()

    def test_changed_source_classes_build_pin_and_tools_are_rejected(self):
        path=self.paths['3-ADD'];source=path/'workspace/scripts/v53/pinned.py';source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'recorded source changed'):self.member()
        source.write_bytes(b'pinned reader');compiled=path/'workspace/target/classes/original.class';compiled.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'original built bytes'):self.member()
        compiled.write_bytes(b'pinned compiled bytes');m.h.save(path/'toolchain.json',dict(exit=0,stdout='different tools',stderr=''))
        self.receipt(toolchainSha256=m.h.digest((path/'toolchain.json').read_bytes()))
        with self.assertRaisesRegex(ValueError,'toolchain receipt'):self.member()

    def test_exact_command_execution_and_unretried_junit(self):
        original=m.read(self.paths['3-ADD']/'receipt.json')
        for changes,reason in ((dict(command=['mvn','test']),'exact whole command'),(dict(execution=dict(exit=False)),'successful processes'),
                               (dict(execution=dict(exit=0,extra=True)),'execution receipt'),(dict(junit={}), 'exact JUnit receipt')):
            self.receipt(**dict(original,**changes))
            with self.assertRaisesRegex(ValueError,reason):self.member()
        self.receipt(**original);report=self.paths['3-ADD']/'workspace'/m.h.MODULE/'target/surefire-reports/TEST-original.xml'
        tree=ET.parse(report);ET.SubElement(tree.getroot()[0],'flakyFailure');tree.write(report)
        with self.assertRaisesRegex(ValueError,'unretried JUnit'):self.member()

    def test_retained_semantic_negatives_and_prefix_receipts_cannot_be_relabelled(self):
        self.receipt(negativeCases=0)
        with self.assertRaisesRegex(ValueError,'retained semantic replay'):self.member()
        self.receipt('4-REMOVE',capturedPrefixes=2)
        with self.assertRaisesRegex(ValueError,'retained retirement replay'):self.member('4-REMOVE')

    def test_remove_capture_requires_exact_original_history_bytes(self):
        path=self.paths['4-REMOVE'];receipt=m.read(path/'receipt.json');raw=path/receipt['raw']
        m.h.save(raw/'events.json',[dict(node='node-2',event='RETIREMENT_OPEN')]);m.h.save(path/'inventory.json',m.h.inventory(raw))
        with self.assertRaisesRegex(ValueError,'original history binding'):self.member('4-REMOVE')

    def test_paths_links_and_duplicate_json_refuse(self):
        path=self.paths['3-ADD'];receipt=m.read(path/'receipt.json');self.receipt(raw='../other')
        with self.assertRaisesRegex(ValueError,'original history path'):self.member()
        self.receipt(**receipt);raw=path/receipt['raw'];saved=self.root/'saved';raw.rename(saved);raw.symlink_to(saved,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'collection root'):self.member()
        (path/'receipt.json').write_text('{"status":"PASS","status":"PARTIAL"}')
        with self.assertRaisesRegex(ValueError,'duplicate metadata'):self.member()

    def test_original_plan_duplicates_cannot_fill_different_slots(self):
        a=self.paths['3-ADD'];b=self.paths['4-ADD'];ra=a/m.read(a/'receipt.json')['raw'];rb=b/m.read(b/'receipt.json')['raw']
        (rb/'original-plan.gsbp').write_bytes((ra/'original-plan.gsbp').read_bytes())
        m.h.save(b/'inventory.json',m.h.inventory(rb))
        with self.readers(),self.assertRaisesRegex(ValueError,'distinct original histories'):self.matrix()

    def test_bad_reader_output_and_unrelated_or_missing_negatives_refuse(self):
        for profile in ('3-ADD','4-REMOVE','3-REPLACE'):
            for change in ('scope','missing','reason','prior'):
                result=self.result(profile)
                if change=='scope':result['original']['phase3Complete']=True
                elif change=='missing':result['negatives'].pop()
                elif change=='reason':result['negatives'][0]['reason']='unrelated error'
                else:result['original']['precondition']={}
                with self.subTest(profile=profile,change=change),self.assertRaises(ValueError):m.check_result(result,profile)
        result=self.result('3-REPLACE');result['negatives']=[dict(v,status='NOT_APPLICABLE') for v in result['negatives']]
        with self.assertRaisesRegex(ValueError,'exact negative results'):m.check_result(result,'3-REPLACE')

    def test_failed_replay_preserves_failure_and_finishes_other_six(self):
        def replay(raw,profile,**kwargs):
            if profile=='3-ADD':raise ValueError('original physical failure')
            return self.result(profile)
        with self.readers(),patch.object(m.joining,'qualify',side_effect=replay):result=self.matrix()
        self.assertEqual('FAIL',result['status']);self.assertFalse(result['declaredMembershipProfileMatrixQualified'])
        self.assertEqual(6,sum(v['status']=='PASS' for v in result['cases']));self.assertEqual('original physical failure',result['cases'][0]['failure']['message'])

    def test_joining_original_inventory_is_required_and_not_recreated_by_verifier(self):
        path=self.paths['3-ADD'];raw=path/m.read(path/'receipt.json')['raw'];(raw/'events.json').write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError,'original history inventory'):self.member()

    def test_original_source_changes_during_replay_refuse(self):
        def change(raw,profile,**kwargs):
            (self.paths[profile]/'workspace/scripts/v53/pinned.py').write_bytes(b'changed');return self.result(profile)
        with patch.object(m.joining,'qualify',side_effect=change),self.assertRaisesRegex(ValueError,'recorded source changed'):
            m.qualify_member(self.paths['3-ADD'],'3-ADD',*self.pins)

    def test_later_member_cannot_change_a_completed_receipt(self):
        def change(raw,profile,**kwargs):
            if profile=='5-REPLACE':self.receipt(note='changed by later member')
            return self.result(profile)
        with self.readers(),patch.object(m.joining,'qualify',side_effect=change),self.assertRaisesRegex(ValueError,'producer changed before completion'):
            self.matrix(workers=1)

    def test_relocation_keeps_metadata_binding_without_rewriting_original_paths(self):
        before=self.member();destination=self.root/'relocated';shutil.copytree(self.paths['3-ADD'],destination)
        after=m.member(destination,'3-ADD',*self.pins)
        self.assertEqual({k:v for k,v in before.items() if k!='raw'},{k:v for k,v in after.items() if k!='raw'})

    def test_cli_keeps_failure_receipt_and_never_overwrites_existing_output(self):
        output=self.root/'cli';argv=['profile_matrix','member',str(output),'--producer',str(self.paths['3-ADD']),'--profile','3-ADD']
        for name,value in zip(('source','build','toolchain','reader'),self.pins):argv+=['--'+name+'-sha256',value]
        self.receipt(status='FAIL')
        with patch('sys.argv',argv),self.assertRaisesRegex(ValueError,'successful whole member'):m.main()
        receipt=m.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertFalse(receipt['phase3Complete'])
        with patch('sys.argv',argv),self.assertRaises(FileExistsError):m.main()


class PortableProfileCollectorTest(unittest.TestCase):
    def test_joining_collector_retains_pre_replay_inventory_and_rejects_changed_original(self):
        collector=m.joining_run
        for mutate in (False,True):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'run';observed={}
                def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
                def execute(args,work,log,**kwargs):
                    if args[0]=='mvn':
                        for name in m.BUILDS:(work/name).mkdir(parents=True,exist_ok=True)
                        reports=work/m.h.MODULE/'target/surefire-reports';reports.mkdir()
                        suite=ET.Element('testsuite',dict(name=m.h.CLASS,tests='1',failures='0',errors='0',skipped='0'))
                        ET.SubElement(suite,'testcase',dict(classname=m.h.CLASS,name=collector.COMPLETE_METHOD))
                        ET.ElementTree(suite).write(reports/'TEST-original.xml')
                        raw=work/m.h.MODULE/'target/v53-native-dispatch/run-fixture';raw.mkdir(parents=True)
                        (raw/'original').write_bytes(b'original execution');observed['raw']=raw
                    else:
                        observed['inventory']=m.read(output/'inventory.json')
                        if mutate:(observed['raw']/'original').write_bytes(b'changed during replay')
                        original=dict(status='PASS',profile='3-ADD',phase3Complete=False,
                                      semanticFinalAndColdQualified=True,finalAndColdReopenQualified=False)
                        m.h.save(log,dict(original=original,negatives=[dict(case=k,status='REJECTED',reason=v)
                                     for k,v in collector.complete_reader.NEGATIVES.items()]))
                    return dict(exit=0)
                from . import process_toolchain
                with patch.object(collector.h,'source_copy',side_effect=source),patch.object(collector.h,'execute',side_effect=execute),\
                     patch.object(process_toolchain,'capture',return_value=dict(exit=0)),redirect_stdout(io.StringIO()):
                    if mutate:
                        with self.assertRaisesRegex(ValueError,'joining prefix original changed'):
                            collector.run(output,'mvn','3-ADD',complete=True,portable_toolchain=True)
                    else:collector.run(output,'mvn','3-ADD',complete=True,portable_toolchain=True)
                self.assertEqual(m.h.digest(b'original execution'),observed['inventory']['files']['original'])
                self.assertEqual(observed['inventory'],m.read(output/'inventory.json'))
                self.assertEqual('FAIL' if mutate else 'PARTIAL',m.read(output/'receipt.json')['status'])

    def test_portable_tool_identity_is_retained_and_does_not_retry_failed_native_execution(self):
        from . import process_toolchain
        for collector,profile,options in ((m.joining_run,'3-ADD',dict(complete=True)),(m.remove_run,'4-REMOVE',dict(retirement_captures=True))):
            with self.subTest(profile=profile),tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'run'
                def source(repo,work):work.mkdir();return dict(head='a'*40,files={})
                tools=dict(exit=0,fixture='portable identity only; not real tools')
                with patch.object(collector.h,'source_copy',side_effect=source),patch.object(process_toolchain,'capture',return_value=tools) as capture,\
                     patch.object(collector.h,'execute',return_value=dict(exit=1)) as execute,redirect_stdout(io.StringIO()):
                    with self.assertRaisesRegex(ValueError,'Maven failed'):collector.run(output,'mvn',profile,portable_toolchain=True,**options)
                capture.assert_called_once_with('mvn',output/'workspace');execute.assert_called_once()
                receipt=m.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertEqual(0,receipt['retries'])
                self.assertEqual(m.h.digest((output/'toolchain.json').read_bytes()),receipt['toolchainSha256'])
                self.assertEqual(tools,m.read(output/'toolchain.json'))

    def test_invalid_portable_option_does_not_launch_or_create_output(self):
        for collector,profile in ((m.joining_run,'3-ADD'),(m.remove_run,'4-REMOVE')):
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'run'
                for value in ('true',1,None):
                    with self.assertRaisesRegex(ValueError,'portable toolchain option'):collector.run(output,'mvn',profile,portable_toolchain=value)
                self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
