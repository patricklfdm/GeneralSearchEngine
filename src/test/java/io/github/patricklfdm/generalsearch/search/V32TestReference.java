package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** Representation-free reference logic reserved for V3.2 offset/highlight tests. */
final class V32TestReference {
    private V32TestReference() {
    }

    static List<OffsetTerm> offsetFixture(
            String source,
            OffsetTerm... terms
    ) {
        Objects.requireNonNull(source, "source");
        List<OffsetTerm> copy = List.of(terms);
        int logicalPosition = -1;
        int previousPosition = -1;
        Range previousPositionRange = null;
        for (int index = 0; index < copy.size(); index++) {
            OffsetTerm term = copy.get(index);
            if (index == 0 && term.positionIncrement() == 0) {
                throw new IllegalArgumentException(
                        "first position increment must be positive");
            }
            logicalPosition = Math.addExact(
                    logicalPosition,
                    term.positionIncrement()
            );
            validateSourceRange(source, term.range());
            if (logicalPosition == previousPosition) {
                if (!term.range().equals(previousPositionRange)) {
                    throw new IllegalArgumentException(
                            "same-position ranges must be equal");
                }
            } else if (previousPositionRange != null
                    && (term.range().start() < previousPositionRange.start()
                    || term.range().end() < previousPositionRange.end())) {
                throw new IllegalArgumentException(
                        "later-position range boundaries must not move backward");
            }
            previousPosition = logicalPosition;
            previousPositionRange = term.range();
        }
        return copy;
    }

    static Optional<PhraseWitness> phraseWitness(
            List<PhraseSlot> slots,
            List<Occurrence> occurrences
    ) {
        List<PhraseSlot> query = List.copyOf(slots);
        List<Occurrence> document = List.copyOf(occurrences);
        if (query.isEmpty()) {
            return Optional.empty();
        }
        validatePhraseSlots(query);

        List<List<Occurrence>> candidates = new ArrayList<>(query.size());
        for (PhraseSlot slot : query) {
            List<Occurrence> matching = document.stream()
                    .filter(occurrence -> slot.alternatives()
                            .contains(occurrence.term()))
                    .toList();
            if (matching.isEmpty()) {
                return Optional.empty();
            }
            candidates.add(matching);
        }

        List<PhraseWitness> witnesses = new ArrayList<>();
        enumerateWitnesses(
                query,
                candidates,
                0,
                new ArrayList<>(),
                witnesses
        );
        return witnesses.stream().min(V32TestReference::compareWitnesses);
    }

    static Optional<FuzzySelection> selectFuzzy(
            String normalizedQueryTerm,
            int maxEdits,
            List<ScoredTerm> documentTerms
    ) {
        Objects.requireNonNull(normalizedQueryTerm, "normalizedQueryTerm");
        if (normalizedQueryTerm.isEmpty()) {
            throw new IllegalArgumentException("query term must not be empty");
        }
        if (maxEdits < 0 || maxEdits > 2) {
            throw new IllegalArgumentException("maxEdits must be between 0 and 2");
        }

        Set<String> uniqueTerms = new HashSet<>();
        List<FuzzyCandidate> accepted = new ArrayList<>();
        int queryLength = normalizedQueryTerm.codePointCount(
                0,
                normalizedQueryTerm.length()
        );
        for (ScoredTerm documentTerm : List.copyOf(documentTerms)) {
            if (!uniqueTerms.add(documentTerm.term())) {
                throw new IllegalArgumentException(
                        "document terms must be unique");
            }
            if (documentTerm.occurrences().isEmpty()) {
                continue;
            }
            int distance = FuzzyTestReference.optimalStringAlignmentDistance(
                    normalizedQueryTerm,
                    documentTerm.term()
            );
            if (distance > maxEdits) {
                continue;
            }
            int candidateLength = documentTerm.term().codePointCount(
                    0,
                    documentTerm.term().length()
            );
            double similarity = 1.0 - (double) distance
                    / Math.max(queryLength, candidateLength);
            double weightedScore = checkedMultiply(
                    documentTerm.score(),
                    similarity
            );
            accepted.add(new FuzzyCandidate(
                    documentTerm,
                    distance,
                    similarity,
                    weightedScore
            ));
        }
        accepted.sort(Comparator
                .comparingInt(FuzzyCandidate::distance)
                .thenComparing(
                        candidate -> candidate.term().term(),
                        FuzzyTestReference::compareCodePoints
                ));

        for (FuzzyCandidate candidate : accepted) {
            if (candidate.distance() == 0) {
                return Optional.of(candidate.toSelection());
            }
        }
        FuzzyCandidate best = null;
        for (FuzzyCandidate candidate : accepted) {
            if (best == null || Double.compare(
                    candidate.weightedScore(),
                    best.weightedScore()
            ) > 0) {
                best = candidate;
            }
        }
        return best == null
                ? Optional.empty()
                : Optional.of(best.toSelection());
    }

