package org.example.generalsearch.catalog;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;
import org.example.generalsearch.index.CategoryIndexBuilder;
import org.example.generalsearch.index.PriceIndexBuilder;
import org.example.generalsearch.index.PrimeIndexBuilder;
import org.example.generalsearch.model.Product;

public final class CatalogSnapshotBuilder {
    private final ProductTableBuilder products;
    private final ImmutableBitmapBuilder activeProducts;
    private final CategoryIndexBuilder categories;
    private final PrimeIndexBuilder primes;
    private final PriceIndexBuilder prices;
    private boolean built;

    public CatalogSnapshotBuilder(CatalogSnapshot base) {
        Objects.requireNonNull(base, "base");
        this.products = new ProductTableBuilder(base.productTable());
        this.activeProducts = new ImmutableBitmapBuilder(base.activeProducts());
        this.categories = new CategoryIndexBuilder(base.categoryIndex());
        this.primes = new PrimeIndexBuilder(base.primeIndex());
        this.prices = new PriceIndexBuilder(base.priceIndex());
    }

    public void add(int docId, Product product) {
        ensureOpen();
        Objects.requireNonNull(product, "product");
        if (activeProducts.get(docId)) {
            throw new IllegalStateException("docId is already active: " + docId);
        }
        products.set(docId, product);
        activeProducts.set(docId);
        categories.add(product.category(), docId);
        primes.add(product.prime(), docId);
        prices.add(product.price(), docId);
    }

    public void update(int docId, Product product) {
        ensureOpen();
        Objects.requireNonNull(product, "product");
        Product oldProduct = requireActiveProduct(docId);
        products.set(docId, product);
        categories.update(oldProduct.category(), product.category(), docId);
        primes.update(oldProduct.prime(), product.prime(), docId);
        prices.update(oldProduct.price(), product.price(), docId);
    }

    public void remove(int docId) {
        ensureOpen();
        if (!activeProducts.get(docId)) {
            return;
        }
        Product product = requireActiveProduct(docId);
        categories.remove(product.category(), docId);
        primes.remove(product.prime(), docId);
        prices.remove(product.price(), docId);
        products.set(docId, null);
        activeProducts.clear(docId);
    }

    public CatalogSnapshot build() {
        ensureOpen();
        built = true;
        return new CatalogSnapshot(
                products.build(),
                activeProducts.build(),
                categories.build(),
                primes.build(),
                prices.build()
        );
    }

    private Product requireActiveProduct(int docId) {
        if (!activeProducts.get(docId)) {
            throw new IllegalStateException("docId is not active: " + docId);
        }
        Product product = products.get(docId);
        if (product == null) {
            throw new IllegalStateException("active docId has no product: " + docId);
        }
        return product;
    }

    private void ensureOpen() {
        if (built) {
            throw new IllegalStateException("builder has already been built");
        }
    }
}
