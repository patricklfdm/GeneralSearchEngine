package io.github.patricklfdm.generalsearch.index;

/**
 * Immutable snapshot facts maintained by one index.
 *
 * @param indexedDocumentCount number of active documents with a non-null indexed value
 * @param distinctKeyCount number of distinct value buckets or term keys in the index
 */
public record IndexStatistics(int indexedDocumentCount, int distinctKeyCount) {
    public IndexStatistics {
        if (indexedDocumentCount < 0) {
            throw new IllegalArgumentException(
                    "indexedDocumentCount must not be negative");
        }
        if (distinctKeyCount < 0) {
            throw new IllegalArgumentException(
                    "distinctKeyCount must not be negative");
        }
    }
}
