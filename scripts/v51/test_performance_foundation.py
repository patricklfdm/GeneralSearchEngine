"""Adversarial semantics/encoding fixtures; these do not replace runtime gates."""
import copy
import struct
import tempfile
import unittest
from pathlib import Path
from . import performance_model as m, performance_plan as p, performance_projection as projection
from . import performance_fixtures as fixture, performance_semantics as semantics
from . import format_encoder as enc, format_inspector as fmt


class PerformancePlanTest(unittest.TestCase):
    def test_frozen_arithmetic_and_independent_corpus(self):
        report = p.validate(p.load())
        self.assertEqual((report['calls'], report['mutations'], report['reads']), (90, 72, 18))
        self.assertEqual((report['corpusDocumentBytes'], report['corpusBytes']), (3149, 3405))
        self.assertEqual((report['maximumDocumentBytes'], report['maximumPayloadBytes']), (58, 285))
        self.assertEqual(report['logicalSlotBounds'], dict(healthy=162, failover=90))
        self.assertEqual(report['finalSequence'], 76)
        self.assertEqual(report['peakDocuments'], 68)

    def test_plan_rejects_drift_even_if_self_declared_hash_is_recomputed(self):
        original = p.load()
        for section, field, value in [('localSmoke', 'seed', 18), ('localSmoke', 'firstCycle', 1),
                ('localSmoke', 'warmupCycles', True), ('localSmoke', 'clientConcurrency', 2),
                ('localSmoke', 'cyclesPerWindow', 2.0), ('budgets', 'wholeSeconds', 901),
                ('budgets', 'auxiliaryBarriersPerGroup', 9), ('replicationBounds', 'maxPendingClientOperations', 16),
                ('automaticPolicy', 'applyTo', 'delayed-third-voter'), ('evidenceBounds', 'files', 4001)]:
            with self.subTest(section=section, field=field):
                changed = copy.deepcopy(original)
                changed[section][field] = value
                with self.assertRaisesRegex(ValueError, 'unreviewed'):
                    p.validate(changed)
        for field, value in [('execution', 'gcp-owned-runtime'), ('evidenceSchema', 'gse-v50-performance-evidence-v1'),
                             ('extra', m.sha(m.canonical(original)))]:
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'unreviewed'):
                p.validate(dict(original, **{field: value}))

    def test_strict_json_and_bounded_regular_plan(self):
        for raw in (b'{"seed":17,"seed":18}', b'{"value":NaN}'):
            with self.assertRaises(ValueError):
                m.strict_json(raw)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            large = root / 'large.json'
            large.write_bytes(b' ' * 65537)
            link = root / 'link.json'
            link.symlink_to(p.PLAN)
            for path in (large, link, root / 'absent'):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'file/bound'):
                    p.load(path)