    static EvidenceEvaluation evaluate(EvidenceNode node) {
        Objects.requireNonNull(node, "node");
        if (node instanceof LeafEvidence leaf) {
            return leaf.matched()
                    ? new EvidenceEvaluation(true, leaf.ranges())
                    : EvidenceEvaluation.NO_MATCH;
        }
        if (node instanceof BoostEvidence boost) {
            return evaluate(boost.child());
        }
        BoolEvidence bool = (BoolEvidence) node;
        int effectiveMinimum = effectiveMinimum(bool);
        List<FieldRange> ranges = new ArrayList<>();
        for (EvidenceNode child : bool.must()) {
            EvidenceEvaluation evaluation = evaluate(child);
            if (!evaluation.matched()) {
                return EvidenceEvaluation.NO_MATCH;
            }
            ranges.addAll(evaluation.ranges());
        }
        int matchedShould = 0;
        for (EvidenceNode child : bool.should()) {
            EvidenceEvaluation evaluation = evaluate(child);
            if (evaluation.matched()) {
                matchedShould++;
                ranges.addAll(evaluation.ranges());
            }
        }
        return matchedShould < effectiveMinimum
                ? EvidenceEvaluation.NO_MATCH
                : new EvidenceEvaluation(true, ranges);
    }

    static List<Range> normalizeRanges(List<Range> ranges) {
        List<Range> ordered = new ArrayList<>(List.copyOf(ranges));
        ordered.sort(Comparator
                .comparingInt(Range::start)
                .thenComparingInt(Range::end));
        List<Range> normalized = new ArrayList<>();
        for (Range range : ordered) {
            if (normalized.isEmpty()) {
                normalized.add(range);
                continue;
            }
            Range previous = normalized.getLast();
            if (range.start() < previous.end()) {
                normalized.set(
                        normalized.size() - 1,
                        new Range(previous.start(), Math.max(
                                previous.end(),
                                range.end()
                        ))
                );
            } else if (!range.equals(previous)) {
                normalized.add(range);
            }
        }
        return List.copyOf(normalized);
    }

    static List<Fragment> fragments(
            String source,
            List<Range> rawRanges,
            int contextCharacters,
            int maxFragments
    ) {
        Objects.requireNonNull(source, "source");
        if (contextCharacters < 0) {
            throw new IllegalArgumentException("context must not be negative");
        }
        if (maxFragments <= 0) {
            throw new IllegalArgumentException("fragment cap must be positive");
        }
        List<Range> spans = normalizeRanges(rawRanges);
        for (Range span : spans) {
            validateSourceRange(source, span);
        }

        List<Range> windows = new ArrayList<>();
        for (Range span : spans) {
            int start = (int) Math.max(
                    0L,
                    (long) span.start() - contextCharacters
            );
            int end = (int) Math.min(
                    source.length(),
                    (long) span.end() + contextCharacters
            );
            start = adjustStartForSurrogate(source, start);
            end = adjustEndForSurrogate(source, end);
            Range window = new Range(start, end);
            if (!windows.isEmpty()
                    && window.start() < windows.getLast().end()) {
                Range previous = windows.removeLast();
                windows.add(new Range(
                        previous.start(),
                        Math.max(previous.end(), window.end())
                ));
            } else {
                windows.add(window);
            }
        }

        List<Fragment> fragments = new ArrayList<>();
        for (Range window : windows) {
            if (fragments.size() == maxFragments) {
                break;
            }
            List<Range> contained = spans.stream()
                    .filter(span -> span.start() >= window.start()
                            && span.end() <= window.end())
                    .toList();
            fragments.add(new Fragment(
                    window,
                    source.substring(window.start(), window.end()),
                    contained
            ));
        }
        return List.copyOf(fragments);
    }

