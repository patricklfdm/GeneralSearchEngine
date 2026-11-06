"""Synthetic decoder contracts, separate from actual native process evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_prefixes as p
from . import test_native_completion_files as fixtures


class NativeCarriedApplicationPrefixesTest(unittest.TestCase):
    def fixture(self,base):
        root=base/'observed';resource=root/'resources/life-1';resource.mkdir(parents=True)
        sidecar=base/'application';objects=sidecar/'objects';objects.mkdir(parents=True)
        fixture=fixtures.NativeCompletionFilesTest();end=dict(fixture.applied(),**{'node.gsr':b'node'})
        initial={k:v for k,v in end.items() if k!='applied-end' and not k.startswith('applied-end/')}
        for folder,files in [('before-network/node-1',initial),('at-cut/node-1',end)]:
            directory=root/'history'/folder;directory.mkdir(parents=True)
            for name,raw in sorted(files.items()):
                path=directory/name
                if raw is None:path.mkdir()
                else:path.write_bytes(raw)
        steps=p.model.application(initial,end,stop=p.CUT)
        raw_pool={p.shared.sha(raw):raw for value in end.values() if value is not None
                  for raw in (b'',value[:len(value)//2],value)}
        events=[dict(node='node-1',event='NODE_OPEN',incarnation=1)];expected=[]
        for i,(kind,point,state) in enumerate(steps,1):
            events.append(dict(node='node-1',event=point,incarnation=1))
            entries=[]
            for name,identity in sorted(state.items()):
                identity=copy.deepcopy(identity)
                if 'bytes' in identity:
                    identity['size']=identity.pop('bytes');digest=identity['sha256'];(objects/digest).write_bytes(raw_pool[digest])
                entries.append(dict(name=name,identity=identity))
            (sidecar/f'capture-{i:04d}.json').write_bytes(p.f.canonical(dict(schema=p.completion.CAPTURE_SCHEMA,
                node='node-1',kind=kind,point=point,eventIndex=i,files=entries)))
            expected.append(dict(node='node-1',kind=kind,point=point,eventIndex=i,files=state))
        encoded=p.f.canonical(events);(resource/'events.json').write_bytes(encoded)
        index=dict(root='a'*64,life=1,pid=101,terminal='CUT_PREFIX',eventsSha256=p.shared.sha(encoded))
        (resource/'index.json').write_bytes(p.f.canonical(index))
        header=dict(index,schema=p.SCHEMA,captures=len(steps),storedBytes=sum(v.stat().st_size for v in sidecar.rglob('*') if v.is_file()),
            interrupted=dict(node='node-1',point=p.CUT,eventIndex=len(events)-1))
        (sidecar/'collection.json').write_bytes(p.f.canonical(header))
        return root,sidecar,expected

    def test_complete_prefix_keeps_original_indices_without_successful_return(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,expected=self.fixture(Path(temp));self.assertEqual(expected,p.plans(root))
            before=p.collection.inventory(Path(temp));result=p.replay(root,sidecar)
            self.assertEqual(32,result['capturedPrefixes']);self.assertEqual('CUT_PREFIX',result['terminal'])
            self.assertTrue(result['interruptedApplicationBytesQualified'])
            for flag in ('postCutTailObserved','recoveryTransientBytesQualified','fullTransientBytesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):
                self.assertFalse(result[flag])
            self.assertEqual(before,p.collection.inventory(Path(temp)))

    def test_every_negative_rejects_for_its_declared_reason(self):
        for name,reason in p.NEGATIVES.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,sidecar,expected=self.fixture(Path(temp));p.mutate(sidecar,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(root,sidecar,expected)

    def test_complete_original_is_mandatory_before_capture_or_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.original,'validate',side_effect=ValueError('original failed')),patch.object(p,'replay') as replay,patch.object(p,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify(temp)
            replay.assert_not_called();mutate.assert_not_called()

    def test_original_first_qualification_preserves_evidence_and_checks_all_mutations(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,expected=self.fixture(Path(temp));before=p.collection.inventory(Path(temp))
            with patch.object(p.original,'validate',return_value={'synthetic prerequisite':True}) as prior:
                result=p.qualify(temp)
            prior.assert_called_once_with(root)
            self.assertEqual([(k,v) for k,v in p.NEGATIVES.items()],[(v['case'],v['reason']) for v in result['negatives']])
            self.assertTrue(result['originalStorageUnchanged']);self.assertEqual(before,p.collection.inventory(Path(temp)))

    def test_extra_lifetime_or_wrong_schema_cannot_claim_complete_family(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp));(Path(temp)/'life-2').mkdir()
            with patch.object(p.original,'validate') as prior:
                with self.assertRaisesRegex(ValueError,'exact wrapper inventory'):p.validate(temp)
            prior.assert_not_called()

    def test_later_original_callback_and_wrong_node_cannot_relabel_crash(self):
        for change in ('later','owner'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root,sidecar,expected=self.fixture(Path(temp));resource=root/'resources/life-1'
                events=json.loads((resource/'events.json').read_bytes())
                if change=='later':events.append(dict(node='node-2',event='WIRE_RESPONSE',incarnation=1))
                else:events[-1]['node']='node-2'
                encoded=p.f.canonical(events);(resource/'events.json').write_bytes(encoded)
                for path in (resource/'index.json',sidecar/'collection.json'):
                    value=json.loads(path.read_bytes());value['eventsSha256']=p.shared.sha(encoded);path.write_bytes(p.f.canonical(value))
                with self.assertRaisesRegex(ValueError,'exact interrupted boundary'):p.replay(root,sidecar,expected)

    def test_linked_original_events_and_distinct_process_are_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,expected=self.fixture(Path(temp));(root/'resources/life-1/events.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError,'original file digest'):p.replay(root,sidecar,expected)

    def test_extra_or_duplicate_plan_rows_cannot_count_twice(self):
        for duplicate in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                root,sidecar,expected=self.fixture(Path(temp));extra=copy.deepcopy(expected[0])
                if not duplicate:extra['eventIndex']=0
                expected.append(extra)
                with self.assertRaisesRegex(ValueError,'complete callback coverage'):p.replay(root,sidecar,expected)

    def test_plan_never_uses_captured_bytes_as_its_oracle(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,expected=self.fixture(Path(temp));p.mutate(sidecar,'application-early-ack')
            self.assertEqual(expected,p.plans(root))
            with self.assertRaisesRegex(ValueError,'exact original state'):p.replay(root,sidecar)

    def test_unrelated_or_accepted_negative_cannot_earn_credit(self):
        for error in (None,ValueError('unrelated')):
            with tempfile.TemporaryDirectory() as temp:
                root,sidecar,expected=self.fixture(Path(temp))
                with patch.object(p,'validate',return_value={}),patch.object(p,'replay',side_effect=error,return_value={}),\
                     patch.object(p,'NEGATIVES',{'missing-copy':'expected'}):
                    with self.assertRaisesRegex(ValueError,'accepted negative' if error is None else 'unrelated negative'):p.qualify(temp)

    def test_original_drift_during_negative_replay_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,expected=self.fixture(Path(temp))
            def corrupt(*args):
                (root/'history/at-cut/node-1/root.gsr').write_bytes(b'changed')
                raise ValueError('expected')
            with patch.object(p,'validate',return_value={}),patch.object(p,'replay',side_effect=corrupt),\
                 patch.object(p,'NEGATIVES',{'missing-copy':'expected'}):
                with self.assertRaisesRegex(ValueError,'qualification changed original'):p.qualify(temp)


if __name__=='__main__':unittest.main()
