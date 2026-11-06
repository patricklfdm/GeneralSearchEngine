"""Synthetic accounting boundaries; original native histories qualify separately."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import native_carried_resource_evidence as m
from .test_resource_transitions import charge,row,trace


class NativeCarriedResourceTest(unittest.TestCase):
    def fixture(self,root,life):
        history=root/'history';directory=root/'resources'/f'life-{life}';directory.mkdir(parents=True)
        (history/'process').mkdir(parents=True,exist_ok=True)
        def write(path,value):path.write_bytes(m.f.canonical(value))
        write(history/'process/result.json',dict(children=[dict(pid=10),dict(pid=20)]))
        owners=[];events=[];points=[];closes=[];identities={}
        for node in m.t.x.process.NODES:
            identity=dict(node=node,storage=node+'-original',host='127.0.0.1',port=12345);identities[node]=identity
            owner=dict(identity=identity,path=node+'.json',registeredAt=len(events));owners.append(owner)
            held=charge('JOURNAL','journal',20)
            rows=[row('START'),row('RESERVE',added=[held],metadata=20,counts={'JOURNAL':1})]
            if life==2:rows.append(row('RELEASE',[held]))
            value=trace(rows);value['stagingLimit']=m.LIMITS[1];write(directory/owner['path'],value)
            owner['sha256']=m.sha((directory/owner['path']).read_bytes())
            for name,seq in (('CURRENT_VALIDATED',0),('NODE_OPEN',1)):
                event=dict(node=node,event=name,incarnation=life)
                if name=='NODE_OPEN':event['counts']=dict(JOURNAL=1)
                points.append(dict(eventIndex=len(events),node=node,sequence=seq,usage=value['changes'][seq]['usage']));events.append(event)
            if life==2:
                closes.extend(dict(node=node,event=label,eventCount=8,sequence=seq,usage=value['changes'][seq]['usage'])
                              for label,seq in (('BEGIN',1),('RETURNED',2)))
        write(directory/'events.json',events);write(directory/'boundaries.json',points);write(directory/'closes.json',closes)
        (history/f'process/life-{life}.jsonl').write_bytes(b'\n'.join(m.f.canonical(dict(action='event',value=v)) for v in events)+b'\n')
        index=dict(schema='gse-v53-node-resource-lifetime-v1',root='root',life=life,pid=10*life,
            terminal='CUT_PREFIX' if life==1 else 'CLOSED',owners=owners,
            eventsSha256=m.sha((directory/'events.json').read_bytes()),boundariesSha256=m.sha((directory/'boundaries.json').read_bytes()),
            closesSha256=m.sha((directory/'closes.json').read_bytes()))
        write(directory/'index.json',index)
        def inventory(path):return {'node.gsr':Path(path).name,'selector.gsr':'selector'}
        def decode(raw,*args):return dict(root='root') if raw=='selector' else dict(identity=identities[raw])
        return directory,history,inventory,decode

    def run_case(self,life,edit=None):
        with tempfile.TemporaryDirectory(prefix='v53-resource-unit-') as temporary:
            directory,history,inventory,decode=self.fixture(Path(temporary),life)
            if edit:edit(directory)
            with patch.object(m.c,'inventory',side_effect=inventory),patch.object(m.f,'decode',side_effect=decode):
                return m.lifetime(directory,history,life)

    def change(self,name,edit):
        def apply(directory):
            path=directory/name;value=json.loads(path.read_bytes());edit(value);path.write_bytes(m.f.canonical(value))
            if name=='index.json':return
            index=json.loads((directory/'index.json').read_bytes())
            keys={'events.json':'eventsSha256','boundaries.json':'boundariesSha256','closes.json':'closesSha256'}
            if name in keys:index[keys[name]]=m.sha(path.read_bytes())
            else:next(v for v in index['owners'] if v['path']==name)['sha256']=m.sha(path.read_bytes())
            (directory/'index.json').write_bytes(m.f.canonical(index))
        return apply

    def test_crash_prefix_and_normal_close_keep_distinct_accounting_scopes(self):
        crash=self.run_case(1);normal=self.run_case(2)
        self.assertTrue(all(not v['closed'] and v['close'] is None for v in crash['owners']))
        self.assertTrue(all(v['closed'] and v['close']['changes']==1 for v in normal['owners']))
        self.assertEqual(8,crash['events']);self.assertEqual(4,len(normal['owners']))

    def test_identity_pid_terminal_and_original_registration_are_bound(self):
        for change,reason in ((lambda v:v.update(pid=99),'process identity'),(lambda v:v.update(terminal='CLOSED'),'process identity'),
            (lambda v:v['owners'][0].update(registeredAt=1),'owner registration'),
            (lambda v:v['owners'][0]['identity'].update(storage='other'),'owner registration')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.run_case(1,self.change('index.json',change))

    def test_resource_limits_or_truncated_observations_cannot_be_relabelled(self):
        for change,reason in ((lambda v:v.update(stagingLimit=512*m.r.MIB),'configured limits'),
            (lambda v:v.update(truncated=True),'incomplete observation'),(lambda v:v.update(failed=True),'incomplete observation')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.run_case(1,self.change('node-1.json',change))

    def test_original_wire_and_storage_events_cannot_be_omitted_from_the_observed_prefix(self):
        with self.assertRaisesRegex(ValueError,'exact original event prefix'):
            self.run_case(1,self.change('events.json',lambda v:v.pop()))

    def test_original_event_and_identity_equality_preserves_numeric_types(self):
        with self.assertRaisesRegex(ValueError,'exact original event prefix'):
            self.run_case(1,self.change('events.json',lambda v:v[0].update(incarnation=True)))
        with self.assertRaisesRegex(ValueError,'owner registration'):
            self.run_case(1,self.change('index.json',lambda v:v['owners'][0]['identity'].update(port=12345.0)))

    def test_checkpoint_needs_original_owner_sequence_and_derived_usage(self):
        for change,reason in ((lambda v:v[0].update(node='node-2'),'checkpoint owner'),
            (lambda v:v[0].update(sequence=999),'checkpoint order'),
            (lambda v:v[0]['usage'].update(metadata=1),'derived usage')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.run_case(1,self.change('boundaries.json',change))

    def test_original_open_counts_cannot_be_satisfied_by_a_stale_empty_checkpoint(self):
        def stale(v):v[1].update(sequence=0,usage=deepcopy(m.r.EMPTY))
        with self.assertRaisesRegex(ValueError,'original open usage'):self.run_case(1,self.change('boundaries.json',stale))

    def test_crash_never_supplies_close_markers_or_drained_state(self):
        with self.assertRaisesRegex(ValueError,'crash is not successful close'):
            self.run_case(1,self.change('closes.json',lambda v:v.append(dict(node='node-1',event='RETURNED'))))
        def drain(v):
            v['changes'].append(dict(row('RELEASE',[charge('JOURNAL','journal',20)]),sequence=2))
            v.update(transitions=3,current=deepcopy(m.r.EMPTY))
        with self.assertRaisesRegex(ValueError,'crash prefix cannot claim drained'):self.run_case(1,self.change('node-1.json',drain))

    def test_successful_close_requires_both_actual_markers_and_final_empty_sequence(self):
        for change,reason in ((lambda v:v.pop(),'crash is not successful close'),
            (lambda v:v[1].update(event='BEGIN'),'exact close pair'),
            (lambda v:v[1].update(sequence=1,usage=deepcopy(v[0]['usage'])),'original close interval')):
            with self.subTest(reason=reason),self.assertRaisesRegex(ValueError,reason):self.run_case(2,self.change('closes.json',change))

    def test_invalid_history_prevents_resource_credit(self):
        with patch.object(m.collection,'inventory',return_value={}),patch.object(m.t,'validate',side_effect=ValueError('bad original')),patch.object(m,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'bad original'):m.validate('/original')
            replay.assert_not_called()

    def test_original_changes_during_accounting_are_rejected(self):
        with patch.object(m.collection,'inventory',side_effect=[{},dict(changed=True)]),patch.object(m.t,'validate'),patch.object(m,'replay'):
            with self.assertRaisesRegex(ValueError,'original changed'):m.validate('/original')

    def test_close_invocation_event_boundary_must_match_its_actual_sequence(self):
        with self.assertRaisesRegex(ValueError,'close event interval'):
            self.run_case(2,self.change('closes.json',lambda v:v[0].update(eventCount=0)))

    def test_each_negative_targets_the_declared_boundary_without_changing_original_history(self):
        with tempfile.TemporaryDirectory(prefix='v53-resource-negative-unit-') as temporary:
            root=Path(temporary)/'raw';self.fixture(root,1);_,_,inventory,decode=self.fixture(root,2)
            before=m.collection.inventory(root/'history');original=m.collection.inventory(root)
            with patch.object(m.c,'inventory',side_effect=inventory),patch.object(m.f,'decode',side_effect=decode):
                self.assertEqual(8,m.replay(root)['ownerLifetimes'])
                for name,reason in m.NEGATIVES.items():
                    with self.subTest(name=name):
                        result=m.negative(root,before,name)
                        self.assertEqual(reason,result['reason']);self.assertTrue(result['originalHistoryUnchanged'])
            self.assertEqual(original,m.collection.inventory(root))

    def test_negative_qualification_requires_original_and_preserves_wrong_rejection(self):
        with patch.object(m,'validate',side_effect=ValueError('invalid original')),patch.object(m,'negative') as negative:
            with self.assertRaisesRegex(ValueError,'invalid original'):m.qualify('/original')
            negative.assert_not_called()
        with tempfile.TemporaryDirectory(prefix='v53-resource-wrong-negative-') as temporary:
            root=Path(temporary);self.fixture(root,1);self.fixture(root,2);before=m.collection.inventory(root/'history')
            with patch.object(m,'replay',side_effect=ValueError('unrelated failure')):
                with self.assertRaisesRegex(ValueError,'wrong negative.*unrelated failure'):m.negative(root,before,'process-pid')
            with patch.object(m,'replay',return_value={}):
                with self.assertRaisesRegex(ValueError,'accepted mutation'):m.negative(root,before,'process-pid')

    def test_negative_cannot_mutate_original_process_evidence(self):
        with tempfile.TemporaryDirectory(prefix='v53-resource-history-protection-') as temporary:
            root=Path(temporary);self.fixture(root,1);self.fixture(root,2);before=m.collection.inventory(root/'history')
            def corrupt(changed,name):(changed/'history/process/result.json').write_text('{}')
            with patch.object(m,'mutate',side_effect=corrupt),patch.object(m,'replay') as replay:
                with self.assertRaisesRegex(ValueError,'negative changed original history'):m.negative(root,before,'process-pid')
                replay.assert_not_called()


if __name__=='__main__':unittest.main()
