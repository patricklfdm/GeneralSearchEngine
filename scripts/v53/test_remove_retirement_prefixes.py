import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remove_retirement_prefixes as p


class RemoveRetirementPrefixesTest(unittest.TestCase):
    def fixture(self,base):
        root=base/'raw';root.mkdir();node=root/'before-network/node-1';node.mkdir(parents=True)
        files={'root.gsr':b'original root','node.gsr':b'original owner','retirement':None,'retirement/images.json':b'prefix'}
        for key in ('root.gsr','node.gsr'):(node/key).write_bytes(files[key])
        events=[dict(node='node-1',event=v) for v in ('RETIREMENT_OLD_FILES_FORCED','RETIREMENT_CREATED')]
        (root/'events.json').write_bytes(p.f.canonical(events));(root/'transition-round-result.json').write_bytes(b'{}')
        sidecar=base/'captures';objects=sidecar/'objects';objects.mkdir(parents=True)
        identities={}
        for key,value in files.items():
            if value is None:identities[key]=dict(directory=True)
            else:
                digest=p.sha(value);(objects/digest).write_bytes(value);identities[key]=dict(size=len(value),sha256=digest)
        for i,event in enumerate(events):
            value=dict(schema=p.SCHEMA,node='node-1',kind='generation',point=event['event'],eventIndex=i,
                       files=[dict(name=k,identity=v) for k,v in sorted(identities.items())])
            (sidecar/f'capture-{i+1:04d}.json').write_bytes(p.f.canonical(value))
        header=dict(schema=p.SCHEMA,profile='4-REMOVE',eventsSha256=p.sha((root/'events.json').read_bytes()),
                    resultSha256=p.sha(b'{}'),captures=2,storedBytes=sum(v.stat().st_size for v in sidecar.rglob('*') if v.is_file()))
        (sidecar/'collection.json').write_bytes(p.f.canonical(header))
        return root,sidecar,files

    def test_original_indices_empty_directories_and_content_are_collected(self):
        with tempfile.TemporaryDirectory() as temp:
            root,sidecar,files=self.fixture(Path(temp));copies,_=p.collect(root,sidecar,'4-REMOVE')
            self.assertEqual({0,1},copies.keys());self.assertEqual(files,copies[0]['files']);self.assertEqual(files,copies[1]['files'])

    def test_other_profile_history_or_bool_bounds_cannot_alias_the_original(self):
        for field,value,reason in [('profile','5-REMOVE','collection header'),('captures',True,'collection header'),
                                   ('storedBytes',False,'collection header'),('eventsSha256','0'*64,'original history binding')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                root,sidecar,_=self.fixture(Path(temp));path=sidecar/'collection.json';header=json.loads(path.read_bytes());header[field]=value;path.write_bytes(p.f.canonical(header))
                with self.assertRaisesRegex(ValueError,'^REMOVE prefix '+reason+'$'):p.collect(root,sidecar,'4-REMOVE')

    def test_sidecar_mutations_refuse_for_their_exact_collection_reason(self):
        for name in ('missing-copy','history-binding','profile-binding','duplicate-index','wrong-callback',
                     'missing-object','altered-object','extra-object','boolean-size','wrong-owner'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temp:
                root,sidecar,_=self.fixture(Path(temp));p.mutate(sidecar,name)
                with self.assertRaisesRegex(ValueError,'^'+p.NEGATIVES[name]+'$'):p.collect(root,sidecar,'4-REMOVE')

    def test_linked_metadata_and_unobserved_directory_are_refused(self):
        for link in (True,False):
            with tempfile.TemporaryDirectory() as temp:
                root,sidecar,_=self.fixture(Path(temp))
                if link:
                    path=sidecar/'capture-0001.json';path.rename(sidecar/'saved');path.symlink_to('saved');reason='collection linked member'
                else:(sidecar/'extra').mkdir();reason='REMOVE prefix exact sidecar layout'
                with self.assertRaisesRegex(ValueError,'^'+reason+'$'):p.collect(root,sidecar,'4-REMOVE')

    def test_duplicate_missing_parent_and_boolean_directory_are_not_invented(self):
        for change,reason in [('duplicate','ordered unique member'),('parent','parent directory'),('boolean','directory type')]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp:
                root,sidecar,_=self.fixture(Path(temp));path=sidecar/'capture-0001.json';value=json.loads(path.read_bytes())
                if change=='duplicate':value['files'].insert(1,value['files'][0])
                elif change=='parent':value['files']=[v for v in value['files'] if v['name']!='retirement']
                else:next(v for v in value['files'] if v['name']=='retirement')['identity']['directory']=1
                path.write_bytes(p.f.canonical(value))
                with self.assertRaisesRegex(ValueError,'^REMOVE prefix '+reason+'$'):p.collect(root,sidecar,'4-REMOVE')

    def test_full_original_must_pass_before_prefixes_or_mutations(self):
        with patch.object(p.r,'validate',side_effect=ValueError('original failed')),patch.object(p,'collect') as collect,patch.object(p,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'^original failed$'):p.qualify('/unused','/unused','4-REMOVE')
        collect.assert_not_called();mutate.assert_not_called()

    def test_comparison_uses_independently_derived_state_and_exact_callback_once(self):
        value=p.Replay.__new__(p.Replay);value.captured_used=set();point='RETIREMENT_PROPOSAL_WRITTEN'
        original={'root.gsr':b'root','retirement':None,'retirement/proposal.gsr':b'actual'}
        value.copies={4:dict(node='node-1',kind='generation',point=point,files=original)}
        actual=[(4,dict(node='node-1',event=point))];expected=[(point,p.r.physical(original))]
        value.transaction('node-1','generation',actual,expected);self.assertEqual({4},value.captured_used)
        with self.assertRaisesRegex(ValueError,'^REMOVE prefix missing or reused callback$'):value.transaction('node-1','generation',actual,expected)
        value.captured_used.clear();wrong=dict(original,**{'retirement/proposal.gsr':b'forged'})
        with self.assertRaisesRegex(ValueError,'^REMOVE prefix exact original state: '+point+'$'):
            value.transaction('node-1','generation',actual,[(point,p.r.physical(wrong))])
        self.assertFalse(value.captured_used)

    def test_prefix_completion_preserves_the_parent_retention_write_set(self):
        value=p.Replay.__new__(p.Replay);value.used={99};value.captured_used=set()
        value.copies={4:dict(node='node-1',kind='generation',point='RETIREMENT_CREATED',files={})}
        value.transaction('node-1','generation',[(4,dict(event='RETIREMENT_CREATED'))],[('RETIREMENT_CREATED',{})])
        self.assertEqual({99},value.used)
        with patch.object(p.r.Replay,'run',return_value={}):self.assertEqual(1,value.run()['capturedPrefixes'])

    def test_missing_capture_wrong_transaction_kind_and_extra_observation_refuse(self):
        value=p.Replay.__new__(p.Replay);value.captured_used=set();value.copies={}
        with self.assertRaisesRegex(ValueError,'^REMOVE prefix missing or reused callback$'):
            value.transaction('node-1','generation',[(0,dict(event='RETIREMENT_CREATED'))],[('RETIREMENT_CREATED',{})])
        value.copies={0:dict(node='node-1',kind='source',point='RETIREMENT_CREATED',files={})}
        with self.assertRaisesRegex(ValueError,'^REMOVE prefix transaction binding$'):
            value.transaction('node-1','generation',[(0,dict(event='RETIREMENT_CREATED'))],[('RETIREMENT_CREATED',{})])
        with patch.object(p.r.Replay,'run',return_value={}):
            with self.assertRaisesRegex(ValueError,'^REMOVE prefix unbound observation$'):value.run()


if __name__=='__main__':unittest.main()
