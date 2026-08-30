package io.github.patricklfdm.generalsearch.index.text;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmapBuilder;
import io.github.patricklfdm.generalsearch.index.CandidateEstimate;
import io.github.patricklfdm.generalsearch.index.EstimateQuality;
import io.github.patricklfdm.generalsearch.index.EstimatingIndexSnapshot;
import io.github.patricklfdm.generalsearch.index.IndexBuilder;
import io.github.patricklfdm.generalsearch.index.IndexStatistics;
import io.github.patricklfdm.generalsearch.internal.index.PersistentAvlMap;
import io.github.patricklfdm.generalsearch.query.AllTermsQuery;
import io.github.patricklfdm.generalsearch.query.AnyTermsQuery;
import io.github.patricklfdm.generalsearch.query.CandidateAccuracy;
import io.github.patricklfdm.generalsearch.query.CandidateResult;
import io.github.patricklfdm.generalsearch.query.Query;
import io.github.patricklfdm.generalsearch.query.TermQuery;
import io.github.patricklfdm.generalsearch.schema.Field;
import io.github.patricklfdm.generalsearch.schema.TextField;

/** Immutable analyzed-term dictionary and posting snapshot. */
public final class TextIndexSnapshot<T> implements EstimatingIndexSnapshot<T> {
    private final TextField<T> textField;
    private final PersistentAvlMap<String, PostingList> postings;
    private final PersistentCodePointTrie fuzzyDictionary;
    private final PersistentAvlMap<Integer, Integer> documentLengths;
    private final long totalDocumentLength;
    private final IndexStatistics statistics;

    private TextIndexSnapshot(
            TextField<T> textField,
            PersistentAvlMap<String, PostingList> postings,
            PersistentCodePointTrie fuzzyDictionary,
            PersistentAvlMap<Integer, Integer> documentLengths,
            long totalDocumentLength
    ) {
        this.textField = Objects.requireNonNull(textField, "textField");
        this.postings = Objects.requireNonNull(postings, "postings");
        this.fuzzyDictionary = Objects.requireNonNull(
                fuzzyDictionary,
                "fuzzyDictionary"
        );
        if (fuzzyDictionary.size() != postings.size()) {
            throw new IllegalArgumentException(
                    "fuzzy dictionary size must equal posting dictionary size");
        }
        this.documentLengths = Objects.requireNonNull(documentLengths, "documentLengths");
        if (totalDocumentLength < 0) {
            throw new IllegalArgumentException("totalDocumentLength must not be negative");
        }
        this.totalDocumentLength = totalDocumentLength;
        this.statistics = new IndexStatistics(documentLengths.size(), postings.size());
    }

    public static <T> TextIndexSnapshot<T> empty(TextField<T> textField) {
        return new TextIndexSnapshot<>(
                textField,
                PersistentAvlMap.empty(PostingList::documentFrequency),
                PersistentCodePointTrie.empty(),
                PersistentAvlMap.empty(Integer::longValue),
                0L
        );
    }

    static <T> TextIndexSnapshot<T> fromPostings(
            TextField<T> textField,
            PersistentAvlMap<String, PostingList> postings,
            PersistentCodePointTrie fuzzyDictionary,
            PersistentAvlMap<Integer, Integer> documentLengths,
            long totalDocumentLength
    ) {
        return new TextIndexSnapshot<>(
                textField,
                postings,
                fuzzyDictionary,
                documentLengths,
                totalDocumentLength
        );
    }

    public TextField<T> textField() {
        return textField;
    }

    @Override
    public Field<T, String> field() {
        return textField.field();
    }

    public PostingList posting(String term) {
        Objects.requireNonNull(term, "term");
        PostingList posting = postings.get(term);
        return posting == null ? PostingList.empty() : posting;
    }

