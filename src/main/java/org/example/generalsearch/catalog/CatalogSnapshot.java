package org.example.generalsearch.catalog;

import java.util.Collection;
import java.util.List;
import java.util.Objects;
import org.example.generalsearch.bitmap.ImmutableBitmap;
import org.example.generalsearch.index.IndexDefinition;
import org.example.generalsearch.index.IndexRegistry;
import org.example.generalsearch.model.Category;
import org.example.generalsearch.model.Product;
import org.example.generalsearch.model.ProductFields;

public final class CatalogSnapshot {
    private final ProductTable productTable;
    private final ImmutableBitmap activeProducts;
    private final IndexRegistry<Product> indexes;

    public CatalogSnapshot() {
        this(defaultIndexDefinitions());
    }

    public CatalogSnapshot(Collection<? extends IndexDefinition<Product>> definitions) {
        this(
                new ProductTable(),
                ImmutableBitmap.empty(),
                IndexRegistry.create(definitions)
        );
    }

    CatalogSnapshot(
            ProductTable productTable,
            ImmutableBitmap activeProducts,
            IndexRegistry<Product> indexes
    ) {
        this.productTable = Objects.requireNonNull(productTable, "productTable");
        this.activeProducts = Objects.requireNonNull(activeProducts, "activeProducts");
        this.indexes = Objects.requireNonNull(indexes, "indexes");
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

    public IndexRegistry<Product> indexes() {
        return indexes;
    }

    public static List<IndexDefinition<Product>> defaultIndexDefinitions() {
        return List.of(
                IndexDefinition.<Product, Category>equality(ProductFields.CATEGORY),
                IndexDefinition.<Product, Boolean>equality(ProductFields.PRIME),
                IndexDefinition.<Product, Double>range(ProductFields.PRICE)
        );
    }
}
