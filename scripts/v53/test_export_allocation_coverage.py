"""Complete original-reader composition, not a sum of green receipt counts."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from . import export_allocation_coverage as coverage
from . import session_content_extents as session
from . import direct_export_evidence as direct
from . import probe_export_evidence as probe
from . import native_resource_evidence as native
from . import native_control_closes as cleanup
from .test_session_content_extents import fixture as session_fixture
from .test_resource_transitions import charge
from .test_transport_resource_evidence import recount
from .direct_export_negatives import renumber


def fixture(role='record-export', nested_probe=False):
    traces, closes, initials, expected = session_fixture(role)
    rows = traces['node-1']['changes']; markers = closes['node-1']['rows']

    def change(event, name, size):
        value = charge('CONTROL', name, size)
        rows.append(dict(event=event, added=[value] if event == 'RESERVE' else [], removed=[value] if event == 'RELEASE' else []))

    def mark(name, event, children=()):
        markers.append(dict(owner=name, event=event, children=list(children), resourceSequence=len(rows)-1))

    direct_name = 'source-export-'+'c'*64+'-00000000-0000-0000-0000-000000000002'
    direct_plan = dict(node='node-1', phase='ACTIVATION', reference='c'*64, bytes=1024, after=len(rows)-1)
    change('RESERVE', direct_name, 1024); mark(direct_name, 'ACTIVATION_BORROW_ACQUIRED')
    change('RESERVE', 'test-body', 1); direct_plan['through'] = len(rows)-1
    change('RELEASE', 'test-body', 1); mark(direct_name, 'ACTIVATION_BORROW_CLOSE_BEGIN')
    change('RELEASE', direct_name, 1024); mark(direct_name, 'ACTIVATION_BORROW_RETURNED')
    probe_role = 'joining-intent' if nested_probe else 'prefix-export'; size = 65536 if nested_probe else 4096
    probe_name = probe_role+'-'+'d'*64+'-00000000-0000-0000-0000-000000000003'
    child = 'prefix-export-'+'e'*64+'-00000000-0000-0000-0000-000000000004'
    probe_plan = dict(node='node-1', role=probe_role, binding='d'*64, bytes=size, before=len(rows)-1,
                      children=[dict(role='prefix-export', binding='e'*64, bytes=4096)] if nested_probe else [])
    change('RESERVE', probe_name, size)
    if nested_probe: change('RESERVE', child, 4096)
    probe_plan['through'] = len(rows)-1; mark(probe_name, 'PROBE_BORROW_ACQUIRED', [child] if nested_probe else [])
    mark(probe_name, 'PROBE_BORROW_CLOSE_BEGIN')
    if nested_probe: change('RELEASE', child, 4096)
    change('RELEASE', probe_name, size); mark(probe_name, 'PROBE_BORROW_RETURNED'); probe_plan['after'] = len(rows)-1
    traces['node-1'] = recount(rows); renumber(closes['node-1'])
    return traces, closes, initials, expected, [direct_plan], [probe_plan]


def bind(data):
    traces, closes, initials, expected, direct_plan, probe_plan = data; bindings = {}
    session.bind(traces, closes, initials, expected, bindings=bindings)
    direct.replay(traces, closes, direct_plan, bindings=bindings)
    probe.replay(traces, closes, probe_plan, bindings=bindings)
    return bindings


class ExportAllocationCoverageTest(unittest.TestCase):
    def test_complete_three_scopes_and_nested_groups_share_one_exact_inventory(self):
        for role in session.exports.ROLES:
            for nested in (False, True):
                data = fixture(role, nested); before = copy.deepcopy(data); bindings = bind(data)
                result = coverage.replay(*data[:2], bindings)
                with self.subTest(role=role, nested=nested):
                    self.assertEqual('PASS', result['status']); self.assertTrue(result['allObservedExportAllocationsQualified'])
                    self.assertEqual(len(bindings), result['allocations']); self.assertEqual(1, result['byScope']['direct'])
                    self.assertEqual(2 if nested else 1, result['byScope']['probe'])
                    self.assertFalse(result['allExportFailurePathsQualified']); self.assertFalse(result['phase3Complete'])
                    self.assertFalse(result['wholeRuntimeResourcesQualified']); self.assertEqual(before, data)

    def test_equal_counts_cannot_replace_exact_allocation_keys(self):
        data = fixture(); bindings = bind(data); key = next(iter(bindings)); value = bindings.pop(key)
        name = value['owner'][:-1]+'9'; bindings[key[0], name] = dict(value, owner=name)
        with self.assertRaisesRegex(ValueError, 'complete original allocation set'): coverage.replay(*data[:2], bindings)

    def test_missing_scope_is_not_filled_from_final_zero_usage(self):
        data = fixture(); bindings = bind(data)
        self.assertEqual(0, data[0]['node-1']['current']['leases'])
        for scope in coverage.SCOPES:
            subset = {k:v for k,v in bindings.items() if v['scope'] != scope}
            with self.subTest(scope=scope), self.assertRaisesRegex(ValueError, 'complete original allocation set'):
                coverage.replay(*data[:2], subset)

    def test_proof_cannot_reassign_scope_identity_size_or_lifetime(self):
        data = fixture(); original = bind(data)
        mutations = (('scope','probe','ownership scope'),('role','vote-export','content identity'),
                     ('binding','f'*64,'content identity'),('bytes',4097,'extent and lifetime'),
                     ('start',1,'extent and lifetime'),('end',900,'extent and lifetime'))
        for field, value, reason in mutations:
            bindings = copy.deepcopy(original); key = next(k for k,v in bindings.items() if v['scope']=='session')
            bindings[key][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, reason): coverage.replay(*data[:2], bindings)

    def test_cross_node_duplicate_nonce_is_not_the_same_allocation(self):
        data = fixture(); bindings = bind(data); key = next(iter(bindings)); value = bindings.pop(key)
        bindings['node-2', key[1]] = dict(value, node='node-2')
        with self.assertRaisesRegex(ValueError, 'complete original allocation set'): coverage.replay(*data[:2], bindings)

    def test_duplicate_publication_and_conflicting_scope_are_atomic_failures(self):
        data = fixture(); bindings = bind(data); before = copy.deepcopy(bindings)
        existing = next(iter(bindings.values())); fresh = dict(existing, owner=existing['owner'][:-1]+'9')
        for batch in ([fresh, existing], [fresh, fresh]):
            with self.subTest(batch=batch), self.assertRaisesRegex(ValueError, 'duplicate allocation proof'):
                coverage.publish(bindings, batch)
            self.assertEqual(before, bindings)

    def test_each_reader_publishes_only_after_complete_original_validation(self):
        for scope in coverage.SCOPES:
            data = fixture('joining-intent', True); traces, closes, initials, expected, dp, pp = data
            bindings = {('untouched','entry'): {'retained': True}}; before = copy.deepcopy(bindings)
            if scope == 'session':
                next(iter(expected.values()))['charges'][-1]['bytes'] += 1
                call = lambda: session.bind(traces,closes,initials,expected,bindings=bindings)
            elif scope == 'direct':
                dp.append(dict(dp[0],reference='f'*64))
                call = lambda: direct.replay(traces,closes,dp,bindings=bindings)
            else:
                pp[0]['children'][0]['binding'] = 'f'*64
                call = lambda: probe.replay(traces,closes,pp,bindings=bindings)
            with self.subTest(scope=scope), self.assertRaises(ValueError): call()
            self.assertEqual(before, bindings)

    def test_invalid_or_unclaimed_original_precedes_proof_inventory(self):
        from . import session_export_negatives
        data = fixture(); bindings = bind(data); data[1]['node-1']['failed'] = True
        with self.assertRaisesRegex(ValueError,'complete bounded recorder'): coverage.replay(*data[:2], bindings)
        data = fixture(); bindings = bind(data); session_export_negatives.mutate(*data[:2], 'unclaimed-export')
        with self.assertRaisesRegex(ValueError,'unclaimed allocation'): coverage.replay(*data[:2], bindings)

    def test_digest_is_stable_across_binding_map_order(self):
        data = fixture('learner-root-export', True); bindings = bind(data)
        first = coverage.replay(*data[:2], bindings); second = coverage.replay(*data[:2], dict(reversed(list(bindings.items()))))
        self.assertEqual(first['allocationBindingsSha256'], second['allocationBindingsSha256'])

    def test_rollback_handles_cannot_be_laundered_as_validated_probes(self):
        from .test_export_rollback_evidence import fixture as rollback
        data = rollback(); account = coverage.exports.close.replay(*data[:2],export_ownership=True); forged = {}
        # Simulate a caller trying to substitute observed labels and sizes for
        # independent content authority. Even a complete count is insufficient.
        for node, owner in account['owners'].items():
            attached = {n for v in owner['exportAttachments'].values() for n in v['children']}
            for name, life in owner['lifetimes'].items():
                role = coverage.exports.kind(name)
                if role is None: continue
                value = next(v for v in data[0][node]['changes'][life['start']]['added'] if v['owner']==name)
                coverage.publish(forged,[coverage.proof(node,name,'session' if name in attached else 'probe',
                                 role,name[len(role)+1:len(role)+65],value['bytes'],life)])
        with self.assertRaisesRegex(ValueError,'original ownership scope'): coverage.replay(*data[:2],forged)

    def test_complete_exports_do_not_claim_non_export_control_coverage(self):
        data = fixture(); bindings = bind(data); result = coverage.replay(*data[:2],bindings)
        self.assertGreater(result['otherControlAllocations'],0)
        self.assertFalse(result['wholeRuntimeResourcesQualified'])

    def test_malformed_binding_types_are_validation_errors(self):
        data = fixture(); original = bind(data)
        for field, value in (('bytes',True),('start',True),('end',None),('role',[]),('binding',None),('scope','rollback'),('node',None)):
            bindings = copy.deepcopy(original); next(iter(bindings.values()))[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError,'exact content binding'): coverage.replay(*data[:2],bindings)

    def test_strict_native_option_enables_required_original_readers_before_any_proof(self):
        for profile in ('stable','5-REPLACE','unknown'):
            with self.assertRaisesRegex(ValueError,'complete export policy'): native.validate('/unused',profile,complete_exports=True)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'control-close-captures').mkdir()
            with patch.object(native.publication,'validate',side_effect=ValueError('bad physical original')) as physical, \
                 patch.object(coverage,'replay') as completed:
                with self.assertRaisesRegex(ValueError,'bad physical original'):
                    native.validate(tmp,'5-REPLACE-required-four',complete_exports=True)
            self.assertTrue(physical.call_args.kwargs['control_closes']); completed.assert_not_called()

    def test_cleanup_binding_requires_content_derivation_and_original_source(self):
        with self.assertRaisesRegex(ValueError,'allocation binding policy'):
            cleanup.replay([],[],{},[],{},'root',{},bindings={})
        bindings = {}
        with patch.object(cleanup.source,'replay',side_effect=ValueError('bad source')),patch.object(session,'bind') as bind_session:
            with self.assertRaisesRegex(ValueError,'bad source'):
                cleanup.replay([],[],{},[],{},'root',{},export_ownership=True,session_extents={'pending':1},bindings=bindings)
        bind_session.assert_not_called(); self.assertEqual({},bindings)


if __name__ == '__main__': unittest.main()
