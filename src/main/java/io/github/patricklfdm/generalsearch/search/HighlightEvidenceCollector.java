package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import io.github.patricklfdm.generalsearch.analysis.OffsetAnalyzedToken;

/** Invocation-local evidence selection from one already-prepared scoring plan. */
final class HighlightEvidenceCollector {
    private HighlightEvidenceCollector() {
    }

    static List<HighlightSpan> collect(
            ScoringPlanNode<?> node,
            int documentId,
            String fieldName,
            List<OffsetAnalyzedToken> tokens
    ) {
        Objects.requireNonNull(node, "node");
        Objects.requireNonNull(fieldName, "fieldName");
        List<OffsetAnalyzedToken> frozenTokens = List.copyOf(tokens);
        if (!node.evaluate(documentId).matched()) {
            return List.of();
        }
        List<HighlightSpan> ranges = new ArrayList<>();
        collectMatched(node, documentId, fieldName, frozenTokens, ranges);
        return List.copyOf(ranges);
    }

    private static void collectMatched(
            ScoringPlanNode<?> node,
            int documentId,
            String fieldName,
            List<OffsetAnalyzedToken> tokens,
            List<HighlightSpan> ranges
    ) {
        if (node instanceof TextPlan<?> text) {
            collectText(text, fieldName, tokens, ranges);
            return;
        }
        if (node instanceof PhrasePlan<?> phrase) {
            collectPhrase(phrase, fieldName, tokens, ranges);
            return;
        }
        if (node instanceof FuzzyPlan<?> fuzzy) {
            collectFuzzy(fuzzy, documentId, fieldName, tokens, ranges);
            return;
        }
        if (node instanceof BoolPlan<?> bool) {
            for (ScoringPlanNode<?> child : bool.must()) {
                if (child.evaluate(documentId).matched()) {
                    collectMatched(child, documentId, fieldName, tokens, ranges);
                }
            }
            for (ScoringPlanNode<?> child : bool.should()) {
                if (child.evaluate(documentId).matched()) {
                    collectMatched(child, documentId, fieldName, tokens, ranges);
                }
            }
            return;
        }
        BoostPlan<?> boost = (BoostPlan<?>) node;
        if (boost.child().evaluate(documentId).matched()) {
            collectMatched(boost.child(), documentId, fieldName, tokens, ranges);
        }
    }

    private static void collectText(
            TextPlan<?> text,
            String fieldName,
            List<OffsetAnalyzedToken> tokens,
            List<HighlightSpan> ranges
    ) {
        if (!fieldName.equals(text.fieldName())) {
            return;
        }
        Set<String> terms = new HashSet<>(text.diagnosticTerms());
        for (OffsetAnalyzedToken token : tokens) {
            if (terms.contains(token.term())) {
                ranges.add(span(token));
            }
        }
    }

    private static void collectPhrase(
            PhrasePlan<?> phrase,
            String fieldName,
            List<OffsetAnalyzedToken> tokens,
            List<HighlightSpan> ranges
    ) {
        if (!fieldName.equals(phrase.fieldName())) {
            return;
        }
        PhraseWitness witness = earliestMinimumSlopWitness(
                tokens,
                phrase.diagnosticSlots(),
                phrase.requestedSlop()
        );
        if (witness == null) {
            throw new IllegalStateException(
                    "matched phrase plan has no offset-token witness");
        }
        Occurrence first = witness.occurrences().getFirst();
        Occurrence last = witness.occurrences().getLast();
        ranges.add(new HighlightSpan(first.startOffset(), last.endOffset()));
    }

    private static void collectFuzzy(
            FuzzyPlan<?> fuzzy,
            int documentId,
            String fieldName,
            List<OffsetAnalyzedToken> tokens,
            List<HighlightSpan> ranges
    ) {
        if (!fieldName.equals(fuzzy.fieldName())) {
            return;
        }
        FuzzyEvaluation evaluation = fuzzy.evaluateFuzzy(documentId);
        if (!evaluation.result().matched()) {
            return;
        }
        for (OffsetAnalyzedToken token : tokens) {
            if (token.term().equals(evaluation.selectedTerm())) {
                ranges.add(span(token));
            }
        }
    }

