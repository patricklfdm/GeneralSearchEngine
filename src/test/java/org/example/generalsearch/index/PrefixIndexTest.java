package org.example.generalsearch.index;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.example.generalsearch.query.CandidateAccuracy;
import org.example.generalsearch.query.CandidatePlanner;
import org.example.generalsearch.query.Query;
import org.example.generalsearch.query.SnapshotSearcher;
import org.example.generalsearch.schema.Field;
import org.example.generalsearch.storage.SearchSnapshot;
import org.junit.jupiter.api.Test;

class PrefixIndexTest {
    private static final Field<Document, String> NAME =
            Field.of("name", String.class, Document::name);

    @Test
    void followsCaseSensitiveRawUnicodeStartsWithSemantics() {
        SearchSnapshot<Document> snapshot = emptySnapshot()
                .add(0, new Document("Alpha"))
                .add(1, new Document("Alphabet"))
                .add(2, new Document("alpha"))
                .add(3, new Document("Äpfel"))
                .add(4, new Document("\ufffftail"))
                .add(5, new Document(null))
                .add(6, new Document("😀 Smile"))
                .add(7, new Document("éclair"))
                .add(8, new Document("e\u0301clair"));
        SnapshotSearcher<Document> searcher = new SnapshotSearcher<>();

        assertEquals(Set.of("Alpha", "Alphabet"),
                names(searcher.search(snapshot, Query.prefix(NAME, "Al"))));
        assertEquals(Set.of("alpha"),
                names(searcher.search(snapshot, Query.prefix(NAME, "al"))));
        assertEquals(Set.of("\ufffftail"),
                names(searcher.search(snapshot, Query.prefix(NAME, "\uffff"))));
        assertEquals(Set.of("😀 Smile"),
                names(searcher.search(snapshot, Query.prefix(NAME, "😀"))));
        assertEquals(Set.of("éclair"),
                names(searcher.search(snapshot, Query.prefix(NAME, "é"))));
        assertEquals(8,
                searcher.search(snapshot, Query.prefix(NAME, "")).size());

        var candidate = new CandidatePlanner<Document>()
                .plan(snapshot, Query.prefix(NAME, "Al"))
                .orElseThrow();
        assertEquals(CandidateAccuracy.EXACT, candidate.accuracy());
        assertEquals(2, candidate.bitmap().cardinality());
        assertTrue(new CandidatePlanner<Document>()
                .plan(snapshot, Query.eq(NAME, null))
                .isEmpty());
    }

    @Test
    void updatesValuesAndPreservesPreviousSnapshots() {
        SearchSnapshot<Document> first = emptySnapshot()
                .add(50_000, new Document("Alpha"))
                .add(50_001, new Document("Alpine"));
        SearchSnapshot<Document> second = first
                .update(50_000, new Document("Beta"))
                .remove(50_001);
        SnapshotSearcher<Document> searcher = new SnapshotSearcher<>();

        assertEquals(Set.of("Alpha", "Alpine"),
                names(searcher.search(first, Query.prefix(NAME, "Al"))));
        assertTrue(searcher.search(second, Query.prefix(NAME, "Al")).isEmpty());
        assertEquals(List.of(new Document("Beta")),
                searcher.search(second, Query.eq(NAME, "Beta")));
    }

    private static SearchSnapshot<Document> emptySnapshot() {
        return new SearchSnapshot<>(List.of(IndexDefinition.prefix(NAME)));
    }

    private static Set<String> names(List<Document> documents) {
        Set<String> names = new HashSet<>();
        documents.forEach(document -> names.add(document.name()));
        return names;
    }

    private record Document(String name) {}
}
