import copy
import unittest
from . import replica_storage_coverage as m

A='a'*64;B='b'*64;UUID='11111111-2222-3333-4444-555555555555'
D={'directory':True}
def file(size=4,sha=A):return dict(bytes=size,sha256=sha)
def charge(unit,owner,size):return dict(unit=unit,owner=owner,bytes=size,claimSource='')


class StorageCoverageTest(unittest.TestCase):
    def fixture(self):
        files={'grants.gsr':file(3),'grants.rotation.gsr':file(5),'root.gsr':file(2),
               'generations':D,'generations/a':D,'generations/a/generation.gsr':file(7),
               'generations/a/'+A+'.image':file(11),'sources':D,'sources/'+UUID:D,
               'sources/'+UUID+'/source.gscp':file(13),'sources/'+UUID+'/'+A+'.image':file(11),
               'floor-copies':D,'floor-copies/'+B:D,'floor-copies/'+B+'/generation.gsr':file(17),
               'floor-copies/'+B+'/'+A+'.image':file(11)}
        charges=[charge('JOURNAL','membership-grants',8),charge('MISC','current-authority',2),
                 charge('GENERATION','a',7),charge('APPLICATION','generation-a:'+A+'.image',11),
                 charge('SOURCE',UUID,13),charge('APPLICATION',UUID+':'+A,11),
                 charge('SOURCE','floor:'+B,17),charge('APPLICATION','floor:'+B+':0',11),
                 charge('APPLICATION','publication-completion',64*m.t.MIB)]
        return files,{m.t.key(v):v for v in charges},{'floor-copies/'+B:[A+'.image']}

    def test_counts_identical_copies_and_rotation_members_once_each(self):
        result=m.compare(*self.fixture());self.assertEqual(80,result['physicalBytes'])
        self.assertEqual(9,result['physicalFiles'])
        images=[v for v in result['required'] if v['unit']=='APPLICATION']
        self.assertEqual(3,len(images));self.assertEqual(33,sum(v['bytes'] for v in images))
        self.assertEqual(8,next(v['bytes'] for v in result['required'] if v['unit']=='JOURNAL'))
        self.assertEqual('publication-completion',result['unboundCharges'][0]['owner'])

    def test_larger_reservation_is_not_physical_consumption(self):
        files,charges,ordinals=self.fixture();charges[m.JOURNAL]['bytes']=32*m.t.MIB
        self.assertEqual(80,m.compare(files,charges,ordinals)['physicalBytes'])

    def test_native_joining_and_learner_retention_share_the_original_journal(self):
        names=('learner-retention.gslr','learner-retention.next.gslr','joining-retention.gsjr',
               'joining-retention.next.gsjr','joining-retention.done.gsjr','joining-retention.done.next.gsjr')
        for name in names:
            files={'grants.gsr':file(5),name:file(13)}
            with self.subTest(name=name):
                result=m.compare(files,{m.JOURNAL:charge(*m.JOURNAL,18)}, {})
                self.assertEqual(18,result['physicalBytes']);self.assertEqual(1,len(result['required']))
                with self.assertRaisesRegex(ValueError,'simultaneous owner extent'):
                    m.compare(files,{m.JOURNAL:charge(*m.JOURNAL,5)}, {})
                with self.assertRaisesRegex(ValueError,'original charge owner'):
                    m.compare(files,{m.MISC:charge(*m.MISC,100)}, {})

    def test_adopted_certificate_stays_with_its_generation_or_floor_copy(self):
        for prefix,key in (('generations/a',('GENERATION','a')),('floor-copies/'+B,('SOURCE','floor:'+B))):
            files={prefix.split('/')[0]:D,prefix:D,prefix+'/generation.gsr':file(7),prefix+'/adopted-certificate.gsr':file(11)}
            with self.subTest(prefix=prefix):
                result=m.compare(files,{key:charge(*key,18)}, {})
                self.assertEqual(18,result['physicalBytes']);self.assertEqual(1,len(result['required']))
                with self.assertRaisesRegex(ValueError,'simultaneous owner extent'):m.compare(files,{key:charge(*key,7)}, {})

    def test_native_ledger_and_adoption_names_do_not_allow_similar_unknown_files(self):
        for name in ('joining-retention.other.gsjr','joining-retention.done.next.next.gsjr','learner-retention.tmp.gslr'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'unclassified root'):m.owners({name:file()}, {})
        for name in ('adopted-certificate.gsr.other','adopted-certificate.next.gsr'):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'generation member'):
                m.owners({'generations':D,'generations/a':D,'generations/a/'+name:file()}, {})

    def test_combined_active_and_candidate_exceeding_one_charge_rejects(self):
        files,charges,ordinals=self.fixture();charges[m.JOURNAL]['bytes']=5
        with self.assertRaisesRegex(ValueError,'^storage coverage simultaneous owner extent$'):m.compare(files,charges,ordinals)

    def test_total_capacity_cannot_substitute_for_exact_owner(self):
        files,charges,ordinals=self.fixture();old=charges.pop(('APPLICATION',UUID+':'+A))
        old['owner']='unrelated';charges[m.t.key(old)]=old
        with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):m.compare(files,charges,ordinals)

    def test_pending_claim_is_not_stored_original(self):
        files,charges,ordinals=self.fixture();charges[('SOURCE',UUID)].update(bytes=0,claimSource='receiving')
        with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):m.compare(files,charges,ordinals)

    def test_empty_file_and_owned_directory_still_need_live_charge(self):
        for files in ({'grants.gsr':file(0)},{'generations':D,'generations/a':D}):
            with self.subTest(files=files),self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):
                m.compare(files,{}, {})

    def test_source_images_and_generation_images_have_distinct_name_rules(self):
        files,charges,ordinals=self.fixture();old=charges.pop(('APPLICATION',UUID+':'+A))
        old['owner']+='.image';charges[m.t.key(old)]=old
        with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):m.compare(files,charges,ordinals)

    def test_unknown_or_unmodeled_data_output_is_not_silently_ignored(self):
        for extra in ({'unknown.gsr':file()},{'application-replay':D,'application-replay/work':D,'application-replay/work/output':D}):
            files,charges,ordinals=self.fixture();files.update(extra)
            with self.subTest(extra=extra),self.assertRaises(ValueError):m.compare(files,charges,ordinals)

    def test_parent_traversal_absolute_path_missing_parent_and_fake_directories_reject(self):
        for files in ({'../grants.gsr':file()},{'/grants.gsr':file()},
                      {'generations/a/generation.gsr':file()}, {'grants.gsr':D},
                      {'generations':D,'generations/a':D,'generations/a/generation.gsr':D},
                      {'generations':D,'generations/a':file()}):
            with self.subTest(files=files),self.assertRaises(ValueError):m.owners(files,{})

    def test_typed_bounded_file_extents_and_hashes(self):
        for value in ({'bytes':True,'sha256':A},{'bytes':-1,'sha256':A},{'bytes':65*m.t.MIB,'sha256':A},
                      {'bytes':1,'sha256':'z'*64},{'directory':1},{'bytes':1,'sha256':A,'extra':True}):
            with self.subTest(value=value),self.assertRaises(ValueError):m.owners({'grants.gsr':value},{})

    def test_nested_control_metadata_must_be_files(self):
        for key in ('applied-end/plan.json','application-replay/claim.json','retirement/proposal.gsr','floor-copies/local.gsr'):
            files={key.split('/')[0]:D,key:D}
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'^storage coverage exact file or directory$'):m.owners(files,{})

    def test_noncanonical_ordinal_list_rejects(self):
        files,charges,ordinals=self.fixture()
        for values in ([B+'.image',A+'.image'],[A+'.image',A+'.image'],[]):
            with self.subTest(values=values),self.assertRaises(ValueError):m.compare(files,charges,{'floor-copies/'+B:values})

    def test_charge_type_and_key_are_checked(self):
        for change in ('bool','key'):
            files,charges,ordinals=self.fixture()
            if change=='bool':charges[m.JOURNAL]['bytes']=True
            else:charges[m.JOURNAL]['owner']='another'
            with self.subTest(change=change),self.assertRaises(ValueError):m.compare(files,charges,ordinals)

    def test_applied_retirement_candidates_and_authority_use_shared_journal(self):
        for marker in ('retirement.gsat','retirement.gsat.next'):
            for size in (0,13):
                files={'grants.gsr':file(5),'applied-end':D,'applied-end/'+marker:file(size),
                       'applied-end/application.image':file(17)}
                charges=[charge('JOURNAL','membership-grants',5+size),charge('APPLICATION','applied-end',17)]
                with self.subTest(marker=marker,size=size):
                    result=m.compare(files,{m.t.key(v):v for v in charges},{})
                    journal=next(v for v in result['required'] if v['unit']=='JOURNAL')
                    self.assertEqual(5+size,journal['bytes']);self.assertIn('applied-end/'+marker,journal['paths'])
                    self.assertEqual(22+size,result['physicalBytes'])

    def test_retirement_marker_cannot_borrow_the_application_reservation(self):
        for marker in ('retirement.gsat','retirement.gsat.next'):
            files={'grants.gsr':file(5),'applied-end':D,'applied-end/'+marker:file(13)}
            for journal in (None,5):
                charges=[charge('APPLICATION','applied-end',m.t.MIB)]
                if journal is not None:charges.append(charge('JOURNAL','membership-grants',journal))
                with self.subTest(marker=marker,journal=journal),self.assertRaisesRegex(ValueError,
                        'original charge owner' if journal is None else 'simultaneous owner extent'):
                    m.compare(files,{m.t.key(v):v for v in charges},{})

    def test_empty_retirement_marker_still_requires_original_journal_owner(self):
        for marker in ('retirement.gsat','retirement.gsat.next'):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'original charge owner'):
                m.compare({'applied-end':D,'applied-end/'+marker:file(0)}, {}, {})

    def test_exact_retirement_marker_names_do_not_admit_arbitrary_members(self):
        for marker in ('retirement.gsat.other','retirement.gsat.next.next','retirement.tmp'):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'applied member'):
                m.owners({'applied-end':D,'applied-end/'+marker:file()}, {})
        with self.assertRaisesRegex(ValueError,'exact file or directory'):
            m.owners({'applied-end':D,'applied-end/retirement.gsat':D}, {})