    /** Returns the analyzed token count for one indexed document, or zero when absent. */
    public int documentLength(int docId) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
        Integer length = documentLengths.get(docId);
        return length == null ? 0 : length;
    }

    /** Returns the sum of analyzed token counts across indexed documents. */
    public long totalDocumentLength() {
        return totalDocumentLength;
    }

    /** Returns the mean analyzed length, or zero for an empty text index. */
    public double averageDocumentLength() {
        return statistics.indexedDocumentCount() == 0
                ? 0.0
                : (double) totalDocumentLength / statistics.indexedDocumentCount();
    }

    /** Returns exact candidates containing at least one supplied normalized term. */
    public ImmutableBitmap documentsContainingAny(List<String> normalizedTerms) {
        Objects.requireNonNull(normalizedTerms, "normalizedTerms");
        normalizedTerms.forEach(term -> Objects.requireNonNull(term, "term"));
        return union(normalizedTerms);
    }

    @Override
    public Optional<CandidateResult> candidates(Query<T> query) {
        Objects.requireNonNull(query, "query");
        if (query instanceof TermQuery<?> term && term.textField() == textField) {
            return exact(posting(term.term()).documents());
        }
        if (query instanceof AnyTermsQuery<?> any && any.textField() == textField) {
            return exact(union(any.terms()));
        }
        if (query instanceof AllTermsQuery<?> all && all.textField() == textField) {
            return exact(intersection(all.terms()));
        }
        return Optional.empty();
    }

    @Override
    public Optional<CandidateEstimate> estimateCandidates(Query<T> query) {
        Objects.requireNonNull(query, "query");
        if (query instanceof TermQuery<?> term && term.textField() == textField) {
            PostingList posting = postings.get(term.term());
            int cardinality = posting == null ? 0 : posting.documentFrequency();
            return Optional.of(estimate(
                    cardinality,
                    posting == null ? 0 : 1,
                    EstimateQuality.EXACT
            ));
        }
        if (query instanceof AnyTermsQuery<?> any && any.textField() == textField) {
            long cardinality = 0;
            int sources = 0;
            for (String term : any.terms()) {
                PostingList posting = postings.get(term);
                if (posting != null) {
                    cardinality += posting.documentFrequency();
                    sources++;
                }
            }
            return Optional.of(estimate(
                    (int) Math.min(statistics.indexedDocumentCount(), cardinality),
                    sources,
                    sources <= 1 ? EstimateQuality.EXACT : EstimateQuality.APPROXIMATE
            ));
        }
        if (query instanceof AllTermsQuery<?> all && all.textField() == textField) {
            if (all.terms().isEmpty()) {
                return Optional.of(estimate(0, 0, EstimateQuality.EXACT));
            }
            int minimum = Integer.MAX_VALUE;
            for (String term : all.terms()) {
                PostingList posting = postings.get(term);
                if (posting == null) {
                    return Optional.of(estimate(0, 0, EstimateQuality.EXACT));
                }
                minimum = Math.min(minimum, posting.documentFrequency());
            }
            return Optional.of(estimate(
                    minimum,
                    all.terms().size(),
                    all.terms().size() == 1
                            ? EstimateQuality.EXACT
                            : EstimateQuality.APPROXIMATE
            ));
        }
        return Optional.empty();
    }

    @Override
    public IndexStatistics statistics() {
        return statistics;
    }

    @Override
    public IndexBuilder<T> toBuilder() {
        return new TextIndexBuilder<>(this);
    }

    PersistentAvlMap<String, PostingList> postings() {
        return postings;
    }

    PersistentCodePointTrie fuzzyDictionary() {
        return fuzzyDictionary;
    }

    PersistentAvlMap<Integer, Integer> documentLengths() {
        return documentLengths;
    }

    private ImmutableBitmap union(List<String> terms) {
        ImmutableBitmap first = null;
        ImmutableBitmapBuilder builder = null;
        for (String term : terms) {
            PostingList posting = postings.get(term);
            if (posting == null) {
                continue;
            }
            if (first == null) {
                first = posting.documents();
            } else {
                if (builder == null) {
                    builder = new ImmutableBitmapBuilder(first);
                }
                builder.or(posting.documents());
            }
        }
        if (first == null) {
            return ImmutableBitmap.empty();
        }
        return builder == null ? first : builder.build();
    }

    private ImmutableBitmap intersection(List<String> terms) {
        if (terms.isEmpty()) {
            return ImmutableBitmap.empty();
        }
        List<PostingList> sources = new ArrayList<>(terms.size());
        for (String term : terms) {
            PostingList posting = postings.get(term);
            if (posting == null) {
                return ImmutableBitmap.empty();
            }
            sources.add(posting);
        }
        sources.sort(Comparator.comparingInt(PostingList::documentFrequency));
        ImmutableBitmap candidates = sources.getFirst().documents();
        for (int index = 1; index < sources.size(); index++) {
            candidates = candidates.and(sources.get(index).documents());
            if (candidates.isEmpty()) {
                break;
            }
        }
        return candidates;
    }

    private Optional<CandidateResult> exact(ImmutableBitmap bitmap) {
        return Optional.of(new CandidateResult(bitmap, CandidateAccuracy.EXACT));
    }

    private CandidateEstimate estimate(
            int cardinality,
            int sources,
            EstimateQuality quality
    ) {
        return new CandidateEstimate(
                cardinality,
                sources,
                quality,
                CandidateAccuracy.EXACT
        );
    }
}
