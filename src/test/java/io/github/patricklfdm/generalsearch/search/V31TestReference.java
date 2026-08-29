package io.github.patricklfdm.generalsearch.search;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.OptionalLong;
import java.util.TreeSet;

/** Independent representation-free reference logic reserved for V3.1 tests. */
final class V31TestReference {
    private V31TestReference() {
    }

    static OptionalLong minimumConsumedSlop(
            List<PhraseSlot> slots,
            List<PositionedTerm> document
    ) {
        Objects.requireNonNull(slots, "slots");
        Objects.requireNonNull(document, "document");
        if (slots.isEmpty()) {
            return OptionalLong.empty();
        }
        validateSlots(slots);
        List<int[]> candidates = new ArrayList<>(slots.size());
        for (PhraseSlot slot : slots) {
            TreeSet<Integer> positions = new TreeSet<>();
            for (PositionedTerm occurrence : document) {
                if (slot.alternatives().contains(occurrence.term())) {
                    positions.add(occurrence.position());
                }
            }
            if (positions.isEmpty()) {
                return OptionalLong.empty();
            }
            candidates.add(positions.stream().mapToInt(Integer::intValue).toArray());
        }

        long best = Long.MAX_VALUE;
        for (int first : candidates.getFirst()) {
            best = findMinimum(slots, candidates, 1, first, first, best);
        }
        return best == Long.MAX_VALUE
                ? OptionalLong.empty()
                : OptionalLong.of(best);
    }

    static Evaluation evaluateBool(
            List<Evaluation> must,
            List<Evaluation> should,
            Integer explicitMinimum
    ) {
        List<Evaluation> required = List.copyOf(must);
        List<Evaluation> optional = List.copyOf(should);
        if (required.isEmpty() && optional.isEmpty()) {
            throw new IllegalArgumentException("a bool requires at least one clause");
        }
        int effectiveMinimum;
        if (explicitMinimum == null) {
            effectiveMinimum = required.isEmpty() ? 1 : 0;
        } else {
            if (explicitMinimum < 0) {
                throw new IllegalArgumentException("minimum must not be negative");
            }
            if (explicitMinimum > optional.size()) {
                throw new IllegalArgumentException(
                        "minimum must not exceed should occurrence count");
            }
            if (explicitMinimum == 0 && required.isEmpty()) {
                throw new IllegalArgumentException(
                        "minimum zero requires at least one must occurrence");
            }
            effectiveMinimum = explicitMinimum;
        }

        double score = 0.0;
        for (Evaluation child : required) {
            if (!child.matched()) {
                return Evaluation.NO_MATCH;
            }
            score = add(score, child.score());
        }
        int matchedShould = 0;
        for (Evaluation child : optional) {
            if (child.matched()) {
                matchedShould++;
                score = add(score, child.score());
            }
        }
        return matchedShould < effectiveMinimum
                ? Evaluation.NO_MATCH
                : new Evaluation(true, score);
    }

    private static long findMinimum(
            List<PhraseSlot> slots,
            List<int[]> candidates,
            int slotIndex,
            int first,
            int previous,
            long best
    ) {
        if (slotIndex == slots.size()) {
            long documentSpan = Math.subtractExact((long) previous, first);
            long querySpan = Math.subtractExact(
                    (long) slots.getLast().relativePosition(),
                    slots.getFirst().relativePosition()
            );
            return Math.min(best, Math.subtractExact(documentSpan, querySpan));
        }

        long minimumGap = Math.subtractExact(
                (long) slots.get(slotIndex).relativePosition(),
                slots.get(slotIndex - 1).relativePosition()
        );
        long result = best;
        for (int position : candidates.get(slotIndex)) {
            if (Math.subtractExact((long) position, previous) < minimumGap) {
                continue;
            }
            result = findMinimum(
                    slots,
                    candidates,
                    slotIndex + 1,
                    first,
                    position,
                    result
            );
        }
        return result;
    }

    private static void validateSlots(List<PhraseSlot> slots) {
        if (slots.getFirst().relativePosition() != 0) {
            throw new IllegalArgumentException("first relative position must be zero");
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

    private static double add(double left, double right) {
        double result = left + right;
        if (!Double.isFinite(result) || result < 0.0) {
            throw new ArithmeticException("reference score addition overflow");
        }
        return result == 0.0 ? 0.0 : result;
    }

    record PhraseSlot(int relativePosition, List<String> alternatives) {
        PhraseSlot {
            if (relativePosition < 0) {
                throw new IllegalArgumentException(
                        "relativePosition must not be negative");
            }
            alternatives = List.copyOf(alternatives);
            if (alternatives.isEmpty()) {
                throw new IllegalArgumentException("alternatives must not be empty");
            }
            alternatives.forEach(term -> {
                if (term == null || term.isEmpty()) {
                    throw new IllegalArgumentException("term must not be empty");
                }
            });
        }
    }

    record PositionedTerm(String term, int position) {
        PositionedTerm {
            if (term == null || term.isEmpty()) {
                throw new IllegalArgumentException("term must not be empty");
            }
            if (position < 0) {
                throw new IllegalArgumentException("position must not be negative");
            }
        }
    }

    record Evaluation(boolean matched, double score) {
        private static final Evaluation NO_MATCH = new Evaluation(false, 0.0);

        Evaluation {
            if (!Double.isFinite(score) || score < 0.0) {
                throw new IllegalArgumentException(
                        "score must be finite and non-negative");
            }
            if (!matched && score != 0.0) {
                throw new IllegalArgumentException(
                        "a non-match cannot carry a score");
            }
            if (score == 0.0) {
                score = 0.0;
            }
        }
    }
}
