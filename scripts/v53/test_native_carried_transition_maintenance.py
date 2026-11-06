"""Original acquisition boundaries; synthetic checks are not native histories."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_carried_transition_maintenance as m


class NativeCarriedTransitionMaintenanceTest(unittest.TestCase):
    def discovery(self,change=None):
        reader=m.Replay.__new__(m.Replay);reader.active_floor=(10,30,dict(ballot={'counter':3}))
        q=dict(view='original view',ballot={'counter':3})
        remote=dict(packet=dict(capsule=dict(cut={'index':5})))
        status=dict(sent=11,delivered=12,request=deepcopy(q),response=dict(payload=dict(cut={'index':5})))
        packet=[dict(offer=dict(sent=13),commit=dict(delivered=18))]
        metadata=[dict(offer=dict(request=q,sent=20),commit=dict(delivered=29))]
        reader.groups=[metadata];statuses=[status]
        if change=='late-metadata':metadata[0]['commit']['delivered']=30
        elif change=='late-packet':packet[0]['commit']['delivered']=31
        elif change=='early-hint':status['sent']=9
        elif change=='late-hint':status['delivered']=13
        elif change=='wrong-ballot':q['ballot']['counter']=4
        elif change=='duplicate-hint':statuses.append(deepcopy(status))
        elif change=='missing-metadata':reader.groups=[]
        elif change=='wrong-cut':status['response']['payload']['cut']['index']=6
        return reader.discovery(statuses,packet,q,remote)

    def test_a_hint_and_packet_never_replace_complete_generation_before_local_recheck(self):
        self.discovery()
        for change,reason in (
            ('late-metadata','local recheck before complete acquisition'),('missing-metadata','local recheck before complete acquisition'),
            ('late-packet','original acquisition lifetime'),('early-hint','original acquisition lifetime'),
            ('late-hint','acquisition before discovery'),('wrong-ballot','original acquisition ballot'),
            ('duplicate-hint','acquisition before discovery'),('wrong-cut','acquisition before discovery')):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,reason):self.discovery(change)

    def acquisition(self,change=None):
        r=m.Replay.__new__(m.Replay);r.history=SimpleNamespace(ranges=[dict(start=-1,stop=40,kind='campaign')])
        r.events=[dict(node='node-1',event='other') for _ in range(35)]
        r.events[10]['event']=r.events[30]['event']='FLOOR_COPY_BEFORE_RETURN'
        copies={'node-1':dict(node='node-1',manifest=b'local'),'node-2':dict(node='node-2',manifest=b'remote')}
        r.expected={(0,'node-1'):dict(copies=deepcopy(copies),ballot={'counter':2})}
        r.copy_callbacks=set();r.used_floors=set();r.acquired_statuses=set();r.discovery_statuses={'startup'};r.status_rows=[]
        if change=='first-missing':r.events[10]['event']='missing'
        elif change=='recheck-missing':r.events[30]['event']='missing'
        elif change=='extra-copy':r.events[20]['event']='FLOOR_COPY_BEFORE_RETURN'
        elif change=='copy-reused':r.copy_callbacks.add(10)
        elif change=='floor-reused':r.used_floors.add((0,'node-1'))
        elif change=='undeclared-floor':r.expected={}
        elif change=='foreign-bytes':copies['node-2']['manifest']=b'other'
        elif change=='missing-voter':copies.pop('node-2')
        statuses=['startup' if change=='startup-hint' else 'acquired']
        if change=='hint-reused':r.acquired_statuses.add('acquired')
        with patch.object(m.x.Replay,'acquired',return_value=(copies,statuses)) as acquired:
            result=r.acquired(copies['node-1'],0,31)
            acquired.assert_called_once_with(copies['node-1'],10,31)
        return r,result

    def test_acquisitions_start_at_the_actual_local_copy_and_bind_both_local_checks(self):
        reader,_=self.acquisition();self.assertEqual({10,30},reader.copy_callbacks)
        for change in ('first-missing','recheck-missing','extra-copy','copy-reused'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'exact local copy boundaries'):self.acquisition(change)

    def test_exact_derived_floor_inventory_cannot_be_replaced_by_endpoint_counts(self):
        for change,reason in (('floor-reused','unexpected floor'),('undeclared-floor','unexpected floor'),
                ('missing-voter','original governing owners'),('foreign-bytes','exact original copy bytes')):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,reason):self.acquisition(change)

    def test_startup_hint_and_prior_floor_hint_cannot_be_reused_as_new_copy_authority(self):
        for change in ('startup-hint','hint-reused'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'discovery reused as copy authority'):self.acquisition(change)

    def startup(self,change=None):
        r=m.Replay.__new__(m.Replay);r.root=Path('/original')
        r.history=SimpleNamespace(ranges=[dict(start=-1,stop=29,kind='campaign',life=1,before='one'),
            dict(start=29,stop=60,kind='campaign',life=2,before='two')])
        r.events=[dict(node='node-1',event='other') for _ in range(60)]
        r.events[10]['event']='ALLOCATOR_BEFORE_WRITE';r.events[40]['event']='FLOOR_COPY_BEFORE_RETURN';r.events[41]['event']='ALLOCATOR_BEFORE_WRITE'
        r.live={'node-1':[(0,29),(30,60)]};r.discovery_statuses=set();r.status_rows=[]
        cut=dict(index=5,view=dict(old=['node-1','node-2','node-3','node-4'],new=['node-1','node-2','node-3','node-4']))
        for life,base in ((1,0),(2,30)):
            for i,peer in enumerate(('node-2','node-3','node-4')):
                r.status_rows.append(dict(sent=base+1+3*i,delivered=base+2+3*i,requestHash=f'{life}-{peer}',
                    request=dict(sender={'node':'node-1'},recipient={'node':peer},ballot={'counter':life}),response=dict(payload=dict(cut=cut))))
        if change=='missing':r.status_rows.pop(0)
        elif change=='duplicate':r.status_rows.insert(0,deepcopy(r.status_rows[0]))
        elif change=='reordered':r.status_rows[0],r.status_rows[1]=r.status_rows[1],r.status_rows[0]
        elif change=='late-delivery':r.status_rows[0]['delivered']=11
        elif change=='overlap':r.status_rows[0]['delivered']=5
        elif change=='wrong-ballot':r.status_rows[0]['request']['ballot']['counter']=99
        elif change=='foreign-sender':r.status_rows[0]['request']['sender']['node']='node-2'
        group=lambda root,name:{n:(1 if name=='one' else 2) for n in m.x.process.NODES}
        with patch.object(m.x.Replay,'statuses'),patch.object(m.forces,'group',side_effect=group),\
                patch.object(m,'copy_of',return_value=dict(identity={'node':'node-1'},packet={'capsule':{'cut':cut}})),\
                patch.object(m.c,'current',side_effect=lambda files:('',{'promise.gsr':files},{'capsule':{'cut':cut}})),\
                patch.object(m.f,'decode',side_effect=lambda raw,*args:dict(ballot={'counter':raw})):
            r.statuses()
        return r

    def test_each_real_open_has_one_ordered_discovery_of_every_original_peer(self):
        r=self.startup();self.assertEqual(6,len(r.discovery_statuses))
        for change in ('missing','duplicate','reordered','foreign-sender'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'exact startup discovery'):self.startup(change)

    def test_startup_probe_correlation_cannot_borrow_later_ballots_or_delivery(self):
        for change in ('late-delivery','overlap','wrong-ballot'):
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'original startup correlation'):self.startup(change)

    def test_every_expected_floor_copy_callback_and_hint_requires_consumption(self):
        r=m.Replay.__new__(m.Replay);r.kind='FINAL';r.expected={(0,'node-1'):dict(phase='campaign')}
        r.events=[dict(event='FLOOR_COPY_BEFORE_RETURN')];r.used_floors=set();r.copy_callbacks=set()
        r.acquired_statuses=set();r.discovery_statuses=set();r.status_rows=[dict(requestHash='hint')]
        with patch.object(r,'statuses'),patch.object(r,'floors',return_value={}):
            with self.assertRaisesRegex(ValueError,'missing required floor'):r.run()
            r.used_floors=set(r.expected)
            with self.assertRaisesRegex(ValueError,'unbound local copy'):r.run()
            r.copy_callbacks={0}
            with self.assertRaisesRegex(ValueError,'unbound discovery'):r.run()
            r.acquired_statuses={'hint'};result=r.run()
        self.assertTrue(result['completeCopyFloorLifetimesQualified'])
        for flag in ('transientBytesCaptured','retentionRevisionCompositionQualified','cohortAdmitted','phase3Complete'):self.assertFalse(result[flag])

    def test_parent_crash_has_a_position_but_is_never_inserted_into_either_child(self):
        lives=[[dict(action='event',value=dict(event='one')),dict(action='response',value={})],
               [dict(action='opened',value=2),dict(action='event',value=dict(event='two'))]]
        observed={}
        with patch.object(m.x.process.process,'rewrite_lives',side_effect=lambda root,edit:edit(lives)):
            m.edit_observations('/original',lambda lives,indexed:observed.update(indexed))
        self.assertEqual([0,1,3],list(observed));self.assertEqual('two',observed[3]['value']['event'])

    def test_bad_original_prevents_maintenance_and_negative_credit(self):
        with patch.object(m.x.process.collection,'inventory',return_value={}),patch.object(m.x,'validate',side_effect=ValueError('bad original')),\
                patch.object(m,'replay') as replay,patch.object(m,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('/original')
            replay.assert_not_called();negative.assert_not_called()

    def test_negatives_require_identical_storage_full_prior_replay_and_exact_refusal(self):
        original=dict(files={'generation':'a'},directories=[])
        for after,precondition,result,reason in (
            (dict(files={'generation':'b'},directories=[]),None,None,'negative changed storage input'),
            (original,ValueError('bad export'),None,'bad export'),
            (original,None,ValueError('unrelated'),'wrong negative'),(original,None,None,'accepted mutation')):
            with self.subTest(reason=reason),patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),\
                    patch.object(m.x.process.collection,'inventory',return_value=after),patch.object(m.x,'validate',side_effect=precondition),\
                    patch.object(m,'replay',side_effect=result),self.assertRaisesRegex(ValueError,reason):
                m.negative('/original','FINAL',original,'local-copy-missing')

    def test_original_change_during_replay_is_not_success(self):
        with patch.object(m.x.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(m.x,'validate',return_value=dict(exports=dict(kind='FINAL'))),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')


if __name__=='__main__':unittest.main()
