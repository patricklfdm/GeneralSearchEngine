package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import io.github.patricklfdm.generalsearch.index.text.FuzzyVocabularyAccess;
import io.github.patricklfdm.generalsearch.index.text.PostingList;
import io.github.patricklfdm.generalsearch.index.text.TextIndexSnapshot;

/** Internal deterministic fuzzy-term expansion boundary. */
interface FuzzyTermExpander {
    List<FuzzyExpansion> expand(
            TextIndexSnapshot<?> textIndex,
            String normalizedQueryTerm,
            int maxEdits
    );
}

/** Immutable prepared lexical fact for one accepted vocabulary term. */
record FuzzyExpansion(
        String term,
        PostingList posting,
        int editDistance,
        int codePointLength,
        double similarity
) {
    FuzzyExpansion {
        Objects.requireNonNull(term, "term");
        Objects.requireNonNull(posting, "posting");
        if (term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
        if (editDistance < 0
                || editDistance > BoundedOptimalStringAlignment.MAX_AUTO_EDITS) {
            throw new IllegalArgumentException(
                    "editDistance must be between 0 and 2");
        }
        if (codePointLength <= 0) {
            throw new IllegalArgumentException("codePointLength must be positive");
        }
        if (!Double.isFinite(similarity)
                || similarity < 0.0
                || similarity > 1.0) {
            throw new IllegalArgumentException(
                    "similarity must be finite and between 0 and 1");
        }
        if (similarity == 0.0) {
            similarity = 0.0;
        }
    }
}

/** Initial Phase 6 expander: one bounded scan of the immutable field vocabulary. */
final class VocabularyScanningFuzzyTermExpander implements FuzzyTermExpander {
    private static final Comparator<FuzzyExpansion> EXPANSION_ORDER = Comparator
            .comparingInt(FuzzyExpansion::editDistance)
            .thenComparing(
                    FuzzyExpansion::term,
                    BoundedOptimalStringAlignment::compareCodePoints
            );

    @Override
    public List<FuzzyExpansion> expand(
            TextIndexSnapshot<?> textIndex,
            String normalizedQueryTerm,
            int maxEdits
    ) {
        Objects.requireNonNull(textIndex, "textIndex");
        Objects.requireNonNull(normalizedQueryTerm, "normalizedQueryTerm");
        if (normalizedQueryTerm.isEmpty()) {
            throw new IllegalArgumentException(
                    "normalizedQueryTerm must not be empty");
        }
        if (maxEdits < 0
                || maxEdits > BoundedOptimalStringAlignment.MAX_AUTO_EDITS) {
            throw new IllegalArgumentException("maxEdits must be between 0 and 2");
        }

        int[] queryPoints = normalizedQueryTerm.codePoints().toArray();
        int queryLength = queryPoints.length;
        int[] candidatePoints = new int[queryLength + maxEdits];
        BoundedOptimalStringAlignment.Workspace distanceWorkspace =
                new BoundedOptimalStringAlignment.Workspace();
        List<FuzzyExpansion> expansions = new ArrayList<>();
        FuzzyVocabularyAccess.forEachTerm(textIndex, candidate -> {
            int candidateLength = candidate.codePointCount(0, candidate.length());
            if (Math.abs(candidateLength - queryLength) > maxEdits) {
                return;
            }
            copyCodePoints(candidate, candidatePoints, candidateLength);
            int distance = BoundedOptimalStringAlignment.distance(
                    queryPoints,
                    queryLength,
                    candidatePoints,
                    candidateLength,
                    maxEdits,
                    distanceWorkspace
            );
            if (distance > maxEdits) {
                return;
            }
            double similarity = 1.0 - (double) distance
                    / Math.max(queryLength, candidateLength);
            expansions.add(new FuzzyExpansion(
                    candidate,
                    textIndex.posting(candidate),
                    distance,
                    candidateLength,
                    similarity
            ));
        });
        expansions.sort(EXPANSION_ORDER);
        return List.copyOf(expansions);
    }

    private static void copyCodePoints(
            String value,
            int[] destination,
            int expectedLength
    ) {
        int offset = 0;
        int index = 0;
        while (offset < value.length()) {
            int codePoint = value.codePointAt(offset);
            destination[index++] = codePoint;
            offset += Character.charCount(codePoint);
        }
        if (index != expectedLength) {
            throw new IllegalStateException("code-point length changed during traversal");
        }
    }
}

/** Persistent-trie fuzzy expansion with exact bounded OSA traversal. */
final class TrieFuzzyTermExpander implements FuzzyTermExpander {
    private static final Comparator<FuzzyExpansion> EXPANSION_ORDER = Comparator
            .comparingInt(FuzzyExpansion::editDistance)
            .thenComparing(
                    FuzzyExpansion::term,
                    BoundedOptimalStringAlignment::compareCodePoints
            );

    @Override
    public List<FuzzyExpansion> expand(
            TextIndexSnapshot<?> textIndex,
            String normalizedQueryTerm,
            int maxEdits
    ) {
        Objects.requireNonNull(textIndex, "textIndex");
        Objects.requireNonNull(normalizedQueryTerm, "normalizedQueryTerm");
        if (normalizedQueryTerm.isEmpty()) {
            throw new IllegalArgumentException(
                    "normalizedQueryTerm must not be empty");
        }
        if (maxEdits < 0
                || maxEdits > BoundedOptimalStringAlignment.MAX_AUTO_EDITS) {
            throw new IllegalArgumentException("maxEdits must be between 0 and 2");
        }

        int queryLength = normalizedQueryTerm.codePointCount(
                0,
                normalizedQueryTerm.length()
        );
        List<FuzzyExpansion> expansions = new ArrayList<>();
        FuzzyVocabularyAccess.forEachWithinEditDistance(
                textIndex,
                normalizedQueryTerm,
                maxEdits,
                (candidate, distance) -> {
                    int candidateLength = candidate.codePointCount(
                            0,
                            candidate.length()
                    );
                    double similarity = 1.0 - (double) distance
                            / Math.max(queryLength, candidateLength);
                    expansions.add(new FuzzyExpansion(
                            candidate,
                            textIndex.posting(candidate),
                            distance,
                            candidateLength,
                            similarity
                    ));
                }
        );
        expansions.sort(EXPANSION_ORDER);
        return List.copyOf(expansions);
    }
}
