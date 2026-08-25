package io.github.patricklfdm.generalsearch.analysis;

import java.util.List;

/** Immutable, deterministic, thread-safe conversion from text to normalized tokens. */
@FunctionalInterface
public interface Analyzer {
    /**
     * Analyzes text in deterministic encounter order. Null and empty input may produce
     * an empty list, and duplicate tokens may be retained.
     */
    List<Token> analyze(String text);

    /** Returns the canonical simple analyzer shipped with v2. */
    static Analyzer simple() {
        return SimpleAnalyzer.INSTANCE;
    }
}