    private static void enumerateWitnesses(
            List<PhraseSlot> slots,
            List<List<Occurrence>> candidates,
            int slotIndex,
            List<Occurrence> selected,
            List<PhraseWitness> witnesses
    ) {
        if (slotIndex == slots.size()) {
            Occurrence first = selected.getFirst();
            Occurrence last = selected.getLast();
            long documentSpan = Math.subtractExact(
                    (long) last.position(),
                    first.position()
            );
            long querySpan = Math.subtractExact(
                    (long) slots.getLast().relativePosition(),
                    slots.getFirst().relativePosition()
            );
            witnesses.add(new PhraseWitness(
                    Math.subtractExact(documentSpan, querySpan),
                    selected,
                    new Range(first.range().start(), last.range().end())
            ));
            return;
        }

        for (Occurrence occurrence : candidates.get(slotIndex)) {
            if (!selected.isEmpty()) {
                Occurrence previous = selected.getLast();
                long requiredGap = Math.subtractExact(
                        (long) slots.get(slotIndex).relativePosition(),
                        slots.get(slotIndex - 1).relativePosition()
                );
                long documentGap = Math.subtractExact(
                        (long) occurrence.position(),
                        previous.position()
                );
                if (documentGap < requiredGap) {
                    continue;
                }
            }
            selected.add(occurrence);
            enumerateWitnesses(
                    slots,
                    candidates,
                    slotIndex + 1,
                    selected,
                    witnesses
            );
            selected.removeLast();
        }
    }

    private static int compareWitnesses(
            PhraseWitness left,
            PhraseWitness right
    ) {
        int comparison = Long.compare(
                left.consumedSlop(),
                right.consumedSlop()
        );
        if (comparison != 0) {
            return comparison;
        }
        comparison = Integer.compare(
                left.occurrences().getFirst().range().start(),
                right.occurrences().getFirst().range().start()
        );
        if (comparison != 0) {
            return comparison;
        }
        for (int index = 1; index < left.occurrences().size(); index++) {
            Range leftRange = left.occurrences().get(index).range();
            Range rightRange = right.occurrences().get(index).range();
            comparison = Integer.compare(leftRange.start(), rightRange.start());
            if (comparison != 0) {
                return comparison;
            }
            comparison = Integer.compare(leftRange.end(), rightRange.end());
            if (comparison != 0) {
                return comparison;
            }
        }
        return Integer.compare(
                left.occurrences().getFirst().range().end(),
                right.occurrences().getFirst().range().end()
        );
    }

    private static void validatePhraseSlots(List<PhraseSlot> slots) {
        if (slots.getFirst().relativePosition() != 0) {
            throw new IllegalArgumentException(
                    "first relative position must be zero");
        }
        int previous = -1;
        for (PhraseSlot slot : slots) {
            if (slot.relativePosition() <= previous) {
                throw new IllegalArgumentException(
                        "relative positions must be strictly increasing");
            }
            previous = slot.relativePosition();
        }
    }

    private static int effectiveMinimum(BoolEvidence bool) {
        if (bool.must().isEmpty() && bool.should().isEmpty()) {
            throw new IllegalArgumentException(
                    "a bool requires at least one clause");
        }
        if (bool.minimumShouldMatch() == null) {
            return bool.must().isEmpty() ? 1 : 0;
        }
        int minimum = bool.minimumShouldMatch();
        if (minimum < 0 || minimum > bool.should().size()) {
            throw new IllegalArgumentException(
                    "invalid minimumShouldMatch");
        }
        if (minimum == 0 && bool.must().isEmpty()) {
            throw new IllegalArgumentException(
                    "minimum zero requires a must clause");
        }
        return minimum;
    }

    private static void validateSourceRange(String source, Range range) {
        if (range.end() > source.length()) {
            throw new IllegalArgumentException("range exceeds source");
        }
        if (splitsSurrogate(source, range.start())
                || splitsSurrogate(source, range.end())) {
            throw new IllegalArgumentException("range splits surrogate pair");
        }
    }

    private static boolean splitsSurrogate(String source, int boundary) {
        return boundary > 0
                && boundary < source.length()
                && Character.isHighSurrogate(source.charAt(boundary - 1))
                && Character.isLowSurrogate(source.charAt(boundary));
    }

    private static int adjustStartForSurrogate(String source, int start) {
        return splitsSurrogate(source, start) ? start - 1 : start;
    }

    private static int adjustEndForSurrogate(String source, int end) {
        return splitsSurrogate(source, end) ? end + 1 : end;
    }

    private static double checkedMultiply(double left, double right) {
        double result = left * right;
        if (!Double.isFinite(result) || result < 0.0) {
            throw new ArithmeticException("reference score multiplication overflow");
        }
        return result == 0.0 ? 0.0 : result;
    }

    record Range(int start, int end) {
        Range {
            if (start < 0 || end <= start) {
                throw new IllegalArgumentException(
                        "range must be non-empty and non-negative");
            }
        }
    }

