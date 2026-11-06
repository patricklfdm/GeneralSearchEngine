"""Process-local export refusal regressions; these are not native histories."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from . import native_carried_transition_exports as m
from . import test_joining_export_evidence as fixture


class NativeCarriedTransitionExportsTest(unittest.TestCase):
    def test_all_owners_have_separate_lives_without_cross_death_authority(self):
        events=[dict(node=n,event='NODE_OPEN') for n in m.process.NODES]+[dict(event='GROUP_CRASH')]+[
            dict(node=n,event='NODE_OPEN') for n in m.process.NODES]+[dict(event='finished')]
        actual=m.lifetimes(events)
        self.assertEqual(8,sum(map(len,actual.values())))
        self.assertEqual([(3,4),(8,10)],actual['node-4'])
        for changed in (events[:4]+events[5:],events+[dict(event='GROUP_CRASH')],events[:8]+events[9:]):
            with self.assertRaisesRegex(ValueError,'group death|owner lifetimes'):m.lifetimes(changed)

    def test_both_exporter_and_receiver_must_live_through_commit_delivery(self):
        q=dict(sender=dict(node='node-1'),recipient=dict(node='node-2'))
        groups=[[dict(offer=dict(request=q,sent=10),commit=dict(delivered=20))]]
        live={n:[(0,30),(40,70)] for n in ('node-1','node-2')};m.transfer_lifetimes(groups,live)
        for node in live:
            for spans in ([(0,20),(30,70)],[(10,30)],[(0,15),(16,30)]):
                with self.subTest(node=node,spans=spans),self.assertRaisesRegex(ValueError,'outside owner lifetime'):
                    m.transfer_lifetimes(groups,dict(live,**{node:spans}))

    def test_selector_windows_stop_at_rename_and_reopen_does_not_bridge_death(self):
        events=[dict(node='node-1',event=name) for name in
            ('NODE_OPEN','INSTALL_SELECTOR_RENAMED','INSTALL_BEFORE_RETURN','GROUP_CRASH','NODE_OPEN','end')]
        live={'node-1':[(0,3),(4,6)]};history=SimpleNamespace(ranges=[dict(kind='campaign',after='life-1-installed-1')])
        files={'g/generation.gsr':b'manifest','node.gsr':b'node'}
        def decode(raw,*args):return dict(identity=dict(node='node-1')) if raw==b'node' else dict(sources=[dict(voter='node-1')])
        with patch.object(m.process,'NODES',('node-1',)),patch.object(m.c,'inventory',return_value=files),\
                patch.object(m.c,'current',return_value=('g/',{'selected.gsr':b'selection'},{})),patch.object(m.f,'decode',side_effect=decode):
            windows=m.generation_windows(Path('/original'),events,history,live)
        self.assertEqual([(0,1),(2,3),(4,6)],[(v['start'],v['end']) for v in windows])
        self.assertEqual(windows[1]['members'],windows[2]['members'])
        for a,b in ((1,2),(2,3),(3,5)):
            with self.assertRaisesRegex(ValueError,'inactive current generation'):m.e.current(windows,'node-1',a,b)

    def test_surviving_source_bytes_do_not_make_a_cross_death_transfer_live(self):
        windows,q,source,values=fixture.JoiningExportEvidenceTest().source()
        # The same durable BASIS can still exist in the successor. A new
        # transfer can use it; the dead owner's earlier borrow cannot resume.
        reopened=[]
        for own in windows:reopened.extend([dict(own,end=9),dict(own,start=9)])
        m.e.authorize_source(values,reopened,[source])
        changed=deepcopy(values);changed[0]['offer']['received']=8
        with self.assertRaisesRegex(ValueError,'inactive current generation'):m.e.authorize_source(changed,reopened,[source])
        retired=dict(source,end=values[-1]['commit']['offered'])
        with self.assertRaisesRegex(ValueError,'inactive frozen source'):m.e.authorize_source(values,reopened,[retired])

    def interrupted(self,point,*,wrong=False):
        windows,q=fixture.JoiningExportEvidenceTest().inputs();own=windows[0];node=own['node']
        selected=dict(root=q['root'],view=q['view'],ballot=q['ballot'],sources=[dict(voter=node)])
        entry=dict(index=6);parts=dict(ENTRY=b'original entry',PAYLOAD=b'original payload')
        expected=dict(root=q['root'],authority=q['view'],ballot=q['ballot'],index=6,entry=m.sha(parts['ENTRY']))
        accept=m.f.encode('records','ACCEPT',expected)
        history=SimpleNamespace(ranges=[dict(kind='interrupted',start=0,stop=90,before='installed')])
        events=[dict(event='other'),dict(node=node,event=point),dict(node=node,event='PROMISE_FORCED')]
        def decode(raw,*args):return selected if raw==b'selected' else entry
        with patch.object(Path,'read_bytes',return_value=b'selected'),patch.object(m.f,'decode',side_effect=decode),\
                patch.object(m.c,'inventory'),patch.object(m.p.data,'pending',return_value=(dict(ENTRY=parts['ENTRY'],ACCEPT=b'wrong' if wrong else accept),{})):
            return m.interrupted_records(Path('/original'),events,history,windows,SimpleNamespace(phases=[parts]))

    def test_rename_without_completed_accept_does_not_authorize_receipt(self):
        self.assertEqual([],self.interrupted('ACCEPT_RENAMED'))
        records=self.interrupted('ACCEPT_BEFORE_RETURN')
        self.assertEqual(4,len(records));self.assertTrue(all(v['start']==1 for v in records))
        self.assertEqual({'pending-record','pending-payload','native-vote-receipt'},{v['family'] for v in records})
        self.assertEqual({2},{v['end'] for v in records if v['ballot'] is not None})
        receipts=[m.json.loads(v['raw']) for v in records if v['family']=='native-vote-receipt']
        self.assertEqual(['ACCEPT'],[v['phase'] for v in receipts])

    def test_interrupted_vote_must_equal_the_original_selected_entry_and_ballot(self):
        with self.assertRaisesRegex(ValueError,'original interrupted vote'):self.interrupted('ACCEPT_BEFORE_RETURN',wrong=True)

    def test_parent_snapshot_positions_include_each_real_response_and_group_death(self):
        lives=[[dict(action=k,value=v) for k,v in (
            ('started',{}),('event',{}),('opened',1),('response',{}),('installed',{}),('event',{}),('cut',{}))],
            [dict(action=k,value=v) for k,v in (
            ('started',{}),('event',{}),('opened',2),('response',{}),('snapshot','life-2-ready'),('closed',{}))]]
        with patch.object(m.process.process.process,'transcript',side_effect=lives):
            result=m.snapshots(Path('/original'),[{}]*6)
        self.assertEqual([(-1,'before-network'),(0,'life-1-opened'),(1,'life-1-installed-1'),(2,'at-cut'),
            (4,'life-2-opened'),(5,'life-2-ready'),(6,'after-close')],result)
        with patch.object(m.process.process.process,'transcript',side_effect=lives),self.assertRaisesRegex(ValueError,'snapshot positions'):
            m.snapshots(Path('/original'),[{}]*7)

    def test_bad_original_never_earns_export_or_negative_credit(self):
        with patch.object(m.process.collection,'inventory',return_value={}),\
                patch.object(m.network,'validate',side_effect=ValueError('bad original')),patch.object(m,'replay') as replay,\
                patch.object(m,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'^bad original$'):m.qualify('/original')
            replay.assert_not_called();negative.assert_not_called()

    def test_negative_requires_unchanged_storage_and_complete_precondition(self):
        before=dict(files={'original':'hash'},directories=[])
        for after,precondition,error,reason in (
            (dict(files={'original':'wrong'},directories=[]),None,None,'negative changed storage'),
            (before,ValueError('broken original'),None,'broken original'),
            (before,None,ValueError('unrelated'),'wrong negative'),(before,None,None,'accepted mutation')):
            with self.subTest(reason=reason),patch.object(m.shutil,'copytree'),patch.object(m,'mutate'),\
                    patch.object(m.process.collection,'inventory',return_value=after),patch.object(m.network,'validate',side_effect=precondition),\
                    patch.object(m,'replay',side_effect=error),self.assertRaisesRegex(ValueError,reason):
                m.negative('/original','INTENT',before,'generation-alias')

    def test_mutating_original_while_reading_is_rejected(self):
        original=dict(original=dict(original=dict(physical=dict(kind='FINAL'))))
        with patch.object(m.process.collection,'inventory',side_effect=[{},dict(changed=True)]),\
                patch.object(m.network,'validate',return_value=original),patch.object(m,'replay',return_value={}):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_export_component_does_not_claim_transient_or_full_cohort_acceptance(self):
        reader=m.Replay.__new__(m.Replay);reader.kind='FINAL';reader.groups=[];reader.live={'node-1':[(0,1),(2,3)]}
        with patch.object(reader,'exports',return_value={}):result=reader.run()
        self.assertTrue(result['observedExportAuthorityQualified'])
        for flag in ('completeCopyFloorLifetimesQualified','transientBytesCaptured','cohortAdmitted','phase3Complete'):
            self.assertFalse(result[flag])


if __name__=='__main__':unittest.main()
