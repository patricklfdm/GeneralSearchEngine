"""Constructor rollback needs original custody, not just matching end counters."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from . import construction_rollback_evidence as r
from . import construction_rollback_negatives as n
from .test_resource_transitions import charge,trace,row


def fixture(scope='checkpoint'):
    rows=[row('START')];original=charge('SOURCE','original-owner',100)
    if scope!='source-service':rows.append(row('RESERVE',added=[original]))
    cases=[];files=[dict(path='original/promise.bin',sha256='a'*64)]
    for name in r.SCOPES[scope]:
        pressure=[charge('CONTROL','constructor-pressure-'+str(i),1) for i in range(r.t.COUNTS['CONTROL'])] if name.endswith('-capacity') else []
        rows.extend(row('RESERVE',added=[v]) for v in pressure)
        begin=len(rows)-1
        if name.endswith(('-bind','-expiry')):
            temporary=charge('CONTROL',r.ROLES[scope]+'12345678-1234-1234-1234-123456789abc',32768)
            rows.extend((row('RESERVE',added=[temporary]),row('RELEASE',[temporary])))
        error='java.net.BindException' if name.endswith('-bind') else 'java.io.IOException' if name.endswith('-guard') else 'java.lang.IllegalArgumentException'
        message=('Address already in use' if name.endswith('-bind') else 'resource ownership/count' if pressure else
                 'construction guard rejected' if name.endswith('-guard') else 'original transfer service deadline/closed')
        cases.append(dict(case=name,begin=dict(sequence=begin,usage={}),failed=dict(sequence=len(rows)-1,usage={}),
                          error=error,message=message,beforeFiles=copy.deepcopy(files),afterFiles=copy.deepcopy(files)))
        rows.extend(row('RELEASE',[v]) for v in pressure)
    if scope!='source-service':rows.append(row('RELEASE',[original]))
    data=(trace(rows),dict(schema='gse-v53-construction-rollback-v1',scope=scope,status='PASS',cases=cases,completeMembershipHistory=False))
    n.recount(*data);return data


class ConstructionRollbackTest(unittest.TestCase):
    def test_each_scope_qualifies_rollback_without_promoting_authority_or_service_recovery(self):
        for scope in r.SCOPES:
            data=fixture(scope);before=copy.deepcopy(data);result=r.replay(*data)
            self.assertEqual(before,data);self.assertEqual(len(r.SCOPES[scope]),result['cases'])
            self.assertEqual(1,result['rolledBackReservations']);self.assertTrue(result['failedConstructionRollbackQualified'])
            for flag in ('serviceRecoveryQualified','physicalStorageQualified','wholeRuntimeResourcesQualified','phase3Complete'):
                self.assertFalse(result[flag])

    def test_all_negatives_reject_the_declared_obligation_in_all_scopes(self):
        for scope in r.SCOPES:
            results=n.replay(fixture(scope))
            self.assertEqual([dict(case=name,status='REJECTED',reason=reason) for name,reason in n.NEGATIVES.items()],results)

    def test_failed_original_is_checked_before_any_mutation(self):
        data=fixture();data[1]['status']='FAIL'
        with patch.object(n,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete conditional history'):n.replay(data)
            mutate.assert_not_called()

    def test_releasing_then_reacquiring_original_ownership_is_not_rollback(self):
        data=fixture();n.mutate(data,'original-gap');r.t.replay(data[0])
        capacity=data[1]['cases'][-1];self.assertEqual(capacity['begin']['usage'],capacity['failed']['usage'])
        with self.assertRaisesRegex(ValueError,'continuous original custody'):r.replay(*data)

    def test_removing_a_temporary_reservation_and_its_release_cannot_hide_rollback(self):
        data=fixture();n.mutate(data,'missing-temporary');r.t.replay(data[0])
        self.assertEqual(0,data[0]['current']['leases'])
        with self.assertRaisesRegex(ValueError,'complete temporary acquisitions'):r.replay(*data)

    def test_failure_return_before_release_fails_even_when_later_cleanup_reaches_zero(self):
        data=fixture();n.mutate(data,'early-failure-return');r.t.replay(data[0])
        with self.assertRaisesRegex(ValueError,'rollback before failure return'):r.replay(*data)

    def test_incomplete_or_wrong_scopes_cannot_substitute_for_covered_constructors(self):
        for field,value in (('scope','other'),('scope','source-service'),('schema','gse-v53-pending-drain-v1'),('completeMembershipHistory',True)):
            data=fixture();data[1][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):r.replay(*data)

    def test_boundary_sequences_reject_boolean_negative_out_of_range_and_reordering(self):
        for value in (True,-1,-2,10000):
            data=fixture();data[1]['cases'][0]['begin']['sequence']=value
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'ordered original boundaries'):r.replay(*data)
        data=fixture();data[1]['cases'][1]['begin']=copy.deepcopy(data[1]['cases'][0]['begin'])
        with self.assertRaisesRegex(ValueError,'ordered original boundaries'):r.replay(*data)

    def test_original_files_require_unique_relative_paths_and_hashes(self):
        for path in ('/tmp/original','../original','a//b','a/./b'):
            data=fixture()
            for field in ('beforeFiles','afterFiles'):data[1]['cases'][0][field][0]['path']=path
            with self.subTest(path=path),self.assertRaisesRegex(ValueError,'original file observations'):r.replay(*data)
        data=fixture()
        for field in ('beforeFiles','afterFiles'):data[1]['cases'][0][field]*=2
        with self.assertRaisesRegex(ValueError,'original file observations'):r.replay(*data)

    def test_final_zero_cannot_replace_complete_accounting(self):
        for field in ('failed','truncated'):
            data=fixture();data[0][field]=True
            with self.assertRaisesRegex(ValueError,'incomplete observation'):r.replay(*data)

    def test_portable_replay_leaves_originals_unchanged(self):
        for scope in r.SCOPES:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                for name,value in zip(('resources.json','history.json'),fixture(scope)):
                    (root/name).write_bytes(r.t.collection.snapshot.f.canonical(value))
                before=r.t.collection.inventory(root);result=n.qualify(root)
                self.assertEqual(14,len(result['negatives']));self.assertEqual(before,r.t.collection.inventory(root))

    def test_extra_files_or_noncanonical_records_do_not_qualify(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,value in zip(('resources.json','history.json'),fixture()):
                (root/name).write_bytes(r.t.collection.snapshot.f.canonical(value))
            (root/'extra').write_text('x')
            with self.assertRaisesRegex(ValueError,'exact original inventory'):r.validate(root)
            (root/'extra').unlink();(root/'history.json').write_bytes((root/'history.json').read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'noncanonical JSON'):r.validate(root)


if __name__=='__main__':unittest.main()
