package io.github.patricklfdm.generalsearch.index.text;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;
import io.github.patricklfdm.generalsearch.analysis.Token;
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
        if (dirty.isEmpty()) {
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
        Map<String, Integer> oldTerms = oldDocument.termFrequencies();
        Map<String, Integer> newTerms = newDocument.termFrequencies();
        if (oldTerms.equals(newTerms)) {
            return;
        }
        documentLengths = newDocument.length() == 0
                ? documentLengths.without(docId)
                : documentLengths.with(docId, newDocument.length());
        totalDocumentLength = Math.addExact(
                totalDocumentLength,
                (long) newDocument.length() - oldDocument.length()
        );
        Set<String> changedTerms = new HashSet<>(oldTerms.keySet());
        changedTerms.addAll(newTerms.keySet());
        for (String term : changedTerms) {
            int oldFrequency = oldTerms.getOrDefault(term, 0);
            int newFrequency = newTerms.getOrDefault(term, 0);
            if (oldFrequency == newFrequency) {
                continue;
            }
            PostingList posting = dirty.computeIfAbsent(term, base::posting);
            dirty.put(term, newFrequency == 0
                    ? posting.without(docId)
                    : posting.withTermFrequency(docId, newFrequency));
        }
    }

    private AnalyzedDocument analyze(T document) {
        Map<String, Integer> frequencies = new HashMap<>();
        int length = 0;
        for (Token token : textField.analyzeDocument(document)) {
            frequencies.merge(token.term(), 1, Math::addExact);
            length = Math.addExact(length, 1);
        }
        return new AnalyzedDocument(frequencies, length);
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }

    private record AnalyzedDocument(
            Map<String, Integer> termFrequencies,
            int length
    ) {
        private static AnalyzedDocument empty() {
            return new AnalyzedDocument(Map.of(), 0);
        }
    }
}
