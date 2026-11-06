import copy
import unittest
from . import replica_storage_coverage as m
from .test_replica_storage_coverage import file,charge,row


class StorageCoverageBindingTest(unittest.TestCase):
    def fixture(self):
        changes=[];state={};limits=(384*m.t.MIB,512*m.t.MIB,64*m.t.MIB)
        def change(event,removed=(),added=()):
            for value in removed:del state[m.t.key(value)]
            for value in added:state[m.t.key(value)]=value
            changes.append(dict(sequence=len(changes),event=event,removed=copy.deepcopy(list(removed)),added=copy.deepcopy(list(added)),usage=m.t.usage(state,limits)))
        a=charge('MISC','current-authority',20);b=charge('JOURNAL','membership-grants',20)
        change('START');change('RESERVE',added=[a]);change('RESERVE',added=[b]);change('RELEASE',removed=[a]);change('RELEASE',removed=[b])
        trace=dict(schema='gse-v53-resource-transitions-v1',metadataLimit=limits[0],stagingLimit=limits[1],queueLimit=limits[2],
                   transitions=len(changes),truncated=False,failed=False,changes=changes,current=changes[-1]['usage'])
        rows=[row(0,'POINT_A',{'root.gsr':file(19),'grants.gsr':file(1)}),
              row(2,'POINT_B',{'root.gsr':file(1),'grants.gsr':file(18)})]
        events=[dict(node='node-1',event='POINT_A'),dict(node='node-2',event='OTHER'),dict(node='node-1',event='POINT_B')]
        bounds=[dict(eventIndex=i,node=v['node'],sequence=2,usage=copy.deepcopy(changes[2]['usage'])) for i,v in enumerate(events)]
        return rows,trace,events,bounds

    def run_binding(self,values,closed=True):
        return m.bind(*values,'node-1',2,closed=closed,ordinals=m.ordinal_plans(values[0]))

    def test_peak_is_single_original_callback_not_sum_of_distinct_maxima(self):
        result=self.run_binding(self.fixture());peak=result['physicalBytePeak']
        self.assertEqual(20,peak['physicalBytes']);self.assertEqual(0,peak['eventIndex'])
        self.assertEqual(('node-1',2,2),(peak['node'],peak['life'],peak['sequence']))
        self.assertEqual([20,19],[v['physicalBytes'] for v in result['snapshots']])
        self.assertEqual(40,peak['usage']['metadata']);self.assertFalse(result['crossNodeSimultaneousPeak'])
        self.assertFalse(result['wholeRuntimeResourcesQualified']);self.assertTrue(result['accounting']['closed'])

    def test_closed_accounting_does_not_erase_earlier_physical_inventory(self):
        result=self.run_binding(self.fixture());self.assertTrue(result['accounting']['closed'])
        self.assertEqual(2,result['physicalBytePeak']['usage']['leases'])

    def test_later_release_cannot_cover_an_earlier_callback(self):
        values=self.fixture();trace=values[1];point=values[3][2]
        point.update(sequence=3,usage=copy.deepcopy(trace['changes'][3]['usage']))
        with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):self.run_binding(values)

    def test_extra_intermediate_broken_transition_is_checked(self):
        values=self.fixture();values[1]['changes'][3]['removed'][0]['bytes']=19
        with self.assertRaisesRegex(ValueError,'^resource transitions original removed charge$'):self.run_binding(values)

    def test_wrong_owner_point_or_boolean_checkpoint_rejects(self):
        for change in ('owner','eventIndex','sequence','usage','point'):
            values=self.fixture();point=values[3][2]
            if change=='owner':point['node']='node-2'
            elif change in ('eventIndex','sequence'):point[change]=True
            elif change=='usage':point['usage']['metadata']-=1
            else:values[0][1]['point']='UNRELATED'
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_binding(values)

    def test_earlier_checkpoint_cannot_supply_later_file_reservations(self):
        values=self.fixture();values[3][0].update(sequence=1,usage=copy.deepcopy(values[1]['changes'][1]['usage']))
        with self.assertRaisesRegex(ValueError,'^storage coverage original charge owner$'):self.run_binding(values)

    def test_sequence_reversal_and_missing_boundary_reject(self):
        values=self.fixture();values[3][2]['sequence']=1
        with self.assertRaisesRegex(ValueError,'^storage coverage checkpoint order$'):self.run_binding(values)
        values=self.fixture();values[3].pop()
        with self.assertRaisesRegex(ValueError,'^storage coverage exact event checkpoints$'):self.run_binding(values)

    def test_empty_owner_cannot_invent_a_physical_peak(self):
        values=self.fixture();result=m.bind(*values,'node-3',2,closed=True,ordinals=m.ordinal_plans(values[0]))
        self.assertEqual(0,result['callbacks']);self.assertIsNone(result['physicalBytePeak'])

    def test_crash_prefix_not_drain_and_exact_callback_retained(self):
        values=self.fixture();trace=values[1];trace['changes']=trace['changes'][:3];trace['transitions']=3;trace['current']=trace['changes'][-1]['usage']
        result=self.run_binding(values,closed=False);self.assertFalse(result['accounting']['closed'])
        self.assertEqual(20,result['physicalBytePeak']['physicalBytes'])
        with self.assertRaisesRegex(ValueError,'^resource transitions outstanding charges at close$'):self.run_binding(values)


if __name__=='__main__':unittest.main()
