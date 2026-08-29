package io.github.patricklfdm.generalsearch.index.text;

import java.util.Objects;

/**
 * Unsupported internal bridge for ordered phrase-position verification.
 *
 * @hidden
 */
public final class PhrasePositionAccess {
    private PhrasePositionAccess() {
    }

    /**
     * Tests one internal document against already-prepared exact phrase slots.
     *
     * @param docId internal document identifier
     * @param relativePositions strictly increasing slot positions beginning at zero
     * @param alternativesBySlot prepared alternative postings for every slot
     * @param anchorSlot deterministic slot whose occurrences drive verification
     * @return whether one anchor occurrence satisfies every exact relative slot
     * @hidden
     */
    public static boolean matches(
            int docId,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot
    ) {
        validate(docId, relativePositions, alternativesBySlot, anchorSlot);
        int anchorRelativePosition = relativePositions[anchorSlot];
        for (PostingList anchorPosting : alternativesBySlot[anchorSlot]) {
            IntPositions anchorPositions = anchorPosting.positions(docId);
            for (int index = 0; index < anchorPositions.size(); index++) {
                int anchorDocumentPosition = anchorPositions.get(index);
                if (matchesAt(
                        docId,
                        relativePositions,
                        alternativesBySlot,
                        anchorSlot,
                        anchorRelativePosition,
                        anchorDocumentPosition
                )) {
                    return true;
                }
            }
        }
        return false;
    }

    /**
     * Finds the minimum consumed ordered extra-gap budget for one internal document.
     * Query gaps are minimum gaps and term transposition is never permitted.
     *
     * @param docId internal document identifier
     * @param relativePositions strictly increasing slot positions beginning at zero
     * @param alternativesBySlot prepared alternative postings for every slot
     * @param anchorSlot deterministic slot whose occurrences drive verification
     * @param requestedSlop non-negative maximum extra-gap budget
     * @return minimum consumed slop no greater than {@code requestedSlop}, or
     *         {@code -1} when no qualifying witness exists
     * @hidden
     */
    public static long minimumConsumedSlop(
            int docId,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot,
            int requestedSlop
    ) {
        if (requestedSlop < 0) {
            throw new IllegalArgumentException(
                    "requestedSlop must not be negative");
        }
        validate(docId, relativePositions, alternativesBySlot, anchorSlot);
        long best = Long.MAX_VALUE;
        for (PostingList anchorPosting : alternativesBySlot[anchorSlot]) {
            IntPositions anchorPositions = anchorPosting.positions(docId);
            for (int index = 0; index < anchorPositions.size(); index++) {
                long consumed = consumedAt(
                        docId,
                        relativePositions,
                        alternativesBySlot,
                        anchorSlot,
                        anchorPositions.get(index)
                );
                if (consumed >= 0L && consumed <= requestedSlop) {
                    best = Math.min(best, consumed);
                    if (best == 0L) {
                        return 0L;
                    }
                }
            }
        }
        return best == Long.MAX_VALUE ? -1L : best;
    }

    private static long consumedAt(
            int docId,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot,
            int anchorDocumentPosition
    ) {
        int left = anchorDocumentPosition;
        for (int slot = anchorSlot - 1; slot >= 0; slot--) {
            long minimumGap = (long) relativePositions[slot + 1]
                    - relativePositions[slot];
            int selected = latestAtOrBefore(
                    alternativesBySlot[slot],
                    docId,
                    (long) left - minimumGap
            );
            if (selected < 0) {
                return -1L;
            }
            left = selected;
        }

        int right = anchorDocumentPosition;
        for (int slot = anchorSlot + 1;
                slot < relativePositions.length;
                slot++) {
            long minimumGap = (long) relativePositions[slot]
                    - relativePositions[slot - 1];
            int selected = earliestAtOrAfter(
                    alternativesBySlot[slot],
                    docId,
                    (long) right + minimumGap
            );
            if (selected < 0) {
                return -1L;
            }
            right = selected;
        }

        long documentSpan = (long) right - left;
        long querySpan = (long) relativePositions[relativePositions.length - 1]
                - relativePositions[0];
        return documentSpan - querySpan;
    }

