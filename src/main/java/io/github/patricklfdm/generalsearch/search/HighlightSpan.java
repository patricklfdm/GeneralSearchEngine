package io.github.patricklfdm.generalsearch.search;

/**
 * One absolute, half-open UTF-16 source range selected for presentation.
 */
public final class HighlightSpan {
    private final int startOffset;
    private final int endOffset;

    /**
     * Creates a non-empty source range.
     *
     * @param startOffset non-negative UTF-16 start offset
     * @param endOffset exclusive UTF-16 end offset
     * @throws IllegalArgumentException when the range is negative, empty, or reversed
     */
    public HighlightSpan(int startOffset, int endOffset) {
        if (startOffset < 0 || endOffset <= startOffset) {
            throw new IllegalArgumentException(
                    "highlight span must be non-empty and non-negative");
        }
        this.startOffset = startOffset;
        this.endOffset = endOffset;
    }

    /** @return the absolute UTF-16 start offset */
    public int startOffset() {
        return startOffset;
    }

    /** @return the exclusive absolute UTF-16 end offset */
    public int endOffset() {
        return endOffset;
    }
}
