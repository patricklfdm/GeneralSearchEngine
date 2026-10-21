"""Counterexamples and an independent bounded check of V5.3 quorum research."""
from dataclasses import fields, replace
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from . import membership_model as m


class MembershipModelTest(unittest.TestCase):
    def test_stable_configuration_bounds_and_identity(self):
        for invalid in ((), m.NODES[:2], m.NODES, list(m.NODES[:3]),
                        ('node-1', 'node-1', 'node-2'), tuple(reversed(m.NODES[:3])),
                        ('node-1', 'node-2', 'node-7')):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                m.configuration(invalid)
        for size in (3, 4, 5):
            self.assertEqual(size, len(m.configuration(m.NODES[:size])))

    def test_only_one_add_remove_or_replace_is_in_scope(self):
        self.assertEqual('add', m.transition_kind(m.NODES[:3], m.NODES[:4]))
        self.assertEqual('remove', m.transition_kind(m.NODES[:5], m.NODES[:4]))
        self.assertEqual('replace', m.transition_kind(m.NODES[:3], (m.NODES[0], m.NODES[1], m.NODES[3])))
        for old, new in ((m.NODES[:3], m.NODES[:3]), (m.NODES[:3], m.NODES[:5]),
                         (m.NODES[:3], m.NODES[3:])):
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                m.transition_kind(old, new)

    def test_four_voters_require_three_distinct_votes(self):
        expected = m.claim(stage='new')
        self.assertFalse(m.certified(expected, m.receipts(expected, m.NODES[:2])))
        self.assertTrue(m.certified(expected, m.receipts(expected, m.NODES[:3])))

    def test_joint_needs_both_majorities_not_union_or_either_side(self):
        expected = m.claim(m.NODES[:4], m.NODES[:5])
        union_only = frozenset((m.NODES[0], m.NODES[1], m.NODES[4]))
        self.assertTrue(m.majority(frozenset(m.NODES[:5]), union_only))
        self.assertFalse(m.certified(expected, m.receipts(expected, union_only)))
        for votes in (m.NODES[:3], m.NODES[:4], m.NODES[:5]):
            self.assertTrue(m.certified(expected, m.receipts(expected, votes)))

    def test_overlapping_membership_does_not_imply_old_new_quorum_intersection(self):
        before = frozenset(m.NODES[:3])
        after = frozenset((m.NODES[0], m.NODES[1], m.NODES[3]))
        old_votes = frozenset((m.NODES[0], m.NODES[2]))
        new_votes = frozenset((m.NODES[1], m.NODES[3]))
        self.assertTrue(m.majority(before, old_votes))
        self.assertTrue(m.majority(after, new_votes))
        self.assertFalse(old_votes & new_votes)
        self.assertFalse(m.joint(before, after, old_votes))
        self.assertFalse(m.joint(before, after, new_votes))

    def test_shared_voter_counts_for_both_sets_but_duplicate_never_counts_twice(self):
        expected = m.claim(m.NODES[:3], (m.NODES[0], m.NODES[1], m.NODES[3]))
        self.assertTrue(m.certified(expected, m.receipts(expected, m.NODES[:2])))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            m.certified(expected, (m.Receipt(m.NODES[0], expected),) * 3)

    def test_learner_and_removed_voter_cannot_augment_a_stable_quorum(self):
        old = m.claim(stage='old')
        with self.assertRaisesRegex(ValueError, 'ineligible'):
            m.certified(old, m.receipts(old, (m.NODES[0], m.NODES[3])))
        new = m.claim(m.NODES[:3], (m.NODES[0], m.NODES[1], m.NODES[3]), stage='new')
        with self.assertRaisesRegex(ValueError, 'ineligible'):
            m.certified(new, m.receipts(new, m.NODES[:3]))

    def test_every_authority_field_is_bound_to_the_expected_claim(self):
        negatives = m.context_negatives()
        for field in fields(m.Claim):
            self.assertIn('foreign-' + field.name, negatives)
        self.assertEqual(19, len(negatives))
        self.assertIn('one-foreign-receipt', negatives)

    def test_accept_ack_cannot_substitute_for_proof_ack(self):
        accept = m.claim(phase='accept')
        proof = replace(accept, phase='proof')
        self.assertTrue(m.certified(proof, m.receipts(proof, m.NODES[:4])))
        with self.assertRaisesRegex(ValueError, 'context'):
            m.certified(proof, m.receipts(accept, m.NODES[:4]))

    def test_claim_bounds_do_not_accept_bool_or_invalid_ballots(self):
        valid = m.claim()
        for name, value in (('generation', True), ('ballot', 0), ('index', -1),
                            ('generation', 1 << 63), ('stage', 'unknown'), ('phase', 'applied'),
                            ('group', ''), ('history', 'x' * 129), ('incarnation', '\u2603'),
                            ('entry_digest', 'A' * 64), ('proposer', 'node-6')):
            with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                replace(valid, **{name: value}).validate()

    def test_receipts_reject_wrong_types_and_excessive_cardinality(self):
        expected = m.claim()
        for rows in ([], ('node-1',), (object(),), (m.Receipt('node-1', expected),) * 7):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                m.certified(expected, rows)
        self.assertFalse(m.certified(expected, ()))

    def test_full_six_identity_domain_is_exhaustive(self):
        result = m.explore()
        self.assertEqual('PASS', result['status'])
        self.assertFalse(result['productionQualified'])
        counts = result['counts']
        # Independent combinatorics: C(6,3)+C(6,4)+C(6,5)=41.
        # Adds: 20*3+15*2=90; removes reverse those 90 edges.
        # Replacements: 20*3*3+15*4*2+6*5*1=330.
        self.assertEqual(41, counts['configurations'])
        self.assertEqual(510, counts['transitions'])
        self.assertEqual(510, counts['expectedTransitions'])
        self.assertEqual((90, 90, 330), (counts['add'], counts['remove'], counts['replace']))
        self.assertEqual({'direct-switch', 'union-majority', 'either-majority'}, set(result['counterexamples']))
        for key in ('receiptSubsets', 'certificateChecks', 'intersectionChecks'):
            self.assertGreater(counts[key], 0)

    def test_partial_traversal_is_never_accepted(self):
        for limit in (0, 1, 509):
            with self.subTest(limit=limit):
                result = m.explore(limit)
                self.assertEqual('INCOMPLETE', result['status'])
                self.assertEqual(limit, result['counts']['transitions'])
                self.assertFalse(result['productionQualified'])
        for invalid in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                m.explore(invalid)

    def test_independent_construction_detects_either_side_quorum_mutant(self):
        with patch.object(m, 'joint', lambda old, new, votes: m.majority(old, votes) or m.majority(new, votes)):
            with self.assertRaisesRegex(ValueError, 'independent construction'):
                m.explore()

    def test_independent_construction_detects_union_quorum_mutant(self):
        with patch.object(m, 'joint', lambda old, new, votes: m.majority(old | new, votes)):
            with self.assertRaisesRegex(ValueError, 'independent construction'):
                m.explore()

    def test_negative_driver_detects_omitted_context_validation(self):
        def unsafe(expected, rows):
            votes = frozenset(row.voter for row in rows)
            return m.joint(frozenset(expected.old), frozenset(expected.new), votes)
        with patch.object(m, 'certified', unsafe):
            with self.assertRaisesRegex(ValueError, 'negative accepted: foreign-group'):
                m.context_negatives()

    def test_optimized_python_still_rejects_duplicates_and_foreign_context(self):
        command = """
from dataclasses import replace
from scripts.v53 import membership_model as m
c=m.claim(stage='old')
for rows in ((m.Receipt('node-1',c),)*2, m.receipts(replace(c,history='wrong'),c.old)):
    try: m.require_certificate(c,rows)
    except ValueError: continue
    raise SystemExit('unsafe certificate accepted')
"""
        result = subprocess.run([sys.executable, '-O', '-c', command],
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_cli_retains_incomplete_receipt_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)/'evidence'
            command = [sys.executable, '-m', 'scripts.v53.membership_model', '--max-transitions', '0', '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(2, result.returncode, result.stderr)
            original = (output/'receipt.json').read_bytes()
            receipt = json.loads(original)
            self.assertEqual('INCOMPLETE', receipt['status'])
            self.assertIn('files', receipt['source'])
            again = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(0, again.returncode)
            self.assertEqual(original, (output/'receipt.json').read_bytes())


if __name__ == '__main__':
    unittest.main()
