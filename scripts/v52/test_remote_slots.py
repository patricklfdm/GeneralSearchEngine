from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from . import remote_command as commands,remote_slots as slots
from .test_cloud_suite import binding


def owner(member='experiment',history=None):
    selected=commands.suite.selection(binding(),member,'1'*32)
    return commands.binding(selected,history or selected['member']['histories'][0],'node-1',commands.boot_id(),'2'*32)


class RemoteSlotsTest(unittest.TestCase):
    def test_same_history_command_has_one_id_and_rejects_fresh_uuid_replay(self):
        bound=owner();original=slots.request(bound,'execute-history')
        self.assertEqual(original,slots.request(deepcopy(bound),'execute-history',{}))
        with tempfile.TemporaryDirectory() as directory:
            store=commands.CommandStore(Path(directory)/'store',bound,create=True);entered=[]
            first=slots.execute(store,original,lambda *a:entered.append(1) or {})
            self.assertEqual(first,slots.execute(store,slots.request(bound,'execute-history'),lambda *a:self.fail('replayed')))
            with self.assertRaisesRegex(ValueError,'semantic command identity'):
                slots.execute(store,dict(original,commandId='f'*32),lambda *a:self.fail('fresh ID replay'))
            self.assertEqual([1],entered)

    def test_lifecycle_slots_and_declared_reopen_do_not_collide(self):
        bound=owner('failure-drill','leader-sigkill-retained-restart')
        values=[slots.request(bound,k) for k in ('prepare-receiver','execute-history','collect')]
        values.extend(slots.request(bound,k,{'generation':generation}) for k in ('start-voter','stop-voter') for generation in (1,2))
        values.append(slots.request(bound,'declared-fault',{'action':'sigkill'}))
        self.assertEqual(8,len({v['commandId'] for v in values}))
        for value in values:self.assertEqual(value,slots.validate(value,bound))

    def test_attempt_session_source_and_node_remain_in_semantic_identity(self):
        original=owner();identity=slots.request(original,'execute-history')['commandId']
        for field,value in (('session','3'*32),('node','node-2')):
            changed=dict(original,**{field:value});self.assertNotEqual(identity,slots.request(changed,'execute-history')['commandId'])
        for field,value in (('attempt','3'*32),('source','3'*40)):
            changed=deepcopy(original)
            if field=='attempt':changed['selection'][field]=value
            else:changed['selection']['binding'][field]=value
            self.assertNotEqual(identity,slots.request(changed,'execute-history')['commandId'])

    def test_undeclared_generations_faults_and_payloads_reject_before_claim(self):
        bound=owner()
        for kind,payload in (('start-voter',{'generation':2}),('stop-voter',{'generation':True}),
                             ('execute-history',{'output':'new-history'}),('collect',{'path':'/etc'}),
                             ('declared-fault',{'action':'sigkill'}),('read',{})):
            with self.subTest(kind=kind,payload=payload),self.assertRaises(ValueError):slots.request(bound,kind,payload)
        bound=owner('failure-drill','follower-snapshot-carried-token')
        a=slots.request(bound,'declared-fault',{'action':'partition'});b=slots.request(bound,'declared-fault',{'action':'heal'})
        self.assertNotEqual(a['commandId'],b['commandId'])
        with self.assertRaises(ValueError):slots.request(bound,'declared-fault',{'action':'sigkill'})


if __name__=='__main__':unittest.main()
