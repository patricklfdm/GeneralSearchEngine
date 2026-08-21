package io.github.patricklfdm.generalsearch.query;

import java.util.Objects;
import io.github.patricklfdm.generalsearch.bitmap.ImmutableBitmap;

public record CandidateResult(ImmutableBitmap bitmap, CandidateAccuracy accuracy) {
    public CandidateResult {
        Objects.requireNonNull(bitmap, "bitmap");
        Objects.requireNonNull(accuracy, "accuracy");
    }
}
