package io.github.patricklfdm.generalsearch.search;

import java.util.List;
import java.util.Objects;

/**
 * Exact source substring and its ordered absolute highlight spans.
 */
public final class HighlightFragment {
    private final int startOffset;
    private final int endOffset;
    private final String text;
    private final List<HighlightSpan> spans;

    /**
     * Creates one validated fragment.
     *
     * @param startOffset non-negative absolute UTF-16 start offset
     * @param endOffset exclusive absolute UTF-16 end offset
     * @param text exact source substring for the fragment range
     * @param spans non-empty, strictly ordered, non-overlapping contained spans
     * @throws NullPointerException when {@code text}, {@code spans}, or an element is
     *         null
     * @throws IllegalArgumentException when a range or containment invariant fails
     */
    public HighlightFragment(
            int startOffset,
            int endOffset,
            String text,
            List<HighlightSpan> spans
    ) {
        if (startOffset < 0 || endOffset <= startOffset) {
            throw new IllegalArgumentException(
                    "highlight fragment must be non-empty and non-negative");
        }
        this.text = Objects.requireNonNull(text, "text");
        if (text.length() != endOffset - startOffset) {
            throw new IllegalArgumentException(
                    "fragment text length must equal its source range length");
        }
        this.spans = List.copyOf(spans);
        if (this.spans.isEmpty()) {
            throw new IllegalArgumentException(
                    "a highlight fragment requires at least one span");
        }
        int previousEnd = -1;
        for (HighlightSpan span : this.spans) {
            if (span.startOffset() < startOffset || span.endOffset() > endOffset) {
                throw new IllegalArgumentException(
                        "fragment spans must be contained by the fragment range");
            }
            if (previousEnd >= 0 && span.startOffset() < previousEnd) {
                throw new IllegalArgumentException(
                        "fragment spans must be strictly ordered and non-overlapping");
            }
            previousEnd = span.endOffset();
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

    /** @return the exact source substring for this fragment */
    public String text() {
        return text;
    }

    /** @return immutable ordered absolute spans contained by this fragment */
    public List<HighlightSpan> spans() {
        return spans;
    }
}
