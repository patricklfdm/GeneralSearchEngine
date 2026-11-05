import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import pending_drain_evidence as r
from . import store_drain_negatives as n
from .test_pending_drain_evidence import fixture as pending


def fixture(listener='checkpoint',mode='callback'):
    trace,history=pending(listener,mode);history['schema']='gse-v53-store-drain-v1'
    history['rows'][5]['sequence']=6
    n.pending.recount(trace,history)
    history['locks']={event:[dict(scope=name,path='/original/'+name+'.lock',key='inode-'+str(i),held=event!='afterSuccess')
                            for i,name in enumerate(('operation','replica','typed'))]
                      for event in ('before','afterFailure','afterSuccess')}
    return trace,history


class StoreDrainTest(unittest.TestCase):
    def test_store_release_needs_complete_drain_then_zero_accounting_and_unlocked_originals(self):
        for listener in ('checkpoint','head'):
            for mode in ('callback','interrupt'):
                data=fixture(listener,mode);before=copy.deepcopy(data);result=r.replay(*data,store=True)
                self.assertEqual(data,before);self.assertEqual(3,result['originalLocks'])
                self.assertTrue(result['storeLockContinuityObserved'])
                for key in ('physicalStorageQualified','wholeRuntimeResourcesQualified','phase3Complete'):self.assertFalse(result[key])

    def test_all_store_negatives_fail_the_declared_obligation(self):
        for listener in ('checkpoint','head'):
            for mode in ('callback','interrupt'):
                result=n.replay(fixture(listener,mode));self.assertEqual(list(n.NEGATIVES),[v['case'] for v in result])

    def test_pending_and_store_closure_scopes_cannot_substitute_for_one_another(self):
        with self.assertRaisesRegex(ValueError,'complete conditional history'):r.replay(*pending(),store=True)
        with self.assertRaisesRegex(ValueError,'complete conditional history'):r.replay(*fixture())
        with self.assertRaisesRegex(ValueError,'scope option'):r.replay(*fixture(),store=1)

    def test_unchanged_file_hashes_and_zero_accounting_do_not_waive_lock_lifetime(self):
        data=fixture();data[1]['locks']['afterFailure'][1]['held']=False
        self.assertEqual(0,data[0]['current']['leases'])
        with self.assertRaisesRegex(ValueError,'lock lifetime'):r.replay(*data,store=True)

    def test_each_lock_scope_must_keep_original_path_and_inode(self):
        for event in ('afterFailure','afterSuccess'):
            for field in ('path','key'):
                data=fixture();data[1]['locks'][event][1][field]+='-replacement'
                with self.assertRaisesRegex(ValueError,'original lock identity'):r.replay(*data,store=True)

    def test_copied_lock_roles_or_duplicate_inode_cannot_replace_three_original_locks(self):
        for field in ('scope','key','path'):
            data=fixture();rows=data[1]['locks']['before'];rows[1][field]=rows[0][field]
            with self.assertRaisesRegex(ValueError,'exact original locks'):r.replay(*data,store=True)

    def test_failed_original_does_not_count_as_successful_negatives(self):
        data=fixture();data[1]['status']='FAIL'
        with patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete conditional history'):n.replay(data)
            mutate.assert_not_called()

    def test_parent_storage_cannot_release_then_reacquire_during_failed_close(self):
        data=fixture();n.mutate(data,'baseline-release-reacquire');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'continuous baseline custody'):r.replay(*data,store=True)

    def test_store_final_return_cannot_reuse_a_pending_owner_baseline(self):
        data=fixture();data[1]['rows'][5]['sequence']=5;n.pending.recount(*data)
        with self.assertRaisesRegex(ValueError,'resources released before return'):r.replay(*data,store=True)

    def test_portable_original_inventory_is_unchanged_by_negative_replay(self):
        data=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,value in zip(('resources.json','history.json'),data):(root/name).write_bytes(r.t.collection.snapshot.f.canonical(value))
            before=r.t.collection.inventory(root);result=n.qualify(root)
            self.assertEqual(18,len(result['negatives']));self.assertEqual(before,r.t.collection.inventory(root))


if __name__=='__main__':unittest.main()
