"""Writer-boundary and orchestration guards; synthetic bytes are not native evidence."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from . import native_joint_floor_history as m


def samples():
    f=m.floor.f;catalog=f.catalog()
    def sample(kind):return f.sample(catalog['records'][kind]['schema'],catalog['types'])
    offered={};sources=[]
    for node in m.floor.NODES:
        value=dict(sample('GENERATION'),node=node);raw=f.encode('records','GENERATION',value);digest=m.h.digest(raw)
        offered[digest]={'generation.gsr':raw,'00.image':b'original-image','source.gscp':b'original-packet'}
        sources.append(dict(voter=node,generation=digest,catalog=value['catalog'],snapshot=value['application']))
    floor=dict(sample('FLOOR'),node='node-2',sources=sources)
    return offered,f.encode('records','FLOOR',floor)


def raw_tree(raw,case):
    raw.mkdir(parents=True);side=raw/'joint-floor-recovery';side.mkdir()
    m.h.save(side/'receipt.json',m.floor.partial_scope(*m.selected(case)))
    (raw/'original-plan.gsbp').write_bytes(b'synthetic-plan')
    captures=raw/'source-retirement-captures';captures.mkdir();(captures/'prefix').write_bytes(b'synthetic-prefix')


def reports(path):
    path.mkdir(parents=True,exist_ok=True)
    suite=ET.Element('testsuite',dict(name=m.CLASS,tests='1',failures='0',errors='0',skipped='0'))
    ET.SubElement(suite,'testcase',dict(classname=m.CLASS,name=m.METHOD))
    ET.ElementTree(suite).write(path/'TEST-native.xml');return suite


class NativeJointFloorHistoryTest(unittest.TestCase):
    def test_all_sixteen_whole_histories_have_exact_unretried_commands(self):
        self.assertEqual(16,len(m.CASES));self.assertEqual(16,len(set(m.CASES)))
        for case in m.CASES:
            args=m.command(case);self.assertEqual(1,sum(a.startswith('-Dtest=') for a in args))
            self.assertIn('-Dv53.native.partial.joint='+case,args)
            self.assertFalse(any('retry' in a.lower() or 'timeout' in a.lower() for a in args))
        for case in (False,None,'','0,FLOOR_COPY_CREATED','01,FLOOR_COPY_CREATED','4,FLOOR_COPIES_FORCED','4,FLOOR_MEMBER_FORCED '):
            with self.subTest(case=case),self.assertRaisesRegex(ValueError,'exact case'):m.command(case)

    def test_declared_partial_cut_cannot_claim_halt_or_weaken_scope(self):
        for ordinal in (True,False,0,5,'1'):
            with self.subTest(ordinal=ordinal),self.assertRaisesRegex(ValueError,'declared partial writer cut'):
                m.floor.partial_scope(ordinal,'FLOOR_COPY_CREATED')
        for field,value in [('handoff',False),('handoff',1),('processDeath',True),('phase3Complete',True),('extra','field')]:
            scope=dict(m.floor.partial_scope(4,'FLOOR_MEMBER_FORCED'),**{field:value})
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'bounded scope'):m.floor.writer_case(scope)
        with self.assertRaisesRegex(ValueError,'bounded scope'):
            m.floor.writer_case(dict(m.floor.SCOPE,ordinal=4))

    def test_writer_prefix_retains_each_real_body_boundary_and_local_last(self):
        offered,proposal=samples();ordered=sorted(offered,key=lambda k:(m.floor.f.decode(offered[k]['generation.gsr'],'records','GENERATION')['node']=='node-2',k))
        for ordinal in range(1,5):
            for cut in m.floor.PARTIAL_CUTS:
                with self.subTest(ordinal=ordinal,cut=cut):
                    value=m.floor.writer_prefix(offered,proposal,m.floor.partial_scope(ordinal,cut));files=value['interrupted']
                    self.assertEqual(ordinal,value['chargedCopies']);self.assertEqual(cut,value['events'][-1])
                    self.assertEqual(ordinal-1,value['events'].count('FLOOR_COPY_HANDED_OFF'))
                    self.assertNotIn('floor-copies/floor.gsr',files)
                    path='floor-copies/'+ordered[ordinal-1]
                    self.assertIn(path,files);self.assertIsNone(files[path])
                    expected=[] if cut=='FLOOR_COPY_CREATED' else ['generation.gsr']
                    if cut in ('FLOOR_IMAGE_FORCED','FLOOR_MEMBER_FORCED'):expected+=['00.image']
                    if cut=='FLOOR_MEMBER_FORCED':expected+=['source.gscp']
                    self.assertEqual(set(expected),{name[len(path)+1:] for name in files if name.startswith(path+'/')})
                    for earlier in ordered[:ordinal-1]:
                        self.assertTrue(all(files['floor-copies/'+earlier+'/'+n]==raw for n,raw in offered[earlier].items()))
                    for later in ordered[ordinal:]:self.assertNotIn('floor-copies/'+later,files)
        self.assertEqual('node-2',m.floor.f.decode(offered[ordered[-1]]['generation.gsr'],'records','GENERATION')['node'])

    def test_complete_copy_legacy_scope_preserves_order_and_exact_bytes(self):
        offered,proposal=samples();value=m.floor.writer_prefix(offered,proposal,m.floor.SCOPE)
        events,files,_,dirs=m.floor.generation.floor.transaction(offered,proposal)
        points=[v['event'] for v in events];self.assertEqual(points[:points.index('FLOOR_COPIES_FORCED')+1],value['events'])
        complete=dict({name:None for name in dirs},**files);self.assertEqual(complete,value['completed'])
        del complete['floor-copies/floor.gsr'];self.assertEqual(complete,value['interrupted'])
        self.assertEqual(4,value['chargedCopies'])

    def test_missing_actual_cut_is_rejected_instead_of_truncating_at_end(self):
        offered,proposal=samples()
        for value in offered.values():value.pop('00.image')
        with self.assertRaisesRegex(ValueError,'declared writer cut absent'):
            m.floor.writer_prefix(offered,proposal,m.floor.partial_scope(1,'FLOOR_IMAGE_FORCED'))

    def test_collection_is_partial_preserves_capture_inventory_and_exact_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'raw';raw_tree(root,m.CASES[0]);before=m.h.inventory(root)
            with patch.object(m.ledger,'validate') as replay:result=m.collect(root,m.CASES[0])
            replay.assert_not_called();self.assertEqual('PARTIAL',result['status']);self.assertFalse(result['nativeHistoryQualified'])
            self.assertEqual(before,m.h.inventory(root));self.assertEqual(before,result['inventory'])
            self.assertEqual(m.h.inventory(root/'source-retirement-captures'),result['captureInventory'])
            with self.assertRaisesRegex(ValueError,'exact producer cut'):m.collect(root,m.CASES[1])
            (root/'source-retirement-captures/prefix').unlink();(root/'source-retirement-captures').rmdir()
            with self.assertRaises(ValueError):m.collect(root,m.CASES[0])

    def test_missing_skipped_retried_and_wrong_junit_are_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);suite=reports(root);self.assertEqual(1,m.junit(root)['tests'])
            for mode in ('skip','retry','failure','method','count','extra'):
                changed=copy.deepcopy(suite)
                if mode=='skip':changed.set('skipped','1');ET.SubElement(changed[0],'skipped')
                elif mode=='retry':ET.SubElement(changed[0],'flakyFailure')
                elif mode=='failure':ET.SubElement(changed[0],'failure')
                elif mode=='method':changed[0].set('name','other')
                elif mode=='count':changed.set('tests','2')
                else:ET.ElementTree(suite).write(root/'TEST-extra.xml')
                ET.ElementTree(changed).write(root/'TEST-native.xml')
                with self.subTest(mode=mode),self.assertRaises(ValueError):m.junit(root)

    def test_capture_rejects_bad_case_or_existing_output_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.h,'execute') as run:
            root=Path(tmp);(root/'keep').write_bytes(b'retained')
            with self.assertRaises(ValueError):m.capture(root,'mvn','bad')
            with self.assertRaises(FileExistsError):m.capture(root,'mvn',m.CASES[0])
            run.assert_not_called();self.assertEqual(b'retained',(root/'keep').read_bytes())

    def test_failed_source_capture_is_retained_and_never_runs_maven(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.h,'source_copy',side_effect=ValueError('source failed')),patch.object(m.h,'execute') as run:
            output=Path(tmp)/'failed'
            with self.assertRaisesRegex(ValueError,'source failed'):m.capture(output,'mvn',m.CASES[0])
            receipt=m.floor.read(output/'receipt.json');self.assertEqual('FAIL',receipt['status']);self.assertFalse(receipt['collectionComplete'])
            run.assert_not_called()

    def test_partial_negatives_change_only_declared_cut_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'raw';raw_tree(root,m.CASES[-1]);path=root/'joint-floor-recovery/receipt.json'
            original=path.read_bytes();before=m.h.inventory(root)
            self.assertEqual(20,len(m.floor.negative_cases(root)))
            for name in m.floor.PARTIAL_NEGATIVES:
                path.write_bytes(original);m.floor.mutate(root,name);changed=m.h.inventory(root)
                self.assertNotEqual(before,changed)
                key='joint-floor-recovery/receipt.json'
                self.assertEqual({k:v for k,v in before['files'].items() if k!=key},
                                 {k:v for k,v in changed['files'].items() if k!=key})
                self.assertEqual(before['directories'],changed['directories'])
            m.h.save(path,m.floor.SCOPE)
            self.assertEqual(17,len(m.floor.negative_cases(root)))
            with self.assertRaisesRegex(ValueError,'requires original partial case'):m.floor.mutate(root,'partial-cut')

    def test_validate_refuses_existing_output_and_never_changes_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);raw=root/'raw';raw_tree(raw,m.CASES[0]);out=root/'result.json';out.write_text('retained')
            argv=['native','validate',str(out),'--case',m.CASES[0],'--raw',str(raw)]
            with patch.object(m.sys,'argv',argv),patch.object(m.ledger,'validate') as replay:
                with self.assertRaisesRegex(ValueError,'refuses overwrite'):m.main()
                replay.assert_not_called()
            self.assertEqual('retained',out.read_text())

    def test_capture_records_no_false_completion_when_maven_fails(self):
        from .test_process_toolchain import record
        def source_copy(repo,work):
            work.mkdir();(work/'source').write_bytes(b'original')
            return dict(head='a'*40,files={'source':m.h.digest(b'original')})
        with tempfile.TemporaryDirectory() as tmp,patch.object(m.h,'source_copy',side_effect=source_copy),\
             patch.object(m,'reader_manifest',return_value=dict(files={},sha256='b'*64)),\
             patch.object(m.tc,'capture',return_value=record()),patch.object(m.h,'execute',return_value=dict(exit=1,elapsedSeconds=1)),\
             patch.object(m,'collect') as collection:
            out=Path(tmp)/'failed'
            with self.assertRaisesRegex(ValueError,'execution failed'):m.capture(out,'mvn',m.CASES[0])
            receipt=m.floor.read(out/'receipt.json');self.assertEqual('FAIL',receipt['status'])
            self.assertEqual(1,receipt['execution']['exit']);self.assertFalse(receipt['collectionComplete'])
            collection.assert_not_called();self.assertEqual(b'original',(out/'workspace/source').read_bytes())


if __name__=='__main__':unittest.main()
