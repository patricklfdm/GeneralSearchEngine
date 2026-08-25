package io.github.patricklfdm.generalsearch.analysis;

/** One normalized analyzed term; P4 intentionally carries no positions or offsets. */
public record Token(String term) {
    public Token {
        if (term == null || term.isEmpty()) {
            throw new IllegalArgumentException("term must not be empty");
        }
    }
}
