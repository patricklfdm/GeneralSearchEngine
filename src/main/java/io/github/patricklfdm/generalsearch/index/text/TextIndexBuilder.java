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
    private int indexedDocumentCount;
    private boolean built;

    public TextIndexBuilder(TextIndexSnapshot<T> base) {
        this.base = Objects.requireNonNull(base, "base");
        this.textField = base.textField();
        this.indexedDocumentCount = base.statistics().indexedDocumentCount();
    }

    @Override
    public void add(int docId, T document) {
        ensureOpen();
        apply(docId, Map.of(), termFrequencies(document));
    }

    @Override
    public void remove(int docId, T document) {
        ensureOpen();
        apply(docId, termFrequencies(document), Map.of());
    }

    @Override
    public void update(int docId, T oldDocument, T newDocument) {
        ensureOpen();
        apply(docId, termFrequencies(oldDocument), termFrequencies(newDocument));
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
                && indexedDocumentCount == base.statistics().indexedDocumentCount()) {
            return base;
        }
        return TextIndexSnapshot.fromPostings(
                textField,
                postings,
                indexedDocumentCount
        );
    }

    private void apply(
            int docId,
            Map<String, Integer> oldTerms,
            Map<String, Integer> newTerms
    ) {
        if (oldTerms.equals(newTerms)) {
            return;
        }
        if (oldTerms.isEmpty() && !newTerms.isEmpty()) {
            indexedDocumentCount++;
        } else if (!oldTerms.isEmpty() && newTerms.isEmpty()) {
            indexedDocumentCount--;
        }
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

    private Map<String, Integer> termFrequencies(T document) {
        Map<String, Integer> frequencies = new HashMap<>();
        for (Token token : textField.analyzeDocument(document)) {
            frequencies.merge(token.term(), 1, Math::addExact);
        }
        return frequencies;
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
