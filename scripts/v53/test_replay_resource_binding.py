import copy
import unittest
from . import replay_resource_binding as m


class ReplayResourceBindingTest(unittest.TestCase):
    def fixture(self,*,extent=64*m.r.MIB,owner=None,interruption=False):
        rows=[];state={};limits=(384*m.r.MIB,512*m.r.MIB,64*m.r.MIB)
        def change(event,removed=(),added=()):
            for value in removed:del state[m.r.key(value)]
            for value in added:state[m.r.key(value)]=value
            rows.append(dict(sequence=len(rows),event=event,removed=list(removed),added=list(added),usage=m.r.usage(state,limits)))
        change('START');a=dict(unit='APPLICATION',owner=owner or m.OWNERS[0],bytes=extent,claimSource='')
        b=dict(a,owner=m.OWNERS[1]);change('RESERVE',added=[a]);change('RESERVE',added=[b]);start=2
        if interruption:change('RELEASE',removed=[a]);change('RESERVE',added=[a])
        end=len(rows)-1;change('RELEASE',removed=[a]);change('RELEASE',removed=[b])
        trace=dict(schema='gse-v53-resource-transitions-v1',metadataLimit=limits[0],stagingLimit=limits[1],queueLimit=limits[2],
                   transitions=len(rows),truncated=False,failed=False,changes=rows,current=rows[-1]['usage'])
        events=[dict(node='node-1',event=v) for v in ('REPLAY_RESERVED','REPLAY_APPLICATION_FINISHED','REPLAY_BEFORE_RETURN')]
        bounds=[dict(node='node-1',eventIndex=i,sequence=seq,usage=copy.deepcopy(rows[seq]['usage'])) for i,seq in enumerate((start,end,end))]
        return trace,events,bounds

    def run_binding(self,values):return m.bind(*values,'node-1',closed=True)

    def test_full_reservations_and_retained_return_then_actual_close(self):
        result=self.run_binding(self.fixture());self.assertEqual(1,result['transactions']);self.assertEqual(3,result['callbacks'])
        self.assertTrue(result['closed']);self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_named_owners_full_extents_and_between_callback_continuity(self):
        for kw in ({'extent':1},{'owner':'unrelated'},{'interruption':True}):
            with self.subTest(kw=kw),self.assertRaisesRegex(ValueError,'^replay resources two continuous full reservations$'):
                self.run_binding(self.fixture(**kw))

    def test_forged_usage_owner_bool_index_or_reversed_sequence_reject(self):
        for change in ('usage','owner','bool','sequence','eventIndex'):
            values=self.fixture();point=values[2][1]
            if change=='usage':point['usage']['staging']-=1
            elif change=='owner':point['node']='node-2'
            elif change=='bool':point['sequence']=True
            elif change=='sequence':point['sequence']=0
            else:point['eventIndex']=True
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_binding(values)

    def test_incomplete_overlapping_or_unstarted_replay_rejects(self):
        for index,point in ((0,'REPLAY_CLAIM_FORCED'),(1,'REPLAY_RESERVED'),(2,'REPLAY_DELETED')):
            values=self.fixture();values[1][index]['event']=point
            with self.assertRaises(ValueError):self.run_binding(values)

    def test_empty_callback_scope_and_unclosed_accounting_are_distinct(self):
        trace,events,bounds=self.fixture();self.assertEqual(0,m.bind(trace,events,bounds,'node-2',closed=True)['transactions'])
        trace['changes']=trace['changes'][:-1];trace['transitions']-=1;trace['current']=trace['changes'][-1]['usage']
        with self.assertRaisesRegex(ValueError,'^resource transitions outstanding charges at close$'):
            m.bind(trace,events,bounds,'node-1',closed=True)


if __name__=='__main__':unittest.main()
