package io.github.patricklfdm.generalsearch.search;

/** Deliberately simple full-matrix reference logic for fuzzy differential tests. */
final class FuzzyTestReference {
    private FuzzyTestReference() {
    }

    static int optimalStringAlignmentDistance(String left, String right) {
        int[] leftPoints = left.codePoints().toArray();
        int[] rightPoints = right.codePoints().toArray();
        int[][] distance = new int[leftPoints.length + 1][rightPoints.length + 1];
        for (int row = 0; row <= leftPoints.length; row++) {
            distance[row][0] = row;
        }
        for (int column = 0; column <= rightPoints.length; column++) {
            distance[0][column] = column;
        }

        for (int row = 1; row <= leftPoints.length; row++) {
            for (int column = 1; column <= rightPoints.length; column++) {
                int substitutionCost = leftPoints[row - 1] == rightPoints[column - 1]
                        ? 0 : 1;
                int best = Math.min(
                        distance[row - 1][column] + 1,
                        Math.min(
                                distance[row][column - 1] + 1,
                                distance[row - 1][column - 1] + substitutionCost
                        )
                );
                if (row > 1
                        && column > 1
                        && leftPoints[row - 1] == rightPoints[column - 2]
                        && leftPoints[row - 2] == rightPoints[column - 1]) {
                    best = Math.min(best, distance[row - 2][column - 2] + 1);
                }
                distance[row][column] = best;
            }
        }
        return distance[leftPoints.length][rightPoints.length];
    }

    static int compareCodePoints(String left, String right) {
        int[] leftPoints = left.codePoints().toArray();
        int[] rightPoints = right.codePoints().toArray();
        int shared = Math.min(leftPoints.length, rightPoints.length);
        for (int index = 0; index < shared; index++) {
            int comparison = Integer.compare(leftPoints[index], rightPoints[index]);
            if (comparison != 0) {
                return comparison;
            }
        }
        return Integer.compare(leftPoints.length, rightPoints.length);
    }
}
