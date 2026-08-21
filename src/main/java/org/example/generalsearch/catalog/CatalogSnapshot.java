package org.example.generalsearch.catalog;

import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.index.CategoryIndexSnapshot;
import org.example.generalsearch.index.PriceIndexSnapshot;
import org.example.generalsearch.index.PrimeIndexSnapshot;
import org.example.generalsearch.model.Product;

public final class CatalogSnapshot {
    private final ProductTable productTable;
    private final ImmutableBitmap activeProducts;
    private final CategoryIndexSnapshot categoryIndex;
    private final PrimeIndexSnapshot primeIndex;
    private final PriceIndexSnapshot priceIndex;

    public CatalogSnapshot() {
        this(
                new ProductTable(),
                ImmutableBitmap.empty(),
                new CategoryIndexSnapshot(),
                new PrimeIndexSnapshot(),
                new PriceIndexSnapshot()
        );
    }

    CatalogSnapshot(
            ProductTable productTable,
            ImmutableBitmap activeProducts,
            CategoryIndexSnapshot categoryIndex,
            PrimeIndexSnapshot primeIndex,
            PriceIndexSnapshot priceIndex
    ) {
        this.productTable = Objects.requireNonNull(productTable, "productTable");
        this.activeProducts = Objects.requireNonNull(activeProducts, "activeProducts");
        this.categoryIndex = Objects.requireNonNull(categoryIndex, "categoryIndex");
        this.primeIndex = Objects.requireNonNull(primeIndex, "primeIndex");
        this.priceIndex = Objects.requireNonNull(priceIndex, "priceIndex");
    }

    public Product get(int docId) {
        return activeProducts.get(docId) ? productTable.get(docId) : null;
    }

    public CatalogSnapshot add(int docId, Product product) {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(this);
        builder.add(docId, product);
        return builder.build();
    }

    public CatalogSnapshot update(int docId, Product product) {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(this);
        builder.update(docId, product);
        return builder.build();
    }

    public CatalogSnapshot remove(int docId) {
        CatalogSnapshotBuilder builder = new CatalogSnapshotBuilder(this);
        builder.remove(docId);
        return builder.build();
    }

    public ProductTable productTable() {
        return productTable;
    }

    public ImmutableBitmap activeProducts() {
        return activeProducts;
    }

    public CategoryIndexSnapshot categoryIndex() {
        return categoryIndex;
    }

    public PrimeIndexSnapshot primeIndex() {
        return primeIndex;
    }

    public PriceIndexSnapshot priceIndex() {
        return priceIndex;
    }
}