class RichModelTest(unittest.TestCase):
    def setUp(self):
        self.plan = p.load()
        self.program = list(m.program(self.plan))

    def test_all_ten_operations_and_abba_never_reset_cycles(self):
        rows = m.expected(self.plan)['rows']
        self.assertEqual([row['operation'] for row in rows[:10]], list(m.OPERATIONS))
        self.assertEqual([row['cycle'] for row in rows[::10]], list(range(9)))
        self.assertEqual([row['window'] for row in rows[::10]],
                         ['warmup', 'baseline-a', 'baseline-a', 'instrumented-a', 'instrumented-a',
                          'instrumented-b', 'instrumented-b', 'baseline-b', 'baseline-b'])
        self.assertEqual([r['afterSequence'] for r in rows[:10]], [5, 6, 7, 8, 9, 10, 11, 12, 12, 12])
        self.assertEqual([r['documentCount'] for r in rows[:10]], [65, 65, 64, 68, 68, 64, 64, 64, 64, 64])

    def test_initial_codec_and_index_order(self):
        state = m.initial(self.plan)
        self.assertEqual(m.application(state.application(), 4).application(), state.application())
        self.assertEqual(list(state.documents), list(range(1, 65)))
        self.assertEqual([d['field'] for d in state.indexes], ['body', 'category', 'price', 'title'])
        self.assertEqual(state.documents[1], (1, 'Java 1', 'news', 34, 'java search memory revision 0'))

    def test_noop_never_changes_sequence_or_application(self):
        state = m.initial(self.plan)
        before = state.application()
        for _ in range(64):
            state.apply(9, b'')
        self.assertEqual(state.sequence, 4)
        self.assertEqual(state.application(), before)
        for op, payload in ((9, b'\0'), (10, b''), (True, self.program[0]['payload'])):
            with self.assertRaises(ValueError):
                state.apply(op, payload)

    def test_queries_and_get_use_ordered_revised_values(self):
        state = m.initial(self.plan)
        for call in self.program[:8]:
            state.apply(m.OP_IDS[call['operation']], call['payload'])
        self.assertEqual(state.answer('GET', 0), 'Doc[id=1, title=Java 1, category=guide, price=35, body=java search memory revision 1]')
        self.assertEqual(state.answer('QUERY', 0)[:5], [1, 2, 4, 5, 6])
        # Reverse insertion order remains observable, even though the same IDs exist.
        state.documents = dict(reversed(list(state.documents.items())))
        self.assertEqual(state.answer('QUERY', 0)[-5:], [6, 5, 4, 2, 1])

    def test_bulk_validation_is_atomic(self):
        state = m.initial(self.plan)
        before = state.application()
        payload = b'\x00\x01' + struct.pack('>i', 2)
        for key in (100000, 1):
            payload += m.blob(struct.pack('>i', key)) + m.blob(m.encode_document(m.document(key, 1)))
        with self.assertRaisesRegex(ValueError, 'precondition'):
            state.apply(4, payload)
        self.assertEqual(state.application(), before)
        self.assertEqual(state.sequence, 4)

    def test_malformed_payloads_and_documents_fail_closed(self):
        payload = self.program[0]['payload']
        variants = [b'', payload[:-1], payload + b'\0', b'\x00\x02' + payload[2:],
                    payload[:2] + struct.pack('>i', -1) + payload[6:],
                    payload[:2] + struct.pack('>i', 17) + payload[6:],
                    payload[:6] + struct.pack('>i', 3) + payload[10:], b'0' * 2049]
        for value in variants:
            with self.subTest(payload=value[:12]), self.assertRaises(ValueError):
                m.decode_command(1, value)
        for value in (b'01\nJava 1\nguide\n35\njava', b'1\nJava 1\nguide\n35\njava\n', b'\xff', b'a' * 257):
            with self.subTest(document=value[:12]), self.assertRaises(ValueError):
                m.decode_document(value)

    def test_duplicate_mutation_keys_and_wrong_key_document_rejected(self):
        doc = m.encode_document(m.document(100000, 1))
        item = m.blob(struct.pack('>i', 100000)) + m.blob(doc)
        for payload in (b'\x00\x01' + struct.pack('>i', 2) + item * 2,
                        b'\x00\x01' + struct.pack('>i', 1) + m.blob(struct.pack('>i', 5)) + m.blob(doc)):
            with self.assertRaises(ValueError):
                m.decode_command(4, payload)

    def test_application_decoder_rejects_unsorted_duplicate_and_unsafe_lengths(self):
        state = m.initial(self.plan)
        raw = state.application()
        variants = [raw[:-1], raw + b'\0', raw[:2] + struct.pack('>i', 5) + raw[6:]]
        for indexes in ([*m.INDEXES[::-1]], [m.INDEXES[0], m.INDEXES[0]]):
            variants.append(b'\x00\x01' + struct.pack('>i', len(indexes)) +
                            b''.join(m.blob(m.canonical(v)) for v in indexes) + struct.pack('>i', 0))
        for value in variants:
            with self.assertRaises(ValueError):
                m.application(value, 4)
        for sequence in (-1, True, 1 << 63):
            with self.assertRaises(ValueError):
                m.application(raw, sequence)

    def test_index_definitions_are_not_just_counts(self):
        for definition in [dict(m.INDEXES[1], kind='range'), dict(m.INDEXES[0], analyzer='wrong'), {'field': 'category'}]:
            payload = b'\x00\x01' + m.blob(m.canonical(definition))
            with self.assertRaisesRegex(ValueError, 'index'):
                m.decode_command(7, payload)


class RichProjectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = p.load()
        cls.fixture = fixture.generate(cls.plan)
        cls.projected = projection.project(cls.fixture['manifest'], cls.fixture['genesis'], cls.fixture['votes'])

    def project(self, votes):
        return projection.project(self.fixture['manifest'], self.fixture['genesis'], votes)

    def test_actual_frame_decoding_with_read_noops_and_complete_snapshot_sequence(self):
        self.assertEqual(len(self.projected['chosen']), 91)
        self.assertEqual(self.projected['states'][1].sequence, 4)
        for raw in self.fixture['snapshots']:
            projection.snapshot(self.projected, raw)
        final = self.projected['states'][91]
        self.assertEqual(final.sequence, 76)
        self.assertEqual(final.application(), m.expected(self.plan)['state'].application())
        report = fixture.encoding_report(self.plan, self.fixture)
        self.assertFalse(report['runtimeRetentionAdmitted'])
        self.assertLessEqual(max(report['recordPeaks'].values()), 16 << 10)

    def test_repeated_observation_cannot_form_another_quorum_voter(self):
        votes = {node: [] for node in self.fixture['votes']}
        votes['node-1'] = self.fixture['votes']['node-1'] * 3
        with self.assertRaisesRegex(ValueError, 'incomplete rich chosen prefix'):
            self.project(votes)

    def test_duplicate_observations_and_reproposals_keep_logical_slot_count(self):
        votes = copy.deepcopy(self.fixture['votes'])
        for node, records in votes.items():
            # A later legal ranked node-1 ballot re-proposes the exact same values.
            records.extend(enc.encode('ACCEPT', dict(fmt.inspect(raw, 'ACCEPT'), epoch=5)) for raw in list(records))
            records.extend(list(records))
        value = self.project(votes)
        self.assertEqual(len(value['chosen']), 91)
        self.assertEqual(value['states'][91].sequence, 76)
        self.assertEqual(value['observations'], 4 * 3 * 91)

    def test_votes_from_different_ballots_do_not_combine(self):
        votes = copy.deepcopy(self.fixture['votes'])
        votes['node-2'] = [enc.encode('ACCEPT', dict(fmt.inspect(raw, 'ACCEPT'), epoch=5)) for raw in votes['node-2']]
        votes['node-3'] = []
        with self.assertRaisesRegex(ValueError, 'incomplete rich chosen prefix'):
            self.project(votes)

    def test_chosen_hole_and_wrong_predecessor_fail(self):
        votes = copy.deepcopy(self.fixture['votes'])
        for rows in votes.values():
            rows.pop(3)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.project(votes)
        for node, rows in votes.items():
            rows[:] = self.fixture['votes'][node]
            vote = fmt.inspect(rows[3], 'ACCEPT')
            entry = fmt.inspect(projection.raw(vote['entry']), 'ENTRY')
            entry['previousDigest'] = 'ab' * 32
            data = enc.encode('ENTRY', entry)
            rows[3] = enc.encode('ACCEPT', dict(vote, entry=fixture.b64(data), entryDigest=data[16:48].hex()))
        with self.assertRaisesRegex(ValueError, 'predecessor'):
            self.project(votes)

    def test_resealed_conflicting_chosen_value_rejected(self):
        votes = copy.deepcopy(self.fixture['votes'])
        entry = fmt.inspect(self.fixture['entries'][0], 'ENTRY')
        data = enc.encode('ENTRY', dict(entry, originEpoch=5))
        original = fmt.inspect(votes['node-1'][0], 'ACCEPT')
        changed = enc.encode('ACCEPT', dict(original, epoch=5, entry=fixture.b64(data), entryDigest=data[16:48].hex()))
        for node in ('node-1', 'node-2'):
            votes[node].append(changed)
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            self.project(votes)

    def test_resealed_snapshot_wrong_state_order_and_sequence_rejected(self):
        original = fmt.inspect(self.fixture['snapshots'][-1], 'SNAPSHOT')
        state = self.projected['states'][91].copy()
        state.documents = dict(reversed(list(state.documents.items())))
        variants = [dict(original, application=fixture.b64(state.application())),
                    dict(original, applicationSequence=77), dict(original, baseSequence=3, applicationSequence=75)]
        for changed in variants:
            with self.subTest(sequence=changed['applicationSequence']), self.assertRaises(ValueError):
                projection.snapshot(self.projected, enc.encode('SNAPSHOT', changed))

    def test_proof_requires_exact_observed_votes_and_predecessor(self):
        original = fmt.inspect(self.fixture['snapshots'][-1], 'SNAPSHOT')
        proof = fmt.inspect(projection.raw(original['terminalProof']), 'PROOF')
        no_third = self.project(dict(self.fixture['votes'], **{'node-3': []}))
        receipt = dict(voter='node-3', digest=fixture.fixtures.fixture_receipt('ACCEPT_ACK', proof['manifestDigest'], 'node-3',
                      proof['epoch'], proof['proposer'], proof['incarnation'], proof['index'], proof['entryDigest']))
        changed = dict(proof, receipts=[proof['receipts'][0], receipt])
        for value in (changed, dict(proof, previousDigest='ab' * 32)):
            raw = enc.encode('SNAPSHOT', dict(original, terminalProof=fixture.b64(enc.encode('PROOF', value))))
            with self.assertRaises(ValueError):
                projection.snapshot(no_third, raw)

    def test_wrong_mode_and_genesis_rejected(self):
        changed = bytearray(self.fixture['manifest'])
        changed[6:8] = b'\x00\x01'
        with self.assertRaises(ValueError):
            projection.project(bytes(changed), self.fixture['genesis'], self.fixture['votes'])
        genesis = fmt.inspect(self.fixture['genesis'], 'GENESIS')
        with self.assertRaisesRegex(ValueError, 'binding'):
            projection.project(self.fixture['manifest'], enc.encode('GENESIS', dict(genesis, baseSequence=5)), self.fixture['votes'])

    def test_lower_slot_ceiling_cannot_be_overridden_by_summary(self):
        with self.assertRaisesRegex(ValueError, 'slot bound'):
            projection.project(self.fixture['manifest'], self.fixture['genesis'], self.fixture['votes'], maximum_slots=90)
        with self.assertRaisesRegex(ValueError, 'slot bound'):
            projection.project(self.fixture['manifest'], self.fixture['genesis'], self.fixture['votes'], maximum_slots=193)


class RichObservationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = p.load()
        expected = m.expected(cls.plan)['rows']
        state = m.initial(cls.plan)
        cls.rows = []
        for wanted, call in zip(expected, m.program(cls.plan)):
            if call['operation'] in m.OP_IDS:
                state.apply(m.OP_IDS[call['operation']], call['payload'])
            row = {k: v for k, v in wanted.items() if k not in ('applicationSha256', 'indexCount', 'documentCount')}
            row.update(outcome='SUCCESS', state=dict(sequence=state.sequence, indexCount=len(state.indexes),
                                                  documents=[list(v) for v in state.documents.values()]))
            cls.rows.append(row)

    def test_complete_observed_tape_and_resealed_semantic_negatives(self):
        from .performance_foundation import negatives
        state = semantics.validate_calls(self.rows, self.plan)
        self.assertEqual(state.sequence, 76)
        self.assertEqual(len(negatives(self.rows, self.plan)), 8)

    def test_fabricated_or_missing_state_and_float_sequence_rejected(self):
        for change in ('state', 'extra', 'float', 'payload', 'metadata'):
            rows = copy.deepcopy(self.rows)
            if change == 'state': rows[0].pop('state')
            elif change == 'extra': rows[0]['admitted'] = True
            elif change == 'float': rows[0]['afterSequence'] = 5.0
            elif change == 'payload': rows[0]['payloadSha256'] = 'ab' * 32
            else: rows[0]['state']['indexCount'] = 3
            with self.subTest(change=change), self.assertRaises(ValueError):
                semantics.validate_calls(rows, self.plan)

    def test_unsupported_rich_documents_cannot_use_an_approximate_query_model(self):
        for doc in [(1, 'Java 1', 'guide', 34, 'java-search'), (1, 'Java 1', 'news', 34, 'java search memory revision 10'),
                    (1, 'Java 1', 'guide', 34, 'java search memory revision 0')]:
            with self.assertRaisesRegex(ValueError, 'frozen'):
                m.decode_document(m.encode_document(doc))


if __name__ == '__main__':
    unittest.main()