    record OffsetTerm(
            String term,
            int positionIncrement,
            Range range
    ) {
        OffsetTerm {
            Objects.requireNonNull(term, "term");
            Objects.requireNonNull(range, "range");
            if (term.isEmpty()) {
                throw new IllegalArgumentException("term must not be empty");
            }
            if (positionIncrement < 0) {
                throw new IllegalArgumentException(
                        "position increment must not be negative");
            }
        }
    }

    record PhraseSlot(int relativePosition, List<String> alternatives) {
        PhraseSlot {
            if (relativePosition < 0) {
                throw new IllegalArgumentException(
                        "relative position must not be negative");
            }
            alternatives = List.copyOf(alternatives);
            if (alternatives.isEmpty()
                    || alternatives.stream().anyMatch(
                            term -> term == null || term.isEmpty())) {
                throw new IllegalArgumentException(
                        "alternatives must contain non-empty terms");
            }
        }
    }

    record Occurrence(String term, int position, Range range) {
        Occurrence {
            Objects.requireNonNull(term, "term");
            Objects.requireNonNull(range, "range");
            if (term.isEmpty()) {
                throw new IllegalArgumentException("term must not be empty");
            }
            if (position < 0) {
                throw new IllegalArgumentException(
                        "position must not be negative");
            }
        }
    }

    record PhraseWitness(
            long consumedSlop,
            List<Occurrence> occurrences,
            Range range
    ) {
        PhraseWitness {
            if (consumedSlop < 0) {
                throw new IllegalArgumentException(
                        "consumed slop must not be negative");
            }
            occurrences = List.copyOf(occurrences);
            Objects.requireNonNull(range, "range");
        }
    }

    record ScoredTerm(String term, double score, List<Range> occurrences) {
        ScoredTerm {
            Objects.requireNonNull(term, "term");
            if (term.isEmpty()) {
                throw new IllegalArgumentException("term must not be empty");
            }
            if (!Double.isFinite(score) || score < 0.0) {
                throw new IllegalArgumentException(
                        "score must be finite and non-negative");
            }
            occurrences = List.copyOf(occurrences);
        }
    }

    record FuzzySelection(
            String term,
            int distance,
            double similarity,
            double weightedScore,
            List<Range> occurrences
    ) {
        FuzzySelection {
            Objects.requireNonNull(term, "term");
            occurrences = List.copyOf(occurrences);
        }
    }

    private record FuzzyCandidate(
            ScoredTerm term,
            int distance,
            double similarity,
            double weightedScore
    ) {
        private FuzzySelection toSelection() {
            return new FuzzySelection(
                    term.term(),
                    distance,
                    similarity,
                    weightedScore,
                    term.occurrences()
            );
        }
    }

    sealed interface EvidenceNode permits LeafEvidence, BoolEvidence, BoostEvidence {
    }

    record LeafEvidence(boolean matched, List<FieldRange> ranges)
            implements EvidenceNode {
        LeafEvidence {
            ranges = List.copyOf(ranges);
            if (!matched && !ranges.isEmpty()) {
                throw new IllegalArgumentException(
                        "unmatched leaf cannot carry ranges");
            }
        }
    }

    record BoolEvidence(
            List<EvidenceNode> must,
            List<EvidenceNode> should,
            Integer minimumShouldMatch
    ) implements EvidenceNode {
        BoolEvidence {
            must = List.copyOf(must);
            should = List.copyOf(should);
        }
    }

    record BoostEvidence(EvidenceNode child) implements EvidenceNode {
        BoostEvidence {
            Objects.requireNonNull(child, "child");
        }
    }

    record FieldRange(String fieldName, Range range) {
        FieldRange {
            Objects.requireNonNull(fieldName, "fieldName");
            Objects.requireNonNull(range, "range");
            if (fieldName.isEmpty()) {
                throw new IllegalArgumentException(
                        "fieldName must not be empty");
            }
        }
    }

    record EvidenceEvaluation(boolean matched, List<FieldRange> ranges) {
        private static final EvidenceEvaluation NO_MATCH =
                new EvidenceEvaluation(false, List.of());

        EvidenceEvaluation {
            ranges = List.copyOf(ranges);
            if (!matched && !ranges.isEmpty()) {
                throw new IllegalArgumentException(
                        "unmatched evaluation cannot carry ranges");
            }
        }
    }

    record Fragment(Range window, String text, List<Range> spans) {
        Fragment {
            Objects.requireNonNull(window, "window");
            Objects.requireNonNull(text, "text");
            spans = List.copyOf(spans);
            if (text.length() != window.end() - window.start()) {
                throw new IllegalArgumentException(
                        "fragment text length must equal window length");
            }
            if (spans.isEmpty()) {
                throw new IllegalArgumentException(
                        "fragment must contain at least one span");
            }
        }
    }
}
