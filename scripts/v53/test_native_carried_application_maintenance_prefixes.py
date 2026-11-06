"""Composition guards; synthetic sidecars never substitute for native history."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_maintenance_prefixes as p
from . import test_native_carried_application_protocol as original_fixture


class NativeCarriedApplicationMaintenancePrefixesTest(unittest.TestCase):
    def fixture(self,root):
        observed=root/'previous/previous/observed';sidecar=root/'maintenance'
        initial=observed/'history/before-network/node-1';initial.mkdir(parents=True)
        for name in ('root.gsr','node.gsr'):(initial/name).write_bytes(name.encode())
        _,_,selector=original_fixture.NativeCarriedApplicationProtocolTest().floor()
        base={'root.gsr':b'root.gsr','node.gsr':b'node.gsr','selector.gsr':selector,
              'generations':None,'generations/a':None,'generations/a/original.image':b'original pinned image'}
        expected={family:[] for family in p.FAMILIES}
        for life in (1,2):
            resource=observed/f'resources/life-{life}';resource.mkdir(parents=True)
            events=[dict(node='node-1',event='NODE_OPEN',incarnation=life)]
            for family,module in p.FAMILIES.items():
                directory=sidecar/family/f'life-{life}';objects=directory/'objects';objects.mkdir(parents=True)
                if family=='retirement':
                    rows=[('generation',point,dict(base)) for point in ('RETIREMENT_OLD_FILES_FORCED','RETIREMENT_CREATED')]
                    schema=p.retirement.shared.SCHEMA
                elif family=='campaigns':
                    rows=[('grant',point,dict(base)) for point in ('PROMISE_BEFORE_WRITE','PROMISE_WRITTEN')]
                    schema=p.campaign.CAPTURE_SCHEMA
                else:
                    schema=p.floor.CAPTURE_SCHEMA
                    if life==1:rows=[('floor',point,dict(base)) for point in ('FLOOR_RESERVED','FLOOR_DIRECTORY_CREATED')]
                    else:
                        pinned=dict(base,**{'floor-copies':None,'floor-copies/local.gsr':selector})
                        cleared=dict(pinned);del cleared['floor-copies/local.gsr']
                        rows=[('floor','FLOOR_LOCAL_ORIGINAL_FORCED',dict(base)),
                              ('floor','FLOOR_LOCAL_SELECTOR_WRITTEN',pinned),
                              ('floor','FLOOR_LOCAL_SELECTOR_FORCED',pinned),
                              ('floor','FLOOR_LOCAL_PARENT_FORCED',pinned),
                              ('floor','FLOOR_AUTHORITY_WRITTEN',pinned),
                              ('floor-release','FLOOR_RELEASE_PROPOSAL_CLEARED',pinned),
                              ('floor-release','FLOOR_RELEASE_LOCAL_CLEARED',cleared)]
                for at,(kind,point,state) in enumerate(rows,1):
                    index=len(events);events.append(dict(node='node-1',event=point,incarnation=life))
                    files=[]
                    for name,raw in sorted(state.items()):
                        identity=dict(directory=True) if raw is None else dict(size=len(raw),sha256=p.shared.sha(raw))
                        if raw is not None:(objects/identity['sha256']).write_bytes(raw)
                        files.append(dict(name=name,identity=identity))
                    (directory/f'capture-{at:04d}.json').write_bytes(p.f.canonical(dict(schema=schema,node='node-1',kind=kind,
                        point=point,eventIndex=index,files=files)))
                    expected[family].append(dict(life=life,node='node-1',kind=kind,point=point,eventIndex=index,files=p.shared.r.physical(state)))
            encoded=p.f.canonical(events);(resource/'events.json').write_bytes(encoded)
            identity=dict(root='a'*64,life=life,pid=100+life,terminal='CUT_PREFIX' if life==1 else 'CLOSED',eventsSha256=p.shared.sha(encoded))
            (resource/'index.json').write_bytes(p.f.canonical(identity))
            for family,module in p.FAMILIES.items():
                directory=sidecar/family/f'life-{life}'
                (directory/'collection.json').write_bytes(p.f.canonical(dict(identity,schema=module.SCHEMA,
                    captures=len(list(directory.glob('capture-*.json'))),storedBytes=sum(v.stat().st_size for v in directory.rglob('*') if v.is_file()))))
        return observed,sidecar,expected

    def test_three_families_share_original_events_but_not_collection_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));before=p.collection.inventory(Path(temp))
            result=p.replay(observed,sidecar,expected)
            self.assertEqual(17,result['capturedPrefixes']);self.assertEqual(set(p.FAMILIES),set(result['families']))
            self.assertTrue(result['maintenanceTransientBytesQualified'])
            for flag in ('postCutTailObserved','fullTransientBytesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):self.assertFalse(result[flag])
            self.assertEqual(before,p.collection.inventory(Path(temp)))

    def test_all_existing_identity_and_layout_mutations_still_refuse(self):
        generic=set(p.retirement.NEGATIVES)-{'borrowed-prefix','wrong-floor','early-generation-delete','late-generation-delete','early-journal-rotation','leftover-saved-file'}
        for family,module in p.FAMILIES.items():
            for name in sorted(generic):
                with self.subTest(family=family,name=name),tempfile.TemporaryDirectory() as temp:
                    observed,sidecar,expected=self.fixture(Path(temp));module.mutate(sidecar/family,name)
                    with self.assertRaisesRegex(ValueError,'^'+module.NEGATIVES[name]+'$'):p.replay(observed,sidecar,expected)

    def test_pinned_original_selector_and_release_mutations_refuse_physical_comparison(self):
        for name,point in p.PIN_POINTS.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                observed,sidecar,expected=self.fixture(Path(temp));p.mutate_pin(sidecar/'floors',name)
                with self.assertRaisesRegex(ValueError,'^carried prefix exact original state: '+point+'$'):
                    p.replay(observed,sidecar,expected)

    def test_complete_original_application_chain_precedes_plans_and_negatives(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.prerequisite,'validate',side_effect=ValueError('old application invalid')),\
                 patch.object(p,'plans') as plans,patch.object(p,'replay') as replay,patch.object(p,'mutate_pin') as mutate:
                with self.assertRaisesRegex(ValueError,'old application invalid'):p.qualify(temp)
            plans.assert_not_called();replay.assert_not_called();mutate.assert_not_called()

    def test_missing_extra_family_expected_plan_or_wrapper_cannot_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));(sidecar/'extra').mkdir()
            with self.assertRaisesRegex(ValueError,'exact family inventory'):p.replay(observed,sidecar,expected)
            (sidecar/'extra').rmdir();expected.pop('floors')
            with self.assertRaisesRegex(ValueError,'complete expected families'):p.replay(observed,sidecar,expected)
            (Path(temp)/'extra').mkdir()
            with patch.object(p.prerequisite,'validate') as prerequisite:
                with self.assertRaisesRegex(ValueError,'capture wrapper inventory'):p.validate(temp)
            prerequisite.assert_not_called()

    def test_original_drift_cannot_be_hidden_by_successful_capture_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                 patch.object(p.prerequisite,'validate'),patch.object(p,'replay'):
                with self.assertRaisesRegex(ValueError,'capture original changed'):p.validate(temp)

    def test_each_expected_family_comes_from_the_original_application_projector(self):
        projected={name:[name] for name in p.PLAN_KEYS.values()}
        with patch.object(p.model,'plans',return_value=projected) as project:
            self.assertEqual({family:projected[name] for family,name in p.PLAN_KEYS.items()},p.plans('/original'))
        project.assert_called_once_with('/original')

    def test_qualification_rejects_exact_mutations_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));before=p.collection.inventory(Path(temp))
            selected={label:reason for label,reason in p.NEGATIVES.items() if label.endswith(':missing-copy') or label.startswith('floors:pin-')}
            with patch.object(p.prerequisite,'validate',return_value={'synthetic prerequisite':True}),\
                 patch.object(p,'plans',return_value=expected),patch.object(p,'NEGATIVES',selected):
                result=p.qualify(temp)
            self.assertEqual([(k,v) for k,v in selected.items()],[(v['case'],v['reason']) for v in result['negatives']])
            self.assertTrue(result['originalStorageUnchanged']);self.assertEqual(before,p.collection.inventory(Path(temp)))

    def test_unrelated_rejection_or_accepted_mutation_gets_no_credit(self):
        for failure,reason in ((None,'accepted negative'),(ValueError('unrelated'),'unrelated negative')):
            with tempfile.TemporaryDirectory() as temp:
                self.fixture(Path(temp))
                with patch.object(p,'validate'),patch.object(p,'plans',return_value={'retirement':[]}),\
                     patch.object(p,'NEGATIVES',{'retirement:missing-copy':'expected'}),\
                     patch.object(p.retirement,'replay',side_effect=failure):
                    with self.assertRaisesRegex(ValueError,reason):p.qualify(temp)


if __name__=='__main__':unittest.main()
