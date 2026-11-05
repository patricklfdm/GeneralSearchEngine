import copy
import unittest
from unittest.mock import patch
from . import probe_export_evidence as r
from . import probe_export_negatives as negatives
from . import direct_export_negatives as direct
from .test_session_export_evidence import fixture as sessions
from .test_resource_transitions import charge
from .test_transport_resource_evidence import recount


def fixture(nested=False,expired=False):
    traces,closes=sessions();rows=traces['node-1']['changes'];before=len(rows)-1
    role='joining-intent' if nested else 'prefix-export';size=65536 if nested else 4096
    parent=role+'-'+'c'*64+'-00000000-0000-0000-0000-000000000002'
    child='prefix-export-'+'d'*64+'-00000000-0000-0000-0000-000000000003'
    def change(event,name,amount):rows.append(dict(event=event,added=[charge('CONTROL',name,amount)] if event=='RESERVE' else [],
                                                removed=[charge('CONTROL',name,amount)] if event=='RELEASE' else []))
    change('RESERVE',parent,size)
    if nested:change('RESERVE',child,4096)
    through=len(rows)-1;markers=closes['node-1']['rows']
    def mark(event,children=()):markers.append(dict(event='PROBE_BORROW_'+event,owner=parent,children=list(children),resourceSequence=len(rows)-1))
    mark('ACQUIRED',[child] if nested else [])
    if expired:change('RELEASE',child if nested else parent,4096)
    mark('CLOSE_BEGIN')
    if nested and not expired:change('RELEASE',child,4096)
    if nested or not expired:change('RELEASE',parent,size)
    mark('RETURNED');after=len(rows)-1
    traces['node-1']=recount(rows);direct.renumber(closes['node-1'])
    plan=dict(node='node-1',role=role,binding='c'*64,bytes=size,children=[dict(role='prefix-export',binding='d'*64,bytes=4096)] if nested else [],
              before=before,through=through,after=after)
    return traces,closes,[plan]


class ProbeExportEvidenceTest(unittest.TestCase):
    def test_single_and_nested_probe_ownership_survive_revocation_without_new_handles(self):
        for nested in (False,True):
            for expired in (False,True):
                result=r.replay(*fixture(nested,expired));self.assertEqual('PASS',result['status'])
                self.assertEqual(2 if nested else 1,result['ownedAllocations']);self.assertEqual(int(expired),result['revokedBeforeCleanup'])
                self.assertFalse(result['nativeProbeContentQualified']);self.assertFalse(result['phase3Complete'])

    def test_exact_negatives_leave_every_original_unchanged(self):
        for nested in (False,True):
            for expired in (False,True):
                data=fixture(nested,expired);before=copy.deepcopy(data);result=negatives.replay(*data)
                self.assertEqual(14 if nested else 12,len(result['negatives']));self.assertEqual(before,data)

    def test_global_inventory_keeps_probe_separate_from_session_and_rollback(self):
        data=fixture(True);result=r.exports.replay(*data[:2]);self.assertEqual('PASS',result['status'])
        self.assertEqual((1,2,0,0),(result['sessionOwnedAllocations'],result['probeOwnedAllocations'],result['rollbackOwnedAllocations'],result['directOwnedAllocations']))

    def test_unobserved_probe_remains_unclaimed_instead_of_becoming_a_session(self):
        data=fixture(True);negatives.mutate(*data,'unobserved-probe');result=r.exports.inspect(*data[:2])
        self.assertEqual('PARTIAL',result['status']);self.assertEqual(2,len(result['unattachedExports']))
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'):r.exports.replay(*data[:2])

    def test_no_return_stays_incomplete_even_at_zero_usage(self):
        data=fixture();negatives.mutate(*data,'missing-return');self.assertEqual(0,data[0]['node-1']['current']['leases'])
        with self.assertRaisesRegex(ValueError,'incomplete probe cleanup'):r.replay(*data)

    def test_invalid_original_cannot_count_as_successful_mutations(self):
        data=fixture();data[1]['node-1']['failed']=True
        with patch.object(negatives,'mutate') as mutate:
            with self.assertRaisesRegex(ValueError,'complete bounded recorder'):negatives.replay(*data)
            mutate.assert_not_called()

    def test_child_binding_and_extent_come_from_independent_original_expectation(self):
        data=fixture(True);data[2][0]['children'][0]['binding']='f'*64
        with self.assertRaisesRegex(ValueError,'original child binding'):r.replay(*data)
        data=fixture(True);data[2][0]['children'][0]['bytes']=1024
        with self.assertRaisesRegex(ValueError,'original content expectation'):r.replay(*data)

    def test_only_the_two_actual_probe_groups_are_admitted(self):
        for field,value in (('role','record-export'),('children',None),('node',None),('binding',False),('bytes',True)):
            data=fixture();data[2][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):r.replay(*data)

    def test_complete_probe_inventory_and_unique_expectations_are_required(self):
        for mode in ('missing','duplicate','foreign'):
            data=fixture()
            if mode=='missing':data[2].clear()
            elif mode=='duplicate':data[2].append(copy.deepcopy(data[2][0]))
            else:data[2][0]['binding']='f'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):r.replay(*data)

    def test_probe_markers_require_explicit_export_observation_policy(self):
        data=fixture()
        with self.assertRaisesRegex(ValueError,'original export attachment|exact ordered row'):r.close.replay(*data[:2])

    def test_a_late_body_point_cannot_prove_live_ownership(self):
        data=fixture();data[2][0]['through']=data[2][0]['after']
        with self.assertRaisesRegex(ValueError,'original operation boundaries'):r.replay(*data)
