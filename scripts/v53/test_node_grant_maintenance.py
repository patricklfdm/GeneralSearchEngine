from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from . import node_grant_maintenance as m


class NodeGrantMaintenanceTest(unittest.TestCase):
    def replay(self,*,selected=False,offered=10,changed=False):
        node='node-3';key=(4,node);ballot=dict(counter=4)
        before={node:dict(original='bytes')};after=dict(derived='bytes');voters=(node,'node-1')
        replay=m.Replay({key:dict(before=before,after=after,voters=voters)})
        phase=SimpleNamespace(at=lambda *args:1,events=[{}]*12,entries=[dict(kind='PREPARE',
            request=dict(recipient=dict(node=node),ballot=ballot),answer='PROMISE',
            response=dict(payload=dict(basis=m.e.digest(b'basis'))),offered=offered)])
        phase.events[2]=dict(node=node,event='SOURCE_RETIREMENT_FORCED')
        for i in range(3,12):phase.events[i]=dict(node='node-1',event='UNRELATED')
        if changed:phase.events[2]['untrusted']='claim'
        selection=dict(ballot=ballot,sources=[dict(voter='node-1'),dict(voter=node if selected else 'node-2')])
        return replay,phase,selection

    def run_replay(self,replay,phase,selection):
        with patch.object(m.p.net.a,'frozen',return_value=(b'promise',b'basis',b'source',{})), \
                patch.object(m,'transaction',return_value=(['SOURCE_RETIREMENT_FORCED'],1)), \
                patch.object(m,'transfers',return_value=1):
            replay(phase,selection)

    def test_only_bound_unselected_transition_completes(self):
        replay,phase,selection=self.replay()
        with self.assertRaisesRegex(ValueError,'unbound derived transition'):replay.complete()
        self.run_replay(replay,phase,selection)
        self.assertEqual([dict(node='node-3',ballot=4,sources=1,callbacks=1,packetOnlyFallbacks=1)],replay.complete())
        with self.assertRaisesRegex(ValueError,'unselected original owner'):self.run_replay(replay,phase,selection)
        replay,phase,selection=self.replay(selected=True)
        with self.assertRaisesRegex(ValueError,'unselected original owner'):self.run_replay(replay,phase,selection)

    def test_force_must_precede_actual_advertised_grant_and_have_exact_shape(self):
        for options in (dict(offered=2),dict(changed=True)):
            with self.subTest(options=options):
                replay,phase,selection=self.replay(**options)
                with self.assertRaisesRegex(ValueError,'complete original callbacks'):self.run_replay(replay,phase,selection)
                self.assertFalse(replay.used)

    def test_reply_cannot_advertise_other_basis_or_ballot(self):
        for field in ('basis','ballot'):
            replay,phase,selection=self.replay();row=phase.entries[0]
            if field=='basis':row['response']['payload']['basis']='0'*64
            else:row['request']['ballot']=dict(counter=3)
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'original advertised grant'):
                self.run_replay(replay,phase,selection)

    def transfer_fixture(self,*,missing):
        image=b'original image';digest=m.e.digest(image)
        remote={'source.gscp':b'packet',digest+'.image':image}
        local={} if missing else {digest+'.image':image}
        packet=dict(capsule=dict(cut='cut'),images={digest:len(image)})
        before={'node-3':dict(local=True),'node-1':{'generations/a/generation.gsr':b'manifest'}}
        def current(files):return ('generations/a/',local,packet) if files.get('local') else ('generations/a/',remote,packet)
        phase=SimpleNamespace(at=Mock(return_value=20),probe=Mock(return_value=3),
            transfer=Mock(side_effect=[dict(arrivals=[[6],[7]]),dict(arrivals=[[9],[10]]),dict(arrivals=[[13]])]))
        return phase,before,current,local,remote,packet

    def run_transfers(self,missing):
        phase,before,current,local,remote,packet=self.transfer_fixture(missing=missing)
        with patch.object(m.c,'current',side_effect=current),patch.object(m.n,'current_reference',return_value='packet-only'), \
                patch.object(m.n,'maintenance_prefixes',return_value=['complete-prefix']), \
                patch.object(m.n,'maintenance_generations',return_value=['complete-generation']):
            result=m.transfers(phase,before,'node-3',('node-3','node-1'),dict(counter=4),1,30)
        return result,phase

    def test_missing_image_requires_completed_probe_then_full_prefix_then_generation(self):
        result,phase=self.run_transfers(True)
        self.assertEqual(1,result);calls=phase.transfer.call_args_list
        self.assertEqual([[('packet-only',b'packet','CAPSULE')]],calls[0].args[2])
        self.assertEqual(['complete-prefix'],calls[1].args[2]);self.assertEqual(['complete-generation'],calls[2].args[2])
        self.assertEqual([(3,20),(7,20),(10,20)],[v.args[-2:] for v in calls])

    def test_available_original_image_needs_no_failed_probe(self):
        result,phase=self.run_transfers(False)
        self.assertEqual(0,result);calls=phase.transfer.call_args_list
        self.assertEqual([['complete-prefix'],['complete-generation']],[v.args[2] for v in calls])
        self.assertEqual([(3,20),(7,20)],[v.args[-2:] for v in calls])

    def test_missing_full_copy_after_probe_is_not_a_floor(self):
        phase,before,current,_,_,_=self.transfer_fixture(missing=True)
        phase.transfer.side_effect=[dict(arrivals=[[7]]),ValueError('missing complete prefix')]
        with patch.object(m.c,'current',side_effect=current),patch.object(m.n,'current_reference',return_value='packet-only'), \
                patch.object(m.n,'maintenance_prefixes',return_value=['complete-prefix']):
            with self.assertRaisesRegex(ValueError,'missing complete prefix'):
                m.transfers(phase,before,'node-3',('node-3','node-1'),{},1,30)
        self.assertEqual(2,phase.transfer.call_count)

    def test_transaction_refuses_other_owner_scope_before_any_pruning(self):
        files={'generations/a':None,m.n.s.FILE:b'ledger'}
        with patch.object(m.c,'current',return_value=('generations/a/',{},{})),patch.object(m,'covering_floor') as floor:
            for voters in (('node-1','node-3'),('node-3','node-3'),('node-3',)):
                with self.subTest(voters=voters),self.assertRaisesRegex(ValueError,'exact floor cohort'):
                    m.transaction({'node-3':files},files,'node-3',voters)
            changed=deepcopy(files);changed['generations/b']=None
            with self.assertRaisesRegex(ValueError,'source-only scope'):
                m.transaction({'node-3':changed},changed,'node-3',('node-3','node-1'))
            with self.assertRaisesRegex(ValueError,'source-only scope'):
                m.transaction({'node-3':files},{m.n.s.FILE:b'other'},'node-3',('node-3','node-1'))
            floor.assert_not_called()


if __name__=='__main__':unittest.main()
