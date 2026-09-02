package io.github.patricklfdm.generalsearch.durability;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class V40DurableHistoryOracleTest {
    @Test
    void committedHistoryReplaysCanonicalSlotsSequenceAndIndexes() {
        V40DurableHistoryOracle oracle = new V40DurableHistoryOracle();
        List<V40DurableHistoryOracle.CommittedUnit> history = new ArrayList<>();
        history.add(oracle.commit(new V40DurableHistoryOracle.BulkUnit(List.of(
                V40DurableHistoryOracle.Mutation.add(document(7, "first")),
                V40DurableHistoryOracle.Mutation.add(document(2, "second"))
        ))));
        history.add(oracle.commit(new V40DurableHistoryOracle.MutationUnit(
                V40DurableHistoryOracle.Mutation.update(document(7, "updated")))));
        history.add(oracle.commit(new V40DurableHistoryOracle.MutationUnit(
                V40DurableHistoryOracle.Mutation.remove(99))));
        history.add(oracle.commit(new V40DurableHistoryOracle.IndexUnit(
                true, "text:body:simple-v1")));
        history.add(oracle.commit(new V40DurableHistoryOracle.MutationUnit(
                V40DurableHistoryOracle.Mutation.remove(2))));

        V40DurableHistoryOracle.State expected = oracle.state();
        assertEquals(expected, V40DurableHistoryOracle.recover(history));
        assertEquals(5L, expected.sequence());
        assertEquals(2, expected.nextDocId());
        assertEquals(List.of(0), expected.slots().stream()
                .map(V40DurableHistoryOracle.Slot::internalId).toList());
        assertEquals(List.of(7), expected.slots().stream()
                .map(slot -> slot.document().id()).toList());
    }

    @Test
    void rejectedCandidateConsumesNoSequenceAndBulkIsAtomic() {
        V40DurableHistoryOracle oracle = new V40DurableHistoryOracle();
        oracle.commit(new V40DurableHistoryOracle.MutationUnit(
                V40DurableHistoryOracle.Mutation.add(document(1, "one"))));
        V40DurableHistoryOracle.State before = oracle.state();

        assertThrows(IllegalArgumentException.class, () -> oracle.commit(
                new V40DurableHistoryOracle.BulkUnit(List.of(
                        V40DurableHistoryOracle.Mutation.update(document(1, "changed")),
                        V40DurableHistoryOracle.Mutation.remove(1)
                ))));

        assertEquals(before, oracle.state());
    }

    @Test
    void recoveryRejectsSequenceGap() {
        assertThrows(IllegalArgumentException.class, () ->
                V40DurableHistoryOracle.recover(List.of(
                        new V40DurableHistoryOracle.CommittedUnit(
                                2,
                                new V40DurableHistoryOracle.MutationUnit(
                                        V40DurableHistoryOracle.Mutation.add(
                                                document(1, "one"))))
                )));
    }

    private static V40DurableHistoryOracle.Document document(int id, String body) {
        return new V40DurableHistoryOracle.Document(id, body);
    }
}
