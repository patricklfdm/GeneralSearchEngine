package io.github.patricklfdm.generalsearch.index.text;

import java.util.Arrays;

/** Immutable primitive logical positions for one term in one document. */
final class IntPositions {
    private static final IntPositions EMPTY = new IntPositions(new int[0]);

    private final int[] values;

    private IntPositions(int[] values) {
        this.values = values;
    }

    static IntPositions empty() {
        return EMPTY;
    }

    static IntPositions copyOf(int[] positions) {
        if (positions.length == 0) {
            return EMPTY;
        }
        int[] copy = positions.clone();
        validateStrictlyIncreasing(copy);
        return new IntPositions(copy);
    }

    static IntPositions sequential(int size) {
        if (size < 0) {
            throw new IllegalArgumentException("size must not be negative");
        }
        if (size == 0) {
            return EMPTY;
        }
        int[] positions = new int[size];
        for (int index = 0; index < size; index++) {
            positions[index] = index;
        }
        return new IntPositions(positions);
    }

    static Builder builder() {
        return new Builder();
    }

    int size() {
        return values.length;
    }

    int get(int index) {
        return values[index];
    }

    boolean contains(int position) {
        return Arrays.binarySearch(values, position) >= 0;
    }

    @Override
    public boolean equals(Object other) {
        return this == other
                || other instanceof IntPositions positions
                && Arrays.equals(values, positions.values);
    }

    @Override
    public int hashCode() {
        return Arrays.hashCode(values);
    }

    @Override
    public String toString() {
        return Arrays.toString(values);
    }

    private static void validateStrictlyIncreasing(int[] positions) {
        int previous = -1;
        for (int position : positions) {
            if (position < 0) {
                throw new IllegalArgumentException("positions must not be negative");
            }
            if (position <= previous) {
                throw new IllegalArgumentException(
                        "positions must be strictly increasing");
            }
            previous = position;
        }
    }

    /** Mutable primitive accumulator that freezes into an immutable value. */
    static final class Builder {
        private int[] values = new int[4];
        private int size;

        void add(int position) {
            if (position < 0) {
                throw new IllegalArgumentException("position must not be negative");
            }
            if (size > 0) {
                int previous = values[size - 1];
                if (position < previous) {
                    throw new IllegalArgumentException(
                            "positions must be added in ascending order");
                }
                if (position == previous) {
                    return;
                }
            }
            ensureCapacity();
            values[size++] = position;
        }

        IntPositions build() {
            return size == 0
                    ? EMPTY
                    : new IntPositions(Arrays.copyOf(values, size));
        }

        private void ensureCapacity() {
            if (size < values.length) {
                return;
            }
            int nextCapacity = Math.addExact(values.length, values.length >> 1);
            values = Arrays.copyOf(values, Math.max(nextCapacity, size + 1));
        }
    }
}
