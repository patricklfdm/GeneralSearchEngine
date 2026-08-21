package org.example.generalsearch.engine.mutation;

import java.util.Objects;
import org.example.generalsearch.model.Product;

public sealed interface CatalogMutation {
    record Add(int docId, Product product) implements CatalogMutation {
        public Add {
            Objects.requireNonNull(product, "product");
        }
    }

    record Update(int docId, Product product) implements CatalogMutation {
        public Update {
            Objects.requireNonNull(product, "product");
        }
    }

    record Remove(int docId) implements CatalogMutation {}
}