    private static PhraseWitness earliestMinimumSlopWitness(
            List<OffsetAnalyzedToken> tokens,
            List<PhraseSlot> slots,
            int requestedSlop
    ) {
        if (slots.isEmpty()) {
            return null;
        }
        List<PositionedOffsetToken> positioned = positioned(tokens);
        List<List<Occurrence>> bySlot = new ArrayList<>(slots.size());
        for (PhraseSlot slot : slots) {
            Set<String> alternatives = new HashSet<>(slot.alternatives());
            List<Occurrence> occurrences = new ArrayList<>();
            for (PositionedOffsetToken token : positioned) {
                if (!alternatives.contains(token.token().term())) {
                    continue;
                }
                Occurrence occurrence = new Occurrence(
                        token.logicalPosition(),
                        token.token().startOffset(),
                        token.token().endOffset()
                );
                if (occurrences.isEmpty()
                        || occurrences.getLast().logicalPosition()
                                != occurrence.logicalPosition()) {
                    occurrences.add(occurrence);
                }
            }
            if (occurrences.isEmpty()) {
                return null;
            }
            bySlot.add(List.copyOf(occurrences));
        }

        PhraseWitness best = null;
        long querySpan = (long) slots.getLast().relativePosition()
                - slots.getFirst().relativePosition();
        for (Occurrence first : bySlot.getFirst()) {
            List<Occurrence> selected = new ArrayList<>(slots.size());
            selected.add(first);
            Occurrence previous = first;
            boolean complete = true;
            for (int slotIndex = 1; slotIndex < slots.size(); slotIndex++) {
                long minimum = (long) previous.logicalPosition()
                        + slots.get(slotIndex).relativePosition()
                        - slots.get(slotIndex - 1).relativePosition();
                Occurrence next = earliestAtOrAfter(bySlot.get(slotIndex), minimum);
                if (next == null) {
                    complete = false;
                    break;
                }
                selected.add(next);
                previous = next;
            }
            if (!complete) {
                continue;
            }
            long consumedSlop = (long) selected.getLast().logicalPosition()
                    - first.logicalPosition()
                    - querySpan;
            if (consumedSlop > requestedSlop) {
                continue;
            }
            PhraseWitness candidate = new PhraseWitness(
                    consumedSlop,
                    List.copyOf(selected)
            );
            if (best == null || compareWitness(candidate, best) < 0) {
                best = candidate;
            }
        }
        return best;
    }

    private static Occurrence earliestAtOrAfter(
            List<Occurrence> occurrences,
            long minimumPosition
    ) {
        int low = 0;
        int high = occurrences.size() - 1;
        int selected = -1;
        while (low <= high) {
            int middle = low + ((high - low) >>> 1);
            if (occurrences.get(middle).logicalPosition() >= minimumPosition) {
                selected = middle;
                high = middle - 1;
            } else {
                low = middle + 1;
            }
        }
        return selected < 0 ? null : occurrences.get(selected);
    }

    private static int compareWitness(PhraseWitness left, PhraseWitness right) {
        int comparison = Long.compare(left.consumedSlop(), right.consumedSlop());
        if (comparison != 0) {
            return comparison;
        }
        comparison = Integer.compare(
                left.occurrences().getFirst().startOffset(),
                right.occurrences().getFirst().startOffset()
        );
        if (comparison != 0) {
            return comparison;
        }
        for (int index = 1; index < left.occurrences().size(); index++) {
            comparison = compareOccurrence(
                    left.occurrences().get(index),
                    right.occurrences().get(index)
            );
            if (comparison != 0) {
                return comparison;
            }
        }
        return Integer.compare(
                left.occurrences().getFirst().endOffset(),
                right.occurrences().getFirst().endOffset()
        );
    }

    private static int compareOccurrence(Occurrence left, Occurrence right) {
        int comparison = Integer.compare(left.startOffset(), right.startOffset());
        return comparison != 0
                ? comparison
                : Integer.compare(left.endOffset(), right.endOffset());
    }

    private static List<PositionedOffsetToken> positioned(
            List<OffsetAnalyzedToken> tokens
    ) {
        List<PositionedOffsetToken> positioned = new ArrayList<>(tokens.size());
        int logicalPosition = -1;
        for (OffsetAnalyzedToken token : tokens) {
            logicalPosition = Math.addExact(
                    logicalPosition,
                    token.positionIncrement()
            );
            positioned.add(new PositionedOffsetToken(logicalPosition, token));
        }
        return List.copyOf(positioned);
    }

    private static HighlightSpan span(OffsetAnalyzedToken token) {
        return new HighlightSpan(token.startOffset(), token.endOffset());
    }

    private record PositionedOffsetToken(
            int logicalPosition,
            OffsetAnalyzedToken token
    ) {
    }

    private record Occurrence(
            int logicalPosition,
            int startOffset,
            int endOffset
    ) {
    }

    private record PhraseWitness(
            long consumedSlop,
            List<Occurrence> occurrences
    ) {
    }
}
