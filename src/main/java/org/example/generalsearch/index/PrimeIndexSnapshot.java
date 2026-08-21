package org.example.generalsearch.index;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;

public final class PrimeIndexSnapshot {
    private final ImmutableBitmap primeProducts;

    public PrimeIndexSnapshot() {
        this(ImmutableBitmap.empty());
    }

    PrimeIndexSnapshot(ImmutableBitmap primeProducts) {
        this.primeProducts = Objects.requireNonNull(primeProducts, "primeProducts");
    }

    public ImmutableBitmap primeProducts() {
        return primeProducts;
    }
}