def row(at,point,files,node='node-1',life=2):return dict(life=life,node=node,eventIndex=at,point=point,files=files)


class StorageOrdinalTest(unittest.TestCase):
    def test_floor_deletion_preserves_original_second_ordinal(self):
        prefix='floor-copies/'+B;files={'floor-copies':D,prefix:D,prefix+'/'+A+'.image':file(),prefix+'/'+B+'.image':file()}
        later={k:v for k,v in files.items() if k!=prefix+'/'+A+'.image'}
        rows=[row(0,'FLOOR_COPY_FORCED',files),row(1,'FLOOR_FILE_DELETED',later)];plans=m.ordinal_plans(rows)
        self.assertEqual([A+'.image',B+'.image'],plans[2,'node-1',1][prefix])
        self.assertEqual(('APPLICATION','floor:'+B+':1'),m.owners(later,plans[2,'node-1',1])[prefix+'/'+B+'.image'])

    def test_retirement_path_reuse_resets_order_but_deletion_does_not(self):
        def files(images):return {'retirement':D,'retirement/source':D,**{'retirement/source/'+v+'.image':file() for v in images}}
        rows=[row(0,'RETIREMENT_OLD_FILES_FORCED',{'root.gsr':file()}),row(1,'RETIREMENT_SOURCE_FORCED',files([A,B])),
              row(2,'RETIREMENT_FILE_DELETED',files([B])),row(3,'RETIREMENT_BEFORE_RETURN',{'root.gsr':file()}),
              row(4,'RETIREMENT_OLD_FILES_FORCED',{'root.gsr':file()}),row(5,'RETIREMENT_SOURCE_FORCED',files([B])),
              row(6,'RETIREMENT_BEFORE_RETURN',{'root.gsr':file()})]
        plans=m.ordinal_plans(rows)
        self.assertEqual(('APPLICATION','retirement:1'),m.owners(files([B]),plans[2,'node-1',2])['retirement/source/'+B+'.image'])
        self.assertEqual(('APPLICATION','retirement:0'),m.owners(files([B]),plans[2,'node-1',5])['retirement/source/'+B+'.image'])

    def test_missing_overlapping_or_incomplete_operation_rejects(self):
        for points in (['RETIREMENT_BEFORE_RETURN'],['RETIREMENT_OLD_FILES_FORCED'],
                       ['RETIREMENT_OLD_FILES_FORCED','RETIREMENT_OLD_FILES_FORCED']):
            with self.subTest(points=points),self.assertRaises(ValueError):
                m.ordinal_plans([row(i,p,{'root.gsr':file()}) for i,p in enumerate(points)])

    def test_owner_and_lifetime_are_not_interchangeable(self):
        rows=[row(0,'X',{'root.gsr':file()},life=1),row(0,'X',{'root.gsr':file()},life=2)]
        self.assertEqual({(1,'node-1',0),(2,'node-1',0)},set(m.ordinal_plans(rows)))
        for change in ('life','node','eventIndex'):
            changed=copy.deepcopy(rows);changed[0][change]=True
            with self.subTest(change=change),self.assertRaises(ValueError):m.ordinal_plans(changed)

    def test_duplicate_or_out_of_order_callback_rejects(self):
        values=[row(0,'X',{'root.gsr':file()}),row(1,'X',{'root.gsr':file()})]
        for rows in ([values[0],values[0]],list(reversed(values))):
            with self.assertRaisesRegex(ValueError,'^storage coverage ordered unique callbacks$'):m.ordinal_plans(rows)


if __name__=='__main__':unittest.main()
