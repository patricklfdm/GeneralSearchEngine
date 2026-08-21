package org.example.generalsearch.catalog;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.bitmap.ImmutableBitmapBuilder;
import org.example.generalsearch.index.IndexRegistryBuilder;
import org.example.generalsearch.model.Product;

public final class CatalogSnapshotBuilder {
    private final ProductTableBuilder products;
    private final ImmutableBitmapBuilder activeProducts;
    private final IndexRegistryBuilder<Product> indexes;
    private boolean built;

    public CatalogSnapshotBuilder(CatalogSnapshot base) {
        Objects.requireNonNull(base, "base");
        this.products = new ProductTableBuilder(base.productTable());
        this.activeProducts = new ImmutableBitmapBuilder(base.activeProducts());
        this.indexes = base.indexes().toBuilder();
    }

    public void add(int docId, Product product) {
        ensureOpen();
        Objects.requireNonNull(product, "product");
        if (activeProducts.get(docId)) {
            throw new IllegalStateException("docId is already active: " + docId);
        }
        products.set(docId, product);
        activeProducts.set(docId);
        indexes.add(docId, product);
    }

    public void update(int docId, Product product) {
        ensureOpen();
        Objects.requireNonNull(product, "product");
        Product oldProduct = requireActiveProduct(docId);
        products.set(docId, product);
        indexes.update(docId, oldProduct, product);
    }

    public void remove(int docId) {
        ensureOpen();
        if (!activeProducts.get(docId)) {
            return;
        }
        Product product = requireActiveProduct(docId);
        indexes.remove(docId, product);
        products.set(docId, null);
        activeProducts.clear(docId);
    }

    public CatalogSnapshot build() {
        ensureOpen();
        built = true;
        return new CatalogSnapshot(
                products.build(),
                activeProducts.build(),
                indexes.build()
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
