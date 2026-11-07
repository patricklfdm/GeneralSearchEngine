"""Synthetic arithmetic/custody regressions, not maximum runtime evidence."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_retirement_storage as m
from . import test_resource_transitions as accounting

SHA='b'*64
DEFAULT=m.native.resource_policy.DEFAULT


def fixture(size=837,sha=SHA,interval=()):
    files={'root.gsr':dict(bytes=12,sha256='a'*64),'grants.gsr':dict(bytes=64,sha256='a'*64),
           'generations':dict(directory=True),'generations/a':dict(directory=True),
           'generations/a/generation.gsr':dict(bytes=32,sha256='a'*64),
           'generations/a/'+sha+'.image':dict(bytes=size,sha256=sha),'sources':dict(directory=True)}
    charges=[accounting.charge('MISC','current-authority',2*m.t.MIB),accounting.charge('JOURNAL','membership-grants',32*m.t.MIB),
             accounting.charge('GENERATION','a',32),accounting.charge('APPLICATION','generation-a:'+sha+'.image',size)]
    for i in range(6):
        owner=f'00000000-0000-0000-0000-{i+1:012d}';prefix='sources/'+owner
        files[prefix]=dict(directory=True);files[prefix+'/source.gscp']=dict(bytes=32,sha256='a'*64)
        files[prefix+'/'+sha+'.image']=dict(bytes=size,sha256=sha)
        charges.extend((accounting.charge('SOURCE',owner,32),accounting.charge('APPLICATION',owner+':'+sha,size)))
    limits=(384*m.t.MIB,m.native.resource_policy.LIMITS[DEFAULT],64*m.t.MIB);state={};changes=[]
    def change(event,removed=(),added=()):
        for v in removed:del state[m.t.key(v)]
        for v in added:state[m.t.key(v)]=v
        changes.append(dict(sequence=len(changes),event=event,removed=list(removed),added=list(added),usage=m.t.usage(state,limits)))
    change('START')
    for v in charges:change('RESERVE',added=[v])
    before=len(changes)-1
    for event,removed,added in interval:change(event,removed,added)
    after=len(changes)-1
    for v in list(state.values()):change('RELEASE',removed=[v])
    trace=dict(schema='gse-v53-resource-transitions-v1',metadataLimit=limits[0],stagingLimit=limits[1],queueLimit=limits[2],
               truncated=False,failed=False,transitions=len(changes),changes=changes,current=changes[-1]['usage'])
    observed=[dict(node='node-1',scope='network-owner',event=0,capturedEvent=1,point='SOURCE_RETIREMENT_CREATED',files=files)]
    events=[dict(node='node-1',event='SOURCE_RETIREMENT_CREATED'),
            dict(node='node-1',scope='network-owner',event=m.retirement.EVENT,point='SOURCE_RETIREMENT_CREATED',sha256='c'*64)]
    boundaries=[dict(eventIndex=i,node='node-1',sequence=seq,usage=changes[seq]['usage']) for i,seq in enumerate((before,after))]
    index=dict(root='a'*64,eventsSha256=m.digest(events),boundariesSha256=m.digest(boundaries),
               owners=[dict(identity=dict(node='node-1'),registeredAt=0,sha256=m.digest(trace))])
    return observed,index,{'node-1':trace},boundaries,events


def result(size=64*m.t.MIB-32,sha=SHA):
    return m.project(*fixture(size,sha),application_bytes=size,application_sha256=sha,resource_profile=DEFAULT)


class NativeRetirementStorageTest(unittest.TestCase):
    def run_projection(self,data,*,size=837,sha=SHA):
        return m.project(*data,application_bytes=size,application_sha256=sha,resource_profile=DEFAULT)

    def test_one_callback_counts_seven_equal_content_physical_files(self):
        value=self.run_projection(fixture());m.check_result(value,application_bytes=837,application_sha256=SHA)
        point=value['firstMatch'];self.assertEqual(7,len(point['images']));self.assertEqual(7*837,point['physicalApplicationBytes'])
        self.assertEqual(1,len({v['sha256'] for v in point['images']}))
        self.assertEqual(dict(APPLICATION=7,GENERATION=1,JOURNAL=1,MISC=1,SOURCE=6),point['nonemptyPhysicalOwnerCounts'])
        self.assertGreater(point['usage']['metadata'],point['physicalMetadataBytes'])
        self.assertEqual(2*m.t.MIB,point['unspentProtectedHeadroomBytes'])
        self.assertTrue(all(value[k] is False for k in m.FALSES))

    def test_maximum_extent_uses_inventory_without_allocating_seven_images(self):
        value=result();m.check_result(value,application_bytes=64*m.t.MIB-32,application_sha256=SHA)
        self.assertEqual(469761824,value['firstMatch']['physicalApplicationBytes'])

    def test_seven_reservations_with_six_files_cannot_pass(self):
        data=fixture();files=data[0][0]['files'];files.pop(next(n for n in files if n.startswith('sources/') and n.endswith('.image')))
        value=self.run_projection(data);self.assertEqual(0,value['matchingCallbacks'])
        with self.assertRaisesRegex(ValueError,'missing simultaneous'):m.check_result(value,application_bytes=837,application_sha256=SHA)

    def test_different_callbacks_cannot_combine_their_files(self):
        data=fixture();rows,index,traces,boundaries,events=data
        other=copy.deepcopy(rows[0]);other.update(event=2,capturedEvent=3);rows.append(other)
        names=[n for n in rows[0]['files'] if n.endswith('.image')]
        rows[0]['files'].pop(names[0])
        for name in names[1:]:other['files'].pop(name)
        events.extend(copy.deepcopy(events));boundaries.extend(dict(v,eventIndex=i+2) for i,v in enumerate(list(boundaries)))
        value=self.run_projection(data);self.assertEqual(2,value['callbacks']);self.assertEqual(0,value['matchingCallbacks'])

    def test_size_and_content_must_match_the_original_bootstrapped_image(self):
        for size,sha in ((838,SHA),(837,'a'*64)):
            value=self.run_projection(fixture(),size=size,sha=sha)
            self.assertEqual(0,value['matchingCallbacks'])

    def test_one_smaller_file_cannot_borrow_extra_bytes_from_other_copies(self):
        data=fixture();files=data[0][0]['files'];files[next(n for n in files if n.endswith('.image'))]['bytes']-=1
        self.assertEqual(0,self.run_projection(data)['matchingCallbacks'])

    def test_wrong_owner_even_with_ample_total_capacity_rejects(self):
        data=fixture();trace=data[2]['node-1']
        for change in trace['changes']:
            for v in change['removed']+change['added']:
                if v['owner'].startswith('generation-a:'):v['owner']='another-original'
        with self.assertRaisesRegex(ValueError,'original charge owner'):self.run_projection(data)

    def test_file_cannot_exceed_its_own_live_lease(self):
        data=fixture();files=data[0][0]['files'];files[next(n for n in files if n.endswith('.image'))]['bytes']+=1
        with self.assertRaisesRegex(ValueError,'simultaneous owner extent'):self.run_projection(data)

    def test_capture_interval_rejects_release_and_reacquire_even_if_endpoints_match(self):
        lease=accounting.charge('APPLICATION','generation-a:'+SHA+'.image',837)
        data=fixture(interval=[('RELEASE',[lease],[]),('RESERVE',[],[lease])])
        with self.assertRaisesRegex(ValueError,'changed during capture'):self.run_projection(data)

    def test_control_callbacks_during_copy_do_not_change_storage_ownership(self):
        lease=accounting.charge('CONTROL','in-flight',17)
        data=fixture(interval=[('RESERVE',[],[lease]),('RELEASE',[lease],[])])
        value=self.run_projection(data);self.assertEqual(1,value['matchingCallbacks'])
        self.assertEqual(2,value['firstMatch']['afterSequence']-value['firstMatch']['beforeSequence'])

    def test_wrong_owner_point_scope_and_resource_sequence_reject(self):
        for field,value in (('node','node-2'),('event',1),('capturedEvent',0),('point','SOURCE_RETIREMENT_FORCED'),('scope','another')):
            data=fixture();data[0][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.run_projection(data)
        data=fixture();data[3][0]['sequence']-=1
        with self.assertRaisesRegex(ValueError,'derived usage'):self.run_projection(data)

    def test_complete_original_trace_including_closure_is_required(self):
        for mutation in ('truncated','failed','missing-close'):
            data=fixture();trace=data[2]['node-1']
            if mutation=='missing-close':
                trace['changes']=trace['changes'][:-1];trace['transitions']-=1;trace['current']=trace['changes'][-1]['usage']
            else:trace[mutation]=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.run_projection(data)

    def test_duplicate_and_foreign_callbacks_cannot_inflate_observed_count(self):
        for change in ('duplicate','foreign'):
            data=fixture()
            if change=='duplicate':data[0].append(copy.deepcopy(data[0][0]))
            else:data[4][1]['node']='node-2'
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_projection(data)

    def test_ordinals_belong_to_one_owner_and_complete_floor_group(self):
        floor='floor-copies/'+'c'*64;first=floor+'/'+'a'*64+'.image';second=floor+'/'+SHA+'.image'
        observed=[dict(node='node-1',files={first:None,second:None}),dict(node='node-1',files={second:None}),
                  dict(node='node-2',files={second:None})]
        plans=m.ordinal_plans(observed)
        self.assertEqual(['a'*64+'.image',SHA+'.image'],plans['node-1'][floor]);self.assertEqual([SHA+'.image'],plans['node-2'][floor])

    def test_segmented_inventory_does_not_materialize_image_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);raw=b'bounded original';sha=m.retirement.sha(raw);(root/sha).write_bytes(raw)
            pool=m.retirement.capture_objects.Pool(root,bootstrap_source=m.retirement.policy.BACKUP,wire_layout=m.retirement.policy.SEGMENTED)
            files=pool.view({'generations':None,'generations/a':None,'generations/a/'+sha+'.image':sha})
            with patch.object(pool,'read',side_effect=AssertionError('no image materialization')):
                observed=m.inventory(files)
            self.assertEqual(dict(bytes=len(raw),sha256=sha),observed['generations/a/'+sha+'.image'])

    def test_receipt_cannot_claim_combined_closure_or_use_old_missing_observations(self):
        original=result()
        for name in (*m.FALSES,'firstMatch','schema','matchingCallbacks','callbacks'):
            value=copy.deepcopy(original)
            value[name]=True if name in m.FALSES else None if name=='firstMatch' else 'old' if name=='schema' else 0
            with self.subTest(name=name),self.assertRaises(ValueError):m.check_result(value,application_bytes=64*m.t.MIB-32,application_sha256=SHA)
        for name in original:
            value=copy.deepcopy(original);value.pop(name)
            with self.subTest(missing=name),self.assertRaises(ValueError):m.check_result(value,application_bytes=64*m.t.MIB-32,application_sha256=SHA)

    def test_receipt_rejects_duplicate_images_wrong_counts_extent_and_boolean_numbers(self):
        for mutation in ('duplicate','digest','bytes','owner','counts','physical','metadata','staging','headroom','limits','boolean','scope'):
            value=result();p=value['firstMatch']
            if mutation=='duplicate':p['images'][-1]=dict(p['images'][0])
            elif mutation in ('digest','bytes','owner'):p['images'][0][{'digest':'sha256','bytes':'bytes','owner':'owner'}[mutation]]= 'a'*64 if mutation=='digest' else 1 if mutation=='bytes' else p['images'][1]['owner']
            elif mutation=='counts':p['nonemptyPhysicalOwnerCounts']['APPLICATION']=6
            elif mutation=='physical':p['physicalApplicationBytes']-=1
            elif mutation=='metadata':p['physicalMetadataBytes']=p['usage']['metadata']+1
            elif mutation=='staging':p['physicalStagingBytes']=p['usage']['staging']+1
            elif mutation=='headroom':p['usage']['metadata']=384*m.t.MIB
            elif mutation=='limits':p['limits']['staging']=512*m.t.MIB
            elif mutation=='boolean':p['eventIndex']=False
            else:p['scope']=''
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):m.check_result(value,application_bytes=64*m.t.MIB-32,application_sha256=SHA)


if __name__=='__main__':unittest.main()
