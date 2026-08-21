package org.example.generalsearch.index;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;

public final class PrimeIndexBuilder {
    private final ImmutableBitmapBuilder products;
    private boolean built;

    public PrimeIndexBuilder(PrimeIndexSnapshot base) {
        Objects.requireNonNull(base, "base");
        this.products = new ImmutableBitmapBuilder(base.primeProducts());
    }

    public void add(boolean prime, int docId) {
        ensureOpen();
        if (prime) {
            products.set(docId);
        }
    }

    public void remove(boolean prime, int docId) {
        ensureOpen();
        if (prime) {
            products.clear(docId);
        }
    }

    public void update(boolean oldPrime, boolean newPrime, int docId) {
        ensureOpen();
        if (oldPrime != newPrime) {
            if (newPrime) {
                products.set(docId);
            } else {
                products.clear(docId);
            }
        }
    }

    public PrimeIndexSnapshot build() {
        ensureOpen();
        built = true;
        return new PrimeIndexSnapshot(products.build());
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
