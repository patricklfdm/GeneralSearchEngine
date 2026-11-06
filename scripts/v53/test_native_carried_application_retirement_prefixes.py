"""Decoder/plan composition guards; synthetic files are not native authority."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_application_retirement_prefixes as p


class NativeCarriedApplicationRetirementPrefixesTest(unittest.TestCase):
    def fixture(self,base):
        observed=base/'previous/observed';directory=observed/'resources/life-2';directory.mkdir(parents=True)
        sidecar=base/'retirement';objects=sidecar/'objects';objects.mkdir(parents=True)
        before={'root.gsr':b'root','node.gsr':b'node','selector.gsr':b'new selector','pending.accept':b'old vote',
                'applied-end':None,'applied-end/selector.gsr':b'old selector','applied-end/plan.json':b'old plan',
                'applied-end/ack.gsr':b'old ack','applied-end/application.image':b'old image'}
        body=p.f.canonical(dict(authority={'selection':'a'*64},files=[dict(path=k.removeprefix('applied-end/'),type='file',
            **p.model.retirement.e.info(v)) for k,v in sorted(before.items()) if k.startswith('applied-end/')]))
        header=struct.pack('>4sHHII',b'GSAT',1,3,0,len(body));marker=header+bytes.fromhex(p.shared.sha(header+body))+body
        frames={'ENTRY':b'entry','PAYLOAD':b'payload','SELECTOR':b'old selector','CERTIFICATE':b'old certificate'}
        decoded={'NODE':{'identity':dict(node='node-1',storage='storage')},'SELECTOR':dict(root='a'*64,node='node-1'),
                 'CERTIFICATE':dict(root='a'*64)}
        image={'gse-backup-'+k:k.encode() for k in ('checkpoint','manifest','metadata')}
        with patch.object(p.model.replay.f,'decode',side_effect=lambda raw,family,kind:decoded[kind]),\
             patch.object(p.model.replay,'image_members',return_value=image):
            replay=p.model.replay._scratch(before,frames,b'old image')
        with patch.object(p.model.application.p.data,'pending',return_value=(frames,('PROOF','CERTIFICATE'))),\
             patch.object(p.model.application,'retire',return_value=p.model.retirement.staging.without_staging(before)),\
             patch.object(p.model.retirement,'authority',return_value=marker),patch.object(p.model.replay,'retirement',return_value=replay):
            steps=p.model.transaction(before)
        claim=p.f.canonical(dict(schema='gse-v53-application-replay/1.3',root='a'*64,node='node-1',storage='storage',
            selector=p.shared.sha(b'old selector'),certificate=p.shared.sha(b'old certificate')))
        values=[v for v in before.values() if v is not None]+[marker,claim]+list(image.values())
        pool={p.shared.sha(raw):raw for value in values for raw in (b'',value[:len(value)//2],value)}
        initial=observed/'history/before-network/node-1';initial.mkdir(parents=True)
        for name in ('root.gsr','node.gsr'):(initial/name).write_bytes(before[name])
        events=[dict(node='node-1',event='NODE_OPEN',incarnation=2)];expected=[]
        for at,(kind,point,state) in enumerate(steps,1):
            events.append(dict(node='node-1',event=point,incarnation=2));files=[]
            for key,identity in sorted(state.items()):
                identity=dict(identity)
                if 'bytes' in identity:
                    identity['size']=identity.pop('bytes');digest=identity['sha256'];(objects/digest).write_bytes(pool[digest])
                files.append(dict(name=key,identity=identity))
            (sidecar/f'capture-{at:04d}.json').write_bytes(p.f.canonical(dict(schema=p.CAPTURE_SCHEMA,node='node-1',
                kind=kind,point=point,eventIndex=at,files=files)))
            expected.append(dict(life=2,node='node-1',kind=kind,point=point,eventIndex=at,files=state))
        encoded=p.f.canonical(events);(directory/'events.json').write_bytes(encoded)
        index=dict(root='a'*64,pid=202,life=2,terminal='CLOSED',eventsSha256=p.shared.sha(encoded))
        (directory/'index.json').write_bytes(p.f.canonical(index))
        header=dict(index,schema=p.SCHEMA,captures=len(expected),storedBytes=sum(v.stat().st_size for v in sidecar.rglob('*') if v.is_file()))
        (sidecar/'collection.json').write_bytes(p.f.canonical(header))
        return observed,sidecar,expected

    def test_complete_original_lifetime_and_scope_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));before=p.collection.inventory(Path(temp))
            result=p.replay(observed,sidecar,expected)
            self.assertEqual(len(expected),result['lifetime']['capturedPrefixes']);self.assertEqual(2,result['lifetime']['life'])
            self.assertEqual('CLOSED',result['lifetime']['terminal']);self.assertTrue(result['retiredApplicationBytesQualified'])
            for flag in ('postCutTailObserved','fullTransientBytesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):self.assertFalse(result[flag])
            self.assertEqual(before,p.collection.inventory(Path(temp)))

    def test_all_mutations_reject_for_the_exact_reason(self):
        for name,reason in p.NEGATIVES.items():
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                observed,sidecar,expected=self.fixture(Path(temp));p.mutate(sidecar,name)
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.replay(observed,sidecar,expected)

    def test_original_application_prefix_and_resource_chain_cannot_be_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.prerequisite,'validate',side_effect=ValueError('original failed')),patch.object(p,'replay') as replay,patch.object(p,'mutate') as mutate:
                with self.assertRaisesRegex(ValueError,'original failed'):p.qualify(temp)
            replay.assert_not_called();mutate.assert_not_called()

    def test_qualification_keeps_inputs_and_rejects_every_declared_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));before=p.collection.inventory(Path(temp))
            with patch.object(p.prerequisite,'validate',return_value={'synthetic prerequisite':True}),patch.object(p,'plans',return_value=expected):
                result=p.qualify(temp)
            self.assertEqual([(k,v) for k,v in p.NEGATIVES.items()],[(v['case'],v['reason']) for v in result['negatives']])
            self.assertEqual(before,p.collection.inventory(Path(temp)));self.assertTrue(result['originalStorageUnchanged'])

    def test_unrelated_failure_or_accepted_mutation_gets_no_credit(self):
        for failure in (None,ValueError('unrelated')):
            with tempfile.TemporaryDirectory() as temp:
                observed,sidecar,expected=self.fixture(Path(temp))
                with patch.object(p,'validate',return_value={}),patch.object(p,'plans',return_value=expected),\
                     patch.object(p,'NEGATIVES',{'missing-copy':'expected'}),patch.object(p,'replay',side_effect=failure,return_value={}):
                    with self.assertRaisesRegex(ValueError,'accepted negative' if failure is None else 'unrelated negative'):p.qualify(temp)

    def test_original_drift_and_extra_wrappers_refuse(self):
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp));(Path(temp)/'extra').mkdir()
            with patch.object(p.prerequisite,'validate') as original:
                with self.assertRaisesRegex(ValueError,'wrapper inventory'):p.validate(temp)
            original.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            self.fixture(Path(temp))
            with patch.object(p.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(p.prerequisite,'validate'),patch.object(p,'replay'):
                with self.assertRaisesRegex(ValueError,'original changed'):p.validate(temp)

    def test_ordinary_retirement_schema_or_first_lifetime_cannot_substitute(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));path=sidecar/'collection.json';header=json.loads(path.read_bytes());header['schema']=p.r.SCHEMA
            path.write_bytes(p.f.canonical(header))
            with self.assertRaisesRegex(ValueError,'original lifetime binding'):p.replay(observed,sidecar,expected)
            expected[0]['life']=1
            with self.assertRaisesRegex(ValueError,'exact recovery lifetime'):p.replay(observed,sidecar,expected)

    def test_expected_bytes_are_independent_and_duplicates_cannot_count_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            observed,sidecar,expected=self.fixture(Path(temp));wrong=copy.deepcopy(expected)
            wrong[0]['files']['pending.accept']['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'exact original state'):p.replay(observed,sidecar,wrong)
            expected.append(expected[0])
            with self.assertRaisesRegex(ValueError,'exact original callback coverage'):p.replay(observed,sidecar,expected)

    def test_binding_preserves_original_object_identity_and_global_indices(self):
        before={'node-1':{'applied-end':None},'node-2':{}}
        events=[dict(node='node-1',event=p) for p in ('ROUND_SLOT_BEGIN','CERTIFICATE_ACTIVE_FORCED',
            'NATIVE_RETIREMENT_CERTIFICATE_RETAINED','STAGED_RETIREMENT_BEFORE_RETURN','ACCEPT_VALIDATED','ROUND_SLOT_COMPLETE')]
        plan=[('application-retirement',row['event'],{'original':row['event']}) for row in events[1:4]]
        cleaned={'node-1':{'original':'STAGED_RETIREMENT_BEFORE_RETURN'}}
        with patch.object(p.protocol,'retired',return_value=(events[4:5],cleaned)) as retired,\
             patch.object(p.model,'transaction',return_value=plan) as projected,patch.object(p.model,'physical',side_effect=lambda v:v):
            result=p.bind_plan(events,before)
        retired.assert_called_once_with(events[1:5],before);projected.assert_called_once_with(before['node-1'])
        self.assertEqual([1,2,3],[v['eventIndex'] for v in result]);self.assertTrue(all(v['life']==2 for v in result))

    def test_unbound_later_retirement_or_missing_slot_refuses(self):
        with self.assertRaisesRegex(ValueError,'original first slot'):p.bind_plan([],{})
        events=[dict(node='node-1',event=v) for v in ('ROUND_SLOT_BEGIN','STAGED_RETIREMENT_BEFORE_RETURN',
            'ROUND_SLOT_COMPLETE','NATIVE_RETIREMENT_CERTIFICATE_RETAINED')]
        with patch.object(p.protocol,'retired',return_value=([],{'node-1':{}})),\
             patch.object(p.model,'transaction',return_value=[('application-retirement',events[1]['event'],{})]),\
             patch.object(p.model,'physical',return_value={}):
            with self.assertRaisesRegex(ValueError,'complete history coverage'):p.bind_plan(events,{'node-1':{'applied-end':None}})

    def test_plan_reads_original_resource_events_and_installed_snapshot_only(self):
        with patch.object(p.prerequisite.resources,'read',return_value={}),patch.object(p.prerequisite.resources,'linked',return_value=[]) as linked,\
             patch.object(p.protocol.forces,'group',return_value={'original':True}) as group,patch.object(p,'bind_plan',return_value=[]) as binding:
            self.assertEqual([],p.plans('/original'))
        group.assert_called_once_with(Path('/original/history'),'life-2-installed-1');binding.assert_called_once_with([],{'original':True})
        self.assertEqual(Path('/original/resources/life-2'),linked.call_args.args[0])


if __name__=='__main__':unittest.main()
