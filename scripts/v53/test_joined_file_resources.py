"""Synthetic equal-image handoffs exercise binding, not native acceptance."""
import copy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import joined_file_resources as r,joined_file_negatives as n
from .test_storage_transfer_evidence import fixture as storage


def fixture():
    trace,captured=storage();events=[];boundaries=[]
    for i,(scope,event) in enumerate(r.handoff.POINTS):
        events.append(dict(node='node-6',scope=scope,event=event))
        seq=2 if i==0 else 3
        boundaries.append(dict(eventIndex=i,node='node-6',sequence=seq,usage=trace['changes'][seq]['usage']))
    plan=dict(node='node-6',pairs=copy.deepcopy(captured['rows'][0]['moves']),files=[
        dict(family=family,path='same.image',key=family,bytes=837,sha256='a'*64,createdAfterCustody=False)
        for family in ('initial','intent')])
    return plan,events,{'node-6':trace},boundaries,{'node-6':captured}


class JoinedFileResourcesTest(unittest.TestCase):
    def test_identical_content_retains_distinct_original_ownership(self):
        data=fixture();before=copy.deepcopy(data);result=r.replay(*data)
        self.assertEqual(2,result['distinctImageFiles']);self.assertEqual(1,result['distinctImageDigests'])
        self.assertEqual(1674,result['originalFileBytes']);self.assertEqual(data,before)
        for flag in ('intermediateFileLifetimesQualified','physicalPeakQualified','wholeRuntimeResourcesQualified',
                     'finalSourceCohortQualified','phase3Complete'):self.assertFalse(result[flag])

    def test_all_negatives_reject_for_exact_reason_including_same_size_swap(self):
        result=n.replay(fixture());self.assertEqual(list(n.NEGATIVES),[v['case'] for v in result])
        self.assertTrue(all(v['status']=='REJECTED' for v in result))

    def test_invalid_original_is_never_counted_as_negative_qualification(self):
        data=fixture();data[2]['node-6']['failed']=True
        with patch.object(n,'mutate') as mutate,self.assertRaisesRegex(ValueError,'incomplete observation'):n.replay(data)
        mutate.assert_not_called()

    def test_complete_native_validation_precedes_mapping_and_mutations(self):
        with patch.object(n.native.collection,'inventory',return_value={}),\
             patch.object(n.native,'validate',side_effect=ValueError('invalid original')) as original,\
             patch.object(r,'derive') as derive,patch.object(n,'replay') as replay,\
             self.assertRaisesRegex(ValueError,'invalid original'):n.qualify('/unused')
        original.assert_called_once_with(n.Path('/unused'),'5-REPLACE-required-four',None,joined_files=True)
        derive.assert_not_called();replay.assert_not_called()

    def test_original_inventory_must_remain_unchanged_through_negative_replay(self):
        data=fixture()
        with patch.object(n.native.collection,'inventory',side_effect=[{'before':1},{'after':1}]),\
             patch.object(n.native,'validate',return_value={'status':'PASS','joinedFileResources':{'status':'PASS','originalFileCustodyQualified':True}}),\
             patch.object(n.native,'load',return_value=({},data[2],data[3],data[1])),\
             patch.object(r.handoff,'original',return_value=SimpleNamespace(owner=object())),\
             patch.object(n.maintenance,'Replay'),patch.object(r,'derive',return_value=data[0]),\
             patch.object(r.transfers,'load',return_value=data[4]),\
             self.assertRaisesRegex(ValueError,'qualification changed original'):n.qualify('/unused')

    def test_partial_or_missing_original_scope_cannot_earn_negatives(self):
        for result in ({'status':'PARTIAL'}, {'status':'PASS'},
                       {'status':'PASS','joinedFileResources':{'status':'PASS','originalFileCustodyQualified':False}}):
            with patch.object(n.native.collection,'inventory',return_value={}),\
                 patch.object(n.native,'validate',return_value=result),patch.object(n.native,'load') as load,\
                 self.assertRaisesRegex(ValueError,'complete original qualification'):n.qualify('/unused')
            load.assert_not_called()

    def test_opt_in_does_not_accept_a_different_topology_or_non_boolean(self):
        for profile,flag in (('stable',True),('5-REPLACE-required-four',1)):
            with self.assertRaisesRegex(ValueError,'joined files policy'):n.native.validate('/unused',profile,joined_files=flag)

    def test_old_original_without_mapping_is_rejected_before_expensive_replay(self):
        with tempfile.TemporaryDirectory() as root,patch.object(n.native.publication,'validate') as original,\
             self.assertRaisesRegex(ValueError,'missing original capture'):
            n.native.validate(root,'5-REPLACE-required-four',joined_files=True)
        original.assert_not_called()

    def test_network_session_identity_is_derived_from_original_bytes(self):
        joining={'node':'node-6'};peer={'node':'node-1'};image=b'same';name=r.p.sha(image)+'.image'
        events=[dict(node='node-6',scope=scope,event=event) for scope,event in r.handoff.POINTS]
        # Put the custody point after all original exchanges.
        events=[dict(node='node-1',event='unrelated') for _ in range(20)]+events
        sources={cut:{'source.gscp':str(cut).encode(),name:image} for cut in (4,8,9)}
        owner=SimpleNamespace(joining=joining,peer=peer,history=SimpleNamespace(sources=sources),replay=SimpleNamespace(joining='node-6'))
        groups=[]
        for cut in sources:
            group=[]
            for kind,raw,identifier in (('CAPSULE',sources[cut]['source.gscp'],str(cut)),('APPLICATION',image,'image-'+str(cut))):
                group.append(dict(kind=kind,raw=raw,offer=dict(sent=1,request=dict(sender=joining,recipient=peer,payload={'id':identifier})),
                                  commit={'delivered':2}))
            groups.append(group)
        reader=SimpleNamespace(events=events,groups=groups)
        self.assertEqual('image-8',r.sessions(owner,reader)[8]['images'][name])
        later=copy.deepcopy(reader);again=copy.deepcopy(groups[-1])
        for content in again:content['offer']['sent']=30;content['commit']['delivered']=31
        later.groups.append(again)
        self.assertEqual(r.sessions(owner,reader),r.sessions(owner,later))
        for kind in ('wrong-peer','duplicate','missing-image','reused-id','late','altered-image'):
            changed=copy.deepcopy(reader)
            if kind=='wrong-peer':changed.groups[0][0]['offer']['request']['recipient']={'node':'node-2'}
            elif kind=='duplicate':changed.groups.append(copy.deepcopy(changed.groups[0]))
            elif kind=='missing-image':changed.groups[0].pop()
            elif kind=='reused-id':changed.groups[1][1]['offer']['request']['payload']['id']='image-4'
            elif kind=='late':changed.groups[0][1]['commit']['delivered']=21
            else:changed.groups[0][1]['raw']=b'wrong'
            with self.subTest(kind=kind),self.assertRaises(ValueError):r.sessions(owner,changed)

    def test_physical_mapping_counts_distinct_equal_files_and_fails_unassigned_or_overdrawn(self):
        image=b'image';name=r.p.sha(image)+'.image'
        sources={cut:{'source.gscp':str(cut).encode(),name:image} for cut in (4,8,9)}
        sessions={cut:dict(capsule='capsule-'+str(cut),images={name:'image-'+str(cut)}) for cut in sources}
        installed={'generations/a/source.gscp':b'9','generations/a/'+name:image}
        expected=dict(operation={'learner.gslp':b'plan'},initialTyped={'backup/file':b'backup'},
                      replica={**{'learner/'+k:v for k,v in sources[4].items()},**installed},
                      intent={**{'source/'+k:v for k,v in sources[9].items()},'intent.json':b'intent'},
                      pendingIntent={**{'source/'+k:v for k,v in sources[8].items()},'pending-intent.json':b'pending'},
                      placement={'placed.json':b'placed'},custody={'custody.json':b'custody'})
        owner=SimpleNamespace(history=SimpleNamespace(sources=sources),installed=installed,expected=expected,plan='a'*64,
                              replay=SimpleNamespace(joining='node-6'),key=lambda family,path:family+'/'+path)
        with patch.object(r,'sessions',return_value=sessions):
            plan=r.derive(owner,None);self.assertEqual(11,len(plan['pairs']))
            self.assertEqual(['placement'],[v['family'] for v in plan['files'] if v['createdAfterCustody']])
            images=[v for v in plan['files'] if v['path'].endswith('.image')]
            self.assertEqual(4,len(images));self.assertEqual(1,len({v['sha256'] for v in images}))
            self.assertEqual(4,len({v['custody']['owner'] for v in images}))
            for kind in ('unassigned','inode','bytes','source','omitted-typed'):
                changed=copy.deepcopy(owner)
                if kind=='unassigned':changed.expected['foreign']={'arbitrary':b'x'}
                elif kind=='inode':changed.key=lambda family,path:'same-inode'
                elif kind=='bytes':changed.expected['operation']['learner.gslp']=b'x'*(2*r.t.MIB+1)
                elif kind=='source':changed.expected['replica']['learner/source.gscp']=b'wrong'
                else:changed.expected.pop('initialTyped')
                with self.subTest(kind=kind),self.assertRaises(ValueError):r.derive(changed,None)


if __name__=='__main__':unittest.main()
