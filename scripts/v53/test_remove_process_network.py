import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import remove_process_network as r


class RemoveProcessNetworkTest(unittest.TestCase):
    def fixture(self,root):
        profile=r.p.run.selected(r.p.run.CASES[1]);parent=[dict(node='node-2',event='CURRENT_VALIDATED')]
        child=[('OPEN','kill'),('CUT',dict(event=profile['point'],index=5))]
        resumed=[('OPEN','resume'),('READY','resume'),('CLOSED','resume')]
        (root/'history').mkdir()
        (root/'history/events.json').write_bytes(r.f.canonical(parent));(root/'history/wire.json').write_bytes(r.f.canonical([]))
        rows=[dict(origin='parent',value=v) for v in parent]
        for mode,worker,values in [('kill','interrupted-worker',child),('resume','resumed-worker',resumed)]:
            (root/worker).mkdir();(root/worker/'stdout').write_text(''.join(k+' '+(v if type(v) is str else r.f.canonical(v).decode())+'\n' for k,v in values))
            rows.extend(dict(origin=mode,value=dict(kind=k,value=v)) for k,v in values)
        self.save(root,rows)
        return profile,rows

    def save(self,root,rows):
        (root/'history/process-trace.jsonl').write_bytes(b''.join(r.f.canonical(v)+b'\n' for v in rows))

    def test_shared_order_must_project_to_each_unchanged_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);profile,rows=self.fixture(root)
            events,wires=r.observations(root,profile);self.assertEqual(6,len(events));self.assertEqual([],wires)
            for origin,reason in [('parent','parent'),('kill','child'),('resume','child')]:
                altered=copy.deepcopy(rows);altered.pop(next(i for i,v in enumerate(altered) if v['origin']==origin));self.save(root,altered)
                with self.subTest(origin=origin),self.assertRaisesRegex(ValueError,'^REMOVE process exact '+reason+' event projection'):
                    r.observations(root,profile)

    def test_old_history_cannot_be_given_synthetic_cross_process_order(self):
        with patch.object(r.Path,'read_bytes') as read,self.assertRaisesRegex(ValueError,'^REMOVE process network requires original v2 capture$'):
            r.observations('/missing',dict(schema=r.p.run.SCHEMAS[0]))
        read.assert_not_called()

    def test_resumed_owner_cannot_overlap_interrupted_owner(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);profile,rows=self.fixture(root);rows.insert(2,rows.pop(3));self.save(root,rows)
            with self.assertRaisesRegex(ValueError,'^REMOVE process shared owner lifetime$'):r.observations(root,profile)

    def test_truncation_duplicate_keys_and_extra_claimed_order_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);profile,rows=self.fixture(root);path=root/'history/process-trace.jsonl'
            original=path.read_bytes();path.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError,'^REMOVE process incomplete shared trace$'):r.observations(root,profile)
            for line in (b'{"origin":"parent","origin":"kill","value":{}}\n',
                         r.f.canonical(dict(rows[0],claimedOrder=1))+b'\n'):
                path.write_bytes(line)
                with self.assertRaises(ValueError):r.observations(root,profile)

    def test_linked_trace_is_refused_before_reading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);profile,_=self.fixture(root);path=root/'history/process-trace.jsonl';path.unlink();path.symlink_to('/missing')
            with self.assertRaisesRegex(ValueError,'^REMOVE process bounded shared trace$'):r.observations(root,profile)

    def test_failed_attempt_remains_a_terminal_and_never_an_ack(self):
        terminal=dict(direction='OUTBOUND',request='a'*64,kind='FUTURE_RETENTION_INTENT',reason='IO')
        rows,wires=r.normalize('FAILURE',terminal)
        self.assertEqual([dict(node='node-1',event='NETWORK_ATTEMPT_FAILED',**terminal)],rows);self.assertEqual([],wires)

    def test_physical_failure_prevents_all_network_claims(self):
        with patch.object(r.p.run.h,'inventory',return_value={}),patch.object(r.p,'validate',side_effect=ValueError('bad original')),patch.object(r,'replay') as replay:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.validate('/original')
        replay.assert_not_called()

    def test_qualification_does_not_start_mutations_after_original_failure(self):
        with patch.object(r,'validate',side_effect=ValueError('bad original')),patch.object(r,'ProcessPoolExecutor') as pool:
            with self.assertRaisesRegex(ValueError,'^bad original$'):r.qualify('/original')
        pool.assert_not_called()

    def test_worker_limit_precedes_any_replay(self):
        for workers in (0,5,True,1.5):
            with patch.object(r,'validate') as validate,self.assertRaisesRegex(ValueError,'^REMOVE process network replay workers$'):
                r.qualify('/original',workers=workers)
            validate.assert_not_called()

    def test_current_mutations_preserve_both_child_streams_and_exact_parent_projection(self):
        for name in r.n.shared.current_lifecycle.NEGATIVES:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root=Path(temp);profile,_=self.fixture(root)
                original={worker:(root/worker/'stdout').read_bytes() for worker in ('interrupted-worker','resumed-worker')}
                before,_=r.observations(root,profile)
                with patch.object(r.p,'profile_at',return_value=profile):r.mutate(root,name)
                events,_=r.observations(root,profile)
                self.assertEqual(before,events[:len(before)])
                self.assertTrue(all(v['event'].startswith('CURRENT_') for v in events[len(before):]))
                self.assertEqual(original,{worker:(root/worker/'stdout').read_bytes() for worker in original})

    def test_mutation_cannot_change_physical_files_or_count_an_unrelated_failure(self):
        before=dict(files={'history/owner/selector.gsr':'a'},directories=[])
        for after,physical_error,network_error,reason in (
            (dict(files={'history/owner/selector.gsr':'b'},directories=[]),None,None,'negative changed physical inputs'),
            (before,ValueError('bad physical'),None,'bad physical'),
            (before,None,ValueError('different'),'unrelated negative'),
            (before,None,None,'mutation accepted')):
            with patch.object(r.shutil,'copytree'),patch.object(r,'mutate'),patch.object(r.p.run.h,'inventory',return_value=after),\
                 patch.object(r.p,'validate',side_effect=physical_error),patch.object(r,'replay',side_effect=network_error):
                with self.assertRaisesRegex(ValueError,reason):r.negative('/original',{},before,'missing-diagnostic')


if __name__=='__main__':unittest.main()