    private static int latestAtOrBefore(
            PostingList[] alternatives,
            int docId,
            long maximum
    ) {
        if (maximum < 0L) {
            return -1;
        }
        int latest = -1;
        for (PostingList posting : alternatives) {
            IntPositions positions = posting.positions(docId);
            int low = 0;
            int high = positions.size() - 1;
            int candidate = -1;
            while (low <= high) {
                int middle = low + ((high - low) >>> 1);
                int position = positions.get(middle);
                if (position <= maximum) {
                    candidate = position;
                    low = middle + 1;
                } else {
                    high = middle - 1;
                }
            }
            latest = Math.max(latest, candidate);
        }
        return latest;
    }

    private static int earliestAtOrAfter(
            PostingList[] alternatives,
            int docId,
            long minimum
    ) {
        if (minimum > Integer.MAX_VALUE) {
            return -1;
        }
        int earliest = -1;
        for (PostingList posting : alternatives) {
            IntPositions positions = posting.positions(docId);
            int low = 0;
            int high = positions.size() - 1;
            int candidate = -1;
            while (low <= high) {
                int middle = low + ((high - low) >>> 1);
                int position = positions.get(middle);
                if (position >= minimum) {
                    candidate = position;
                    high = middle - 1;
                } else {
                    low = middle + 1;
                }
            }
            if (candidate >= 0 && (earliest < 0 || candidate < earliest)) {
                earliest = candidate;
            }
        }
        return earliest;
    }

    private static boolean matchesAt(
            int docId,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot,
            int anchorRelativePosition,
            int anchorDocumentPosition
    ) {
        for (int slot = 0; slot < relativePositions.length; slot++) {
            if (slot == anchorSlot) {
                continue;
            }
            long required = (long) anchorDocumentPosition
                    + ((long) relativePositions[slot] - anchorRelativePosition);
            if (required < 0L || required > Integer.MAX_VALUE) {
                return false;
            }
            if (!contains(
                    alternativesBySlot[slot],
                    docId,
                    (int) required
            )) {
                return false;
            }
        }
        return true;
    }

    private static boolean contains(
            PostingList[] alternatives,
            int docId,
            int requiredPosition
    ) {
        for (PostingList posting : alternatives) {
            if (posting.positions(docId).contains(requiredPosition)) {
                return true;
            }
        }
        return false;
    }

    private static void validate(
            int docId,
            int[] relativePositions,
            PostingList[][] alternativesBySlot,
            int anchorSlot
    ) {
        if (docId < 0) {
            throw new IllegalArgumentException("docId must not be negative");
        }
        Objects.requireNonNull(relativePositions, "relativePositions");
        Objects.requireNonNull(alternativesBySlot, "alternativesBySlot");
        if (relativePositions.length == 0) {
            throw new IllegalArgumentException("a phrase requires at least one slot");
        }
        if (relativePositions.length != alternativesBySlot.length) {
            throw new IllegalArgumentException(
                    "relative positions and alternative slots must have equal length");
        }
        if (anchorSlot < 0 || anchorSlot >= relativePositions.length) {
            throw new IllegalArgumentException("anchorSlot is out of range");
        }

        int previousPosition = -1;
        for (int slot = 0; slot < relativePositions.length; slot++) {
            int relativePosition = relativePositions[slot];
            if (slot == 0 && relativePosition != 0) {
                throw new IllegalArgumentException(
                        "the first relative position must be zero");
            }
            if (relativePosition <= previousPosition) {
                throw new IllegalArgumentException(
                        "relative positions must be strictly increasing");
            }
            previousPosition = relativePosition;

            PostingList[] alternatives = Objects.requireNonNull(
                    alternativesBySlot[slot],
                    "alternativesBySlot[" + slot + "]"
            );
            if (alternatives.length == 0) {
                throw new IllegalArgumentException(
                        "every phrase slot requires at least one alternative");
            }
            for (int index = 0; index < alternatives.length; index++) {
                Objects.requireNonNull(
                        alternatives[index],
                        "alternativesBySlot[" + slot + "][" + index + "]"
                );
            }
        }
    }
}
