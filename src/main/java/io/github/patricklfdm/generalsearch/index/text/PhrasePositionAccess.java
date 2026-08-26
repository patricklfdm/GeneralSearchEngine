package io.github.patricklfdm.generalsearch.index.text;

import java.util.Objects;

/**
 * Unsupported internal bridge for exact phrase-position verification.
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
