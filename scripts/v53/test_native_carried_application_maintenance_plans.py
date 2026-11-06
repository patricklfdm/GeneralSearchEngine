"""Guard original state and collector scope around interrupted application maintenance."""
import copy
import unittest
from unittest.mock import patch
from . import native_carried_application_protocol as p
from . import native_carried_application_maintenance_plans as m


class NativeCarriedApplicationMaintenanceTest(unittest.TestCase):
    def test_campaign_uses_staged_owner_projection_not_generic_retirement(self):
        before={'node-1':{'applied-end':None},'node-2':{}}
        with patch.object(p.forces,'campaign',return_value=[]) as campaign:
            p.campaign([],before,{},campaign_prefixes=[])
        self.assertIs(p.application.maintain,campaign.call_args.kwargs['maintenance_projection'])
        self.assertIs(p.maintenance,campaign.call_args.kwargs['maintainer'])

    def test_custom_projection_is_required_only_when_campaign_files_are_requested(self):
        selected={'sources':[]}
        with patch.object(p.forces.c,'current',return_value=('',{'selected.gsr':b'selected'},{})),\
             patch.object(p.forces.f,'decode',return_value=selected),\
             patch.object(p.forces.p.t.t,'reconcile',return_value={}),\
             patch.object(p.forces.p,'maintain',side_effect=ValueError('generic projection forbidden')):
            with patch.object(p.application,'maintain',return_value={}) as projection:
                p.forces.campaign([],{}, {'node-1':{}},campaign_prefixes=[],maintenance_projection=projection)
                projection.assert_called_once_with({},[],campaign=True)
            with patch.object(p.application,'maintain',side_effect=ValueError('not requested')) as projection:
                p.forces.campaign([],{}, {'node-1':{}},maintenance_projection=projection)
                projection.assert_not_called()
            with self.assertRaisesRegex(ValueError,'generic projection forbidden'):
                p.forces.campaign([],{}, {'node-1':{}},campaign_prefixes=[])

    def test_supported_crash_collectors_are_forwarded_without_changing_inputs(self):
        before={'node-1':{'applied-end':None}};after={'node-1':{'ack':b'original'}}
        snapshot=copy.deepcopy((before,after));prefixes=[];floors=[]
        with patch.object(p,'interrupted',return_value=['original stats']) as interrupted:
            self.assertEqual(['original stats'],p.slot([],before,None,after,first=True,
                point=p.application.CUT,prefixes=prefixes,floor_prefixes=floors))
        interrupted.assert_called_once_with([],before,after,prefixes=prefixes,floor_prefixes=floors,vote_prefixes=None,replay_prefixes=None)
        self.assertEqual(snapshot,(before,after))
        for point,first in ((p.application.CUT,False),('PROOF_RENAMED',True)):
            with self.assertRaisesRegex(ValueError,'exact interrupted cut'):
                p.slot([],before,None,after,first=first,point=point,prefixes=[])

    def test_recovery_projects_only_after_validating_and_removing_old_end(self):
        before={'node-1':{'applied-end':None}};cleaned={'node-1':{'selector.gsr':b'original'}}
        event={'node':'node-1','event':'ACCEPT_VALIDATED'};rows=[event];prefixes=[];floors=[]
        with patch.object(p,'retired',return_value=(rows,cleaned)) as retired,\
             patch.object(p.forces,'slot',return_value=[]) as slot,\
             patch.object(p.c,'current',return_value=('',{'selected.gsr':b'selected'},{})),\
             patch.object(p.f,'decode',return_value={'sources':[]}):
            p.slot(rows,before,{}, {},first=True,prefixes=prefixes,floor_prefixes=floors)
        retired.assert_called_once_with(rows,before,replay_prefixes=None)
        slot.assert_called_once_with(rows,cleaned,{}, {},first=True,maintainer=p.maintenance,
            prefixes=prefixes,floor_prefixes=floors,vote_prefixes=None,completion_prefixes=None,replay_prefixes=None,
            maintenance_projection=p.application.maintain)
        self.assertIs(event,slot.call_args.args[0][0])
        with patch.object(p,'retired',side_effect=ValueError('unbound old end')),patch.object(p.forces,'slot') as slot:
            with self.assertRaisesRegex(ValueError,'unbound old end'):p.slot(rows,before,{}, {},first=True,prefixes=[])
        slot.assert_not_called()

    def test_unimplemented_collectors_cannot_earn_apparent_coverage(self):
        for collector in ('ledger_prefixes','unknown'):
            with patch.object(p,'retired') as retired,patch.object(p,'interrupted') as interrupted:
                for point in (None,p.application.CUT):
                    with self.assertRaisesRegex(ValueError,'transient collectors unsupported'):
                        p.slot([],{},None,{},first=True,point=point,**{collector:[]})
                retired.assert_not_called();interrupted.assert_not_called()

    def test_staged_projection_preserves_original_end_and_all_deferred_owner_files(self):
        before={'node-1':{'applied-end':None,'applied-end/ack.gsr':b'old ACK','sources/x':b'pin'},'node-2':{}}
        snapshot=copy.deepcopy(before)
        with patch.object(p.application.p,'maintain',return_value=before) as maintenance:
            self.assertEqual(before,p.application.maintain(before,['node-1','node-2'],campaign=True))
        maintenance.assert_called_once_with(before,['node-2'],campaign=True)
        self.assertEqual(snapshot,before)

    def test_original_resource_chain_cannot_be_skipped_or_changed(self):
        with patch.object(m.collection,'inventory',return_value={}),\
             patch.object(m.original,'validate',side_effect=ValueError('bad original')),patch.object(m,'plans') as plans:
            with self.assertRaisesRegex(ValueError,'bad original'):m.validate('/original')
        plans.assert_not_called()
        with patch.object(m.collection,'inventory',side_effect=[{},dict(changed=True)]),\
             patch.object(m.original,'validate'),patch.object(m,'plans',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_projected_states_cannot_be_reported_as_captured_native_bytes(self):
        projected={family:[dict(life=1),dict(life=2)] for family in m.FAMILIES}
        with patch.object(m.collection,'inventory',return_value={}),\
             patch.object(m.original,'validate',return_value={'original':True}),patch.object(m,'plans',return_value=projected):
            result=m.validate('/original')
        self.assertEqual('PARTIAL',result['status']);self.assertTrue(result['originalCallbackCoverage'])
        for flag in ('capturedBytesQualified','fullTransientBytesQualified','wholeRuntimeResourcesQualified','cohortAdmitted','phase3Complete'):
            self.assertFalse(result[flag])
        self.assertTrue(all(row['prefixes']==2 for row in result['projectedFamilies'].values()))

    def test_plan_binds_exact_axis_and_each_callback_to_one_family(self):
        info=dict(carriedKind='INTENT',cut=p.application.CUT)
        def populate(*args,**kwargs):
            self.assertIs(p,kwargs['handlers'])
            for at,argument in enumerate(m.FAMILIES.values()):
                kwargs[argument].extend(dict(life=life,eventIndex=at) for life in (1,2))
        with patch.object(p.p.process,'read',return_value=info),patch.object(p.forces,'replay',side_effect=populate):
            self.assertEqual(set(m.FAMILIES),set(m.plans('/original')))
        for broken in ({},dict(carriedKind='DATA',cut=p.application.CUT),dict(carriedKind='INTENT',cut='PROOF_RENAMED')):
            with patch.object(p.p.process,'read',return_value=broken),patch.object(p.forces,'replay') as replay:
                with self.assertRaises((KeyError,ValueError)):m.plans('/original')
                replay.assert_not_called()
        def duplicate(*args,**kwargs):
            populate(*args,**kwargs);kwargs['floor_prefixes'][0]['eventIndex']=0
        with patch.object(p.p.process,'read',return_value=info),patch.object(p.forces,'replay',side_effect=duplicate):
            with self.assertRaisesRegex(ValueError,'duplicate callback ownership'):m.plans('/original')
        with patch.object(p.p.process,'read',return_value=info),patch.object(p.forces,'replay'):
            with self.assertRaisesRegex(ValueError,'both original lifetimes'):m.plans('/original')


if __name__=='__main__':unittest.main()
