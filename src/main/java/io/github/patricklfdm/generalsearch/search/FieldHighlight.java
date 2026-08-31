package io.github.patricklfdm.generalsearch.search;

import java.util.List;

/** Ordered structured highlights for one requested text field. */
public final class FieldHighlight {
    private final String fieldName;
    private final List<HighlightFragment> fragments;

    /**
     * Creates one field result.
     *
     * @param fieldName non-empty logical field name
     * @param fragments non-empty, strictly ordered, non-overlapping fragments
     * @throws NullPointerException when the list or one of its elements is null
     * @throws IllegalArgumentException when the name or fragment order is invalid
     */
    public FieldHighlight(
            String fieldName,
            List<HighlightFragment> fragments
    ) {
        if (fieldName == null || fieldName.isEmpty()) {
            throw new IllegalArgumentException("fieldName must not be empty");
        }
        this.fragments = List.copyOf(fragments);
        if (this.fragments.isEmpty()) {
            throw new IllegalArgumentException(
                    "a field highlight requires at least one fragment");
        }
        int previousEnd = -1;
        for (HighlightFragment fragment : this.fragments) {
            if (previousEnd >= 0 && fragment.startOffset() < previousEnd) {
                throw new IllegalArgumentException(
                        "field fragments must be strictly ordered and non-overlapping");
            }
            previousEnd = fragment.endOffset();
        }
        this.fieldName = fieldName;
    }

    /** @return the requested logical field name */
    public String fieldName() {
        return fieldName;
    }

    /** @return immutable ordered fragments */
    public List<HighlightFragment> fragments() {
        return fragments;
    }
}
