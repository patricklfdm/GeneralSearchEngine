package io.github.patricklfdm.generalsearch.ranking;

/** Immutable BM25 saturation and document-length normalization parameters. */
public record Bm25Config(double k1, double b) {
    /** Conventional P5 defaults. */
    public static final Bm25Config DEFAULT = new Bm25Config(1.2, 0.75);

    public Bm25Config {
        if (!Double.isFinite(k1) || k1 < 0.0) {
            throw new IllegalArgumentException("k1 must be finite and non-negative");
        }
        if (!Double.isFinite(b) || b < 0.0 || b > 1.0) {
            throw new IllegalArgumentException("b must be finite and in [0, 1]");
        }
    }
}
