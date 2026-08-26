package io.github.patricklfdm.generalsearch.index.text;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.analysis.AnalyzedToken;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexSnapshot;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Single-publication mutation builder for an immutable inverted index snapshot. */
public final class TextIndexBuilder<T> implements IndexBuilder<T> {
    private final TextIndexSnapshot<T> base;
    private final TextField<T> textField;
    private final Map<String, PostingList> dirty = new TreeMap<>();
    private PersistentAvlMap<Integer, Integer> documentLengths;
    private long totalDocumentLength;
    private boolean built;

    public TextIndexBuilder(TextIndexSnapshot<T> base) {
        this.base = Objects.requireNonNull(base, "base");
        this.textField = base.textField();
        this.documentLengths = base.documentLengths();
        this.totalDocumentLength = base.totalDocumentLength();
    }

    @Override
    public void add(int docId, T document) {
        ensureOpen();
        apply(docId, AnalyzedDocument.empty(), analyze(document));
    }

    @Override
    public void remove(int docId, T document) {
        ensureOpen();
        apply(docId, analyze(document), AnalyzedDocument.empty());
    }

    @Override
    public void update(int docId, T oldDocument, T newDocument) {
        ensureOpen();
        apply(docId, analyze(oldDocument), analyze(newDocument));
    }

    @Override
    public IndexSnapshot<T> build() {
        ensureOpen();
        if (dirty.isEmpty()
                && documentLengths == base.documentLengths()
                && totalDocumentLength == base.totalDocumentLength()) {
            built = true;
            return base;
        }
        PersistentAvlMap<String, PostingList> postings = base.postings();
        for (var entry : dirty.entrySet()) {
            PostingList posting = entry.getValue();
            postings = posting.documentFrequency() == 0
                    ? postings.without(entry.getKey())
                    : postings.with(entry.getKey(), posting);
        }
        built = true;
        if (postings == base.postings()
                && documentLengths == base.documentLengths()
                && totalDocumentLength == base.totalDocumentLength()) {
            return base;
        }
        return TextIndexSnapshot.fromPostings(
                textField,
                postings,
                documentLengths,
                totalDocumentLength
        );
    }

    private void apply(
            int docId,
            AnalyzedDocument oldDocument,
            AnalyzedDocument newDocument
    ) {
        if (oldDocument.equals(newDocument)) {
            return;
        }
        Map<String, IntPositions> oldTerms = oldDocument.positionsByTerm();
        Map<String, IntPositions> newTerms = newDocument.positionsByTerm();
        PersistentAvlMap<Integer, Integer> updatedLengths = newDocument.tokenCount() == 0
                ? documentLengths.without(docId)
                : documentLengths.with(docId, newDocument.tokenCount());
        long updatedTotalLength = Math.addExact(
                totalDocumentLength,
                (long) newDocument.tokenCount() - oldDocument.tokenCount()
        );
        Set<String> changedTerms = new HashSet<>(oldTerms.keySet());
        changedTerms.addAll(newTerms.keySet());
        Map<String, PostingList> updatedPostings = new TreeMap<>();
        for (String term : changedTerms) {
            IntPositions oldPositions = oldTerms.getOrDefault(
                    term, IntPositions.empty());
            IntPositions newPositions = newTerms.getOrDefault(
                    term, IntPositions.empty());
            if (oldPositions.equals(newPositions)) {
                continue;
            }
            PostingList posting = dirty.getOrDefault(term, base.posting(term));
            updatedPostings.put(term, newPositions.size() == 0
                    ? posting.without(docId)
                    : posting.withPositions(docId, newPositions));
        }
        documentLengths = updatedLengths;
        totalDocumentLength = updatedTotalLength;
        dirty.putAll(updatedPostings);
    }

    private AnalyzedDocument analyze(T document) {
        String text = textField.field().valueOf(document);
        var tokens = textField.analyzer().analyzeWithPositions(text);
        if (tokens == null) {
            throw invalidAnalysis("returned a null token list");
        }
        Map<String, IntPositions.Builder> builders = new HashMap<>();
        int logicalPosition = -1;
        int tokenCount = 0;
        for (int index = 0; index < tokens.size(); index++) {
            AnalyzedToken token = tokens.get(index);
            if (token == null) {
                throw invalidAnalysis("returned a null token at index " + index);
            }
            if (token.term() == null || token.term().isEmpty()) {
                throw invalidAnalysis("returned an empty term at index " + index);
            }
            int increment = token.positionIncrement();
            if (index == 0 && increment < 1) {
                throw invalidAnalysis(
                        "returned a non-positive first position increment");
            }
            if (increment < 0) {
                throw invalidAnalysis(
                        "returned a negative position increment at index " + index);
            }
            try {
                logicalPosition = Math.addExact(logicalPosition, increment);
            } catch (ArithmeticException failure) {
                throw invalidAnalysis(
                        "overflowed logical position at token index " + index,
                        failure
                );
            }
            builders.computeIfAbsent(token.term(), ignored -> IntPositions.builder())
                    .add(logicalPosition);
            tokenCount = Math.addExact(tokenCount, 1);
        }
        Map<String, IntPositions> positionsByTerm = new HashMap<>();
        builders.forEach((term, builder) -> positionsByTerm.put(term, builder.build()));
        return new AnalyzedDocument(Map.copyOf(positionsByTerm), tokenCount);
    }

    private IllegalArgumentException invalidAnalysis(String detail) {
        return new IllegalArgumentException(
                "Analyzer for text field '" + textField.name() + "' " + detail);
    }

    private IllegalArgumentException invalidAnalysis(
            String detail,
            RuntimeException cause
    ) {
        return new IllegalArgumentException(
                "Analyzer for text field '" + textField.name() + "' " + detail,
                cause
        );
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }

    private record AnalyzedDocument(
            Map<String, IntPositions> positionsByTerm,
            int tokenCount
    ) {
        private static AnalyzedDocument empty() {
            return new AnalyzedDocument(Map.of(), 0);
        }
    }
}
