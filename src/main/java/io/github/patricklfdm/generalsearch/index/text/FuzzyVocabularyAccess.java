package io.github.patricklfdm.generalsearch.index.text;

import java.util.Objects;
import java.util.function.Consumer;

/**
 * Unsupported internal bridge for synchronous normalized-vocabulary traversal.
 *
 * @hidden
 */
public final class FuzzyVocabularyAccess {
    private FuzzyVocabularyAccess() {
    }

    /**
     * Visits every normalized term in one immutable text-index snapshot.
     *
     * @param textIndex immutable canonical text-index snapshot
     * @param consumer synchronous normalized-term consumer
     * @hidden
     */
    public static void forEachTerm(
            TextIndexSnapshot<?> textIndex,
            Consumer<? super String> consumer
    ) {
        Objects.requireNonNull(textIndex, "textIndex");
        Objects.requireNonNull(consumer, "consumer");
        textIndex.postings().forEachInRange(
                null,
                true,
                null,
                true,
                (term, ignored) -> consumer.accept(term)
        );
    }
}
