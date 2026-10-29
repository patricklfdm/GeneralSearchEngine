"""Bounded byte/lineage regressions; actual authority uses native replay evidence."""
import copy
import struct
import unittest
from unittest.mock import patch
from . import learner_retention_evidence as e
from . import learner_cancellation_evidence as cancellation


class LearnerRetentionEvidenceTest(unittest.TestCase):
    def state(self,indices=(),revision=0):
        types=e.f.catalog()['types'];root='a'*64
        owner=e.f.sample('identity',types);request=e.f.sample('request',types)
        request.update(root=root,kind='ADD');learner=request['target'][-1]
        points=[]
        for index in indices:
            cut=e.f.sample('cut',types);cut['index']=index
            points.append(dict(cut=cut,catalog='b'*64,application='c'*64))
        return dict(root=root,owner=owner,revision=revision,previous='d'*64 if revision else None,
                    plan=dict(root=root,request=request if indices else None,learner=learner if indices else None,possible=points))

    def test_canonical_frame_checksum_and_extent(self):
        original=self.state();raw=e.frame(original);self.assertEqual(original,e.decode(raw))
        for damaged in (raw[:-1],raw+b'\0',b'bad'+raw,raw[:44]+bytes([raw[44]^1])+raw[45:]):
            with self.subTest(size=len(damaged)),self.assertRaises(ValueError):e.decode(damaged)
        body=e.f.canonical(original)+b' '
        altered=struct.pack('>IHHI',0x47534c52,1,3,44+len(body))+bytes.fromhex(e.sha(body))+body
        with self.assertRaisesRegex(ValueError,'canonical bytes'):e.decode(altered)

    def test_exact_fields_empty_binding_and_reserved_revision(self):
        for changed in ('field','binding','revision','predecessor','root'):
            value=self.state()
            if changed=='field':value['foreign']=0
            elif changed=='binding':value['plan']['request']=self.state((1,))['plan']['request']
            elif changed=='revision':value['revision']=2**63-1
            elif changed=='predecessor':value['previous']='e'*64
            else:value['plan']['root']='e'*64
            with self.subTest(changed=changed),self.assertRaises(ValueError):e.frame(value)

    def test_merged_originals_never_drop_uncertain_endpoint(self):
        initial=e.frame(self.state());first=e.frame(self.state((3,),1));second=e.frame(self.state((5,),2))
        merged=e.decode(e.merged(first,[initial,second]));self.assertEqual([3,5],[v['cut']['index'] for v in merged['plan']['possible']])
        self.assertEqual(2,merged['revision']);self.assertEqual(e.sha(first),merged['previous'])
        self.assertEqual(initial,e.merged(initial,[initial]));self.assertEqual(first,e.merged(first,[first,initial]))
        with self.assertRaisesRegex(ValueError,'endpoint capacity'):e.merged(e.frame(self.state((2,3),1)),[second])

    def test_foreign_binding_or_conflicting_same_index_refuses(self):
        before=e.frame(self.state((3,),1))
        for field in ('root','request','learner','endpoint'):
            value=self.state((3,),2);p=value['plan']
            if field=='root':value['root']=p['root']=p['request']['root']='f'*64
            elif field=='request':p['request']['number']+=1
            elif field=='learner':
                p['learner']['storage']='00000000-0000-0000-0000-000000000053'
                # sample's learner shares this target member intentionally.
            else:p['possible'][0]['catalog']='f'*64
            with self.subTest(field=field),self.assertRaises(ValueError):e.merged(before,[e.frame(value)])
        for values in ([],[before]*7):
            with self.assertRaisesRegex(ValueError,'merge count'):e.merged(before,values)

    def test_snapshot_binds_entire_original_promise_and_ledger(self):
        value=self.state();raw=e.frame(value);promise=e.f.sample(e.f.catalog()['records']['PROMISE']['schema'],e.f.catalog()['types'])
        promise.update(root=value['root'],basisId='00000000-0000-0000-0000-000000000053')
        original=e.f.encode('records','PROMISE',promise);wrapped=e.wrap(original,raw)
        body=struct.pack('>I',len(original))+original+struct.pack('>I',len(raw))+raw
        prefix=struct.pack('>IHHII',0x47534c46,1,3,0,len(body))
        self.assertEqual(prefix+bytes.fromhex(e.sha(prefix+body))+body,wrapped)
        changed=copy.deepcopy(promise);changed['ballot']['counter']+=1
        self.assertNotEqual(wrapped,e.wrap(e.f.encode('records','PROMISE',changed),raw))
        promise['root']='f'*64
        with self.assertRaisesRegex(ValueError,'frozen promise'):e.wrap(e.f.encode('records','PROMISE',promise),raw)

    def test_retained_mode_checks_original_before_any_negative(self):
        with patch.object(cancellation,'validate',side_effect=ValueError('original ledger failed')) as original,patch.object(cancellation.shutil,'copytree') as copied:
            with self.assertRaisesRegex(ValueError,'original ledger failed'):cancellation.qualify('/absent',retained_learners=True)
            original.assert_called_once_with(cancellation.Path('/absent'),retained_learners=True);copied.assert_not_called()

    def test_new_learner_attempts_do_not_relax_old_future_attempt_budget(self):
        def rows(kind,count):
            return [dict(node='node-3',kind=kind,request='a'*64,
                failure='java.lang.IllegalArgumentException: higher ballot observed; fresh campaign required')]*count
        with patch.object(cancellation.d,'read',return_value=rows('FUTURE_RETENTION_INTENT',15)+rows('LEARNER_RETENTION_INTENT',6)):
            self.assertEqual(21,cancellation.native_failures(cancellation.Path('/absent'),retained_learners=True))
        with patch.object(cancellation.d,'read',return_value=rows('FUTURE_RETENTION_INTENT',16)+rows('LEARNER_RETENTION_INTENT',4)):
            with self.assertRaisesRegex(ValueError,'unexpected native failure'):
                cancellation.native_failures(cancellation.Path('/absent'),retained_learners=True)

    def test_well_framed_foreign_owner_is_not_authority(self):
        value=self.state();value['owner']['storage']='00000000-0000-0000-0000-000000000053'
        self.assertEqual(value,e.decode(e.frame(value)))
        # The native negative matrix changes this owner with a correct checksum;
        # original bootstrap derivation, not the parser, must reject that file.
        self.assertIn('retention-genesis-owner',e.NEGATIVES)


if __name__=='__main__':unittest.main()
