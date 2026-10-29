"""Conditional copied records exercise the independent binding checker only."""
import unittest
from . import learner_vacancy_evidence as v
s=v.s


class LearnerVacancyEvidenceTest(unittest.TestCase):
    def fixture(self,candidate=False):
        roots={k:{} for k in s.ROOTS}
        for root,names in [('seed',v.SEED),('slot-typed',v.TYPED)]:
            roots[root]={name:None if name in ('.','backup') else (root+'/'+name).encode() for name in names}
        roots['slots']={'.':None,'source-b':None,'b.json':b'original-plan',
                        'source-b/source.gscp':b'original-packet','source-b/generation.gsr':b'original-generation'}
        ids={k:dict(path='/original/'+k,present=bool(files),members={}) for k,files in roots.items()}
        def put(root,name,raw):
            roots[root][name]=raw;key=root+'::'+name
            ids[root]['members'][name]=dict(key=key,directory=True) if raw is None else dict(key=key,bytes=len(raw),sha256=s.digest(raw))
        for root,files in roots.items():
            for name,raw in list(files.items()):put(root,name,raw)
        snapshot=s.Snapshot(ids,roots,{})
        head=dict(schema='gse-v53-learner-slot-head/1.3',headKey='slots::head.json',
                  plan=s.digest(roots['slots']['b.json']),source=s.digest(roots['slots']['source-b/source.gscp']),
                  generation=s.digest(roots['slots']['source-b/generation.gsr']),receipt=s.digest(roots['slot-typed']['learner.gsr']),
                  seedFiles=snapshot.fingerprints('seed',v.SEED),currentFiles=snapshot.fingerprints('slot-typed',v.TYPED),
                  previousFiles=[dict(path='.',sha256='a'*64)],previousTyped=[dict(path='.',sha256='b'*64)])
        put('slots','head.json',s.f.canonical(head));name='cleared.next.json' if candidate else 'cleared.json'
        clear=dict(schema='gse-v53-learner-slot-cleared/1.3',plan=head['plan'],head=s.digest(roots['slots']['head.json']),
                   headKey=head['headKey'],clearKey='slots::'+name)
        clear.update({k:s.digest(s.f.canonical(head[k])) for k in ('previousFiles','previousTyped','seedFiles')})
        put('slots',name,s.f.canonical(clear));return snapshot

    def test_original_active_and_candidate_bindings_remain_distinct(self):
        for candidate in (False,True):
            with self.subTest(candidate=candidate):
                result=v.binding(self.fixture(candidate));self.assertEqual(candidate,result['candidateOnly'])

    def test_modified_previous_fingerprint_hash_is_rejected(self):
        snapshot=self.fixture();clear=s.e.parse(snapshot.files['slots']['cleared.json']);clear['previousFiles']='0'*64
        snapshot.files['slots']['cleared.json']=s.f.canonical(clear)
        with self.assertRaisesRegex(ValueError,'^learner vacancy exact selected binding$'):v.binding(snapshot)

    def test_copied_marker_or_selecting_inode_is_rejected(self):
        for name in ('head.json','cleared.json'):
            with self.subTest(name=name):
                snapshot=self.fixture();snapshot.identities['slots']['members'][name]['key']='replacement'
                with self.assertRaisesRegex(ValueError,'^learner vacancy original selecting inode$'):v.binding(snapshot)

    def test_both_marker_names_are_rejected(self):
        snapshot=self.fixture();snapshot.files['slots']['cleared.next.json']=snapshot.files['slots']['cleared.json']
        with self.assertRaisesRegex(ValueError,'^learner vacancy original marker location$'):v.binding(snapshot)

    def test_recreated_old_source_or_typed_is_rejected(self):
        for source in (False,True):
            with self.subTest(source=source):
                snapshot=self.fixture()
                if source:snapshot.files['seed']['source']=None
                else:snapshot.identities['seed-typed']['present']=True
                with self.assertRaisesRegex(ValueError,'^learner vacancy original roots not cleared$'):v.binding(snapshot)

    def test_seed_metadata_or_current_typed_identity_changes_are_rejected(self):
        for root,reason in [('seed','immutable seed metadata'),('slot-typed','current typed fingerprints')]:
            with self.subTest(root=root):
                snapshot=self.fixture();snapshot.identities[root]['members']['.']['key']='different'
                with self.assertRaisesRegex(ValueError,'^learner vacancy '+reason+'$'):v.binding(snapshot)

    def test_changed_current_generation_cannot_hide_behind_vacancy_hashes(self):
        snapshot=self.fixture();snapshot.files['slots']['source-b/generation.gsr']=b'changed'
        with self.assertRaisesRegex(ValueError,'^learner vacancy current original binding$'):v.binding(snapshot)

    def test_directory_in_place_of_record_or_current_member_is_rejected(self):
        for name,reason in [('head.json','original head required'),('cleared.json','bounded marker'),
                            ('source-b/generation.gsr','current original binding')]:
            with self.subTest(name=name):
                snapshot=self.fixture();snapshot.files['slots'][name]=None
                with self.assertRaisesRegex(ValueError,'^learner vacancy '+reason+'$'):v.binding(snapshot)

    def test_noncanonical_fingerprint_inventory_is_rejected(self):
        snapshot=self.fixture();head=s.e.parse(snapshot.files['slots']['head.json']);head['previousFiles']*=2
        snapshot.files['slots']['head.json']=s.f.canonical(head)
        with self.assertRaisesRegex(ValueError,'^learner vacancy fingerprint shape$'):v.binding(snapshot)


if __name__=='__main__':unittest.main()
