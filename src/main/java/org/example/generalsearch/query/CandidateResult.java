package org.example.generalsearch.query;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;

public record CandidateResult(ImmutableBitmap bitmap, CandidateAccuracy accuracy) {
    public CandidateResult {
        Objects.requireNonNull(bitmap, "bitmap");
        Objects.requireNonNull(accuracy, "accuracy");
    }
}
