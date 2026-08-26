package io.github.patricklfdm.generalsearch.search;

import java.util.Arrays;
import java.util.Objects;

/** Bounded Optimal String Alignment distance over Unicode code points. */
final class BoundedOptimalStringAlignment {
    static final int MAX_AUTO_EDITS = 2;

    private BoundedOptimalStringAlignment() {
    }

    static int autoMaxEdits(String normalizedTerm) {
        Objects.requireNonNull(normalizedTerm, "normalizedTerm");
        int length = normalizedTerm.codePointCount(0, normalizedTerm.length());
        if (length <= 2) {
            return 0;
        }
        return length <= 5 ? 1 : MAX_AUTO_EDITS;
    }

    /** Returns the exact in-bound distance, or {@code maxEdits + 1}. */
    static int distance(String left, String right, int maxEdits) {
        Objects.requireNonNull(left, "left");
        Objects.requireNonNull(right, "right");
        return distance(left.codePoints().toArray(), right.codePoints().toArray(), maxEdits);
    }

    static int distance(int[] leftPoints, int[] rightPoints, int maxEdits) {
        Objects.requireNonNull(leftPoints, "leftPoints");
        Objects.requireNonNull(rightPoints, "rightPoints");
        if (maxEdits < 0 || maxEdits > MAX_AUTO_EDITS) {
            throw new IllegalArgumentException("maxEdits must be between 0 and 2");
        }
        if (Arrays.equals(leftPoints, rightPoints)) {
            return 0;
        }

        int sentinel = maxEdits + 1;
        if (Math.abs(leftPoints.length - rightPoints.length) > maxEdits) {
            return sentinel;
        }
        if (rightPoints.length > leftPoints.length) {
            int[] held = leftPoints;
            leftPoints = rightPoints;
            rightPoints = held;
        }

        int[] twoRowsBack = new int[rightPoints.length + 1];
        int[] previous = new int[rightPoints.length + 1];
        int[] current = new int[rightPoints.length + 1];
        Arrays.fill(twoRowsBack, sentinel);
        Arrays.fill(previous, sentinel);
        for (int column = 0;
                column <= Math.min(rightPoints.length, maxEdits);
                column++) {
            previous[column] = column;
        }

        for (int row = 1; row <= leftPoints.length; row++) {
            Arrays.fill(current, sentinel);
            int firstColumn = Math.max(0, row - maxEdits);
            int lastColumn = Math.min(rightPoints.length, row + maxEdits);
            if (firstColumn == 0) {
                current[0] = row;
            }

            for (int column = Math.max(1, firstColumn);
                    column <= lastColumn;
                    column++) {
                int deletion = increment(previous[column], sentinel);
                int insertion = increment(current[column - 1], sentinel);
                int substitution = previous[column - 1] >= sentinel
                        ? sentinel
                        : previous[column - 1]
                                + (leftPoints[row - 1] == rightPoints[column - 1]
                                        ? 0 : 1);
                int best = Math.min(deletion, Math.min(insertion, substitution));

                if (row > 1
                        && column > 1
                        && leftPoints[row - 1] == rightPoints[column - 2]
                        && leftPoints[row - 2] == rightPoints[column - 1]) {
                    best = Math.min(
                            best,
                            increment(twoRowsBack[column - 2], sentinel)
                    );
                }
                current[column] = Math.min(best, sentinel);
            }

            int[] reusable = twoRowsBack;
            twoRowsBack = previous;
            previous = current;
            current = reusable;
        }

        return Math.min(previous[rightPoints.length], sentinel);
    }

    static int compareCodePoints(String left, String right) {
        Objects.requireNonNull(left, "left");
        Objects.requireNonNull(right, "right");
        int leftIndex = 0;
        int rightIndex = 0;
        while (leftIndex < left.length() && rightIndex < right.length()) {
            int leftPoint = left.codePointAt(leftIndex);
            int rightPoint = right.codePointAt(rightIndex);
            int comparison = Integer.compare(leftPoint, rightPoint);
            if (comparison != 0) {
                return comparison;
            }
            leftIndex += Character.charCount(leftPoint);
            rightIndex += Character.charCount(rightPoint);
        }
        return Integer.compare(
                left.length() - leftIndex,
                right.length() - rightIndex
        );
    }

    private static int increment(int value, int sentinel) {
        return value >= sentinel ? sentinel : value + 1;
    }
}
