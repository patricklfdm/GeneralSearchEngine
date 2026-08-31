package io.github.patricklfdm.generalsearch.search;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.OptionalLong;
import java.util.Set;
import org.junit.jupiter.api.Test;

class V33Phase1FixtureTest {
    private static final List<V33TestReference.Candidate> CANDIDATES = List.of(
            candidate(8, 2.0, true, true),
            candidate(2, 5.0, true, true),
            candidate(7, 3.0, false, true),
            candidate(0, 5.0, true, true),
            candidate(5, 3.0, true, false),
            candidate(4, 4.0, true, true),
            candidate(1, 5.0, true, true),
            candidate(9, 1.0, true, true)
    );

    @Test
    void denseTiePageWalkHasNoGapDuplicateOrReordering() {
        List<V33TestReference.Candidate> expected = List.of(
                candidate(0, 5.0, true, true),
                candidate(1, 5.0, true, true),
                candidate(2, 5.0, true, true),
                candidate(4, 4.0, true, true),
                candidate(8, 2.0, true, true),
                candidate(9, 1.0, true, true)
        );

        assertEquals(expected, V33TestReference.walk(CANDIDATES, 2, false));
        assertEquals(expected, V33TestReference.walk(CANDIDATES, 4, false));
        assertEquals(expected, V33TestReference.walk(CANDIDATES, 20, false));
    }

    @Test
    void exactTotalIsComputedBeforeCursorAndLimitOnEveryPage() {
        V33TestReference.Page first = V33TestReference.page(
                CANDIDATES,
                2,
                null,
                true
        );
        V33TestReference.Page second = V33TestReference.page(
                CANDIDATES,
                2,
                first.nextCursor().orElseThrow(),
                true
        );
        V33TestReference.Page finalPage = V33TestReference.page(
                CANDIDATES,
                2,
                second.nextCursor().orElseThrow(),
                true
        );

        assertEquals(OptionalLong.of(6L), first.totalHits());
        assertEquals(first.totalHits(), second.totalHits());
        assertEquals(first.totalHits(), finalPage.totalHits());
        assertEquals(List.of(8, 9), finalPage.hits().stream()
                .map(V33TestReference.Candidate::documentId)
                .toList());
        assertTrue(finalPage.nextCursor().isEmpty());

        V33TestReference.Page disabled = V33TestReference.page(
                CANDIDATES,
                2,
                null,
                false
        );
        assertTrue(disabled.totalHits().isEmpty());
        assertEquals(first.hits(), disabled.hits());
    }

    @Test
    void cursorReasonPrecedenceIsFrozen() {
        V33TestReference.ReferenceEngine first =
                new V33TestReference.ReferenceEngine();
        V33TestReference.ReferenceEngine second =
                new V33TestReference.ReferenceEngine();
        Object request = new Object();
        Object otherRequest = new Object();
        V33TestReference.ReferenceCursor cursor = first.cursor(
                request,
                new V33TestReference.Anchor(5.0, 2)
        );

        assertEquals(
                V33TestReference.CursorReason.UNSUPPORTED_CURSOR,
                first.rejectionReason(new Object(), request).orElseThrow()
        );
        assertEquals(
                V33TestReference.CursorReason.DIFFERENT_ENGINE,
                second.rejectionReason(cursor, otherRequest).orElseThrow()
        );
        first.publish();
        assertEquals(
                V33TestReference.CursorReason.DIFFERENT_REQUEST,
                first.rejectionReason(cursor, otherRequest).orElseThrow()
        );
        assertEquals(
                V33TestReference.CursorReason.STALE_SNAPSHOT,
                first.rejectionReason(cursor, request).orElseThrow()
        );
    }

    @Test
    void onlySuccessfulPublicationStalesCursor() {
        V33TestReference.ReferenceEngine engine =
                new V33TestReference.ReferenceEngine();
        Object request = new Object();
        V33TestReference.ReferenceCursor cursor = engine.cursor(
                request,
                new V33TestReference.Anchor(4.0, 3)
        );

        assertTrue(engine.rejectionReason(cursor, request).isEmpty());
        engine.failedPublication();
        assertTrue(engine.rejectionReason(cursor, request).isEmpty());
        engine.publish();
        assertEquals(
                V33TestReference.CursorReason.STALE_SNAPSHOT,
                engine.rejectionReason(cursor, request).orElseThrow()
        );
    }

    @Test
    void referenceCursorRetainsOnlyOwnerTokenAndExactRequest() {
        V33TestReference.ReferenceEngine engine =
                new V33TestReference.ReferenceEngine();
        Object request = new Object();
        V33TestReference.ReferenceCursor cursor = engine.cursor(
                request,
                new V33TestReference.Anchor(3.25, 12)
        );

        Set<Object> directReferences =
                V33TestReference.directReferenceValues(cursor);
        assertEquals(2, directReferences.size());
        assertTrue(directReferences.contains(request));
        assertFalse(directReferences.contains(engine));
        assertEquals(new V33TestReference.Anchor(3.25, 12), cursor.anchor());
    }

    private static V33TestReference.Candidate candidate(
            int documentId,
            double score,
            boolean queryMatched,
            boolean filterMatched
    ) {
        return new V33TestReference.Candidate(
                documentId,
                score,
                queryMatched,
                filterMatched
        );
    }
}
