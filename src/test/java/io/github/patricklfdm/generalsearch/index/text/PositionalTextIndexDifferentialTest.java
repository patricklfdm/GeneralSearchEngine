package io.github.patricklfdm.generalsearch.index.text;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.Set;
import java.util.TreeSet;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.analysis.Analyzer;
import io.github.patricklfdm.generalsearch.analysis.Token;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;
import org.junit.jupiter.api.Test;

class PositionalTextIndexDifferentialTest {
    private static final List<String> TERMS = List.of("alpha", "beta", "gamma", "delta");
    private static final Field<Document, String> BODY =
            Field.of("body", String.class, Document::body);
    private static final TextField<Document> TEXT =
            TextField.of(BODY, encodedAnalyzer());

    @Test
    void randomizedMutationsMatchReferenceModelAndPreserveOldSnapshots() {
        Random random = new Random(0x504f534954494f4eL);
        TextIndexSnapshot<Document> snapshot = TextIndexSnapshot.empty(TEXT);
        Map<Integer, Document> documents = new HashMap<>();

        for (int iteration = 0; iteration < 400; iteration++) {
            TextIndexSnapshot<Document> oldSnapshot = snapshot;
            Map<Integer, Document> oldDocuments = Map.copyOf(documents);
            TextIndexBuilder<Document> builder = new TextIndexBuilder<>(snapshot);
            int docId = random.nextInt(32);
            Document existing = documents.get(docId);

            if (existing == null) {
                Document added = randomDocument(random);
                builder.add(docId, added);
                documents.put(docId, added);
            } else if (random.nextInt(5) == 0) {
                builder.remove(docId, existing);
                documents.remove(docId);
            } else if (random.nextInt(6) == 0) {
                builder.update(docId, existing, existing);
                assertSame(snapshot, builder.build());
                assertIndexMatches(snapshot, documents);
                continue;
            } else {
                Document replacement = randomDocument(random);
                builder.update(docId, existing, replacement);
                documents.put(docId, replacement);
            }

            snapshot = (TextIndexSnapshot<Document>) builder.build();
            assertIndexMatches(snapshot, documents);
            assertIndexMatches(oldSnapshot, oldDocuments);
        }
    }

    private static void assertIndexMatches(
            TextIndexSnapshot<Document> index,
            Map<Integer, Document> documents
    ) {
        long totalLength = 0;
        int indexedDocuments = 0;
        Set<String> indexedTerms = new TreeSet<>();
        Map<Integer, ReferenceDocument> reference = new HashMap<>();
        for (var entry : documents.entrySet()) {
            ReferenceDocument analyzed = reference(entry.getValue());
            reference.put(entry.getKey(), analyzed);
            totalLength += analyzed.tokenCount();
            if (analyzed.tokenCount() > 0) {
                indexedDocuments++;
            }
            indexedTerms.addAll(analyzed.positionsByTerm().keySet());
        }

        assertEquals(totalLength, index.totalDocumentLength());
        assertEquals(new IndexStatistics(indexedDocuments, indexedTerms.size()),
                index.statistics());
        for (int docId = 0; docId < 32; docId++) {
            ReferenceDocument analyzed = reference.getOrDefault(
                    docId, ReferenceDocument.empty());
            assertEquals(analyzed.tokenCount(), index.documentLength(docId));
            for (String term : TERMS) {
                List<Integer> expected = analyzed.positionsByTerm()
                        .getOrDefault(term, List.of());
                PostingList posting = index.posting(term);
                assertEquals(expected, positions(posting, docId),
                        "positions for term=" + term + ", docId=" + docId);
                assertEquals(expected.size(), posting.termFrequency(docId));
                assertEquals(!expected.isEmpty(), posting.documents().get(docId));
            }
        }
        for (String term : TERMS) {
            long expectedFrequency = reference.values().stream()
                    .filter(document -> document.positionsByTerm().containsKey(term))
                    .count();
            assertEquals(expectedFrequency, index.posting(term).documentFrequency());
        }
    }

    private static ReferenceDocument reference(Document document) {
        Map<String, TreeSet<Integer>> mutable = new HashMap<>();
        int logicalPosition = -1;
        List<AnalyzedToken> tokens = parse(document.body());
        for (AnalyzedToken token : tokens) {
            logicalPosition += token.positionIncrement();
            mutable.computeIfAbsent(token.term(), ignored -> new TreeSet<>())
                    .add(logicalPosition);
        }
        Map<String, List<Integer>> positions = new HashMap<>();
        mutable.forEach((term, values) -> positions.put(term, List.copyOf(values)));
        return new ReferenceDocument(Map.copyOf(positions), tokens.size());
    }

    private static Document randomDocument(Random random) {
        int tokenCount = random.nextInt(9);
        List<String> encoded = new ArrayList<>(tokenCount);
        for (int index = 0; index < tokenCount; index++) {
            String term = TERMS.get(random.nextInt(TERMS.size()));
            int increment = index == 0
                    ? 1 + random.nextInt(3)
                    : random.nextInt(4);
            encoded.add(term + ":" + increment);
        }
        return new Document(String.join(",", encoded));
    }

    private static Analyzer encodedAnalyzer() {
        return new Analyzer() {
            @Override
            public List<Token> analyze(String text) {
                return parse(text).stream()
                        .map(token -> new Token(token.term()))
                        .toList();
            }

            @Override
            public List<AnalyzedToken> analyzeWithPositions(String text) {
                return parse(text);
            }
        };
    }

    private static List<AnalyzedToken> parse(String text) {
        if (text.isEmpty()) {
            return List.of();
        }
        List<AnalyzedToken> tokens = new ArrayList<>();
        for (String encoded : text.split(",")) {
            int separator = encoded.lastIndexOf(':');
            tokens.add(new AnalyzedToken(
                    encoded.substring(0, separator),
                    Integer.parseInt(encoded.substring(separator + 1))));
        }
        return List.copyOf(tokens);
    }

    private static List<Integer> positions(PostingList posting, int docId) {
        IntPositions positions = posting.positions(docId);
        List<Integer> values = new ArrayList<>(positions.size());
        for (int index = 0; index < positions.size(); index++) {
            values.add(positions.get(index));
        }
        return List.copyOf(values);
    }

    private record Document(String body) {}

    private record ReferenceDocument(
            Map<String, List<Integer>> positionsByTerm,
            int tokenCount
    ) {
        private static ReferenceDocument empty() {
            return new ReferenceDocument(Map.of(), 0);
        }
    }
}
